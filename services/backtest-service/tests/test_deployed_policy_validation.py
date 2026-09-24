"""A deployed policy's own refusals must surface when a run configuration is validated."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from backtest_service.config import RunConfig
from pydantic import ValidationError


def _raw_config(money_management: dict[str, object]) -> dict[str, object]:
    return {
        "run_name": "deployed-policy-check",
        "strategy_id": "supertrend-ema200-flip",
        "params": {},
        "symbol": "BTCUSDT",
        "exchange": "binance",
        "timeframe": "1h",
        "market_type": "futures",
        "data_source": "crypto_data.ohlcv_futures",
        "start": datetime(2026, 5, 1, tzinfo=UTC),
        "end": datetime(2026, 5, 4, tzinfo=UTC),
        "initial_capital": Decimal("10000"),
        "profile_ref": "supertrend-ema200-flip-v1",
        "money_management": money_management,
    }


def test_a_deployed_policy_default_configuration_validates() -> None:
    config = RunConfig.model_validate(_raw_config({"mode": "signal-exit-atr"}))
    assert config.money_management is not None
    assert config.money_management.mode == "signal-exit-atr"


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"atr_stop_multiple": 10.5}, "atr_stop_multiple must be finite and in"),
        ({"leverage_cap": 0}, "leverage_cap must be an integer in"),
        ({"atr_period": 201}, "atr_period must be an integer in"),
        ({"atr_period": 20}, "not a registered ATR combination"),
    ],
)
def test_a_value_the_policy_refuses_is_refused_at_validation(
    settings: dict[str, object], message: str
) -> None:
    """The generated model runs the policy's ``__post_init__`` instead of accepting a value
    the run would only reject after it had been queued."""
    with pytest.raises(ValidationError, match=message):
        RunConfig.model_validate(_raw_config({"mode": "signal-exit-atr", **settings}))
