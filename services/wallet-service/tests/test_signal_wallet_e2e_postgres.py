"""Opt-in signal_db -> paper fill -> wallet_db check on disposable local schemas."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast

import psycopg
import pytest
from core_lib.candles import resample_confirmed_ohlcv
from core_lib.types import MarketType, PositionSide, SignalType, TradingSignal
from psycopg import Connection
from psycopg.conninfo import conninfo_to_dict
from signal_service.domain import PersistedSignal, SignalIntent, SignalMode
from signal_service.infrastructure import PostgresSignalSink
from wallet_service.core import RiskPolicy
from wallet_service.infrastructure import ReadConnection, WriteConnection
from wallet_service.main import build_signal_db_paper_wallet

pytestmark = pytest.mark.integration

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SIGNAL_MIGRATION = (
    REPOSITORY_ROOT
    / "init-scripts"
    / "signal-service"
    / "20260726"
    / "01-create-trading-signals.sql"
)
WALLET_MIGRATIONS = tuple(
    sorted((REPOSITORY_ROOT / "init-scripts" / "wallet-service" / "20260726").glob("*.sql"))
)


def _dsn() -> str:
    if os.environ.get("WALLET_SERVICE_DISPOSABLE_TEST") != "1":
        pytest.skip("set WALLET_SERVICE_DISPOSABLE_TEST=1 for a disposable local database")
    dsn = os.environ.get("WALLET_SERVICE_TEST_DSN")
    if dsn is None:
        pytest.skip("WALLET_SERVICE_TEST_DSN is not set")
    values = conninfo_to_dict(dsn)
    dbname = values.get("dbname")
    host = values.get("host")
    if not isinstance(dbname, str) or not isinstance(host, str):
        raise RuntimeError("integration DSN must contain string dbname and host values")
    if not dbname.endswith("_test"):
        raise RuntimeError("integration database name must end in _test")
    if host not in {"localhost", "127.0.0.1", "::1"} and not host.startswith("/"):
        raise RuntimeError("integration database must use a local host or Unix socket")
    return dsn


def _migration_sql(path: Path, schema: str) -> str:
    source = path.read_text()
    sql = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("\\"))
    return sql.replace("public.", f'"{schema}".').replace(
        "SCHEMA public",
        f'SCHEMA "{schema}"',
    )


def _minute_row(at: datetime, price: int) -> tuple[object, ...]:
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


def _seed_crypto(
    connection: Connection[tuple[object, ...]],
    schema: str,
    base: datetime,
) -> dict[str, list[tuple[object, ...]]]:
    connection.execute(
        f"""
        CREATE TABLE "{schema}".ohlcv_futures (
            symbol VARCHAR(30) NOT NULL,
            exchange VARCHAR(20) NOT NULL,
            timeframe VARCHAR(10) NOT NULL,
            time TIMESTAMPTZ NOT NULL,
            open NUMERIC(20, 8) NOT NULL,
            high NUMERIC(20, 8) NOT NULL,
            low NUMERIC(20, 8) NOT NULL,
            close NUMERIC(20, 8) NOT NULL,
            volume NUMERIC(30, 8) NOT NULL,
            quote_volume NUMERIC(30, 8),
            trade_count INTEGER
        )
        """
    )
    rows_by_symbol = {
        "ETHUSDT": [
            _minute_row(base + timedelta(minutes=index), 2_000 + index) for index in range(120)
        ],
        "BTCUSDT": [
            _minute_row(base + timedelta(minutes=index), 100 + index) for index in range(120)
        ],
    }
    with connection.cursor() as cursor:
        cursor.executemany(
            f"""
            INSERT INTO "{schema}".ohlcv_futures (
                symbol, exchange, timeframe, time, open, high, low, close,
                volume, quote_volume, trade_count
            )
            VALUES (%s, 'binance', '1m', %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [(symbol, *row) for symbol, rows in rows_by_symbol.items() for row in rows],
        )
    return rows_by_symbol


def _persisted_signal(
    rows: list[tuple[object, ...]],
    base: datetime,
    *,
    symbol: str,
) -> PersistedSignal:
    decision = resample_confirmed_ohlcv(
        rows[:60],
        symbol=symbol,
        exchange="binance",
        timeframe="1h",
        boundary=base + timedelta(hours=1),
    ).candles[0]
    signal = TradingSignal(
        symbol=decision.symbol,
        timestamp=decision.close_time,
        confidence=0.9,
        price=decision.close,
        stop_loss=decision.close - 5.0,
        take_profit=decision.close + 10.0,
        market_type=MarketType.FUTURES,
        leverage=2,
        reason="disposable e2e",
        metadata={"source": "signal-service-e2e"},
    )
    return PersistedSignal(
        strategy_id=f"paper-e2e-{symbol.casefold()}",
        params={"fixture": True, "symbol": symbol},
        mode=SignalMode.PAPER,
        timeframe="1h",
        candle=decision,
        signal=signal,
        signal_type=SignalType.BUY,
        intent=SignalIntent.ENTER,
        side=PositionSide.LONG,
    )


