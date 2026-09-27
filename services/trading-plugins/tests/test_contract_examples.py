"""The contract's two example blocks are deployable code, proved by deploying them.

Design: ``docs/fullspec/author_check_and_scaffold_design.md`` section 3.3. The code blocks in
``docs/strategy-authoring-contract.md`` whose first line is ``# contract-example: strategy`` or
``# contract-example: policy`` are written into a throwaway package and put through discovery,
the identifier rule, adapter construction, runtime composition with every mode the strategy
declares, and one decision on the contract's minimal scenario (two EMA values and an engulfing
pattern). A block without the marker is prose and is not executed.

Registration statements and the catalog precheck are not exercised here: both require a module
path inside the deployed packages, which a throwaway package cannot have, and both are tested
on the deployed plugins. The fact functions take no test-only bypass for that.
"""

from __future__ import annotations

import contextlib
import importlib
import re
import sys
import uuid
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest
from core_lib.identifiers import is_plugin_identifier
from core_lib.money_management import (
    AccountRiskSnapshot,
    MarketSnapshot,
    MoneyManagementBase,
    MoneyManagementFactory,
    RiskLimits,
)
from core_lib.ports import StrategyRegistry
from core_lib.series import series_key_of
from core_lib.strategy import (
    AdapterClass,
    AdapterManager,
    InProcessStrategyRegistry,
    StrategyDecisionContract,
)
from core_lib.types import Candle, DecisionAction, DecisionIntent, MarketType
from trading_plugins import discovery, registered_money_management

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CONTRACT = REPOSITORY_ROOT / "docs" / "strategy-authoring-contract.md"
_MARKED_BLOCK = re.compile(r"```python\n# contract-example: (strategy|policy)\n(.*?)```", re.DOTALL)
_KINDS = frozenset({"strategy", "policy"})


def _example_blocks() -> dict[str, str]:
    """The two marked blocks, keyed by kind; exactly one of each must be marked."""
    found: dict[str, str] = {}
    for kind, body in _MARKED_BLOCK.findall(CONTRACT.read_text()):
        assert kind not in found, f"more than one {kind} example is marked"
        found[kind] = body
    assert set(found) == _KINDS, f"marked examples: {sorted(found)}"
    return found


@contextlib.contextmanager
def _deployed(tmp_path: Path, bodies: Mapping[str, str]) -> Iterator[ModuleType]:
    """Write the bodies as modules of a throwaway package and import it."""
    name = f"_contract_example_{uuid.uuid4().hex}"
    root = tmp_path / name
    root.mkdir()
    (root / "__init__.py").write_text('"""Throwaway package for the contract examples."""\n')
    for kind, body in bodies.items():
        (root / f"example_{kind}.py").write_text(body)
    sys.path.insert(0, str(tmp_path))
    try:
        yield importlib.import_module(name)
    finally:
        sys.path.remove(str(tmp_path))
        for module in [key for key in sys.modules if key == name or key.startswith(f"{name}.")]:
            sys.modules.pop(module, None)


@pytest.fixture
def examples(tmp_path: Path) -> Iterator[ModuleType]:
    with _deployed(tmp_path, _example_blocks()) as package:
        yield package


class _Rows(StrategyRegistry):
    """The registration row each example class would carry, minus lifecycle."""

    def __init__(self, classes: Mapping[str, AdapterClass]) -> None:
        self._classes = dict(classes)

    def get(self, strategy_id: str) -> dict[str, object]:
        cls = self._classes[strategy_id]
        return {
            "strategy_id": strategy_id,
            "class_name": cls.__name__,
            "module_path": cls.__module__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get(strategy_id) for strategy_id in self._classes]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError("read-only fixture")


def _manager(
    strategies: Mapping[str, AdapterClass],
    policies: Mapping[str, type[MoneyManagementBase]],
) -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    for strategy_id, cls in strategies.items():
        plugins.register(strategy_id, cls)
    return AdapterManager(_Rows(strategies), plugins, money_management_policies=policies)


def _the_strategy(package: ModuleType) -> tuple[str, AdapterClass]:
    strategies, faults = discovery.discover_strategies(package)
    assert faults == (), faults
    ((identifier, cls),) = strategies.items()
    return identifier, cls


def _raw(identifier: str) -> dict[str, object]:
    return {"strategy_id": identifier, "params": {}}


# --- the examples as written ---------------------------------------------------------------


def test_both_examples_are_discovered_without_faults_and_follow_the_identifier_rule(
    examples: ModuleType,
) -> None:
    strategies, strategy_faults = discovery.discover_strategies(examples)
    policies, policy_faults = discovery.discover_money_management(examples)

    assert strategy_faults == () and policy_faults == ()
    assert len(strategies) == 1 and len(policies) == 1
    for identifier in (*strategies, *policies):
        assert is_plugin_identifier(identifier)
    (cls,) = strategies.values()
    assert cls.get_metadata().decision_contract is StrategyDecisionContract.DECISION_INTENT


