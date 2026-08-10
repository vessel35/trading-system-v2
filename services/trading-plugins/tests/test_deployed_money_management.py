"""Characterize the calculations of the two deployed money-management policies."""

from datetime import UTC, datetime, timedelta

import pytest
from core_lib.money_management import (
    AccountRiskSnapshot,
    MarketSnapshot,
    MoneyManagementError,
    RiskLimits,
)
from core_lib.types import DecisionAction, DecisionIntent, MarketType
from trading_plugins.money_management.manual import ManualMoneyManagement
from trading_plugins.money_management.turtle import TurtleMoneyManagement

_NOW = datetime(2026, 1, 21, tzinfo=UTC)


def _decision() -> DecisionIntent:
    return DecisionIntent(
        action=DecisionAction.ENTER_LONG,
        symbol="BTC/USDT:USDT",
        timestamp=_NOW,
        reference_price=101.0,
        confidence=1.0,
        reason="fixture-entry",
        metadata={"edge": "ema"},
    )


def _account(*, cash: float = 10_000.0) -> AccountRiskSnapshot:
    return AccountRiskSnapshot(
        equity=10_000.0,
        available_cash=cash,
        market_type=MarketType.FUTURES,
    )


def _limits() -> RiskLimits:
    return RiskLimits(risk_per_trade=0.01, maintenance_margin_rate=0.004)


def test_manual_policy_exactly_reproduces_legacy_vessel_protection() -> None:
    policy = ManualMoneyManagement(leverage=3, reward_risk=2.0, atr_stop_multiple=2.0)
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
        policy.plan_entry(_decision(), market, _account(cash=100.0), _limits())

    with pytest.raises(MoneyManagementError, match="liquidation"):
        policy.plan_entry(
            _decision(),
            MarketSnapshot(
                reference_price=100.0,
                volatility=20.0,
                volatility_name="TURTLE_N",
                volatility_timestamp=_NOW - timedelta(days=1),
            ),
            _account(cash=100.0),
            _limits(),
        )
