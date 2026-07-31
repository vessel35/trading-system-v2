"""Shared fixtures for the catalog-mutating web-api tests.

These tests need a run they are allowed to change and to delete. Borrowing a
real catalog row would both mutate the operator's data and make the suite
depend on what happens to be stored, so each test creates its own disposable
run with a stand-in Evidence artifact and removes it afterwards.
"""

from collections.abc import Callable, Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from web_api.database import connect_catalog, connect_catalog_writer, get_settings
from web_api.main import app

_INSERT_DISPOSABLE_RUN = """
WITH issued AS (
    SELECT
        nextval('public.backtest_run_seq') AS run_seq,
        to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYYMMDD') AS utc_day
),
named AS (
    SELECT
        run_seq,
        'BT_' || utc_day || '_'
        || lpad(run_seq::text, greatest(6, length(run_seq::text)), '0')
        || '_' || %s AS run_id
    FROM issued
)
INSERT INTO public.backtest_run (
    run_id, run_seq, run_name, status, strategy_id, strategy_name, strategy_version,
    params_schema_version, symbol, exchange, timeframe, period_start, period_end,
    data_source, initial_capital, risk_per_trade, engine_version, core_lib_version,
    config_hash, evidence_path
)
SELECT
    named.run_id, named.run_seq, %s, 'EVALUATED', 'disposable-fixture',
    'DisposableFixture', '1.0.0', '1.0.0', 'BTC/USDT:USDT', 'binance', '1h',
    TIMESTAMPTZ '2025-01-01 00:00:00+00', TIMESTAMPTZ '2025-01-02 00:00:00+00',
    'crypto_data.ohlcv_futures', 10000, 0.0100, 'test', 'test', repeat('0', 64),
    named.run_id || '.sqlite'
FROM named
RETURNING run_id
"""


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def catalog_available() -> None:
    """Skip when no catalog is reachable, for tests that need a real answer.

    Without a database every catalog endpoint answers 503, so a test asserting
    404 or 400 would fail for a reason that has nothing to do with the code.
    Continuous integration deliberately runs without one.
    """

    try:
        with connect_catalog() as connection:
            connection.execute("SELECT 1").fetchone()
    except (OSError, RuntimeError, psycopg.Error) as exc:
        pytest.skip(f"development backtest_db is unavailable: {type(exc).__name__}")


@pytest.fixture
def disposable_run() -> Iterator[tuple[str, Path]]:
    """Create one run of our own with a stand-in artifact, and clean up either way."""

    run_name = "disposable-fixture"
    try:
        with connect_catalog_writer() as connection:
            row = connection.execute(
                _INSERT_DISPOSABLE_RUN,
                (run_name, run_name),
            ).fetchone()
            assert row is not None
            run_id = str(row["run_id"])
            connection.execute(
                """
                INSERT INTO public.backtest_tag (run_id, tag_type, tag_value)
                VALUES (%s, 'purpose', 'disposable-fixture')
                """,
                (run_id,),
            )
            connection.commit()
    # Only an unreachable database is a skip; a rejected row is a real failure.
    except (OSError, RuntimeError, psycopg.OperationalError) as exc:
        pytest.skip(f"development backtest_db is unavailable: {type(exc).__name__}")

    artifact = get_settings().evidence_root / f"{run_id}.sqlite"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"SQLite format 3\x00 stand-in artifact")
    Path(f"{artifact}-wal").write_bytes(b"write-ahead sidecar")
    try:
        yield run_id, artifact
    finally:
        for leftover in (artifact, Path(f"{artifact}-wal"), Path(f"{artifact}-shm")):
            leftover.unlink(missing_ok=True)
        with connect_catalog_writer() as connection:
            connection.execute(
                "DELETE FROM public.backtest_run WHERE run_id = %s",
                (run_id,),
            )
            connection.commit()


@pytest.fixture
def tag_count() -> Callable[[str], int]:
    """Return a reader for how many tag rows still point at one run."""

    def count(run_id: str) -> int:
        with connect_catalog_writer() as connection:
            row = connection.execute(
                "SELECT count(*) AS total FROM public.backtest_tag WHERE run_id = %s",
                (run_id,),
            ).fetchone()
        assert row is not None
        return int(row["total"])

    return count
