"""A deployed policy's refusal must reach the client as a 422 at validation time."""

from __future__ import annotations

import pytest
from core_lib.money_management import (
    MoneyManagementAvailability,
    reconcile_money_management_availability,
)
from trading_plugins import registered_money_management
from web_api.main import ApiError, _validated_run_config


def _payload(money_management: dict[str, object]) -> dict[str, object]:
    return {
        "run_name": "deployed-policy-ranges",
        "strategy_id": "supertrend-ema200-flip",
        "params": {},
        "money_management": money_management,
        "symbol": "BTC/USDT:USDT",
        "exchange": "binance",
        "timeframe": "1h",
        "market_type": "futures",
        "data_source": "crypto_data.ohlcv_futures",
        "start": "2026-05-01T00:00:00Z",
        "end": "2026-05-04T00:00:00Z",
        "initial_capital": "10000.00",
        "seed": 0,
        "sizing_method": "risk_based",
        "risk_per_trade": 0.01,
        "cost_values": {
            "futures_taker_fee_rate": "0.0004",
            "futures_entry_slippage_rate": "0.0005",
            "exit_slippage_rate": "0.0001",
            "funding_fallback_rate": "0.0001",
        },
        "indicator_mode": "auto",
        "explicit_indicators": [],
        "trigger_feed": "tf_candle",
        "fill_timing": "next_bar",
        "profile_ref": "supertrend-ema200-flip-v1",
    }


def _availability() -> tuple[MoneyManagementAvailability, ...]:
    return tuple(reconcile_money_management_availability(None, registered_money_management()))


def test_a_deployed_policy_default_is_accepted() -> None:
    config = _validated_run_config(_payload({"mode": "signal-exit-atr"}), _availability())
    assert config.money_management is not None
    assert config.money_management.mode == "signal-exit-atr"


@pytest.mark.parametrize(
    "settings",
    [{"atr_stop_multiple": 10.5}, {"leverage_cap": 0}, {"atr_period": 20}],
)
def test_a_value_the_policy_refuses_is_a_422_before_any_run_is_queued(
    settings: dict[str, object],
) -> None:
    with pytest.raises(ApiError) as error:
        _validated_run_config(
            _payload({"mode": "signal-exit-atr", **settings}),
            _availability(),
        )
    assert error.value.status_code == 422
    assert error.value.code == "invalid_run_config"
    assert "money_management" in str(error.value.details)
