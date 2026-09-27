"""The scaffold writes four artifacts that pass the pre-deployment stages without a decision.

Design: ``docs/fullspec/author_check_and_scaffold_design.md`` section 3.5. The scaffold is
written under a temporary root that mirrors the repository layout; the registration statement
is built by a test builder because the fact module discovers only the fixed package.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest
from core_lib.series import series_key_of
from core_lib.strategy import AdapterClass, StrategyConfig, StrategyDecisionContract
from core_lib.types import Candle, DecisionAction, DecisionIntent
from trading_plugins import author_check, registered_money_management, scaffold
from trading_plugins.scaffold import ScaffoldResult, ScaffoldSpec

# The generated modules are judged by the plugins service's own ruff configuration, as stage 7 is.
_PLUGINS_CONFIG = Path(__file__).resolve().parents[1] / "pyproject.toml"

_INPUT: dict[str, object] = {
    "strategy_id": "ema-cross-scaffold",
    "class_name": "EmaCrossScaffold",
    "display_name": "EMA cross scaffold",
    "description": "Enters when the fast EMA crosses the slow one; the decision is to write.",
    "series": [
        {"name": "EMA", "params": {"period": 9}},
        {"name": "EMA", "params": {"period": 21}},
        {"name": "pat_engulfing", "params": {}},
    ],
    "supported_timeframes": ["1h", "4h"],
    "min_history": 2,
    "money_management": {
        "supported": ["manual"],
        "default": "manual",
        "default_settings": {"manual": {"atr_stop_multiple": 1.5, "reward_risk": 2.0}},
    },
    "capabilities": {
        "supports_external_stop": True,
        "supports_external_take_profit": True,
        "supports_signal_exit": True,
        "supports_pyramiding": False,
    },
    "parameters": {"min_strength": {"type": "number", "default": 1.0, "range": [0.5, 1.0]}},
    "profile": {
        "id": "ema-cross-scaffold-v1",
        "family": "trend",
        "bar": "1h",
        "expected_win_rate": [0.3, 0.55],
        "expected_payoff": [1.2, 3.0],
        "tail_shape": "right_fat",
        "holding_horizon": "multi_day",
        "primary_metric": "calmar",
        "risk_adjusted_pref": "sortino",
        "profit_structure_to_preserve": "trend-capture",
        "envelope_tolerance": 0.2,
        "envelope_status": "provisional",
    },
    "registration_date": "20260927",
}


def _spec(**overrides: object) -> ScaffoldSpec:
    return ScaffoldSpec.from_json({**_INPUT, **overrides})


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A repository-shaped root with the init script the scaffold appends to."""
    (tmp_path / "init-scripts").mkdir()
    (tmp_path / "init-scripts" / "06-init-signal-registry.sql").write_text(
        "\\set ON_ERROR_STOP on\n\n\\connect signal_db\n\n\\ir signal-service/x/01-x.sql\n"
    )
    (tmp_path / "services" / "trading-plugins" / "trading_plugins" / "strategies").mkdir(
        parents=True
    )
    (tmp_path / "services" / "trading-plugins" / "tests").mkdir(parents=True)
    return tmp_path


def _load(path: Path, name: str) -> ModuleType:
    module_spec = importlib.util.spec_from_file_location(name, path)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[name] = module
    try:
        module_spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


@pytest.fixture
def written(root: Path) -> Iterator[tuple[ScaffoldResult, AdapterClass]]:
    """Scaffold the sample and load its class under the deployed package's module name."""
    spec = _spec()
    name = f"trading_plugins.strategies.{spec.module_name}"

    def statement_for(strategy_id: str, display_name: str, description: str) -> str:
        # The module exists by now, as it does for the default builder's discovery.
        _load(
            root / "services/trading-plugins/trading_plugins/strategies" / f"{spec.module_name}.py",
            name,
        )
        return f"-- statement for {strategy_id} ({display_name}: {description})\n"

    result = scaffold.scaffold(spec, root, statement_for=statement_for)
    module = sys.modules[name]
    try:
        yield result, getattr(module, spec.class_name)
    finally:
        sys.modules.pop(name, None)


def test_the_input_is_validated_before_anything_is_written(root: Path) -> None:
    for override, message in (
        ({"strategy_id": "Ema_Cross"}, "kebab-case"),
        ({"class_name": "ema"}, "capitalized identifier"),
        ({"series": [{"name": "EMA"}]}, "series must be a list"),
        ({"supported_timeframes": []}, "non-empty list"),
        ({"min_history": 0}, "at least 1"),
        (
            {"money_management": {"supported": ["manual"], "default": "turtle"}},
            "one of the supported",
        ),
        ({"capabilities": {"supports_signal_exit": True}}, "exactly"),
        ({"parameters": {"leverage": {"type": "integer"}}}, "belongs to the money-management"),
        ({"profile": {"id": "x"}}, "twelve fields"),
        ({"registration_date": "2026-09-27"}, "YYYYMMDD"),
        ({"extra": 1}, "unknown input keys"),
    ):
        with pytest.raises(ValueError, match=message):
            _spec(**override)
    assert list((root / "services/trading-plugins/trading_plugins/strategies").iterdir()) == []


