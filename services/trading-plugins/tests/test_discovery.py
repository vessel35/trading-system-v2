"""Verify that placing a file is enough to deploy, and that a bad file is refused."""

from __future__ import annotations

import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path

import pytest
import trading_plugins
from trading_plugins import discovery

_STRATEGY_DIR = Path(discovery.STRATEGY_PACKAGE.__path__[0])
_POLICY_DIR = Path(discovery.MONEY_MANAGEMENT_PACKAGE.__path__[0])


@pytest.fixture
def dropped_file() -> Iterator[list[Path]]:
    """Write plugin modules for one test and remove them and their imports after."""
    written: list[Path] = []
    yield written
    for path in written:
        path.unlink(missing_ok=True)
        module = f"trading_plugins.{path.parent.name}.{path.stem}"
        sys.modules.pop(module, None)


def _write(written: list[Path], directory: Path, name: str, body: str) -> Path:
    path = directory / f"{name}.py"
    path.write_text(textwrap.dedent(body))
    written.append(path)
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


def test_placing_a_strategy_file_is_enough_to_deploy_it(dropped_file: list[Path]) -> None:
    assert "dropped-trend" not in discovery.discover_strategies()

    _write(
        dropped_file,
        _STRATEGY_DIR,
        "dropped_trend",
        _STRATEGY_BODY.format(class_name="DroppedTrend", strategy_id="dropped-trend"),
    )

    found = discovery.discover_strategies()
    assert "dropped-trend" in found
    assert found["dropped-trend"].__name__ == "DroppedTrend"
    assert "dropped-trend" in discovery.build_strategy_registry().list()


def test_built_in_strategies_stay_registered_alongside_deployed_ones() -> None:
    assert "vessel-reference" in discovery.build_strategy_registry().list()


def test_a_strategy_without_a_declared_id_is_refused(dropped_file: list[Path]) -> None:
    """A file must claim the name it is deployed under, or it is not deployed."""
    _write(
        dropped_file,
        _STRATEGY_DIR,
        "nameless",
        _STRATEGY_BODY.format(class_name="Nameless", strategy_id="temp").replace(
            '        STRATEGY_ID: ClassVar[str] = "temp"\n', ""
        ),
    )

    with pytest.raises(ValueError, match="must declare a non-empty STRATEGY_ID"):
        discovery.discover_strategies()


def test_two_files_claiming_one_strategy_id_are_refused(dropped_file: list[Path]) -> None:
    for name, class_name in (("first_claim", "FirstClaim"), ("second_claim", "SecondClaim")):
        _write(
            dropped_file,
            _STRATEGY_DIR,
            name,
            _STRATEGY_BODY.format(class_name=class_name, strategy_id="contested"),
        )

    with pytest.raises(ValueError, match="is claimed by both"):
        discovery.discover_strategies()


def test_a_deployed_strategy_may_not_take_a_built_in_id(dropped_file: list[Path]) -> None:
    """Silently replacing a shipped strategy would change results with no trace."""
    _write(
        dropped_file,
        _STRATEGY_DIR,
        "shadow_vessel",
        _STRATEGY_BODY.format(class_name="ShadowVessel", strategy_id="vessel-reference"),
    )

    with pytest.raises(ValueError, match="already registered in-process"):
        discovery.build_strategy_registry()


_POLICY_BODY = """
    from collections.abc import Mapping
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


    class {class_name}(MoneyManagementBase):
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
            stop_distance = market.volatility * 2.0
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


def test_placing_a_policy_file_is_enough_to_deploy_it(dropped_file: list[Path]) -> None:
    assert "dropped-atr" not in discovery.discover_money_management()

    _write(
        dropped_file,
        _POLICY_DIR,
        "dropped_atr",
        _POLICY_BODY.format(class_name="DroppedAtr", mode="dropped-atr"),
    )

    found = discovery.discover_money_management()
    assert "dropped-atr" in found
    assert found["dropped-atr"].__name__ == "DroppedAtr"


def test_two_files_claiming_one_policy_mode_are_refused(dropped_file: list[Path]) -> None:
    for name, class_name in (("mode_one", "ModeOne"), ("mode_two", "ModeTwo")):
        _write(
            dropped_file,
            _POLICY_DIR,
            name,
            _POLICY_BODY.format(class_name=class_name, mode="contested-mode"),
        )

    with pytest.raises(ValueError, match="is claimed by both"):
        discovery.discover_money_management()


def test_the_package_exposes_only_the_discovery_surface() -> None:
    assert set(trading_plugins.__all__) == {
        "build_strategy_registry",
        "discover_money_management",
        "discover_strategies",
    }
