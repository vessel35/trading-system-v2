"""Supply bounded historical candles and funding from crypto_data."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol, cast

from core_lib.candles import resample_confirmed_ohlcv
from core_lib.ports import DataFeed
from core_lib.types import Candle

_LOGGER = logging.getLogger(__name__)
_MINUTE = timedelta(minutes=1)
# Exchange rates are fixed at the boundary; crypto_data may timestamp their
# collection a few milliseconds later. The coordinator-approved normalization
# window is deliberately capped at one second so no later funding event can be
# pulled into the current eight-hour boundary.
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
_CANDLES_SINCE_SQL = """
SELECT time, open, high, low, close, volume, quote_volume, trade_count
FROM public.ohlcv_futures
WHERE symbol = %s
  AND exchange = %s
  AND timeframe = '1m'
  AND time >= %s
  AND time < %s
ORDER BY time
"""
_SOURCE_CANDLES_SQL = """
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
    """The read surface shared by psycopg cursors and unit-test stubs."""

    def fetchall(self) -> list[Sequence[object]]:
        """Return all selected rows."""

    def fetchone(self) -> Sequence[object] | None:
        """Return one selected row or no row."""


class ReadConnection(Protocol):
    """The query-only connection surface used by input adapters."""

    def execute(
        self,
        query: str,
        params: tuple[object, ...],
    ) -> QueryResult:
        """Execute one parameterized SELECT."""


