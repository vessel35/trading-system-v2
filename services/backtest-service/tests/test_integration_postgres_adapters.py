"""Read-only integration checks against the local development PostgreSQL."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast

import psycopg
import pytest
from backtest_service.adapters.broker import BacktestBroker
from backtest_service.adapters.catalog_store import (
    BacktestCatalogStore,
    WriteConnection,
    normalized_config_hash,
)
from backtest_service.adapters.clock import BacktestClock
from backtest_service.adapters.cost_model import BacktestCostModel
from backtest_service.adapters.data_feed import BacktestDataFeed, ReadConnection
from backtest_service.adapters.evidence_sink import BacktestEvidenceSink
from backtest_service.adapters.strategy_registry import BacktestStrategyRegistry
from backtest_service.config import RunConfig
from backtest_service.engine import Engine
from core_lib.ports import DataFeed, StrategyRegistry
from core_lib.strategy import AdapterManager, InProcessStrategyRegistry
from core_lib.strategy.adaptees import STRATEGY_ID as VESSEL_STRATEGY_ID
from core_lib.strategy.adaptees import VesselReference
from core_lib.types import Candle

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


class _GapFreeVesselFeed(DataFeed):
    """Serve one immutable, explicitly contiguous fixture without future exposure."""

    def __init__(self, candles: list[Candle]) -> None:
        self._candles = list(candles)

    def candles(self, symbol: str, tf: str, up_to: datetime) -> list[Candle]:
        assert symbol == "BTCUSDT"
        if tf == "1m":
            return []
        assert tf == "1h"
        return [candle for candle in self._candles if candle.close_time <= up_to]

    def funding(self, symbol: str, at: datetime) -> Decimal:
        del symbol, at
        raise LookupError("fixture deliberately uses the configured zero fallback")

    def mark_price(self, symbol: str, at: datetime) -> Decimal:
        del symbol, at
        return Decimal("100")


class _VesselCatalog(StrategyRegistry):
    def get(self, strategy_id: str) -> dict[str, object]:
        assert strategy_id == VESSEL_STRATEGY_ID
        return {
            "strategy_id": strategy_id,
            "class_name": VesselReference.__name__,
            "module_path": VesselReference.__module__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get(VESSEL_STRATEGY_ID)]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError("the E2E fixture catalog is read-only")


def _gap_free_vessel_candles() -> tuple[datetime, list[Candle]]:
    start = datetime(2026, 5, 1, 1, tzinfo=UTC)
    first = start - timedelta(hours=21)
    candles: list[Candle] = []
    for index in range(27):
        opened = first + timedelta(hours=index)
        open_price = 100.0 + index
        close = open_price + 0.5
        candles.append(
            Candle(
                symbol="BTCUSDT",
                exchange="binance",
                timeframe="1h",
                open_time=opened,
                close_time=opened + timedelta(hours=1),
                open=open_price,
                high=close + 0.25,
                low=open_price - 0.25,
                close=close,
                volume=100.0,
                quote_volume=10_000.0,
                trade_count=100,
            )
        )
    assert all(
        left.close_time == right.open_time
        for left, right in zip(candles, candles[1:], strict=False)
    )
    return start, candles


def _vessel_manager() -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    plugins.register(VESSEL_STRATEGY_ID, VesselReference)
    return AdapterManager(_VesselCatalog(), plugins)


def _vessel_config(start: datetime) -> RunConfig:
    return RunConfig(
        run_name="m10-vessel-e2e",
        strategy_id=VESSEL_STRATEGY_ID,
        params={},
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="1h",
        market_type="futures",
        data_source="gap-free-fixture",
        start=start,
        end=start + timedelta(hours=6),
        initial_capital=Decimal("10000"),
        risk_per_trade=0.01,
        seed=17,
        cost_values={
            "futures_taker_fee_rate": Decimal("0"),
            "futures_entry_slippage_rate": Decimal("0"),
            "exit_slippage_rate": Decimal("0"),
            "funding_fallback_rate": Decimal("0"),
        },
        profile_ref="vessel-reference-v1",
    )


def test_vessel_e2e_writes_evidence_and_real_catalog_with_hash_parity(
    tmp_path: Path,
) -> None:
    """Issue two real run ids while proving logical Evidence hash parity."""
    start, candles = _gap_free_vessel_candles()
    config = _vessel_config(start)
    schedule = [candles[0].open_time, *(candle.close_time for candle in candles)]
    prereg = {
        "hypothesis": "Vessel reference traverses the complete pipeline",
        "primary_metric": "pf",
        "success_threshold": 1.3,
        "failure_threshold": 1.0,
        "edge_distinguishable": True,
        "higher_is_better": True,
    }

    with _connect_writer("backtest_db") as connection:
        catalog = BacktestCatalogStore(cast(WriteConnection, connection))
        results = []
        for label in ("first", "second"):
            costs = BacktestCostModel(config.cost_values)
            run_prereg = {
                **prereg,
                "hypothesis": (
                    prereg["hypothesis"]
                    if label == "first"
                    else "Same criteria with independently revised declaration prose"
                ),
            }
            result = Engine(
                _GapFreeVesselFeed(candles),
                BacktestBroker(costs),
                BacktestClock(schedule),
                costs,
                BacktestEvidenceSink(tmp_path / label),
                catalog,
                _vessel_manager(),
                prereg=run_prereg,
            ).run(config)
            results.append(result)

        rows = connection.execute(
            """
            SELECT run_id, status, resolved_indicators_json, config_hash, evidence_hash
            FROM public.backtest_run
            WHERE run_id = ANY(%s)
            ORDER BY run_seq
            """,
            ([result.run_id for result in results],),
        ).fetchall()

    first_result, second_result = results
    assert first_result.run_id != second_result.run_id
    assert first_result.evidence_hash == second_result.evidence_hash
    assert len(rows) == 2
    assert all(row[1] == "EVALUATED" for row in rows)
    assert all(len(cast(list[object], row[2])) == 3 for row in rows)
    assert rows[0][3] == rows[1][3]
    assert rows[0][4] == rows[1][4] == first_result.evidence_hash
    with sqlite3.connect(second_result.evidence_path) as evidence:
        detail = json.loads(
            evidence.execute(
                """
                SELECT detail_json
                FROM INTEGRITY_CHECK
                WHERE check_name = 'deterministic'
                """
            ).fetchone()[0]
        )
        assert detail["status"] == "matched"
        assert detail["comparison_run_id"] == first_result.run_id
    for result in results:
        with sqlite3.connect(result.evidence_path) as evidence:
            assert evidence.execute(
                "SELECT COUNT(*) FROM BACKTEST_RUN_LOCAL"
            ).fetchone() == (1,)
            assert evidence.execute("SELECT COUNT(*) FROM TRADE").fetchone() == (1,)


def test_vessel_engine_traverses_real_crypto_data_feed(
    tmp_path: Path,
) -> None:
    """Exercise the Engine through the bounded read-only PostgreSQL DataFeed."""
    start = datetime(2025, 6, 18, 21, tzinfo=UTC)
    end = start + timedelta(hours=6)
    config = RunConfig(
        run_name="m10-real-data-feed",
        strategy_id=VESSEL_STRATEGY_ID,
        params={},
        symbol="BTC/USDT:USDT",
        exchange="binance",
        timeframe="1h",
        market_type="futures",
        data_source="crypto_data.ohlcv_futures",
        start=start,
        end=end,
        initial_capital=Decimal("10000"),
        risk_per_trade=0.01,
        seed=17,
        cost_values={
            "futures_taker_fee_rate": Decimal("0"),
            "futures_entry_slippage_rate": Decimal("0"),
            "exit_slippage_rate": Decimal("0"),
            "funding_fallback_rate": Decimal("0"),
        },
        profile_ref="vessel-reference-v1",
    )
    prereg = {
        "hypothesis": "Vessel traverses the real bounded crypto_data adapter",
        "primary_metric": "pf",
        "success_threshold": 1.3,
        "failure_threshold": 1.0,
        "edge_distinguishable": True,
        "higher_is_better": True,
    }

    with (
        _connect("crypto_data") as crypto_connection,
        _connect_writer("backtest_db") as catalog_connection,
    ):
        feed = BacktestDataFeed(
            cast(ReadConnection, crypto_connection),
            exchange=config.exchange,
        )
        history = feed.candles(config.symbol, config.timeframe, config.end)
        evaluation = [
            candle
            for candle in history
            if candle.open_time >= start and candle.close_time <= end
        ]
        assert len(evaluation) == 6
        assert all(
            left.close_time == right.open_time
            for left, right in zip(evaluation, evaluation[1:], strict=False)
        )
        costs = BacktestCostModel(config.cost_values)
        result = Engine(
            feed,
            BacktestBroker(costs),
            BacktestClock(
                [history[0].open_time, *(candle.close_time for candle in history)]
            ),
            costs,
            BacktestEvidenceSink(tmp_path / "real-data-feed"),
            BacktestCatalogStore(cast(WriteConnection, catalog_connection)),
            _vessel_manager(),
            prereg=prereg,
        ).run(config)

    assert result.integrity_status == "passed"
    with sqlite3.connect(result.evidence_path) as evidence:
        source = evidence.execute(
            """
            SELECT source_ref, timeframe, row_count
            FROM SOURCE_DATA_SNAPSHOT
            WHERE source_kind = 'ohlcv' AND timeframe = '1h'
            """
        ).fetchone()
        assert source is not None
        assert source[:2] == ("crypto_data.ohlcv_futures", "1h")
        assert source[2] == len(history)
        assert len(history) >= 27
        assert evidence.execute(
            "SELECT COUNT(*) FROM PORTFOLIO_PNL"
        ).fetchone() == (6,)
