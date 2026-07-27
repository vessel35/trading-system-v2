"""SQL contract tests without opening a PostgreSQL connection."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from typing import Self, cast

import psycopg
import pytest
from collector_service.domain import Candle, FundingRate, Symbol
from collector_service.infrastructure.postgres import (
    ConfigSymbolRepository,
    ConnectionProvider,
    DatabaseConnection,
    PostgresAggregateRefresher,
    PostgresFundingRepository,
    PostgresOhlcvRepository,
    QueryResult,
    TableName,
    connection_provider,
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


class ConnectableFakeConnection(FakeConnection):
    def __init__(self) -> None:
        super().__init__()
        self.autocommit_assignments: list[bool] = []

    @property
    def autocommit(self) -> bool:
        return self.autocommit_assignments[-1] if self.autocommit_assignments else False

    @autocommit.setter
    def autocommit(self, value: bool) -> None:
        self.autocommit_assignments.append(value)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


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


def one_funding(*, rate: str = "0.0000875001") -> FundingRate:
    return FundingRate(
        symbol="ETH/USDT:USDT",
        exchange="binance",
        time=datetime(2026, 7, 26, tzinfo=UTC),
        funding_rate=Decimal(rate),
        mark_price=Decimal("3750.12345678"),
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


def test_funding_sql_uses_exact_key_and_decimal_parameters_without_quantizing() -> None:
    connection = FakeConnection()
    repository = PostgresFundingRepository(
        provider(connection),
        table=TableName("collector_test", "funding_rates"),
    )

    repository.upsert_batch([one_funding()])

    query, params = connection.executed[0]
    statement = " ".join(render(query).split())
    assert 'INSERT INTO "collector_test"."funding_rates"' in statement
    assert "ON CONFLICT (time, symbol, exchange)" in statement
    assert "funding_rate = EXCLUDED.funding_rate" in statement
    assert "mark_price = EXCLUDED.mark_price" in statement
    assert params[3] == Decimal("0.0000875001")
    assert params[4] == Decimal("3750.12345678")
    assert all(not isinstance(value, float) for value in params)


def test_empty_batch_executes_no_sql() -> None:
    connection = FakeConnection()
    PostgresOhlcvRepository(provider(connection)).upsert_batch([])
    PostgresFundingRepository(provider(connection)).upsert_batch([])
    assert connection.executed == []


def test_aggregate_refresh_calls_allowlisted_view_with_bound_range() -> None:
    connection = FakeConnection()
    repository = PostgresAggregateRefresher(provider(connection))
    start = datetime(2021, 1, 1, tzinfo=UTC)
    end = datetime(2022, 1, 1, tzinfo=UTC)

    repository.refresh_range("public.ohlcv_futures_1h", start, end)

    assert connection.executed == [
        (
            "CALL refresh_continuous_aggregate(%s, %s, %s)",
            ("public.ohlcv_futures_1h", start, end),
        )
    ]


def test_aggregate_refresh_rejects_non_allowlisted_view() -> None:
    connection = FakeConnection()

    with pytest.raises(ValueError, match="unsupported aggregate view"):
        PostgresAggregateRefresher(provider(connection)).refresh_range(
            "public.not_collector_owned",
            datetime(2021, 1, 1, tzinfo=UTC),
            datetime(2022, 1, 1, tzinfo=UTC),
        )

    assert connection.executed == []


@pytest.mark.parametrize(
    ("autocommit", "assignments"),
    [(False, []), (True, [True])],
)
def test_connection_provider_enables_autocommit_only_when_requested(
    monkeypatch: pytest.MonkeyPatch,
    autocommit: bool,
    assignments: list[bool],
) -> None:
    connection = ConnectableFakeConnection()
    connect_calls: list[tuple[str, dict[str, object]]] = []

    def fake_connect(dsn: str, **kwargs: object) -> ConnectableFakeConnection:
        connect_calls.append((dsn, kwargs))
        return connection

    monkeypatch.setattr(psycopg, "connect", fake_connect)
    connections = connection_provider(
        "postgresql://data",
        read_only=False,
        application_name="collector-aggregate-refresher",
        autocommit=autocommit,
    )

    with connections() as provided:
        assert provided is connection

    assert connection.autocommit_assignments == assignments
    assert connect_calls == [
        (
            "postgresql://data",
            {
                "connect_timeout": 5,
                "application_name": "collector-aggregate-refresher",
            },
        )
    ]
