"""Verify common manual and Turtle money-management calculations."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

import pytest
from core_lib.money_management import (
    AccountRiskSnapshot,
    ManualMoneyManagement,
    MarketSnapshot,
    MoneyManagementBase,
    MoneyManagementError,
    MoneyManagementFactory,
    MoneyManagementPolicy,
    PolicyIndicatorRequirement,
    RiskLimits,
    TurtleMoneyManagement,
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


def test_manual_policy_exactly_reproduces_legacy_vessel_protection() -> None:
    policy = ManualMoneyManagement(
        leverage=3,
        reward_risk=2.0,
        atr_stop_multiple=2.0,
    )
    plan = policy.plan_entry(
        _decision(),
        MarketSnapshot(
            reference_price=101.0,
            volatility=2.0,
            volatility_name="ATR(14)",
            volatility_timestamp=_NOW,
        ),
        _account(),
        _limits(),
    )
    assert plan.stop_loss == 97.0
    assert plan.take_profit == 109.0
    assert plan.requested_quantity == 25.0
    assert plan.requested_leverage == 3
    assert plan.initial_risk_amount == 100.0


def test_turtle_policy_sizes_one_percent_risk_and_minimum_leverage() -> None:
    policy = TurtleMoneyManagement()
    plan = policy.plan_entry(
        DecisionIntent(
            action=DecisionAction.ENTER_LONG,
            symbol="BTC/USDT:USDT",
            timestamp=_NOW,
            reference_price=100.0,
            confidence=1.0,
            reason="fixture-entry",
            metadata={},
        ),
        MarketSnapshot(
            reference_price=100.0,
            volatility=2.0,
            volatility_name="TURTLE_N",
            volatility_timestamp=_NOW - timedelta(days=1),
        ),
        _account(cash=1_000.0),
        _limits(),
    )
    assert plan.stop_loss == 96.0
    assert plan.take_profit is None
    assert plan.requested_quantity == 25.0
    assert plan.requested_leverage == 3
    assert plan.initial_risk_amount == 100.0
    assert plan.diagnostics["liquidation_safe"] is True


def test_turtle_rejects_cap_and_liquidation_safety_failures() -> None:
    policy = TurtleMoneyManagement(leverage_cap=10)
    market = MarketSnapshot(
        reference_price=100.0,
        volatility=2.0,
        volatility_name="TURTLE_N",
        volatility_timestamp=_NOW - timedelta(days=1),
    )
    with pytest.raises(MoneyManagementError, match="leverage"):
        policy.plan_entry(
            DecisionIntent(
                action=DecisionAction.ENTER_LONG,
                symbol="BTC/USDT:USDT",
                timestamp=_NOW,
                reference_price=100.0,
                confidence=1.0,
                reason="fixture-entry",
                metadata={},
            ),
            market,
            _account(cash=100.0),
            _limits(),
        )

    with pytest.raises(MoneyManagementError, match="liquidation"):
        policy.plan_entry(
            DecisionIntent(
                action=DecisionAction.ENTER_LONG,
                symbol="BTC/USDT:USDT",
                timestamp=_NOW,
                reference_price=100.0,
                confidence=1.0,
                reason="fixture-entry",
                metadata={},
            ),
            MarketSnapshot(
                reference_price=100.0,
                volatility=20.0,
                volatility_name="TURTLE_N",
                volatility_timestamp=_NOW - timedelta(days=1),
            ),
            _account(cash=100.0),
            _limits(),
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


@pytest.mark.parametrize(
    "raw",
    [
        {"mode": "manual", "leverage": 3},
        {"mode": "turtle", "n_period": 20, "n_timeframe": "1d"},
    ],
)
def test_factory_returns_only_registered_validated_modes(raw: dict[str, object]) -> None:
    policy = MoneyManagementFactory.create(raw)
    assert policy.id == raw["mode"]


def test_factory_rejects_unknown_or_extra_policy_fields() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        MoneyManagementFactory.create({"mode": "kelly"})
    with pytest.raises(ValueError, match="unexpected"):
        MoneyManagementFactory.create({"mode": "manual", "api_key": "forbidden"})


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


def test_shipped_policies_inherit_the_base_and_still_satisfy_the_protocol() -> None:
    for policy in (ManualMoneyManagement(), TurtleMoneyManagement()):
        assert isinstance(policy, MoneyManagementBase)
        assert isinstance(policy, MoneyManagementPolicy)


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
