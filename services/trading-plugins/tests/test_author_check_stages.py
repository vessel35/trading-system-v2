"""Stages 1 to 5 of the pre-deployment check, on the deployed strategies and on injected faults.

Design: ``docs/fullspec/author_check_and_scaffold_design.md`` sections 3.4, 3.4.2 and 6. The
faults are strategies and policies written into a throwaway package and injected into the stage
functions as discovery results; that injection is a Python argument and is not on the command
line or the MCP surface.
"""

from __future__ import annotations

import contextlib
import importlib
import json
import re
import sys
import textwrap
import uuid
from collections.abc import Iterator, Mapping
from pathlib import Path
from types import ModuleType

import pytest
from core_lib.indicators.registry import build_default_registry
from core_lib.patterns import TALIB_PATTERN_REGISTRY
from trading_plugins import author_check, discovery, registered_money_management
from trading_plugins.author_check import (
    MONEY_MANAGEMENT_OWNED_PARAMETERS,
    RULES,
    Finding,
    check,
    main,
    parse_arguments,
)

_DEPLOYED = sorted(discovery.discover_strategies()[0])


# --- the deployed strategies -------------------------------------------------------------


@pytest.mark.parametrize("strategy_id", _DEPLOYED)
def test_every_deployed_strategy_passes_stages_one_to_five(strategy_id: str) -> None:
    report = check(strategy_id)
    assert [stage.stage for stage in report.stages] == [1, 2, 3, 4, 5]
    assert report.passed, json.dumps(report.as_json(), indent=1)
    composed = report.stages[2].data["composed_modes"]
    declared = discovery.discover_strategies()[0][strategy_id].get_metadata().money_management
    assert composed == list(declared.supported)


def test_an_unknown_id_fails_at_discovery_and_the_later_stages_do_not_run() -> None:
    report = check("not-deployed")
    assert report.passed is False
    assert report.stages[0].status == "failed"
    assert [finding.rule for finding in report.stages[0].findings] == ["discovery-fault"]
    assert [stage.status for stage in report.stages[1:]] == ["failed"] * 4
    assert all(
        [finding.rule for finding in stage.findings] == ["stage-not-run"]
        for stage in report.stages[1:]
    )


def test_an_id_that_is_not_kebab_case_is_refused_before_discovery() -> None:
    report = check("Not_Kebab")
    assert [finding.rule for finding in report.stages[0].findings] == ["identifier-format"]


# --- injected faults ----------------------------------------------------------------------

_STRATEGY_TEMPLATE = """
    from collections.abc import Mapping
    from typing import ClassVar

    from core_lib.strategy import (
        FieldSpec,
        MoneyManagementSupport,
        ParameterSchema,
        ResolvedConfig,
        StrategyBase,
        StrategyDecisionContract,
        StrategyMetadata,
        StrategyProfile,
    )
    from core_lib.types import DecisionIntent, Position


    class {class_name}(StrategyBase):
        STRATEGY_ID: ClassVar[str] = "{strategy_id}"
        VERSION: ClassVar[str] = "1.0.0"

        def __init__(self, config: ResolvedConfig) -> None:
            self.config = config

        @classmethod
        def get_metadata(cls) -> StrategyMetadata:
            return StrategyMetadata(
                required_indicators={series},
                min_history=1,
                supported_timeframes={timeframes},
                profile=StrategyProfile(
                    id="{strategy_id}-profile",
                    family="trend",
                    bar="1h",
                    expected_win_rate=(0.3, 0.6),
                    expected_payoff=(1.0, 3.0),
                    tail_shape="right_fat",
                    holding_horizon="intraday",
                    primary_metric="calmar",
                    risk_adjusted_pref="sortino",
                    profit_structure_to_preserve="trend",
                    envelope_tolerance=0.2,
                    envelope_status="provisional",
                ),
                money_management=MoneyManagementSupport(
                    supported={supported}, default={default}, supports_signal_exit=True
                ),
                decision_contract=StrategyDecisionContract.DECISION_INTENT,
            )

        @classmethod
        def get_parameter_schema(cls) -> ParameterSchema:
            return ParameterSchema(fields={fields})

        def analyze(
            self,
            market_data: dict[str, object],
            current_position: Position | None,
        ) -> DecisionIntent | None:
            del market_data, current_position
            return None
"""

