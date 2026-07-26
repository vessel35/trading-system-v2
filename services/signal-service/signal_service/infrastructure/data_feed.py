"""Supply finalized candles and market facts from read-only crypto_data queries."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from core_lib.candles import resample_confirmed_ohlcv
from core_lib.types import Candle

from signal_service.application import SignalDataFeed

_LOGGER = logging.getLogger(__name__)
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
        result = resample_confirmed_ohlcv(
            rows,
            symbol=symbol,
            exchange=self._exchange,
            timeframe=tf,
            boundary=boundary,
        )
        if result.dropped_bucket_count:
            self._dropped_bucket_count += result.dropped_bucket_count
            _LOGGER.warning(
                "discarded %d incomplete OHLCV bucket(s) for %s %s through %s",
                result.dropped_bucket_count,
                symbol,
                tf,
                boundary.isoformat(),
            )
        return list(result.candles)

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
