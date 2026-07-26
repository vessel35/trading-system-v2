"""Psycopg 3 adapters for config reads and idempotent futures writes."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import datetime
from itertools import chain
from typing import Protocol, cast

import psycopg
from psycopg import sql

from collector_service.domain.models import Candle, FundingRate, Symbol

_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
_OHLCV_COLUMNS = 11
_FUNDING_COLUMNS = 5


class QueryResult(Protocol):
    """Small cursor surface shared by psycopg and unit-test doubles."""

    def fetchone(self) -> Sequence[object] | None:
        """Return one row."""

    def fetchall(self) -> list[Sequence[object]]:
        """Return all rows."""


class DatabaseConnection(Protocol):
    """Parameterized execution surface required by the repositories."""

    def execute(
        self,
        query: object,
        params: Sequence[object] = (),
    ) -> QueryResult:
        """Execute one SQL statement."""


ConnectionProvider = Callable[[], AbstractContextManager[DatabaseConnection]]


@dataclass(frozen=True, slots=True)
class TableName:
    """Validated identifier pair used to isolate integration-test tables."""

    schema: str
    table: str

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.schema) or not _IDENTIFIER.fullmatch(self.table):
            raise ValueError("schema and table must be simple PostgreSQL identifiers")

    def identifier(self) -> sql.Identifier:
        return sql.Identifier(self.schema, self.table)


_CONFIG_SYMBOLS_TABLE = TableName("public", "symbols")
_OHLCV_FUTURES_TABLE = TableName("public", "ohlcv_futures")
_FUNDING_RATES_TABLE = TableName("public", "funding_rates")


def connection_provider(
    dsn: str,
    *,
    read_only: bool,
    application_name: str,
) -> ConnectionProvider:
    """Create short-lived sessions, physically read-only for config_db access."""

    @contextmanager
    def connect() -> Iterator[DatabaseConnection]:
        if read_only:
            connection_context = psycopg.connect(
                dsn,
                connect_timeout=5,
                application_name=application_name,
                options="-c default_transaction_read_only=on",
            )
        else:
            connection_context = psycopg.connect(
                dsn,
                connect_timeout=5,
                application_name=application_name,
            )
        with connection_context as connection:
            yield cast(DatabaseConnection, connection)

    return connect


class ConfigSymbolRepository:
    """Read active symbols from config_db.symbols and nowhere else."""

    def __init__(
        self,
        connections: ConnectionProvider,
        *,
        table: TableName = _CONFIG_SYMBOLS_TABLE,
    ) -> None:
        self._connections = connections
        self._table = table

    def active_symbols(
        self,
        *,
        exchange: str,
        symbol: str | None,
    ) -> list[Symbol]:
        predicate: sql.Composable = sql.SQL("is_active = TRUE AND exchange = %s")
        params: list[object] = [exchange]
        if symbol is not None:
            predicate += sql.SQL(" AND symbol = %s")
            params.append(symbol)
        query = sql.SQL(
            """
            SELECT symbol, exchange
            FROM {}
            WHERE {}
            ORDER BY symbol
            LIMIT 2
            """
        ).format(self._table.identifier(), predicate)
        with self._connections() as connection:
            rows = connection.execute(query, params).fetchall()
        return [Symbol(value=cast(str, row[0]), exchange=cast(str, row[1])) for row in rows]


class PostgresOhlcvRepository:
    """Upsert confirmed candles into the 1m futures base table."""

    def __init__(
        self,
        connections: ConnectionProvider,
        *,
        table: TableName = _OHLCV_FUTURES_TABLE,
    ) -> None:
        self._connections = connections
        self._table = table

    def latest_open_time(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
    ) -> datetime | None:
        query = sql.SQL(
            """
            SELECT time
            FROM {}
            WHERE symbol = %s AND exchange = %s AND timeframe = %s
            ORDER BY time DESC
            LIMIT 1
            """
        ).format(self._table.identifier())
        with self._connections() as connection:
            row = connection.execute(query, (symbol, exchange, timeframe)).fetchone()
        if row is None:
            return None
        value = row[0]
        if not isinstance(value, datetime):
            raise TypeError("ohlcv_futures.time must be returned as datetime")
        return value

    def upsert_batch(self, candles: list[Candle]) -> None:
        if not candles:
            return
        if any(candle.timeframe != "1m" for candle in candles):
            raise ValueError("repository accepts only 1m candles")

        row_placeholder = (
            sql.SQL("(") + sql.SQL(", ").join([sql.Placeholder()] * _OHLCV_COLUMNS) + sql.SQL(")")
        )
        values_clause = sql.SQL(", ").join([row_placeholder] * len(candles))
        query = sql.SQL(
            """
            INSERT INTO {} (
                time, symbol, exchange, timeframe,
                open, high, low, close, volume, quote_volume, trade_count
            )
            VALUES {}
            ON CONFLICT (time, symbol, exchange, timeframe)
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                quote_volume = EXCLUDED.quote_volume,
                trade_count = EXCLUDED.trade_count,
                ingest_time = NOW()
            """
        ).format(self._table.identifier(), values_clause)
        rows = (
            (
                candle.open_time,
                candle.symbol,
                candle.exchange,
                candle.timeframe,
                candle.open,
                candle.high,
                candle.low,
                candle.close,
                candle.volume,
                candle.quote_volume,
                candle.trade_count,
            )
            for candle in candles
        )
        params = tuple(chain.from_iterable(rows))
        with self._connections() as connection:
            connection.execute(query, params)


class PostgresFundingRepository:
    """Upsert observed settlements into the funding source table."""

    def __init__(
        self,
        connections: ConnectionProvider,
        *,
        table: TableName = _FUNDING_RATES_TABLE,
    ) -> None:
        self._connections = connections
        self._table = table

    def upsert_batch(self, rates: list[FundingRate]) -> None:
        if not rates:
            return

        row_placeholder = (
            sql.SQL("(") + sql.SQL(", ").join([sql.Placeholder()] * _FUNDING_COLUMNS) + sql.SQL(")")
        )
        values_clause = sql.SQL(", ").join([row_placeholder] * len(rates))
        query = sql.SQL(
            """
            INSERT INTO {} (
                time, symbol, exchange, funding_rate, mark_price
            )
            VALUES {}
            ON CONFLICT (time, symbol, exchange)
            DO UPDATE SET
                funding_rate = EXCLUDED.funding_rate,
                mark_price = EXCLUDED.mark_price,
                created_at = NOW()
            """
        ).format(self._table.identifier(), values_clause)
        rows = (
            (
                rate.time,
                rate.symbol,
                rate.exchange,
                rate.funding_rate,
                rate.mark_price,
            )
            for rate in rates
        )
        params = tuple(chain.from_iterable(rows))
        with self._connections() as connection:
            connection.execute(query, params)
