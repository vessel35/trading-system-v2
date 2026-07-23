"""Verify RunConfig owns run settings but not strategy parameter semantics."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from backtest_service.config import RunConfig
from pydantic import ValidationError


def _raw_config() -> dict[str, object]:
    return {
        "run_name": "btc-breakout-oos",
        "strategy_id": "fake-breakout",
        "params": {"strategy_owned_unknown": {"nested": True}},
        "symbol": "BTCUSDT",
        "exchange": "binance",
        "timeframe": "1h",
        "market_type": "futures",
        "data_source": "crypto_data.ohlcv_futures",
        "start": datetime(2025, 1, 1, tzinfo=UTC),
        "end": datetime(2026, 1, 1, tzinfo=UTC),
        "initial_capital": Decimal("10000"),
        "profile_ref": "breakout-v1",
    }


def test_valid_config_defaults_and_manager_selection() -> None:
    """Validate run-level fields and pass strategy params through untouched."""
    config = RunConfig.model_validate(_raw_config())
    config.revalidate()
    assert config.fill_timing == "next_bar"
    assert config.trigger_feed == "tf_candle"
    assert config.indicator_mode == "auto"
    assert config.risk_per_trade == 0.01
    assert config.selection() == {
        "strategy_id": "fake-breakout",
        "params": {"strategy_owned_unknown": {"nested": True}},
        "symbol": "BTCUSDT",
        "timeframe": "1h",
    }


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"end": datetime(2024, 1, 1, tzinfo=UTC)}, "start must be earlier"),
        ({"fill_timing": "immediate"}, "next_bar"),
        ({"risk_per_trade": 0.0101}, "risk_per_trade"),
        ({"position_size_pct": 0.2}, "position_size_pct"),
        ({"run_name": "../escape"}, "filename-safe"),
        ({"start": datetime(2025, 1, 1)}, "timezone-aware"),
        ({"cost_values": {"unknown_rate": "0.1"}}, "unknown cost parameter"),
        ({"cost_values": {"gap_multiplier": "0.5"}}, "at least one"),
    ],
)
def test_run_config_rejects_invalid_contracts(
    updates: dict[str, object],
    message: str,
) -> None:
    raw = {**_raw_config(), **updates}
    with pytest.raises((ValidationError, NotImplementedError), match=message):
        RunConfig.model_validate(raw)


def test_pct_sizing_requires_only_its_own_fraction() -> None:
    raw = {
        **_raw_config(),
        "sizing_method": "pct",
        "position_size_pct": 0.2,
    }
    config = RunConfig.model_validate(raw)
    assert config.risk_per_trade is None
    assert config.position_size_pct == 0.2


def test_reserved_m1_feed_fails_loudly_instead_of_falling_back() -> None:
    raw = {**_raw_config(), "trigger_feed": "m1_subcandle"}
    with pytest.raises(NotImplementedError, match="reserved"):
        RunConfig.model_validate(raw)


def test_extra_run_keys_are_forbidden() -> None:
    raw = {**_raw_config(), "strategy_parameter_schema": {"forbidden": True}}
    with pytest.raises(ValidationError, match="Extra inputs"):
        RunConfig.model_validate(raw)


def test_json_schema_exposes_run_choices_but_no_strategy_parameter_schema() -> None:
    schema = RunConfig.model_json_schema()
    properties = schema["properties"]
    assert properties["trigger_feed"]["enum"] == ["tf_candle", "m1_subcandle"]
    assert properties["fill_timing"]["enum"] == ["immediate", "next_bar"]
    assert "strategy_parameter_schema" not in properties