_POLICY_TEMPLATE = """
    from collections.abc import Mapping
    from dataclasses import dataclass
    from typing import ClassVar

    from core_lib.money_management import (
        AccountRiskSnapshot,
        MarketSnapshot,
        MoneyManagementBase,
        MoneyManagementPlan,
        PolicyIndicatorRequirement,
        RiskLimits,
    )
    from core_lib.types import DecisionIntent


    @dataclass(frozen=True, slots=True)
    class {class_name}(MoneyManagementBase):
        {settings}

        id: ClassVar[str] = "{mode}"
        version: ClassVar[str] = "1.0.0"
        requires_signal_exit: ClassVar[bool] = True

        def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
            return (
                PolicyIndicatorRequirement(
                    name="ATR", params={{"period": 14}}, timeframe="strategy", min_history=14
                ),
            )

        def resolved_config(self) -> Mapping[str, object]:
            return {{"mode": self.id}}

        def plan_entry(
            self,
            decision: DecisionIntent,
            market: MarketSnapshot,
            account: AccountRiskSnapshot,
            global_limits: RiskLimits,
        ) -> MoneyManagementPlan:
            side = self.entry_side(decision)
            stop_distance = market.volatility * 2.0
            budget, quantity = self.risk_inputs(market, account, global_limits, stop_distance)
            return MoneyManagementPlan(
                stop_loss=market.reference_price - side * stop_distance,
                take_profit=None,
                requested_quantity=quantity,
                requested_leverage=1,
                initial_risk_amount=budget,
                diagnostics={{}},
            )
"""

_MANUAL_LIKE_SERIES = '[{"name": "EMA", "params": {"period": 9}}]'


def _strategy_source(
    strategy_id: str,
    *,
    series: str = _MANUAL_LIKE_SERIES,
    timeframes: str = '["1h"]',
    supported: str,
    default: str,
    fields: str = "{}",
) -> str:
    return textwrap.dedent(
        _STRATEGY_TEMPLATE.format(
            class_name="Injected",
            strategy_id=strategy_id,
            series=series,
            timeframes=timeframes,
            supported=supported,
            default=default,
            fields=fields,
        )
    )


def _policy_source(mode: str, *, settings: str = "atr_stop_multiple: float = 2.0") -> str:
    return textwrap.dedent(
        _POLICY_TEMPLATE.format(class_name="InjectedPolicy", mode=mode, settings=settings)
    )


@contextlib.contextmanager
def _package(tmp_path: Path, modules: Mapping[str, str]) -> Iterator[ModuleType]:
    name = f"_author_check_fixture_{uuid.uuid4().hex}"
    root = tmp_path / name
    root.mkdir()
    (root / "__init__.py").write_text('"""Throwaway package."""\n')
    for module, body in modules.items():
        (root / f"{module}.py").write_text(body)
    sys.path.insert(0, str(tmp_path))
    try:
        yield importlib.import_module(name)
    finally:
        sys.path.remove(str(tmp_path))
        for key in [key for key in sys.modules if key == name or key.startswith(f"{name}.")]:
            sys.modules.pop(key, None)


def _deployed_mode() -> str:
    """A mode that is deployed, read from discovery rather than written here."""
    return sorted(registered_money_management())[0]


def _rules(report: author_check.CheckReport, stage: int) -> list[str]:
    return [finding.rule for finding in report.stages[stage - 1].findings]


def test_a_policy_with_an_underscore_id_is_a_discovery_fault_the_strategy_sees_at_stage_3(
    tmp_path: Path,
) -> None:
    modules = {
        "under_score": _policy_source("under_score"),
        "user": _strategy_source(
            "injected-user", supported='("under_score",)', default='"under_score"'
        ),
    }
    with _package(tmp_path, modules) as package:
        strategies = discovery.discover_strategies(package)
        policies, faults = discovery.discover_money_management(package)
        assert policies == {} and len(faults) == 1 and "not kebab-case" in faults[0].reason
        report = check(
            "injected-user",
            discovered=strategies,
            policies={**registered_money_management(), **policies},
            with_registration=False,
        )
    assert _rules(report, 1) == [] and _rules(report, 2) == []
    assert _rules(report, 3) == ["policy-mode-not-deployed"]
    assert report.stages[2].findings[0].data["mode"] == "under_score"


