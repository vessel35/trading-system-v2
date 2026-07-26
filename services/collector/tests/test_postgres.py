"""SQL contract tests without opening a PostgreSQL connection."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from collector_service.domain import Candle, Symbol
from collector_service.infrastructure.postgres import (
    ConfigSymbolRepository,
    ConnectionProvider,
    DatabaseConnection,
    PostgresOhlcvRepository,
    QueryResult,
    TableName,
)
from psycopg import sql


class FakeResult:
    def __init__(self, rows: list[Sequence[object]]) -> None:
        self.rows = rows

    def fetchone(self) -> Sequence[object] | None:
        return self.rows[0] if self.rows else None

    def fetchall(self) -> list[Sequence[object]]:
        return self.rows


class FakeConnection:
    def __init__(self, rows: list[Sequence[object]] | None = None) -> None:
        self.rows = rows or []
        self.executed: list[tuple[object, Sequence[object]]] = []

    def execute(
        self,
        query: object,
        params: Sequence[object] = (),
    ) -> QueryResult:
        self.executed.append((query, params))
        return FakeResult(self.rows)


def provider(connection: FakeConnection) -> ConnectionProvider:
    @contextmanager
    def provide() -> Iterator[DatabaseConnection]:
        yield cast(DatabaseConnection, connection)

    return provide


def render(query: object) -> str:
    return cast(sql.Composable, query).as_string()


def one_candle(*, close: str = "100") -> Candle:
    return Candle(
        symbol="ETH/USDT:USDT",
        exchange="binance",
        timeframe="1m",
        open_time=datetime(2026, 7, 26, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal(close),
        volume=Decimal("12.5"),
        quote_volume=Decimal("1250"),
        trade_count=42,
    )


def test_batch_sql_has_exact_idempotency_key_and_updates_all_payload_fields() -> None:
    connection = FakeConnection()
    repository = PostgresOhlcvRepository(
        provider(connection),
        table=TableName("collector_test", "ohlcv_futures"),
    )

    repository.upsert_batch([one_candle()])

    assert len(connection.executed) == 1
    query, params = connection.executed[0]
    statement = " ".join(render(query).split())
    assert 'INSERT INTO "collector_test"."ohlcv_futures"' in statement
    assert "ON CONFLICT (time, symbol, exchange, timeframe)" in statement
    for field in (
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "ingest_time",
    ):
        assert f"{field} =" in statement
    assert len(params) == 11
    assert all(not isinstance(value, float) for value in params)


def test_config_query_reads_only_active_exchange_rows_and_optional_selector() -> None:
    connection = FakeConnection([("ETH/USDT:USDT", "binance")])
    repository = ConfigSymbolRepository(
        provider(connection),
        table=TableName("collector_test", "symbols"),
    )

    result = repository.active_symbols(
        exchange="binance",
        symbol="ETH/USDT:USDT",
    )

    assert result == [Symbol("ETH/USDT:USDT", "binance")]
    query, params = connection.executed[0]
    statement = " ".join(render(query).split())
    assert 'FROM "collector_test"."symbols"' in statement
    assert "is_active = TRUE" in statement
    assert "exchange = %s" in statement
    assert "symbol = %s" in statement
    assert "LIMIT 2" in statement
    assert params == ["binance", "ETH/USDT:USDT"]


def test_empty_batch_executes_no_sql() -> None:
    connection = FakeConnection()
    repository = PostgresOhlcvRepository(provider(connection))
    repository.upsert_batch([])
    assert connection.executed == []
