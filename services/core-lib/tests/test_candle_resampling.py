"""Lock the shared confirmed-candle aggregation contract."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from core_lib.candles import resample_confirmed_ohlcv


def _row(at: datetime, price: int) -> tuple[object, ...]:
    value = Decimal(price)
    return (
        at,
        value,
        value + 2,
        value - 1,
        value + 1,
        Decimal("1"),
        Decimal("10"),
        2,
    )


def test_resample_preserves_the_signal_service_candle_bytes() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    result = resample_confirmed_ohlcv(
        [_row(base + timedelta(minutes=index), 100 + index) for index in range(6)],
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="5m",
        boundary=base + timedelta(minutes=5),
    )

    payload = json.dumps(
        [asdict(candle) for candle in result.candles],
        default=lambda value: value.isoformat(),
        separators=(",", ":"),
    ).encode()

    assert payload == (
        b'[{"symbol":"BTCUSDT","exchange":"binance","timeframe":"5m",'
        b'"open_time":"2026-01-01T00:00:00+00:00",'
        b'"close_time":"2026-01-01T00:05:00+00:00","open":100.0,"high":106.0,'
        b'"low":99.0,"close":105.0,"volume":5.0,"quote_volume":50.0,"trade_count":10}]'
    )
    assert result.dropped_bucket_count == 0


def test_resample_reports_gaps_and_never_synthesizes_the_bucket() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [_row(base + timedelta(minutes=index), 100 + index) for index in range(5)]
    del rows[2]

    result = resample_confirmed_ohlcv(
        rows,
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="5m",
        boundary=base + timedelta(minutes=5),
    )

    assert result.candles == ()
    assert result.dropped_bucket_count == 1


def test_resample_excludes_the_unconfirmed_final_bucket() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    result = resample_confirmed_ohlcv(
        [_row(base + timedelta(minutes=index), 100 + index) for index in range(6)],
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="5m",
        boundary=base + timedelta(minutes=6),
    )

    assert len(result.candles) == 1
    assert result.candles[0].open_time == base
    assert result.dropped_bucket_count == 0


def test_any_whole_minute_timeframe_is_built_from_1m_rows() -> None:
    """``candles.resampled_timeframes``: a run timeframe needs no table of its own.

    Three minutes, five minutes, two hours, and one day are all regrouped from the same
    confirmed 1m rows, so a 5m run is served by the 1m data the collector stores.
    """
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for timeframe, minutes in (("3m", 3), ("5m", 5), ("2h", 120), ("1d", 1440)):
        rows = [_row(base + timedelta(minutes=index), 100 + index) for index in range(minutes)]
        result = resample_confirmed_ohlcv(
            rows,
            symbol="BTCUSDT",
            exchange="binance",
            timeframe=timeframe,
            boundary=base + timedelta(minutes=minutes),
        )
        assert len(result.candles) == 1, timeframe
        candle = result.candles[0]
        assert candle.timeframe == timeframe
        assert candle.open_time == base
        assert candle.close_time == base + timedelta(minutes=minutes)
        assert candle.open == 100.0 and candle.close == 100 + minutes
        assert result.dropped_bucket_count == 0
