"""Opt-in transaction check against an explicitly disposable local wallet DB."""

from __future__ import annotations

import os
import uuid
from decimal import Decimal
from pathlib import Path
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

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WALLET_MIGRATION_DIRECTORY = REPOSITORY_ROOT / "init-scripts" / "wallet-service" / "20260726"


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


def _migration_sql(schema: str) -> str:
    """Relocate the real psql migration into one disposable test schema."""
    source = "\n".join(
        path.read_text() for path in sorted(WALLET_MIGRATION_DIRECTORY.glob("*.sql"))
    )
    sql = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("\\"))
    return sql.replace("public.", f'"{schema}".').replace(
        "SCHEMA public",
        f'SCHEMA "{schema}"',
    )


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
        if (
            connection.execute("SELECT 1 FROM pg_roles WHERE rolname = 'wallet_writer'").fetchone()
            is None
        ):
            pytest.skip("disposable v2 database must provision wallet_writer")
        connection.execute(f'CREATE SCHEMA "{schema}"')
        connection.commit()
        connection.execute(_migration_sql(schema))

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
                (SELECT count(*) FROM "{schema}".wallet_accounts),
                (SELECT count(*) FROM "{schema}".wallet_signal_consumption)
            """
        ).fetchone()
        assert counts == (1, 1, 1, 1, 1)
        constraints = {
            row[0]
            for row in connection.execute(
                """
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_schema = %s
                  AND constraint_type = 'CHECK'
                """,
                (schema,),
            ).fetchall()
        }
        assert {
            "ck_wallet_accounts_paper_only",
            "ck_fills_paper_only",
            "ck_positions_paper_only",
            "ck_accounting_paper_only",
            "ck_accounting_identity",
            "ck_wallet_signal_consumption_paper_only",
        } <= constraints
        with pytest.raises(psycopg.errors.CheckViolation):
            connection.execute(
                f'UPDATE "{schema}".wallet_accounts SET mode = %s',
                ("not-paper",),
            )
        connection.rollback()
    finally:
        connection.rollback()
        connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        connection.commit()
        connection.close()
