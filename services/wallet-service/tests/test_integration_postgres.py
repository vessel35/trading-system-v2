"""Opt-in transaction check against an explicitly disposable local wallet DB."""

from __future__ import annotations

import os
import uuid
from decimal import Decimal
from typing import cast

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict
from wallet_service.application import WalletRepository, WalletService
from wallet_service.core import RiskPolicy
from wallet_service.domain import WalletExecution
from wallet_service.infrastructure import (
    PaperBroker,
    PaperCostModel,
    PostgresWalletRepository,
    WriteConnection,
)

from tests.conftest import QueueDouble, paper_signal

pytestmark = pytest.mark.integration


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


_TABLES = """
CREATE TABLE "{schema}".wallet_accounts (
    wallet_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    cash_balance NUMERIC NOT NULL,
    total_equity NUMERIC NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE "{schema}".fills (
    fill_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    wallet_id TEXT NOT NULL,
    signal_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    order_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    position_side TEXT NOT NULL,
    reference_price NUMERIC NOT NULL,
    price NUMERIC NOT NULL,
    quantity NUMERIC NOT NULL,
    fee NUMERIC NOT NULL,
    slippage NUMERIC NOT NULL,
    liquidity TEXT NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL,
    reduce_only BOOLEAN NOT NULL,
    exit_reason TEXT,
    gap_filled BOOLEAN NOT NULL,
    qty_truncated BOOLEAN NOT NULL,
    UNIQUE (wallet_id, order_id),
    UNIQUE (wallet_id, signal_id, reduce_only)
);
CREATE TABLE "{schema}".positions (
    wallet_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity NUMERIC NOT NULL,
    average_price NUMERIC NOT NULL,
    total_cost NUMERIC NOT NULL,
    current_price NUMERIC NOT NULL,
    unrealized_pnl NUMERIC NOT NULL,
    market_type TEXT NOT NULL,
    leverage INTEGER NOT NULL,
    margin_type TEXT NOT NULL,
    margin NUMERIC NOT NULL,
    entry_price NUMERIC NOT NULL,
    mark_price NUMERIC NOT NULL,
    liquidation_price NUMERIC NOT NULL,
    funding_fee_total NUMERIC NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (wallet_id, symbol, side)
);
CREATE TABLE "{schema}".accounting_snapshots (
    snapshot_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    wallet_id TEXT NOT NULL,
    signal_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    cash_balance NUMERIC NOT NULL,
    position_value NUMERIC NOT NULL,
    total_equity NUMERIC NOT NULL,
    fee_total NUMERIC NOT NULL,
    slippage_total NUMERIC NOT NULL,
    UNIQUE (wallet_id, signal_id)
);
"""


class _Capture(WalletRepository):
    def __init__(self) -> None:
        self.value: WalletExecution | None = None

    def store(self, execution: WalletExecution) -> bool:
        self.value = execution
        return True


def test_repository_commits_to_disposable_wallet_schema_and_rejects_replay() -> None:
    schema = f"wallet_service_test_{uuid.uuid4().hex}"
    connection = psycopg.connect(_dsn())
    try:
        connection.execute(f'CREATE SCHEMA "{schema}"')
        connection.execute(_TABLES.format(schema=schema))
        connection.commit()

        capture = _Capture()
        service = WalletService(
            "wallet-1",
            QueueDouble(),
            PaperBroker(PaperCostModel()),
            capture,
            RiskPolicy(frozenset({"BTCUSDT"})),
            initial_cash=Decimal("1000"),
        )
        assert service.process(paper_signal()) is not None
        execution = capture.value
        assert execution is not None
        repository = PostgresWalletRepository(
            cast(WriteConnection, connection),
            schema=schema,
        )

        assert repository.store(execution) is True
        assert repository.store(execution) is False
        counts = connection.execute(
            f"""
            SELECT
                (SELECT count(*) FROM "{schema}".fills),
                (SELECT count(*) FROM "{schema}".positions),
                (SELECT count(*) FROM "{schema}".accounting_snapshots),
                (SELECT count(*) FROM "{schema}".wallet_accounts)
            """
        ).fetchone()
        assert counts == (1, 1, 1, 1)
    finally:
        connection.rollback()
        connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        connection.commit()
        connection.close()
