"""Verify that malformed confirmed candles cannot be constructed."""

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from core_lib.types import Candle


def make_candle(
    *,
    timeframe: str = "1h",
    close_time: datetime | None = None,
    open_price: float = 100.0,
    high: float = 110.0,
    low: float = 90.0,
    close: float = 105.0,
    volume: float = 12.0,
    quote_volume: float | None = None,
    trade_count: int | None = None,
) -> Candle:
    open_time = datetime(2026, 1, 1, tzinfo=UTC)
    return Candle(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=timeframe,
        open_time=open_time,
        close_time=close_time or open_time + timedelta(hours=1),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        quote_volume=quote_volume,
        trade_count=trade_count,
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


@pytest.mark.parametrize("timeframe", ["", "0h", "1w", "hourly"])
def test_unsupported_timeframes_are_rejected(timeframe: str) -> None:
    with pytest.raises(ValueError, match="timeframe"):
        make_candle(timeframe=timeframe)


def test_optional_quote_volume_and_trade_count_are_validated() -> None:
    candle = make_candle(quote_volume=1000.0, trade_count=42)
    assert candle.quote_volume == 1000.0
    assert candle.trade_count == 42
    with pytest.raises(ValueError, match="quote_volume"):
        make_candle(quote_volume=-0.01)
    with pytest.raises(ValueError, match="trade_count"):
        make_candle(trade_count=-1)
    with pytest.raises(TypeError, match="quote_volume"):
        make_candle(quote_volume=cast(float, "1000"))
    with pytest.raises(TypeError, match="trade_count"):
        make_candle(trade_count=True)
