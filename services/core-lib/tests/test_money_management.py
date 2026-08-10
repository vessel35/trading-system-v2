"""Verify common manual and Turtle money-management calculations."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

import pytest
from core_lib.money_management import (
    AccountRiskSnapshot,
    MarketSnapshot,
    MoneyManagementBase,
    MoneyManagementError,
    MoneyManagementFactory,
    MoneyManagementPlan,
    PolicyIndicatorRequirement,
    RiskLimits,
    turtle_n_series,
)
from core_lib.types import Candle, DecisionAction, DecisionIntent, MarketType

_NOW = datetime(2026, 1, 21, tzinfo=UTC)


def _decision(action: DecisionAction = DecisionAction.ENTER_LONG) -> DecisionIntent:
    return DecisionIntent(
        action=action,
        symbol="BTC/USDT:USDT",
        timestamp=_NOW,
        reference_price=101.0,
        confidence=1.0,
        reason="fixture-entry",
        metadata={"edge": "ema"},
    )


def _account(
    *,
    equity: float = 10_000.0,
    cash: float = 10_000.0,
    market_type: MarketType = MarketType.FUTURES,
) -> AccountRiskSnapshot:
    return AccountRiskSnapshot(
        equity=equity,
        available_cash=cash,
        market_type=market_type,
    )


def _limits() -> RiskLimits:
    return RiskLimits(
        risk_per_trade=0.01,
        maintenance_margin_rate=0.004,
    )


def test_turtle_n_uses_only_finalized_candle_values_and_wilder_update() -> None:
    candles = []
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for index in range(21):
        opened = start + timedelta(days=index)
        candles.append(
            Candle(
                symbol="BTC/USDT:USDT",
                exchange="binance",
                timeframe="1d",
                open_time=opened,
                close_time=opened + timedelta(days=1),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=1.0,
                quote_volume=None,
                trade_count=None,
            )
        )
    values = turtle_n_series(candles, period=20)
    assert values == (
        (candles[19].close_time, 2.0),
        (candles[20].close_time, 2.0),
    )
    assert values[0][0] > candles[19].open_time


@dataclass(frozen=True, slots=True)
class _FixturePolicy(MoneyManagementBase):
    leverage: int = 1

    id: ClassVar[str] = "manual"
    version: ClassVar[str] = "test"

    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        return ()

    def resolved_config(self) -> Mapping[str, object]:
        return {"mode": self.id, "leverage": self.leverage}

    def plan_entry(
        self,
        decision: DecisionIntent,
        market: MarketSnapshot,
        account: AccountRiskSnapshot,
        global_limits: RiskLimits,
    ) -> MoneyManagementPlan:
        del decision, market, account, global_limits
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class _AlternateFixturePolicy(_FixturePolicy):
    id: ClassVar[str] = "turtle"


_POLICIES = {"manual": _FixturePolicy, "turtle": _AlternateFixturePolicy}


@pytest.mark.parametrize(
    "raw",
    [
        {"mode": "manual", "leverage": 3},
        {"mode": "turtle", "leverage": 3},
    ],
)
def test_factory_returns_only_registered_validated_modes(raw: dict[str, object]) -> None:
    policy = MoneyManagementFactory.create(raw, _POLICIES)
    assert policy.id == raw["mode"]


def test_factory_rejects_unknown_or_extra_policy_fields() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        MoneyManagementFactory.create({"mode": "kelly"}, _POLICIES)
    with pytest.raises(ValueError, match="unexpected"):
        MoneyManagementFactory.create({"mode": "manual", "api_key": "forbidden"}, _POLICIES)


def test_factory_rejects_a_configuration_without_a_mode() -> None:
    with pytest.raises(TypeError, match="mode must be a string"):
        MoneyManagementFactory.create({}, _POLICIES)


def test_factory_and_mode_listing_require_an_explicit_policy_mapping() -> None:
    from core_lib.money_management import money_management_modes

    with pytest.raises(TypeError):
        MoneyManagementFactory.create({"mode": "manual"})  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        money_management_modes()  # type: ignore[call-arg]


def test_base_refuses_a_policy_that_leaves_a_member_unimplemented() -> None:
    """The protocol accepts a wrong signature; the base refuses the instance up front."""

    class Incomplete(MoneyManagementBase):
        id = "incomplete"
        version = "1.0.0"

        def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
            return ()

        def resolved_config(self) -> Mapping[str, object]:
            return {"mode": self.id}

    with pytest.raises(TypeError, match="plan_entry"):
        Incomplete()  # type: ignore[abstract]


def test_the_base_is_the_only_money_management_contract() -> None:
    for policy in (_FixturePolicy(), _AlternateFixturePolicy()):
        assert isinstance(policy, MoneyManagementBase)
    assert isinstance(
        MoneyManagementFactory.create({"mode": "manual"}, _POLICIES), MoneyManagementBase
    )

    repository = Path(__file__).resolve().parents[3]
    production_sources = (
        path for path in (repository / "services").rglob("*.py") if "tests" not in path.parts
    )
    assert not any("MoneyManagementPolicy" in path.read_text() for path in production_sources)


def test_base_risk_budget_comes_only_from_the_global_cap() -> None:
    """A policy cannot widen the per-trade risk by choosing its own fraction."""
    budget, quantity = MoneyManagementBase.risk_inputs(
        MarketSnapshot(
            reference_price=101.0,
            volatility=2.0,
            volatility_name="ATR(14)",
            volatility_timestamp=_NOW,
        ),
        _account(equity=10_000.0),
        _limits(),
        stop_distance=5.0,
    )
    assert budget == pytest.approx(10_000.0 * 0.01)
    assert quantity == pytest.approx(budget / 5.0)


def test_base_entry_side_refuses_a_decision_that_is_not_an_entry() -> None:
    assert MoneyManagementBase.entry_side(_decision(DecisionAction.ENTER_LONG)) == 1
    assert MoneyManagementBase.entry_side(_decision(DecisionAction.ENTER_SHORT)) == -1
    with pytest.raises(MoneyManagementError, match="entry decisions only"):
        MoneyManagementBase.entry_side(_decision(DecisionAction.EXIT))
