"""Verify that future and unfinalized candles cannot enter calculations."""

from datetime import UTC, datetime, timedelta

import pytest
from core_lib.indicators.contracts import (
    UnfinalizedCandleError,
    assert_finalized,
    drop_unfinalized,
)
from core_lib.types import Candle


def make_candle(index: int) -> Candle:
    open_time = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=index)
    price = 100.0 + index
    return Candle(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe="1h",
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open=price,
        high=price + 1.0,
        low=price - 1.0,
        close=price + 0.5,
        volume=10.0,
        quote_volume=None,
        trade_count=None,
    )


def test_candle_is_finalized_at_or_before_decision_time() -> None:
    candle = make_candle(0)
    assert_finalized(candle, candle.close_time)
    with pytest.raises(UnfinalizedCandleError, match="after decision time"):
        assert_finalized(candle, candle.close_time - timedelta(microseconds=1))


def test_drop_unfinalized_removes_the_open_tail() -> None:
    candles = [make_candle(index) for index in range(3)]
    decision_time = candles[1].close_time
    assert drop_unfinalized(candles, decision_time) == candles[:2]