def _utc(value: datetime, *, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _decimal(value: object, *, name: str) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be returned as Decimal")
    return value


def _funding_symbol(symbol: str) -> str:
    """Validate the symbol and keep the form crypto_data stores.

    ``funding_rates`` and ``ohlcv_futures`` are written by the same v2 collector under
    one identifier, the CCXT symbol, so both tables are queried by the same value. An
    earlier revision folded ``BTC/USDT:USDT`` into ``BTCUSDT`` because the referenced v1
    database stored the exchange form; against a v2 database that mapping matches no row,
    every lookup misses, and the Engine silently settles on the fallback rate instead of
    measured funding.
    """
    normalized = symbol.strip().upper()
    if _DERIVATIVE_SYMBOL.fullmatch(normalized) or normalized.isalnum():
        return normalized
    raise ValueError(f"unsupported crypto_data symbol format: {symbol!r}")


class BacktestDataFeed(DataFeed):
    """Read only confirmed crypto_data facts available at a simulation boundary."""

    def __init__(self, connection: ReadConnection, *, exchange: str = "binance") -> None:
        if not exchange:
            raise ValueError("exchange must not be empty")
        self._connection = connection
        self._exchange = exchange
        self._dropped_bucket_count = 0
        self._funding_exact_count = 0
        self._funding_normalized_count = 0
        self._funding_missing_count = 0
        self._mark_exact_count = 0
        self._mark_normalized_count = 0
        self._mark_missing_count = 0
        self._history_floor: datetime | None = None
        self._source_cache: dict[
            tuple[str, datetime, datetime | None],
            tuple[Sequence[object], ...],
        ] = {}
        # Resampling a multi-year 1m series costs far more than the single query that
        # produced it, and the Engine asks for the same series more than once per run.
        self._candle_cache: dict[tuple[str, str, datetime, datetime | None], list[Candle]] = {}

    def limit_history(self, floor: datetime | None) -> None:
        """Bound source reads below, or release the bound when given ``None``.

        Without a floor every read starts at the oldest stored candle, so the cost of a
        run grows with the whole retained history rather than with the window it covers.
        Callers that know how much warm-up they need set the floor; caches keyed without
        it are dropped so no previously widened series is served under the new bound.
        """
        bounded = None if floor is None else _utc(floor, name="floor")
        if bounded == self._history_floor:
            return
        self._history_floor = bounded
        self._source_cache.clear()
        self._candle_cache.clear()

    @property
    def dropped_bucket_count(self) -> int:
        """Return the cumulative number of incomplete or invalid buckets dropped."""
        return self._dropped_bucket_count

    def funding_diagnostics(self) -> dict[str, int]:
        """Return cumulative funding and mark-price measurement quality counts."""
        return {
            "exact_count": self._funding_exact_count,
            "normalized_count": self._funding_normalized_count,
            "missing_count": self._funding_missing_count,
            "mark_exact_count": self._mark_exact_count,
            "mark_normalized_count": self._mark_normalized_count,
            "mark_missing_count": self._mark_missing_count,
        }

    def candles(self, symbol: str, tf: str, up_to: datetime) -> list[Candle]:
        """Resample 1m source rows and expose only buckets closed by ``up_to``."""
        boundary = _utc(up_to, name="up_to")
        floor = self._history_floor
        resampled = self._candle_cache.get((symbol, tf, boundary, floor))
        if resampled is not None:
            return list(resampled)
        source_key = (symbol, boundary, floor)
        rows = self._source_cache.get(source_key)
        if rows is None:
            rows = tuple(
                self._connection.execute(
                    _CANDLES_SQL if floor is None else _CANDLES_SINCE_SQL,
                    (symbol, self._exchange, boundary)
                    if floor is None
                    else (symbol, self._exchange, floor, boundary),
                ).fetchall()
            )
            self._source_cache[source_key] = rows
        if not rows:
            self._candle_cache[(symbol, tf, boundary, floor)] = []
            return []

        resampling = resample_confirmed_ohlcv(
            rows,
            symbol=symbol,
            exchange=self._exchange,
            timeframe=tf,
            boundary=boundary,
        )
        result = list(resampling.candles)
        dropped = resampling.dropped_bucket_count

        if dropped:
            self._dropped_bucket_count += dropped
            _LOGGER.warning(
                "discarded %d incomplete OHLCV bucket(s) for %s %s through %s",
                dropped,
                symbol,
                tf,
                boundary.isoformat(),
            )
        # Keeping the resampled series also keeps the dropped-bucket tally honest: the
        # same series is now counted once instead of once per repeated request.
        self._candle_cache[(symbol, tf, boundary, floor)] = result
        return list(result)

    def source_candles(
        self,
        symbol: str,
        range_start: datetime,
        range_end: datetime,
    ) -> tuple[Candle, ...]:
        """Query bounded 1m values independently for Evidence validation."""
        start = _utc(range_start, name="range_start")
        end = _utc(range_end, name="range_end")
        if start >= end:
            raise ValueError("source validation range must be positive")
        rows = self._connection.execute(
            _SOURCE_CANDLES_SQL,
            (symbol, self._exchange, start, end),
        ).fetchall()
        result: list[Candle] = []
        for row in rows:
            if len(row) != 8 or not isinstance(row[0], datetime):
                raise TypeError("ohlcv_futures source value query returned invalid rows")
            opened = _utc(row[0], name="ohlcv_futures.time")
            result.append(
                self._build_candle(
                    symbol,
                    "1m",
                    opened,
                    _MINUTE,
                    [row],
                )
            )
        if any(
            left.open_time >= right.open_time
            for left, right in zip(result, result[1:], strict=False)
        ):
            raise ValueError("1m origin timestamps must be strictly increasing")
        return tuple(result)

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
        """Return the boundary rate, normalizing only approved collection jitter."""
        boundary = _utc(at, name="at")
        deadline = boundary + _FUNDING_COLLECTION_WINDOW
        row = self._connection.execute(
            _FUNDING_SQL,
            (_funding_symbol(symbol), self._exchange, boundary, deadline),
        ).fetchone()
        if row is None:
            self._funding_missing_count += 1
            raise LookupError(f"no measured funding rate for {symbol} at {boundary.isoformat()}")
        observed_at = row[0]
        if not isinstance(observed_at, datetime):
            raise TypeError("funding_rates.time must be datetime")
        normalized_at = _utc(observed_at, name="funding_rates.time")
        if not boundary <= normalized_at <= deadline:
            raise ValueError("funding observation falls outside the collection window")
        if normalized_at == boundary:
            self._funding_exact_count += 1
        else:
            self._funding_normalized_count += 1
        return _decimal(row[1], name="funding_rate")

    def mark_price(self, symbol: str, at: datetime) -> Decimal:
        """Return the mark paired with the normalized funding boundary."""
        boundary = _utc(at, name="at")
        deadline = boundary + _FUNDING_COLLECTION_WINDOW
        row = self._connection.execute(
            _MARK_PRICE_SQL,
            (_funding_symbol(symbol), self._exchange, boundary, deadline),
        ).fetchone()
        if row is None or row[1] is None:
            self._mark_missing_count += 1
            raise LookupError(f"no measured mark price for {symbol} at {boundary.isoformat()}")
        observed_at = row[0]
        if not isinstance(observed_at, datetime):
            raise TypeError("funding_rates.time must be datetime")
        normalized_at = _utc(observed_at, name="funding_rates.time")
        if not boundary <= normalized_at <= deadline:
            raise ValueError("mark-price observation falls outside the collection window")
        if normalized_at == boundary:
            self._mark_exact_count += 1
        else:
            self._mark_normalized_count += 1
        return _decimal(row[1], name="mark_price")