def test_an_unregistered_series_combination_fails_stage_2(tmp_path: Path) -> None:
    mode = _deployed_mode()
    modules = {
        "user": _strategy_source(
            "injected-series",
            series='[{"name": "EMA", "params": {"period": 7}}]',
            supported=f'("{mode}",)',
            default=f'"{mode}"',
        )
    }
    with _package(tmp_path, modules) as package:
        report = check(
            "injected-series",
            discovered=discovery.discover_strategies(package),
            with_registration=False,
        )
    assert _rules(report, 2) == ["series-unregistered"]
    assert report.stages[1].findings[0].data["declared"] == {
        "name": "EMA",
        "params": {"period": 7},
    }


def test_a_malformed_timeframe_fails_stage_2(tmp_path: Path) -> None:
    mode = _deployed_mode()
    modules = {
        "user": _strategy_source(
            "injected-timeframe",
            timeframes='["1h", "hourly"]',
            supported=f'("{mode}",)',
            default=f'"{mode}"',
        )
    }
    with _package(tmp_path, modules) as package:
        report = check(
            "injected-timeframe",
            discovered=discovery.discover_strategies(package),
            with_registration=False,
        )
    assert _rules(report, 2) == ["timeframe-format"]
    assert report.stages[1].findings[0].data["timeframe"] == "hourly"


def test_a_mode_that_is_not_deployed_fails_stage_3(tmp_path: Path) -> None:
    modules = {
        "user": _strategy_source(
            "injected-mode", supported='("never-deployed",)', default='"never-deployed"'
        )
    }
    with _package(tmp_path, modules) as package:
        report = check(
            "injected-mode",
            discovered=discovery.discover_strategies(package),
            with_registration=False,
        )
    assert _rules(report, 3) == ["policy-mode-not-deployed"]


def test_a_policy_setting_without_a_default_needs_mode_settings(tmp_path: Path) -> None:
    modules = {
        "needy": _policy_source("needy-policy", settings="required_multiple: float"),
        "user": _strategy_source(
            "injected-needy", supported='("needy-policy",)', default='"needy-policy"'
        ),
    }
    with _package(tmp_path, modules) as package:
        strategies = discovery.discover_strategies(package)
        policies = {
            **registered_money_management(),
            **discovery.discover_money_management(package)[0],
        }
        without = check(
            "injected-needy", discovered=strategies, policies=policies, with_registration=False
        )
        with_settings = check(
            "injected-needy",
            discovered=strategies,
            policies=policies,
            mode_settings={"needy-policy": {"required_multiple": 1.5}},
            with_registration=False,
        )
    assert _rules(without, 3) == ["policy-settings-required"]
    assert without.stages[2].findings[0].data["missing"] == ["required_multiple"]
    assert with_settings.stages[2].status == "passed"


def test_a_runtime_refusal_is_reported_by_rule(tmp_path: Path) -> None:
    """A policy that requires signal exits, on a strategy without them: the runtime refuses."""
    mode = _deployed_mode()
    source = _strategy_source(
        "injected-refused", supported=f'("{mode}",)', default=f'"{mode}"'
    ).replace("supports_signal_exit=True", "supports_signal_exit=False")
    modules = {"user": source, "strict": _policy_source("strict-exit")}
    with _package(tmp_path, modules) as package:
        strategies = discovery.discover_strategies(package)
        policies = {
            **registered_money_management(),
            **discovery.discover_money_management(package)[0],
        }
        cls = strategies[0]["injected-refused"]
        stage = author_check.stage_money_management(
            "injected-refused",
            cls,
            policies={**policies},
            mode_settings=None,
        )
    assert stage.status == "passed"  # the deployed mode composes; now the strict one
    with _package(
        tmp_path,
        {
            "user": source.replace(f'("{mode}",)', '("strict-exit",)').replace(
                f'"{mode}"', '"strict-exit"'
            ),
            "strict": _policy_source("strict-exit"),
        },
    ) as package:
        strategies = discovery.discover_strategies(package)
        policies = {
            **registered_money_management(),
            **discovery.discover_money_management(package)[0],
        }
        report = check(
            "injected-refused", discovered=strategies, policies=policies, with_registration=False
        )
    assert _rules(report, 3) == ["runtime-refused"]
    assert "requires strategy signal exits" in report.stages[2].findings[0].detail


