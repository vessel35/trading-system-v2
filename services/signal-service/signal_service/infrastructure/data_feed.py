"""Supply finalized candles and market facts from read-only crypto_data queries."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol, cast

from core_lib.types import Candle

from signal_service.application import SignalDataFeed

_LOGGER = logging.getLogger(__name__)
_TIMEFRAME_PATTERN = re.compile(r"^(?P<count>[1-9]\d*)(?P<unit>[mhd])$")
_TIMEFRAME_SECONDS = {"m": 60, "h": 3600, "d": 86400}
_MINUTE = timedelta(minutes=1)
_FUNDING_COLLECTION_WINDOW = timedelta(seconds=1)
_DERIVATIVE_SYMBOL = re.compile(r"^(?P<base>[A-Z0-9]+)/(?P<quote>[A-Z0-9]+)(?::[A-Z0-9]+)?$")

_CANDLES_SQL = """
SELECT time, open, high, low, close, volume, quote_volume, trade_count
FROM public.ohlcv_futures
WHERE symbol = %s
  AND exchange = %s
  AND timeframe = '1m'
  AND time < %s
ORDER BY time
"""
_CANDLES_AFTER_SQL = """
SELECT time, open, high, low, close, volume, quote_volume, trade_count
FROM public.ohlcv_futures
WHERE symbol = %s
  AND exchange = %s
  AND timeframe = '1m'
  AND time >= %s
  AND time < %s
ORDER BY time
"""
_FUNDING_SQL = """
SELECT time, funding_rate
FROM public.funding_rates
WHERE symbol = %s
  AND exchange = %s
  AND time >= %s
  AND time <= %s
ORDER BY time
LIMIT 1
"""
_MARK_PRICE_SQL = """
SELECT time, mark_price
FROM public.funding_rates
WHERE symbol = %s
  AND exchange = %s
  AND time >= %s
  AND time <= %s
