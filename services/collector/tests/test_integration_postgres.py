"""Opt-in idempotency check against a disposable local PostgreSQL schema."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from collector_service.domain import Candle, Symbol
from collector_service.infrastructure.postgres import (
    ConfigSymbolRepository,
    PostgresOhlcvRepository,
    TableName,
    connection_provider,
)
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

pytestmark = pytest.mark.integration

_FORBIDDEN_DATABASES = {
    "backtest_db",
    "config_db",
    "crypto_data",
    "signal_db",
    "wallet_db",
}
_LOCAL_HOSTS = {"", "/tmp", "127.0.0.1", "::1", "localhost"}


def local_test_dsn() -> str:
    dsn = os.environ.get("COLLECTOR_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("COLLECTOR_TEST_DATABASE_URL is not set")
    info = conninfo_to_dict(dsn)
    host = info.get("host", "")
    database = info.get("dbname", "")
    if host not in _LOCAL_HOSTS:
        pytest.skip("collector integration database must be local")
    if not database or database in _FORBIDDEN_DATABASES:
        pytest.skip("collector integration database must be a dedicated non-production database")
    return dsn


def test_config_read_and_ohlcv_upsert_are_isolated_and_idempotent() -> None:
    dsn = local_test_dsn()
    schema = f"collector_test_{uuid4().hex}"
    schema_identifier = sql.Identifier(schema)
    with psycopg.connect(dsn) as setup:
        setup.execute(sql.SQL("CREATE SCHEMA {}").format(schema_identifier))
        setup.execute(
            sql.SQL(
                """
                CREATE TABLE {}.symbols (
                    symbol TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL
                )
                """
            ).format(schema_identifier)
        )
        setup.execute(
            sql.SQL(
                """
                CREATE TABLE {}.ohlcv_futures (
                    time TIMESTAMPTZ NOT NULL,
                    symbol VARCHAR(30) NOT NULL,
                    exchange VARCHAR(20) NOT NULL DEFAULT 'binance',
                    timeframe VARCHAR(10) NOT NULL,
                    open NUMERIC(20, 8),
                    high NUMERIC(20, 8),
                    low NUMERIC(20, 8),
                    close NUMERIC(20, 8),
                    volume NUMERIC(30, 8),
                    quote_volume NUMERIC(30, 8),
                    trade_count INTEGER,
                    ingest_time TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (time, symbol, exchange, timeframe)
                )
                """
            ).format(schema_identifier)
        )
        setup.execute(
            sql.SQL("INSERT INTO {}.symbols VALUES (%s, %s, TRUE)").format(schema_identifier),
            ("ETH/USDT:USDT", "binance"),
        )

    try:
        symbols = ConfigSymbolRepository(
            connection_provider(
                dsn,
                read_only=True,
                application_name="collector-disposable-config-test",
            ),
            table=TableName(schema, "symbols"),
        )
        assert symbols.active_symbols(exchange="binance", symbol=None) == [
            Symbol("ETH/USDT:USDT", "binance")
        ]

        repository = PostgresOhlcvRepository(
            connection_provider(
                dsn,
                read_only=False,
                application_name="collector-disposable-ohlcv-test",
            ),
            table=TableName(schema, "ohlcv_futures"),
        )
        original = Candle(
            symbol="ETH/USDT:USDT",
            exchange="binance",
            timeframe="1m",
            open_time=datetime(2026, 7, 26, tzinfo=UTC),
            open=Decimal("100"),
            high=Decimal("103"),
            low=Decimal("99"),
            close=Decimal("101"),
            volume=Decimal("12.5"),
            quote_volume=Decimal("1262.5"),
            trade_count=10,
        )
        repository.upsert_batch([original])
        repository.upsert_batch([replace(original, close=Decimal("102"), trade_count=11)])

        with psycopg.connect(dsn) as verification:
            verification_query = sql.SQL(
                "SELECT COUNT(*), MAX(close), MAX(trade_count) FROM {}.ohlcv_futures"
            ).format(schema_identifier)
            row = verification.execute(verification_query).fetchone()
        assert row == (1, Decimal("102.00000000"), 11)
    finally:
        with psycopg.connect(dsn, autocommit=True) as cleanup:
            cleanup.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(schema_identifier))
