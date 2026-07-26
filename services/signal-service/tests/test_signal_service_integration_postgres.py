"""Opt-in sink check against an explicitly disposable local PostgreSQL schema."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import psycopg
import pytest
from core_lib.types import Candle, MarketType, PositionSide, SignalType, TradingSignal
from psycopg.conninfo import conninfo_to_dict
from signal_service.domain import PersistedSignal, SignalIntent, SignalMode
from signal_service.infrastructure import PostgresSignalSink, WriteConnection

pytestmark = pytest.mark.integration


def _dsn() -> str:
    if os.environ.get("SIGNAL_SERVICE_DISPOSABLE_TEST") != "1":
        pytest.skip("set SIGNAL_SERVICE_DISPOSABLE_TEST=1 for a disposable local database")
    dsn = os.environ.get("SIGNAL_SERVICE_TEST_DSN")
    if dsn is None:
        pytest.skip("SIGNAL_SERVICE_TEST_DSN is not set")
    values = conninfo_to_dict(dsn)
    dbname_value = values.get("dbname")
    host_value = values.get("host")
    if not isinstance(dbname_value, str) or not isinstance(host_value, str):
        raise RuntimeError("integration DSN must contain string dbname and host values")
    dbname = dbname_value
    host = host_value
    if not dbname.endswith("_test"):
        raise RuntimeError("integration database name must end in _test")
    if host not in {"localhost", "127.0.0.1", "::1"} and not host.startswith("/"):
        raise RuntimeError("integration database must use a local host or Unix socket")
    return dsn


def _record() -> PersistedSignal:
    opened = datetime(2026, 1, 1, tzinfo=UTC)
    candle = Candle(
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="1h",
        open_time=opened,
        close_time=opened + timedelta(hours=1),
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1.0,
        quote_volume=None,
        trade_count=None,
    )
    signal = TradingSignal(
        symbol=candle.symbol,
        timestamp=candle.close_time,
        confidence=1.0,
        price=candle.close,
        stop_loss=95.0,
        take_profit=111.0,
        market_type=MarketType.FUTURES,
        leverage=1,
        reason="integration",
        metadata={"disposable": True},
    )
    return PersistedSignal(
        strategy_id="probe",
        mode=SignalMode.PAPER,
        timeframe="1h",
        candle=candle,
        signal=signal,
        signal_type=SignalType.BUY,
        intent=SignalIntent.ENTER,
        side=PositionSide.LONG,
    )


def test_postgres_sink_in_a_disposable_schema() -> None:
    schema = f"signal_service_test_{uuid.uuid4().hex}"
    connection = psycopg.connect(_dsn(), autocommit=True)
    try:
        connection.execute(f'CREATE SCHEMA "{schema}"')
        connection.execute(
            f"""
            CREATE TABLE "{schema}".trading_signals (
                signal_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                source_mode TEXT NOT NULL,
                symbol TEXT NOT NULL,
                exchange TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                candle_open_time TIMESTAMPTZ NOT NULL,
                candle_close_time TIMESTAMPTZ NOT NULL,
                signal_time TIMESTAMPTZ NOT NULL,
                signal_type TEXT NOT NULL,
                derived_intent TEXT NOT NULL,
                derived_side TEXT,
                price NUMERIC NOT NULL,
                confidence NUMERIC NOT NULL,
                stop_loss NUMERIC,
                take_profit NUMERIC,
                market_type TEXT NOT NULL,
                leverage INTEGER,
                reason TEXT NOT NULL,
                metadata_json JSONB NOT NULL,
                UNIQUE (
                    strategy_id, source_mode, symbol, timeframe, candle_close_time
                )
            )
            """
        )
        sink = PostgresSignalSink(
            cast(WriteConnection, connection),
            schema=schema,
        )
        record = _record()
        assert sink.store(record) is True
        assert sink.store(record) is False
        count = connection.execute(f'SELECT count(*) FROM "{schema}".trading_signals').fetchone()
        assert count == (1,)
    finally:
        connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        connection.close()