def test_rejected_signal_does_not_block_the_following_paper_fill() -> None:
    dsn = _dsn()
    suffix = uuid.uuid4().hex
    signal_schema = f"signal_e2e_{suffix}"
    crypto_schema = f"crypto_e2e_{suffix}"
    wallet_schema = f"wallet_e2e_{suffix}"
    admin = psycopg.connect(dsn)
    signal_reader: Connection[tuple[object, ...]] | None = None
    crypto_reader: Connection[tuple[object, ...]] | None = None
    wallet: Connection[tuple[object, ...]] | None = None
    try:
        roles = {
            row[0]
            for row in admin.execute(
                """
                SELECT rolname
                FROM pg_roles
                WHERE rolname IN ('signal_reader', 'signal_writer', 'wallet_writer')
                """
            ).fetchall()
        }
        if roles != {"signal_reader", "signal_writer", "wallet_writer"}:
            pytest.skip("disposable v2 database must provision v2 signal and wallet roles")
        for schema in (signal_schema, crypto_schema, wallet_schema):
            admin.execute(f'CREATE SCHEMA "{schema}"')
        admin.commit()
        admin.execute(_migration_sql(SIGNAL_MIGRATION, signal_schema))
        for migration in WALLET_MIGRATIONS:
            admin.execute(_migration_sql(migration, wallet_schema))
        rows_by_symbol = _seed_crypto(
            admin,
            crypto_schema,
            datetime(2026, 1, 1, tzinfo=UTC),
        )
        admin.commit()

        sink = PostgresSignalSink(admin, schema=signal_schema)
        for symbol in ("ETHUSDT", "BTCUSDT"):
            assert sink.store(
                _persisted_signal(
                    rows_by_symbol[symbol],
                    datetime(2026, 1, 1, tzinfo=UTC),
                    symbol=symbol,
                )
            )

        signal_reader = psycopg.connect(dsn)
        signal_reader.read_only = True
        crypto_reader = psycopg.connect(dsn)
        crypto_reader.read_only = True
        wallet = psycopg.connect(dsn)
        with build_signal_db_paper_wallet(
            wallet_id="wallet-e2e",
            signal_reader=cast(ReadConnection, signal_reader),
            crypto_reader=cast(ReadConnection, crypto_reader),
            wallet_reader=cast(ReadConnection, wallet),
            wallet_writer=cast(WriteConnection, wallet),
            policy=RiskPolicy(frozenset({"BTCUSDT"})),
            initial_cash=Decimal("1000"),
            signal_schema=signal_schema,
            crypto_schema=crypto_schema,
            wallet_schema=wallet_schema,
        ) as service:
            assert service.run_once() is None
            execution = service.run_once()
            assert execution is not None
            assert execution.signal_id == "2"
            assert execution.symbol == "BTCUSDT"
            assert len(execution.fills) == 1
            assert execution.fills[0].timestamp >= datetime(
                2026,
                1,
                1,
                1,
                tzinfo=UTC,
            )
            assert service.run_once() is None

        assert signal_reader.closed
        assert crypto_reader.closed
        counts = wallet.execute(
            f"""
            SELECT
                (SELECT count(*) FROM "{wallet_schema}".wallet_signal_consumption),
                (SELECT count(*) FROM "{wallet_schema}".fills),
                (SELECT count(*) FROM "{wallet_schema}".positions),
                (SELECT count(*) FROM "{wallet_schema}".accounting_snapshots),
                (SELECT count(*) FROM "{wallet_schema}".wallet_accounts)
            """
        ).fetchone()
        assert counts == (2, 1, 1, 1, 1)
        receipts = wallet.execute(
            f"""
            SELECT signal_id, status
            FROM "{wallet_schema}".wallet_signal_consumption
            ORDER BY signal_id::bigint
            """
        ).fetchall()
        assert receipts == [("1", "rejected"), ("2", "filled")]
        assert admin.execute(
            f'SELECT count(*) FROM "{signal_schema}".trading_signals'
        ).fetchone() == (2,)
        assert admin.execute(
            f'SELECT count(*) FROM "{crypto_schema}".ohlcv_futures'
        ).fetchone() == (240,)
    finally:
        for connection in (signal_reader, crypto_reader, wallet):
            if connection is not None:
                connection.close()
        admin.rollback()
        for schema in (signal_schema, crypto_schema, wallet_schema):
            admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        admin.commit()
        admin.close()
