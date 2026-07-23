"""Read-only integration checks against the local development PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast

import psycopg
import pytest
from backtest_service.adapters.catalog_store import (
    BacktestCatalogStore,
    WriteConnection,
    normalized_config_hash,
)
from backtest_service.adapters.data_feed import BacktestDataFeed, ReadConnection
from backtest_service.adapters.strategy_registry import BacktestStrategyRegistry

pytestmark = pytest.mark.integration


def _env() -> dict[str, str]:
    path = Path(__file__).parents[3] / ".env"
    if not path.exists():
        pytest.skip("repository .env is unavailable")
    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    required = {"PGHOST", "PGPORT", "PGUSER", "PGPASSWORD"}
    if not required <= values.keys():
        pytest.skip("repository .env lacks PostgreSQL connection keys")
    return values


def _connect(database: str) -> psycopg.Connection[tuple[object, ...]]:
    values = _env()
    return psycopg.connect(
        host=values["PGHOST"],
        port=int(values["PGPORT"]),
        user=values["PGUSER"],
        password=values["PGPASSWORD"],
        dbname=database,
        options="-c default_transaction_read_only=on",
    )


def _connect_writer(database: str) -> psycopg.Connection[tuple[object, ...]]:
    values = _env()
    return psycopg.connect(
        host=values["PGHOST"],
        port=int(values["PGPORT"]),
        user=values["PGUSER"],
        password=values["PGPASSWORD"],
        dbname=database,
    )


def test_crypto_data_adapter_reads_only_contract_tables() -> None:
    with _connect("crypto_data") as connection:
        sample = connection.execute(
            """
            SELECT symbol, exchange, time
            FROM public.ohlcv_futures
            WHERE volume IS NOT NULL
            ORDER BY time
            LIMIT 1
            """
        ).fetchone()
        if sample is None:
            pytest.skip("crypto_data.ohlcv_futures is empty")
        symbol, exchange, open_time = sample
        assert isinstance(symbol, str)
        assert isinstance(exchange, str)
        assert isinstance(open_time, datetime)
        up_to = open_time + timedelta(minutes=1)
        feed = BacktestDataFeed(
            cast(ReadConnection, connection),
            exchange=exchange,
        )
        candles = feed.candles(symbol, "1m", up_to)
        assert candles
        assert all(candle.close_time <= up_to for candle in candles)

        funding_sample = connection.execute(
            """
            SELECT symbol, exchange, time
            FROM public.funding_rates
            WHERE mark_price IS NOT NULL
            ORDER BY time
            LIMIT 1
            """
        ).fetchone()
        if funding_sample is not None:
            funding_symbol, funding_exchange, at = funding_sample
            assert isinstance(funding_symbol, str)
            assert isinstance(funding_exchange, str)
            assert isinstance(at, datetime)
            funding_feed = BacktestDataFeed(
                cast(ReadConnection, connection),
                exchange=funding_exchange,
            )
            assert funding_feed.funding(funding_symbol, at).is_finite()
            assert funding_feed.mark_price(funding_symbol, at).is_finite()


def test_signal_registry_adapter_reads_only_registry_table() -> None:
    with _connect("signal_db") as connection:
        registry = BacktestStrategyRegistry(cast(ReadConnection, connection))
        entries = registry.list()
        assert all("strategy_id" in entry for entry in entries)
        if entries:
            strategy_id = entries[0]["strategy_id"]
            assert isinstance(strategy_id, str)
            assert registry.get(strategy_id)["strategy_id"] == strategy_id


def test_catalog_issues_run_id_then_records_prereg_and_evaluated_metadata() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    run_meta: dict[str, object] = {
        "run_name": "m9-integration",
        "strategy_id": "m9-fixture",
        "strategy_name": "M9Fixture",
        "strategy_version": "1.0.0",
        "params_json": {},
        "resolved_indicators_json": [
            {"name": "EMA", "params": {"period": 9}, "version": "1.0.0"}
        ],
        "params_schema_version": "1.0.0",
        "symbol": "BTCUSDT",
        "exchange": "binance",
        "timeframe": "1h",
        "market_type": "FUTURES",
        "period_start": start,
        "period_end": start + timedelta(days=1),
        "warmup_start": None,
        "warmup_candles": 0,
        "data_source": "integration-fixture",
        "indicator_mode": "auto",
        "trigger_feed": "tf_candle",
        "fill_timing": "next_bar",
        "initial_capital": Decimal("10000"),
        "sizing_method": "risk_based",
        "risk_per_trade": Decimal("0.01"),
        "position_size_pct": None,
        "framework_compliant": True,
        "cost_values_json": {},
        "seed": 0,
        "engine_version": "1.0.0",
        "core_lib_version": "0.1.0",
        "config_hash": "",
        "profile_ref": "m9-profile",
        "strategy_profile_json": {"family": "fixture"},
        "envelope_status_declared": "provisional",
        "sweep_id": None,
        "fold_label": "integration",
    }
    run_meta["config_hash"] = normalized_config_hash(run_meta)
    with _connect_writer("backtest_db") as connection:
        catalog = BacktestCatalogStore(cast(WriteConnection, connection))
        run_id = catalog.register(run_meta)
        reference = catalog.determinism_reference(
            run_id,
            str(run_meta["config_hash"]),
        )
        assert reference.catalog_config_matches is True
        catalog.save_prereg(
            {
                "run_id": run_id,
                "hypothesis": "M9 catalog adapter integration",
                "primary_metric": "pf",
                "success_criteria_json": {"threshold": 1.3},
                "failure_criteria_json": {"threshold": 1.0},
                "profile_update_declared": False,
                "declared_by": "pytest-integration",
                "declared_at": start,
            }
        )
        catalog.upsert_summary(
            {
                "run_id": run_id,
                "trade_count": 0,
                "win_count": 0,
                "loss_count": 0,
                "r_excluded_count": 0,
                "initial_capital": Decimal("10000"),
                "integrity_passed": True,
                "integrity_status": "passed",
                "decision_route": "retest",
                "evidence_hash": "b" * 64,
            }
        )
        row = connection.execute(
            """
            SELECT r.run_seq, r.run_id, r.status, r.evidence_path,
                   r.evidence_hash, p.locked_at IS NOT NULL,
                   s.integrity_status
            FROM public.backtest_run AS r
            JOIN public.backtest_prereg AS p ON p.run_id = r.run_id
            JOIN public.backtest_summary AS s ON s.run_id = r.run_id
            WHERE r.run_id = %s
            """,
            (run_id,),
        ).fetchone()

    assert row is not None
    run_seq, stored_id, status, path, evidence_hash, locked, integrity = row
    assert isinstance(run_seq, int)
    assert run_id == stored_id
    assert f"_{run_seq:0{max(6, len(str(run_seq)))}}" in run_id
    assert status == "EVALUATED"
    assert path == f"{run_id}.sqlite"
    assert evidence_hash == "b" * 64
    assert locked is True
    assert integrity == "passed"
