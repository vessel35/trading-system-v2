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
