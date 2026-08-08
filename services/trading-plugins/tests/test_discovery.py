"""Verify that placing a file is enough to deploy, and that a bad file is refused."""

from __future__ import annotations

import importlib
import sys
import textwrap
import uuid
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
import trading_plugins
from core_lib.money_management import (
    BUILTIN_POLICIES,
    MoneyManagementFactory,
    money_management_modes,
)
from trading_plugins import discovery


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Iterator[ModuleType]:
    """Give each test its own throwaway package to deploy into.

    Writing into the real plugin directory would let a crashed run leave files
    behind, and a fixture name that later matches a real strategy would delete
    that strategy's file on teardown.
    """
    name = f"_plugin_fixture_{uuid.uuid4().hex}"
    root = tmp_path / name
    root.mkdir()
    (root / "__init__.py").write_text('"""Throwaway plugin package."""\n')
    sys.path.insert(0, str(tmp_path))
    try:
        yield importlib.import_module(name)
    finally:
        sys.path.remove(str(tmp_path))
        for module in [key for key in sys.modules if key == name or key.startswith(f"{name}.")]:
            sys.modules.pop(module, None)


def _write(package: ModuleType, name: str, body: str) -> Path:
    path = Path(package.__path__[0]) / f"{name}.py"
    path.write_text(textwrap.dedent(body))
    return path


_STRATEGY_BODY = """
    from collections.abc import Mapping
    from typing import ClassVar

    from core_lib.strategy import (
        MoneyManagementSupport,
        ParameterSchema,
        StrategyBase,
        StrategyMetadata,
        StrategyProfile,
    )
    from core_lib.types import DecisionIntent, Position


    class {class_name}(StrategyBase):
        STRATEGY_ID: ClassVar[str] = "{strategy_id}"
        VERSION: ClassVar[str] = "1.0.0"

        @classmethod
        def get_metadata(cls) -> StrategyMetadata:
            return StrategyMetadata(
                required_indicators=[{{"name": "EMA", "params": {{"period": 9}}}}],
                min_history=1,
                supported_timeframes=["1h"],
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
                    supported=("manual",), default="manual"
                ),
            )

        @classmethod
        def get_parameter_schema(cls) -> ParameterSchema:
            return ParameterSchema(fields={{}})

        def analyze(
            self,
            market_data: dict[str, object],
            current_position: Position | None,
        ) -> DecisionIntent | None:
            del market_data, current_position
            return None
"""


def test_placing_a_strategy_file_is_enough_to_deploy_it(plugin_dir: ModuleType) -> None:
    _write(
        plugin_dir,
        "dropped_trend",
        _STRATEGY_BODY.format(class_name="DroppedTrend", strategy_id="dropped-trend"),
    )

    found, faults = discovery.discover_strategies(plugin_dir)

    assert faults == ()
    assert found["dropped-trend"].__name__ == "DroppedTrend"


def test_built_in_strategies_stay_registered_alongside_deployed_ones() -> None:
    assert "vessel-reference" in discovery.build_strategy_registry().list()


def test_an_id_that_is_only_inherited_does_not_count_as_declared(
    plugin_dir: ModuleType,
) -> None:
    """A file must claim its own name; inheriting one is not claiming it."""
    # The template is indented so ``_write`` can dedent it; the extra class has to
    # match that indentation or the whole module fails to parse.
    _write(
        plugin_dir,
        "inherited",
        _STRATEGY_BODY.format(class_name="Parent", strategy_id="parent-id")
        + "\n\n    class Child(Parent):\n        pass\n",
    )

    found, faults = discovery.discover_strategies(plugin_dir)

    assert "parent-id" in found and found["parent-id"].__name__ == "Parent"
    assert any("must declare its own" in fault.reason for fault in faults)


def test_two_files_claiming_one_strategy_id_keep_the_first_and_report_the_second(
    plugin_dir: ModuleType,
) -> None:
    for name, class_name in (("first_claim", "FirstClaim"), ("second_claim", "SecondClaim")):
        _write(
            plugin_dir, name, _STRATEGY_BODY.format(class_name=class_name, strategy_id="contested")
        )

    found, faults = discovery.discover_strategies(plugin_dir)

    assert len(found) == 1
    assert any("already claimed by" in fault.reason for fault in faults)


