"""Verify the deployed ATR-stop-only policy's plan, refusals, and declarations."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from core_lib.money_management import (
    AccountRiskSnapshot,
    MarketSnapshot,
    MoneyManagementError,
    RiskLimits,
)
from core_lib.types import DecisionAction, DecisionIntent, MarketType
from trading_plugins import registered_money_management
from trading_plugins.money_management.signal_exit_atr import SignalExitAtrMoneyManagement

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_REGISTRATION_FILE = (
    _REPOSITORY_ROOT / "init-scripts/signal-service/20260923/04-register-signal-exit-atr.sql"
)


def _decision(action: DecisionAction) -> DecisionIntent:
    return DecisionIntent(
        action=action,
        symbol="BTCUSDT",
        timestamp=datetime(2026, 1, 1, 1, tzinfo=UTC),
        reference_price=100.0,
        confidence=1.0,
        reason="test",
        metadata={},
    )


def _market(volatility: float = 2.0) -> MarketSnapshot:
    return MarketSnapshot(
        reference_price=100.0,
        volatility=volatility,
        volatility_name="atr:period=14@1h",
        volatility_timestamp=datetime(2026, 1, 1, 1, tzinfo=UTC),
    )


def _account(
    market_type: MarketType = MarketType.FUTURES, cash: float = 10_000.0
) -> AccountRiskSnapshot:
    return AccountRiskSnapshot(equity=10_000.0, available_cash=cash, market_type=market_type)


def _limits() -> RiskLimits:
    return RiskLimits(risk_per_trade=0.01, maintenance_margin_rate=0.004, max_leverage=20)


def test_policy_is_deployed_and_declares_that_the_strategy_must_exit() -> None:
    assert SignalExitAtrMoneyManagement.requires_signal_exit is True
    assert SignalExitAtrMoneyManagement.protection_and_leverage_ignore_account_state is False
    assert registered_money_management()["signal-exit-atr"] is SignalExitAtrMoneyManagement
    assert SignalExitAtrMoneyManagement().resolved_config() == {
        "mode": "signal-exit-atr",
        "atr_period": 14,
        "atr_stop_multiple": 2.5,
        "leverage_cap": 5,
    }


def test_policy_requires_one_atr_input_on_the_strategy_timeframe() -> None:
    # 14 is the one registered ATR period today; the requirement mirrors the setting.
    (requirement,) = SignalExitAtrMoneyManagement(atr_period=14).required_indicators()
    assert requirement.name == "ATR"
    assert requirement.params == {"period": 14}
    assert requirement.timeframe == "strategy"
    assert requirement.min_history == 14


def test_long_plan_places_the_stop_below_entry_and_no_target() -> None:
    plan = SignalExitAtrMoneyManagement().plan_entry(
        _decision(DecisionAction.ENTER_LONG), _market(), _account(), _limits()
    )
    assert plan.stop_loss == pytest.approx(100.0 - 2.5 * 2.0)
    assert plan.take_profit is None
    assert plan.initial_risk_amount == pytest.approx(100.0)
    assert plan.requested_quantity == pytest.approx(100.0 / 5.0)
    assert plan.requested_leverage == 1
    assert plan.diagnostics["stop_distance"] == pytest.approx(5.0)
    assert plan.diagnostics["policy_id"] == "signal-exit-atr"
    assert plan.diagnostics["liquidation_safe"] is True
    # Leverage 1 with a 0.4% maintenance rate liquidates a long only at 0.4% of entry.
    assert plan.diagnostics["liquidation_price"] == pytest.approx(100.0 * 0.004)


def test_plan_refuses_a_stop_the_liquidation_price_would_reach_first() -> None:
    # risk 100 / stop 5 = 20 units at 100 -> notional 2000 over 50 cash -> leverage 40.
    # A long at 40x liquidates near 97.9, above the 95 stop, so the stop is never kept.
    with pytest.raises(MoneyManagementError, match="liquidation would occur before the stop"):
        SignalExitAtrMoneyManagement(atr_stop_multiple=1.0, leverage_cap=100).plan_entry(
            _decision(DecisionAction.ENTER_LONG),
            _market(volatility=5.0),
            _account(cash=50.0),
            RiskLimits(risk_per_trade=0.01, maintenance_margin_rate=0.004, max_leverage=100),
        )


def test_policy_refuses_an_atr_period_that_is_not_registered() -> None:
    # 20 sits inside the accepted range but no ATR(20) combination is registered, so a
    # run would only fail at series resolution; the policy refuses it at construction.
    with pytest.raises(ValueError, match="not a registered ATR combination"):
        SignalExitAtrMoneyManagement(atr_period=20)


def test_short_plan_places_the_stop_above_entry() -> None:
    plan = SignalExitAtrMoneyManagement(atr_stop_multiple=1.5).plan_entry(
        _decision(DecisionAction.ENTER_SHORT), _market(), _account(), _limits()
    )
    assert plan.stop_loss == pytest.approx(100.0 + 1.5 * 2.0)
    assert plan.take_profit is None


def test_plan_requests_the_minimum_integer_leverage_the_notional_needs() -> None:
    # risk 100 / stop 0.5 = 200 units at 100 -> notional 20000 over 10000 cash -> leverage 2.
    plan = SignalExitAtrMoneyManagement(atr_stop_multiple=0.5).plan_entry(
        _decision(DecisionAction.ENTER_LONG), _market(volatility=1.0), _account(), _limits()
    )
    assert plan.requested_quantity == pytest.approx(200.0)
    assert plan.requested_leverage == 2


def test_plan_refuses_leverage_above_the_cap_instead_of_shrinking() -> None:
    # risk 100 / stop 0.05 = 2000 units at 100 -> notional 200000 over 200 cash -> 1000x.
    with pytest.raises(MoneyManagementError, match="leverage above the cap"):
        SignalExitAtrMoneyManagement(atr_stop_multiple=0.1).plan_entry(
            _decision(DecisionAction.ENTER_LONG),
            _market(volatility=0.5),
            _account(cash=200.0),
            _limits(),
        )


def test_plan_refuses_non_entry_decisions_and_negative_stops() -> None:
    policy = SignalExitAtrMoneyManagement()
    with pytest.raises(MoneyManagementError, match="entry decisions only"):
        policy.plan_entry(_decision(DecisionAction.EXIT), _market(), _account(), _limits())
    with pytest.raises(MoneyManagementError, match="stop price must remain positive"):
        policy.plan_entry(
            _decision(DecisionAction.ENTER_LONG), _market(volatility=50.0), _account(), _limits()
        )


def test_spot_plan_uses_leverage_one_and_refuses_when_cash_is_short() -> None:
    plan = SignalExitAtrMoneyManagement().plan_entry(
        _decision(DecisionAction.ENTER_LONG), _market(), _account(MarketType.SPOT), _limits()
    )
    assert plan.requested_leverage == 1
    with pytest.raises(MoneyManagementError, match="exceeds available cash"):
        SignalExitAtrMoneyManagement().plan_entry(
            _decision(DecisionAction.ENTER_LONG),
            _market(),
            _account(MarketType.SPOT, cash=100.0),
            _limits(),
        )


@pytest.mark.parametrize(
    "settings",
    [
        {"atr_period": 1},
        {"atr_period": 201},
        {"atr_stop_multiple": 0.0},
        {"atr_stop_multiple": 10.5},
        {"atr_stop_multiple": float("nan")},
        {"leverage_cap": 0},
        {"leverage_cap": 101},
    ],
)
def test_policy_rejects_out_of_range_settings(settings: dict[str, Any]) -> None:
    with pytest.raises((ValueError, TypeError)):
        SignalExitAtrMoneyManagement(**settings)


def test_policy_does_not_mutate_its_inputs() -> None:
    decision = _decision(DecisionAction.ENTER_LONG)
    market = _market()
    account = _account()
    limits = _limits()
    SignalExitAtrMoneyManagement().plan_entry(decision, market, account, limits)
    assert market == _market()
    assert account == _account()
    assert limits == _limits()
    assert decision == _decision(DecisionAction.ENTER_LONG)


def test_registration_script_matches_the_deployed_policy() -> None:
    sql = _REGISTRATION_FILE.read_text()
    identity = re.search(
        r"VALUES \(\s*'(?P<mode>[a-z0-9-]+)',\s*'(?P<class_name>\w+)',\s*'(?P<module>[\w.]+)',",
        sql,
    )
    assert identity is not None
    assert identity["mode"] == SignalExitAtrMoneyManagement.id
    assert identity["class_name"] == SignalExitAtrMoneyManagement.__name__
    assert identity["module"] == SignalExitAtrMoneyManagement.__module__
    version = re.search(
        r"'(?P<version>\d+\.\d+\.\d+)',\s*ARRAY\[(?P<settings>[^\]]+)\]::text\[\]", sql
    )
    assert version is not None
    assert version["version"] == SignalExitAtrMoneyManagement.version
    settings = [item.strip().strip("'") for item in version["settings"].split(",")]
    assert settings == ["atr_period", "atr_stop_multiple", "leverage_cap"]