def test_settings_cannot_select_another_mode_than_the_one_they_are_keyed_by(
    tmp_path: Path,
) -> None:
    """A ``mode`` inside a mode's settings would compose one policy under another's name."""
    mode = _deployed_mode()
    other = sorted(registered_money_management())[-1]
    modules = {
        "user": _strategy_source("injected-swap", supported=f'("{mode}",)', default=f'"{mode}"')
    }
    with _package(tmp_path, modules) as package:
        report = check(
            "injected-swap",
            discovered=discovery.discover_strategies(package),
            mode_settings={mode: {"mode": other}},
            with_registration=False,
        )
    assert _rules(report, 3) == ["mode-settings-invalid"]
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({mode: {"mode": other}}))
    with pytest.raises(ValueError, match="must not carry 'mode'"):
        author_check.load_mode_settings(str(path))


def test_a_policy_owned_parameter_name_fails_stage_4(tmp_path: Path) -> None:
    mode = _deployed_mode()
    modules = {
        "user": _strategy_source(
            "injected-parameter",
            supported=f'("{mode}",)',
            default=f'"{mode}"',
            fields='{"leverage": FieldSpec(type="integer", default=1, range=(1, 10))}',
        )
    }
    with _package(tmp_path, modules) as package:
        report = check(
            "injected-parameter",
            discovered=discovery.discover_strategies(package),
            with_registration=False,
        )
    assert _rules(report, 4) == ["parameter-policy-owned"]
    assert report.stages[3].findings[0].data["parameter"] == "leverage"


# --- the vocabulary and the source ---------------------------------------------------------


def test_the_rule_vocabulary_is_fixed() -> None:
    assert RULES == {
        "discovery-fault",
        "identifier-format",
        "timeframe-format",
        "series-unregistered",
        "policy-mode-not-deployed",
        "policy-settings-required",
        "runtime-refused",
        "parameter-policy-owned",
        "precheck-failed",
        "declaration-unreadable",
        "dry-run-error",
        "dry-run-integrity",
        "dry-run-nondeterministic",
        "qa-failed",
        "unit-tests-failed",
        "integration-tests-failed",
        "mode-settings-invalid",
        "stage-not-run",
    }
    with pytest.raises(ValueError, match="unknown rule name"):
        Finding("made-up", "detail")


def test_the_owned_parameter_names_are_the_contract_section_4_2_list() -> None:
    assert MONEY_MANAGEMENT_OWNED_PARAMETERS == {
        "leverage",
        "reward_risk",
        "atr_stop_multiple",
        "risk_per_trade",
        "position_size_pct",
        "margin",
        "quantity",
    }


def test_the_source_names_no_deployed_inventory() -> None:
    """Like ``facts.py``: a mode, indicator, or pattern name in the source would pin inventory."""
    source = Path(author_check.__file__).read_text()
    words = {word.casefold() for word in re.findall(r"[A-Za-z_][A-Za-z0-9_\-]*", source)}
    inventory = {
        name.casefold()
        for name in (
            *registered_money_management(),
            *(spec.name for spec in build_default_registry().list()),
            *(spec.name for spec in TALIB_PATTERN_REGISTRY.list()),
        )
    }
    assert words & inventory == set()


# --- the command line ---------------------------------------------------------------------


def test_the_command_reports_json_and_exit_codes(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([_DEPLOYED[0]]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"] == "passed" and report["passed"] is True
    assert len(report["stages"]) == 5 and report["skipped_stages"] == []

    assert main(["not-deployed"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["passed"] is False and report["stages"][0]["status"] == "failed"

    assert main([]) == 1
    assert "usage" in json.loads(capsys.readouterr().out)["error"]

    assert main(["x", "--mode-settings"]) == 1
    assert "usage" in json.loads(capsys.readouterr().out)["error"]


def test_mode_settings_are_read_from_a_json_file(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"some-mode": {"a": 1}}))
    assert parse_arguments(["vessel", "--mode-settings", str(path)]) == ("vessel", str(path))
    assert author_check.load_mode_settings(str(path)) == {"some-mode": {"a": 1}}
    path.write_text(json.dumps({"some-mode": 3}))
    with pytest.raises(ValueError, match="mode to settings object"):
        author_check.load_mode_settings(str(path))
