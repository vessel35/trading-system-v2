"""Pure aggregation of confirmed one-minute database rows into strategy candles."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

from core_lib.types import Candle

_TIMEFRAME_PATTERN = re.compile(r"^(?P<count>[1-9]\d*)(?P<unit>[mhd])$")
_TIMEFRAME_SECONDS = {"m": 60, "h": 3600, "d": 86400}
_MINUTE = timedelta(minutes=1)


@dataclass(frozen=True, slots=True)
class ResampledCandles:
    """Return finalized candles together with the number of incomplete buckets."""

    candles: tuple[Candle, ...]
    dropped_bucket_count: int


def timeframe_duration(timeframe: str) -> timedelta:
    """Return a supported candle duration that is an exact number of minutes."""
    match = _TIMEFRAME_PATTERN.fullmatch(timeframe)
    if match is None:
        raise ValueError(f"unsupported timeframe: {timeframe!r}")
    seconds = _TIMEFRAME_SECONDS[match.group("unit")] * int(match.group("count"))
    if seconds % 60 != 0:
        raise ValueError("signal candles must be a whole number of minutes")
    return timedelta(seconds=seconds)


def resample_confirmed_ohlcv(
    rows: Sequence[Sequence[object]],
    *,
    symbol: str,
    exchange: str,
    timeframe: str,
    boundary: datetime,
) -> ResampledCandles:
    """Aggregate exact 1m buckets and report, rather than synthesize, every gap."""
    normalized_boundary = _utc(boundary, name="boundary")
    duration = timeframe_duration(timeframe)
    if not rows:
        return ResampledCandles((), 0)

    grouped: dict[datetime, dict[datetime, Sequence[object]]] = {}
    for row in rows:
        if len(row) != 8:
            raise ValueError("ohlcv_futures SELECT returned an unexpected row shape")
        open_time = row[0]
        if not isinstance(open_time, datetime):
            raise TypeError("ohlcv_futures.time must be datetime")
        for index, name in (
            (1, "open"),
            (2, "high"),
            (3, "low"),
            (4, "close"),
            (5, "volume"),
        ):
            _decimal(row[index], name=name)
        normalized_time = _utc(open_time, name="ohlcv_futures.time")
        group = grouped.setdefault(_bucket_start(normalized_time, duration), {})
        if normalized_time in group:
            raise ValueError("duplicate 1m source candle")
        group[normalized_time] = row

    first_bucket = min(grouped)
    latest_complete_bucket = _bucket_start(normalized_boundary - duration, duration)
    if latest_complete_bucket < first_bucket:
        return ResampledCandles((), 0)

    candles: list[Candle] = []
    dropped = 0
    expected_count = int(duration / _MINUTE)
    current = first_bucket
    while current <= latest_complete_bucket:
        bucket = grouped.get(current, {})
        expected_times = {current + index * _MINUTE for index in range(expected_count)}
        if set(bucket) != expected_times:
            dropped += 1
            current += duration
            continue
        ordered = [bucket[at] for at in sorted(bucket)]
        candles.append(
            _build_candle(
                rows=ordered,
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe,
                open_time=current,
                duration=duration,
            )
        )
        current += duration

    return ResampledCandles(tuple(candles), dropped)


def _utc(value: datetime, *, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _bucket_start(value: datetime, duration: timedelta) -> datetime:
    seconds = int(duration.total_seconds())
    epoch_seconds = int(_utc(value, name="candle time").timestamp())
    return datetime.fromtimestamp(epoch_seconds - epoch_seconds % seconds, tz=UTC)


def _decimal(value: object, *, name: str) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be returned as Decimal")
    return value


def _trade_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("trade_count must be int")
    return value


def _build_candle(
    *,
    rows: list[Sequence[object]],
    symbol: str,
    exchange: str,
    timeframe: str,
    open_time: datetime,
    duration: timedelta,
) -> Candle:
    opens = [cast(Decimal, row[1]) for row in rows]
    highs = [cast(Decimal, row[2]) for row in rows]
    lows = [cast(Decimal, row[3]) for row in rows]
    closes = [cast(Decimal, row[4]) for row in rows]
    volumes = [cast(Decimal, row[5]) for row in rows]
    quote_volume = (
        None
        if any(row[6] is None for row in rows)
        else float(sum((_decimal(row[6], name="quote_volume") for row in rows), Decimal(0)))
    )
    trade_count = (
        None if any(row[7] is None for row in rows) else sum(_trade_count(row[7]) for row in rows)
    )
    return Candle(
        symbol=symbol,
        exchange=exchange,
        timeframe=timeframe,
        open_time=open_time,
        close_time=open_time + duration,
        open=float(opens[0]),
        high=float(max(highs)),
        low=float(min(lows)),
        close=float(closes[-1]),
        volume=float(sum(volumes, Decimal(0))),
        quote_volume=quote_volume,
        trade_count=trade_count,
    )


__all__ = ["ResampledCandles", "resample_confirmed_ohlcv", "timeframe_duration"]
