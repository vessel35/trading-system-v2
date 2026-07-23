"""Verify that malformed confirmed candles cannot be constructed."""

from datetime import UTC, datetime, timedelta

import pytest
from core_lib.types import Candle


def make_candle(
    *,
    close_time: datetime | None = None,
    open_price: float = 100.0,
    high: float = 110.0,
    low: float = 90.0,
    close: float = 105.0,
    volume: float = 12.0,
) -> Candle:
    open_time = datetime(2026, 1, 1, tzinfo=UTC)
    return Candle(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe="1h",
        open_time=open_time,
        close_time=close_time or open_time + timedelta(hours=1),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        quote_volume=None,
        trade_count=None,
    )


def test_valid_candle_is_constructed_and_can_be_revalidated() -> None:
    candle = make_candle()
    candle.validate()
    assert candle.close_time == candle.open_time + timedelta(hours=1)


def test_close_time_must_equal_open_time_plus_timeframe() -> None:
    with pytest.raises(ValueError, match="close_time"):
        make_candle(
            close_time=datetime(2026, 1, 1, 2, tzinfo=UTC),
        )


def test_all_prices_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        make_candle(open_price=0.0)


def test_high_must_cover_open_and_close() -> None:
    with pytest.raises(ValueError, match="high"):
        make_candle(high=104.0)


def test_low_must_cover_open_and_close() -> None:
    with pytest.raises(ValueError, match="low"):
        make_candle(low=101.0)


def test_volume_must_be_non_negative() -> None:
    with pytest.raises(ValueError, match="volume"):
        make_candle(volume=-0.01)