ORDER BY time
LIMIT 1
"""


class QueryResult(Protocol):
    """The read surface shared by psycopg cursors and test doubles."""

    def fetchall(self) -> list[Sequence[object]]:
        """Return all selected rows."""

    def fetchone(self) -> Sequence[object] | None:
        """Return one selected row or no row."""


class ReadConnection(Protocol):
    """The parameterized SELECT-only connection surface."""

    def execute(
        self,
        query: str,
        params: tuple[object, ...],
    ) -> QueryResult:
        """Execute one read query."""


def _utc(value: datetime, *, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _timeframe_duration(timeframe: str) -> timedelta:
    match = _TIMEFRAME_PATTERN.fullmatch(timeframe)
    if match is None:
        raise ValueError(f"unsupported timeframe: {timeframe!r}")
    seconds = _TIMEFRAME_SECONDS[match.group("unit")] * int(match.group("count"))
    if seconds % 60 != 0:
        raise ValueError("signal candles must be a whole number of minutes")
    return timedelta(seconds=seconds)


def _bucket_start(value: datetime, duration: timedelta) -> datetime:
    seconds = int(duration.total_seconds())
    epoch_seconds = int(_utc(value, name="candle time").timestamp())
    return datetime.fromtimestamp(epoch_seconds - epoch_seconds % seconds, tz=UTC)


def _decimal(value: object, *, name: str) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be returned as Decimal")
    return value


def _funding_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    match = _DERIVATIVE_SYMBOL.fullmatch(normalized)
    if match is not None:
        return f"{match.group('base')}{match.group('quote')}"
    if normalized and normalized.isalnum():
        return normalized
    raise ValueError(f"unsupported crypto_data symbol format: {symbol!r}")


class CryptoDataFeed(SignalDataFeed):
    """Resample confirmed 1m source rows without writing to crypto_data."""

    def __init__(self, connection: ReadConnection, *, exchange: str = "binance") -> None:
        if not exchange:
            raise ValueError("exchange must not be empty")
        self._connection = connection
        self._exchange = exchange
        self._dropped_bucket_count = 0

    @property
    def dropped_bucket_count(self) -> int:
        """Return the number of incomplete buckets structurally excluded."""
        return self._dropped_bucket_count

    def candles(self, symbol: str, tf: str, up_to: datetime) -> list[Candle]:
        """Return only complete buckets whose close time is at most the boundary."""
        boundary = _utc(up_to, name="up_to")
        rows = self._connection.execute(
            _CANDLES_SQL,
            (symbol, self._exchange, boundary),
        ).fetchall()
        return self._resample(symbol, tf, boundary, rows)

    def candles_after(
        self,
        symbol: str,
        tf: str,
        after: datetime,
        up_to: datetime,
    ) -> list[Candle]:
        """Read only source rows at or after the last processed close time."""
        cursor = _utc(after, name="after")
        boundary = _utc(up_to, name="up_to")
        if cursor >= boundary:
            return []
        rows = self._connection.execute(
            _CANDLES_AFTER_SQL,
            (symbol, self._exchange, cursor, boundary),
        ).fetchall()
        return [
            candle
            for candle in self._resample(symbol, tf, boundary, rows)
            if candle.open_time >= cursor
        ]

    def _resample(
        self,
        symbol: str,
        tf: str,
        boundary: datetime,
        rows: list[Sequence[object]],
    ) -> list[Candle]:
        duration = _timeframe_duration(tf)
        if not rows:
            return []

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
        latest_complete_bucket = _bucket_start(boundary - duration, duration)
        if latest_complete_bucket < first_bucket:
            return []

        result: list[Candle] = []
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
            result.append(self._build_candle(symbol, tf, current, duration, ordered))
            current += duration

        if dropped:
            self._dropped_bucket_count += dropped
            _LOGGER.warning(
                "discarded %d incomplete OHLCV bucket(s) for %s %s through %s",
                dropped,
                symbol,
                tf,
                boundary.isoformat(),
            )
        return result

    def _build_candle(
        self,
        symbol: str,
        timeframe: str,
        open_time: datetime,
        duration: timedelta,
        rows: list[Sequence[object]],
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
            None
            if any(row[7] is None for row in rows)
            else sum(self._trade_count(row[7]) for row in rows)
        )
        return Candle(
            symbol=symbol,
            exchange=self._exchange,
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

    @staticmethod
    def _trade_count(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("trade_count must be int")
        return value

    def funding(self, symbol: str, at: datetime) -> Decimal:
        """Return the observed boundary rate through a SELECT-only query."""
        boundary = _utc(at, name="at")
        deadline = boundary + _FUNDING_COLLECTION_WINDOW
        row = self._connection.execute(
            _FUNDING_SQL,
            (_funding_symbol(symbol), self._exchange, boundary, deadline),
        ).fetchone()
        if row is None:
            raise LookupError(f"no measured funding rate for {symbol} at {boundary.isoformat()}")
        self._validate_observation_time(row, boundary, deadline, value_name="funding_rates.time")
        return _decimal(row[1], name="funding_rate")

    def mark_price(self, symbol: str, at: datetime) -> Decimal:
        """Return the mark paired with the observed boundary through SELECT only."""
        boundary = _utc(at, name="at")
        deadline = boundary + _FUNDING_COLLECTION_WINDOW
        row = self._connection.execute(
            _MARK_PRICE_SQL,
            (_funding_symbol(symbol), self._exchange, boundary, deadline),
        ).fetchone()
        if row is None or row[1] is None:
            raise LookupError(f"no measured mark price for {symbol} at {boundary.isoformat()}")
        self._validate_observation_time(row, boundary, deadline, value_name="funding_rates.time")
        return _decimal(row[1], name="mark_price")

    @staticmethod
    def _validate_observation_time(
        row: Sequence[object],
        boundary: datetime,
        deadline: datetime,
        *,
        value_name: str,
    ) -> None:
        if len(row) != 2:
            raise ValueError("funding_rates SELECT returned an unexpected row shape")
        observed_at = row[0]
        if not isinstance(observed_at, datetime):
            raise TypeError(f"{value_name} must be datetime")
        normalized_at = _utc(observed_at, name=value_name)
        if not boundary <= normalized_at <= deadline:
            raise ValueError("market observation falls outside the collection window")