def test_one_unloadable_file_does_not_hide_the_others(plugin_dir: ModuleType) -> None:
    """A broken deployment must not take working strategies down with it."""
    _write(plugin_dir, "explodes", "raise RuntimeError('deployed badly')\n")
    _write(
        plugin_dir, "healthy", _STRATEGY_BODY.format(class_name="Healthy", strategy_id="healthy")
    )

    found, faults = discovery.discover_strategies(plugin_dir)

    assert "healthy" in found
    assert [fault.module for fault in faults] == [f"{plugin_dir.__name__}.explodes"]


def test_a_broken_plugin_leaves_the_built_in_strategies_usable() -> None:
    assert "vessel-reference" in discovery.build_strategy_registry().list()


_POLICY_BODY = """
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
    from core_lib.types import DecisionIntent, MarketType


    @dataclass(frozen=True, slots=True)
    class {class_name}(MoneyManagementBase):
        atr_stop_multiple: float = 2.0

        id: ClassVar[str] = "{mode}"
        version: ClassVar[str] = "1.0.0"

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
            stop_distance = market.volatility * float(self.atr_stop_multiple)
            budget, quantity = self.risk_inputs(market, account, global_limits, stop_distance)
            return MoneyManagementPlan(
                stop_loss=market.reference_price - side * stop_distance,
                take_profit=None,
                requested_quantity=quantity,
                requested_leverage=1 if account.market_type is MarketType.SPOT else 2,
                initial_risk_amount=budget,
                diagnostics={{"policy_id": self.id}},
            )
"""


def test_placing_a_policy_file_is_enough_to_deploy_it(plugin_dir: ModuleType) -> None:
    _write(
        plugin_dir, "dropped_atr", _POLICY_BODY.format(class_name="DroppedAtr", mode="dropped-atr")
    )

    found, faults = discovery.discover_money_management(plugin_dir)

    assert faults == ()
    assert found["dropped-atr"].__name__ == "DroppedAtr"


def test_two_files_claiming_one_policy_mode_keep_the_first_and_report_the_second(
    plugin_dir: ModuleType,
) -> None:
    for name, class_name in (("mode_one", "ModeOne"), ("mode_two", "ModeTwo")):
        _write(plugin_dir, name, _POLICY_BODY.format(class_name=class_name, mode="contested-mode"))

    found, faults = discovery.discover_money_management(plugin_dir)

    assert len(found) == 1
    assert any("already claimed by" in fault.reason for fault in faults)


def test_the_package_exposes_only_the_discovery_surface() -> None:
    assert set(trading_plugins.__all__) == {
        "build_strategy_registry",
        "discover_money_management",
        "discover_strategies",
        "registered_money_management",
    }


def test_a_deployed_policy_becomes_configurable_without_touching_the_factory(
    plugin_dir: ModuleType,
) -> None:
    """The factory reads the policy's own fields, so no branch is added for it."""
    _write(plugin_dir, "atr_only", _POLICY_BODY.format(class_name="AtrOnly", mode="atr-only"))
    found, faults = discovery.discover_money_management(plugin_dir)
    assert faults == ()

    registered = {**dict(BUILTIN_POLICIES), **dict(found)}
    policy = MoneyManagementFactory.create({"mode": "atr-only"}, registered)

    assert policy.id == "atr-only"
    assert money_management_modes(registered) == ("atr-only", "manual", "turtle")


def test_a_deployed_policy_may_not_take_a_built_in_mode(plugin_dir: ModuleType) -> None:
    _write(plugin_dir, "shadow", _POLICY_BODY.format(class_name="Shadow", mode="manual"))
    found, _ = discovery.discover_money_management(plugin_dir)
    assert "manual" in found

    assert discovery.registered_money_management()["manual"] is not found["manual"]


def test_an_unknown_mode_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match="unsupported money-management mode: 'nope'"):
        MoneyManagementFactory.create({"mode": "nope"})


def test_a_setting_the_policy_does_not_declare_is_refused() -> None:
    with pytest.raises(ValueError, match="unexpected money-management parameters"):
        MoneyManagementFactory.create({"mode": "manual", "invented": 1})