def test_the_four_artifacts_are_written_where_the_repository_keeps_them(
    root: Path, written: tuple[ScaffoldResult, AdapterClass]
) -> None:
    result, _ = written
    assert result.strategy_module == (
        root / "services/trading-plugins/trading_plugins/strategies/ema_cross_scaffold.py"
    )
    assert result.test_module == root / "services/trading-plugins/tests/test_ema_cross_scaffold.py"
    assert result.registration_sql == (
        root / "init-scripts/signal-service/20260927/01-register-ema-cross-scaffold.sql"
    )
    assert (
        result.init_script_line == "\\ir signal-service/20260927/01-register-ema-cross-scaffold.sql"
    )
    assert result.init_script.read_text().splitlines()[-1] == result.init_script_line
    sql = result.registration_sql.read_text()
    assert sql.startswith("\\set ON_ERROR_STOP on\n\nBEGIN;\n") and sql.endswith("\nCOMMIT;\n")
    assert "statement for ema-cross-scaffold" in sql
    assert result.formatted is True


def test_the_scaffold_declares_the_input_and_the_target_contract_and_holds(
    written: tuple[ScaffoldResult, AdapterClass],
) -> None:
    _, cls = written
    metadata = cls.get_metadata()
    assert metadata.decision_contract is StrategyDecisionContract.DECISION_INTENT
    assert metadata.supported_timeframes == ["1h", "4h"] and metadata.min_history == 2
    assert [dict(item) for item in metadata.required_indicators] == _INPUT["series"]
    assert metadata.money_management.supported == ("manual",)
    assert metadata.money_management.default_settings["manual"]["reward_risk"] == 2.0
    assert metadata.money_management.supports_pyramiding is False
    assert set(cls.get_parameter_schema().fields) == {"min_strength"}
    source = Path(sys.modules[cls.__module__].__file__ or "").read_text()
    assert "decision_contract=StrategyDecisionContract.DECISION_INTENT" in source
    assert "# 여기부터 판단" in source

    stages = author_check.check(
        "ema-cross-scaffold",
        discovered=({"ema-cross-scaffold": cls}, ()),
        with_registration=False,
    )
    assert [stage.status for stage in stages.stages] == ["passed"] * 4, stages.as_json()


def test_the_generated_modules_pass_ruff_and_the_generated_test_holds(
    root: Path, written: tuple[ScaffoldResult, AdapterClass]
) -> None:
    result, _ = written
    for path in (result.strategy_module, result.test_module):
        check = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--config",
                str(_PLUGINS_CONFIG),
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert check.returncode == 0, check.stdout + check.stderr
        fmt = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "format",
                "--check",
                "--config",
                str(_PLUGINS_CONFIG),
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert fmt.returncode == 0, fmt.stdout + fmt.stderr
    test_source = result.test_module.read_text()
    assert "series_key_of(" in test_source and "# 여기부터 판단 시험" in test_source
    assert 'series_key_of("EMA", {"period": 9}, _TIMEFRAME): 1.0' in test_source


def test_an_existing_file_is_refused_before_anything_is_written(
    root: Path, written: tuple[ScaffoldResult, AdapterClass]
) -> None:
    result, _ = written
    before = result.init_script.read_text()
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        scaffold.scaffold(_spec(), root, statement_for=lambda *_: "-- again\n")
    assert result.init_script.read_text() == before
    numbered = scaffold.scaffold(
        _spec(strategy_id="second-scaffold", class_name="SecondScaffold"),
        root,
        statement_for=lambda *_: "-- second\n",
    )
    assert numbered.registration_sql.name == "02-register-second-scaffold.sql"


def test_the_command_reports_json_and_refuses_bad_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert scaffold.main([]) == 1
    assert "usage" in json.loads(capsys.readouterr().out)["error"]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({**_INPUT, "strategy_id": "Bad_Id"}))
    assert scaffold.main([str(bad)]) == 1
    assert "kebab-case" in json.loads(capsys.readouterr().out)["error"]


# --- what the Codex review of this changeset asked for -------------------------------------