def test_the_strategy_example_composes_with_every_mode_it_declares(examples: ModuleType) -> None:
    identifier, cls = _the_strategy(examples)
    example_policies, _ = discovery.discover_money_management(examples)
    policies = {**registered_money_management(), **example_policies}
    manager = _manager({identifier: cls}, policies)

    manager.create(identifier, _raw(identifier))
    support = cls.get_metadata().money_management
    assert support.supported, "the example declares at least one policy"
    for mode in support.supported:
        runtime = manager.create_runtime(identifier, _raw(identifier), {"mode": mode})
        assert runtime.money_management is not None
        assert runtime.money_management.id == mode


def test_the_strategy_example_decides_on_the_minimal_scenario(examples: ModuleType) -> None:
    """Two EMA values in an uptrend and a bullish engulfing bar: the example enters long."""
    identifier, cls = _the_strategy(examples)
    strategy = _manager({identifier: cls}, registered_money_management()).create(
        identifier, _raw(identifier)
    )
    metadata = cls.get_metadata()
    timeframe = metadata.supported_timeframes[0]
    open_time = datetime(2026, 1, 1, tzinfo=UTC)
    candle = Candle(
        symbol="BTCUSDT",
        exchange="binance",
        timeframe=timeframe,
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1.0,
        quote_volume=None,
        trade_count=None,
    )
    indicators: dict[str, object] = {
        series_key_of("EMA", {"period": 21}, timeframe): 101.0,
        series_key_of("EMA", {"period": 55}, timeframe): 100.0,
        series_key_of("pat_engulfing", {}, timeframe): {
            "occurred": 1.0,
            "direction": 1.0,
            "strength": 1.0,
            "confirmed": 1.0,
        },
    }
    declared = {
        series_key_of(
            str(item["name"]), cast(Mapping[str, object], item.get("params", {})), timeframe
        )
        for item in metadata.required_indicators
    }
    assert set(indicators) == declared, "the scenario must carry exactly the declared series"

    decision = strategy.analyze(
        {
            "candles": [candle],
            "candle": candle,
            "symbol": candle.symbol,
            "timeframe": timeframe,
            "market_type": MarketType.FUTURES,
            "indicators": indicators,
        },
        None,
    )

    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.ENTER_LONG
    assert decision.timestamp == candle.close_time


def test_the_policy_example_plans_a_long_entry_and_leaves_the_exit_to_the_strategy(
    examples: ModuleType,
) -> None:
    policies, faults = discovery.discover_money_management(examples)
    assert faults == ()
    ((mode, cls),) = policies.items()
    policy = MoneyManagementFactory.create({"mode": mode}, policies)
    assert policy.requires_signal_exit is True
    now = datetime(2026, 1, 1, 1, tzinfo=UTC)
    decision = DecisionIntent(
        action=DecisionAction.ENTER_LONG,
        symbol="BTCUSDT",
        timestamp=now,
        reference_price=100.0,
        confidence=1.0,
        reason="example",
        metadata={},
    )

    plan = policy.plan_entry(
        decision,
        MarketSnapshot(
            reference_price=100.0,
            volatility=2.0,
            volatility_name="ATR(14)",
            volatility_timestamp=now,
        ),
        AccountRiskSnapshot(
            equity=10_000.0, available_cash=10_000.0, market_type=MarketType.FUTURES
        ),
        RiskLimits(risk_per_trade=0.01, maintenance_margin_rate=0.005),
    )

    assert 0.0 < plan.stop_loss < 100.0
    assert plan.take_profit is None
    assert plan.requested_quantity > 0.0
    assert cls.id == mode


# --- the examples broken on purpose: each defect the design names is caught ----------------


def _strategy_body_without(text: str) -> dict[str, str]:
    bodies = dict(_example_blocks())
    assert bodies["strategy"].count(text) == 1, f"the example no longer carries {text!r}"
    bodies["strategy"] = bodies["strategy"].replace(text, "")
    return bodies


def test_an_underscore_in_the_example_id_is_a_discovery_fault(tmp_path: Path) -> None:
    bodies = dict(_example_blocks())
    original = 'STRATEGY_ID = "ema-engulfing-example"'
    assert bodies["strategy"].count(original) == 1
    bodies["strategy"] = bodies["strategy"].replace(
        original, 'STRATEGY_ID = "ema_engulfing_example"'
    )
    with _deployed(tmp_path, bodies) as package:
        strategies, faults = discovery.discover_strategies(package)
    assert strategies == {}
    assert len(faults) == 1 and "not kebab-case" in faults[0].reason


def test_removing_the_class_declaration_is_a_discovery_fault(tmp_path: Path) -> None:
    bodies = _strategy_body_without("    STRATEGY_ID = STRATEGY_ID")
    with _deployed(tmp_path, bodies) as package:
        strategies, faults = discovery.discover_strategies(package)
    assert strategies == {}
    assert len(faults) == 1 and "must declare its own" in faults[0].reason


def test_removing_the_decision_contract_declaration_is_refused_at_composition(
    tmp_path: Path,
) -> None:
    bodies = _strategy_body_without(
        "            decision_contract=StrategyDecisionContract.DECISION_INTENT,\n"
    )
    with _deployed(tmp_path, bodies) as package:
        identifier, cls = _the_strategy(package)
        manager = _manager({identifier: cls}, registered_money_management())
        manager.create(identifier, _raw(identifier))
        mode = cls.get_metadata().money_management.supported[0]
        with pytest.raises(ValueError, match="cannot attach money management"):
            manager.create_runtime(identifier, _raw(identifier), {"mode": mode})