def _write(root: Path, spec: ScaffoldSpec) -> tuple[ScaffoldResult, AdapterClass]:
    name = f"trading_plugins.strategies.{spec.module_name}"
    strategies = root / "services/trading-plugins/trading_plugins/strategies"

    def statement_for(strategy_id: str, display_name: str, description: str) -> str:
        _load(strategies / f"{spec.module_name}.py", name)
        return f"-- statement for {strategy_id} ({display_name}: {description})\n"

    result = scaffold.scaffold(spec, root, statement_for=statement_for)
    return result, getattr(sys.modules[name], spec.class_name)


def test_a_series_declared_on_its_own_timeframe_is_read_with_that_timeframe(root: Path) -> None:
    spec = _spec(
        strategy_id="higher-tf-scaffold",
        class_name="HigherTfScaffold",
        series=[
            {"name": "EMA", "params": {"period": 9}},
            {"name": "EMA", "params": {"period": 21}, "timeframe": "4h"},
        ],
        supported_timeframes=["1h"],
    )
    result, cls = _write(root, spec)
    try:
        source = result.strategy_module.read_text()
        assert 'self.series(inputs, "EMA", {"period": 21}, "4h")' in source
        assert 'self.series(inputs, "EMA", {"period": 9})' in source
        candle = Candle(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe="1h",
            open_time=datetime(2026, 1, 1, tzinfo=UTC),
            close_time=datetime(2026, 1, 1, 1, tzinfo=UTC),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1.0,
            quote_volume=None,
            trade_count=None,
        )
        strategy = cast(Any, cls)(
            StrategyConfig.resolve(
                cls.get_parameter_schema(), {"strategy_id": spec.strategy_id, "params": {}}
            )
        )
        decision = strategy.analyze(
            {
                "candles": [candle],
                "candle": candle,
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "market_type": "futures",
                "indicators": {
                    series_key_of("EMA", {"period": 9}, "1h"): 1.0,
                    series_key_of("EMA", {"period": 21}, "4h"): 2.0,
                },
            },
            None,
        )
        assert isinstance(decision, DecisionIntent) and decision.action is DecisionAction.HOLD
        stage = author_check.stage_declaration(spec.strategy_id, cls)
        assert stage.status == "passed", stage.as_json()
        assert 'series_key_of("EMA", {"period": 21}, "4h"): 1.0' in result.test_module.read_text()
    finally:
        sys.modules.pop(f"trading_plugins.strategies.{spec.module_name}", None)


def test_what_stages_2_and_3_would_refuse_is_refused_before_writing(root: Path) -> None:
    signal_exit_mode = next(
        mode for mode, cls in registered_money_management().items() if cls.requires_signal_exit
    )
    for override, message in (
        ({"series": [{"name": "NOT_A_SERIES", "params": {}}]}, "does not resolve"),
        ({"series": [{"name": "EMA", "params": {"period": 7}}]}, "does not resolve"),
        (
            {"series": [{"name": "EMA", "params": {"period": 9}, "timeframe": "weekly"}]},
            "does not resolve",
        ),
        ({"supported_timeframes": ["weekly"]}, "malformed"),
        (
            {"money_management": {"supported": ["never-deployed"], "default": "never-deployed"}},
            "not deployed",
        ),
        (
            {
                "money_management": {
                    "supported": ["manual"],
                    "default": "manual",
                    "default_settings": {"manual": {"not_a_setting": 1}},
                }
            },
            "are refused",
        ),
        (
            {
                "money_management": {"supported": [signal_exit_mode], "default": signal_exit_mode},
                "capabilities": {
                    **cast(dict[str, bool], _INPUT["capabilities"]),
                    "supports_signal_exit": False,
                },
            },
            "requires signal exits",
        ),
        ({"description": 'has a """ delimiter'}, "docstring delimiter"),
        ({"display_name": "two\nlines"}, "one line"),
    ):
        with pytest.raises(ValueError, match=message):
            _spec(**override)
    assert list((root / "services/trading-plugins/trading_plugins/strategies").iterdir()) == []


def test_a_failing_statement_builder_leaves_nothing_behind(root: Path) -> None:
    init_script = root / "init-scripts/06-init-signal-registry.sql"
    before = init_script.read_text()

    def failing(strategy_id: str, display_name: str, description: str) -> str:
        raise RuntimeError("no statement")

    with pytest.raises(RuntimeError, match="no statement"):
        scaffold.scaffold(_spec(), root, statement_for=failing)
    assert list((root / "services/trading-plugins/trading_plugins/strategies").iterdir()) == []
    assert list((root / "services/trading-plugins/tests").iterdir()) == []
    assert init_script.read_text() == before
    assert not (root / "init-scripts/signal-service/20260927").exists() or not list(
        (root / "init-scripts/signal-service/20260927").iterdir()
    )
