"""Read-only integration checks against the local development PostgreSQL."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import ClassVar, cast

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
from backtest_service.engine import Engine, RunResult
from backtest_service.runner import FeedDecorator
from core_lib.ports import DataFeed, StrategyRegistry
from core_lib.strategy import (
    AdapterManager,
    FieldSpec,
    InProcessStrategyRegistry,
    ParameterSchema,
    ResolvedConfig,
    StrategyMetadata,
    StrategyProfile,
)
from core_lib.strategy.adaptees import STRATEGY_ID as VESSEL_STRATEGY_ID
from core_lib.strategy.adaptees import VesselReference
from core_lib.types import Candle, MarketType, Position, PositionSide, TradingSignal

pytestmark = pytest.mark.integration


@dataclass(frozen=True, slots=True)
class _RealDataRegressionCase:
    """One visible cell in the bounded real-data regression matrix."""

    case_id: str
    tier: str
    start: datetime
    end: datetime
    directions: tuple[str, ...]
    funding_rate_signs: tuple[str, ...]
    leverages: tuple[int, ...]
    contract: str


_MATRIX_START = datetime(2025, 7, 1, tzinfo=UTC)
# This is a 10-cell coverage matrix, not a Cartesian benchmark explosion.
# Short: baseline-3d and slippage-bearing reversal-3d.
# Long: window-3d, window-10d, funding-long-positive-30d, window-45d,
# slippage-bearing funding-exhaustion-135d, funding-short-negative-20h-39x,
# funding-short-negative-180d, and missing-data-330d.
_REAL_DATA_REGRESSION_MATRIX = (
    _RealDataRegressionCase(
        "baseline-3d",
        "short",
        _MATRIX_START,
        _MATRIX_START + timedelta(days=3),
        ("LONG", "SHORT"),
        ("positive",),
        (1,),
        "bounded feed, measured funding, fees, and catalog",
    ),
    _RealDataRegressionCase(
        "reversal-3d",
        "short",
        _MATRIX_START,
        _MATRIX_START + timedelta(days=3),
        ("LONG", "SHORT"),
        ("positive",),
        (3,),
        "real-price reversal with entry and exit slippage",
    ),
    _RealDataRegressionCase(
        "window-3d",
        "long",
        datetime(2025, 10, 1, tzinfo=UTC),
        datetime(2025, 10, 4, tzinfo=UTC),
        ("LONG",),
        ("positive",),
        (1,),
        "entry reservation window invariance",
    ),
    _RealDataRegressionCase(
        "window-10d",
        "long",
        datetime(2025, 10, 1, tzinfo=UTC),
        datetime(2025, 10, 11, tzinfo=UTC),
        ("LONG",),
        ("positive",),
        (1,),
        "entry reservation window invariance",
    ),
    _RealDataRegressionCase(
        "funding-long-positive-30d",
        "long",
        _MATRIX_START,
        _MATRIX_START + timedelta(days=30),
        ("LONG",),
        ("positive",),
        (1,),
        "positive-rate long debit",
    ),
    _RealDataRegressionCase(
        "window-45d",
        "long",
        datetime(2025, 10, 1, tzinfo=UTC),
        datetime(2025, 11, 15, tzinfo=UTC),
        ("LONG",),
        ("positive", "negative"),
        (1,),
        "entry reservation window invariance",
    ),
    _RealDataRegressionCase(
        "funding-exhaustion-135d",
        "long",
        datetime(2025, 6, 22, 14, tzinfo=UTC),
        datetime(2025, 11, 4, 10, tzinfo=UTC),
        ("LONG",),
        ("positive", "negative"),
        (39,),
        "measured funding exhaustion with entry and liquidation slippage",
    ),
    _RealDataRegressionCase(
        "funding-short-negative-20h-39x",
        "long",
        datetime(2025, 6, 22, 14, tzinfo=UTC),
        datetime(2025, 6, 23, 10, tzinfo=UTC),
        ("SHORT",),
        ("negative",),
        (39,),
        "negative measured funding at 39x short leverage",
    ),
    _RealDataRegressionCase(
        "funding-short-negative-180d",
        "long",
        _MATRIX_START,
        _MATRIX_START + timedelta(days=180),
        ("SHORT",),
        ("negative",),
        (1,),
        "negative-rate short debit",
    ),
    _RealDataRegressionCase(
        "missing-data-330d",
        "long",
        _MATRIX_START,
        _MATRIX_START + timedelta(days=330),
        ("LONG", "SHORT"),
        ("positive", "negative"),
        (1,),
        "declared gaps, DATA_GAP exits, and full Evidence",
    ),
)


def _matrix_case(case_id: str) -> _RealDataRegressionCase:
    matches = [case for case in _REAL_DATA_REGRESSION_MATRIX if case.case_id == case_id]
    if len(matches) != 1:
        raise AssertionError(f"real-data matrix case must be unique: {case_id}")
    return matches[0]


def _assert_matrix_axes(
    evidence: sqlite3.Connection,
    case: _RealDataRegressionCase,
) -> None:
    observed_directions = {
        row[0]
        for row in evidence.execute("SELECT DISTINCT position_side FROM EXECUTION").fetchall()
    }
    observed_signs = {
        "positive" if row[0] > 0 else "negative"
        for row in evidence.execute(
            "SELECT DISTINCT funding_rate FROM FUNDING_SETTLEMENT WHERE funding_rate <> 0"
        ).fetchall()
    }
    observed_leverages = {
        row[0] for row in evidence.execute("SELECT DISTINCT leverage FROM TRADE").fetchall()
    }
    assert set(case.directions) <= observed_directions
    assert set(case.funding_rate_signs) <= observed_signs
    assert set(case.leverages) <= observed_leverages


def test_real_data_regression_matrix_covers_every_contract_axis() -> None:
    assert len(_REAL_DATA_REGRESSION_MATRIX) == 10
    assert len({case.case_id for case in _REAL_DATA_REGRESSION_MATRIX}) == len(
        _REAL_DATA_REGRESSION_MATRIX
    )
    assert {case.tier for case in _REAL_DATA_REGRESSION_MATRIX} == {"short", "long"}
    assert {
        direction for case in _REAL_DATA_REGRESSION_MATRIX for direction in case.directions
    } == {"LONG", "SHORT"}
    assert {sign for case in _REAL_DATA_REGRESSION_MATRIX for sign in case.funding_rate_signs} == {
        "positive",
        "negative",
    }
    assert {leverage for case in _REAL_DATA_REGRESSION_MATRIX for leverage in case.leverages} == {
        1,
        3,
        39,
    }
    assert {(case.case_id, case.contract) for case in _REAL_DATA_REGRESSION_MATRIX} == {
        ("baseline-3d", "bounded feed, measured funding, fees, and catalog"),
        ("reversal-3d", "real-price reversal with entry and exit slippage"),
        ("window-3d", "entry reservation window invariance"),
        ("window-10d", "entry reservation window invariance"),
        ("funding-long-positive-30d", "positive-rate long debit"),
        ("window-45d", "entry reservation window invariance"),
        (
            "funding-exhaustion-135d",
            "measured funding exhaustion with entry and liquidation slippage",
        ),
        (
            "funding-short-negative-20h-39x",
            "negative measured funding at 39x short leverage",
        ),
        ("funding-short-negative-180d", "negative-rate short debit"),
        (
            "missing-data-330d",
            "declared gaps, DATA_GAP exits, and full Evidence",
        ),
    }


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


def test_crypto_data_funding_reads_ccxt_symbol_and_collection_jitter() -> None:
    boundary = datetime(2025, 7, 1, 8, tzinfo=UTC)
    with _connect("crypto_data") as connection:
        feed = BacktestDataFeed(
            cast(ReadConnection, connection),
            exchange="binance",
        )
        rate = feed.funding("BTC/USDT:USDT", boundary)
        mark = feed.mark_price("BTC/USDT:USDT", boundary)

    assert rate == Decimal("0.0000433400")
    assert mark.is_finite()
    assert feed.funding_diagnostics() == {
        "exact_count": 0,
        "normalized_count": 1,
        "missing_count": 0,
        "mark_exact_count": 0,
        "mark_normalized_count": 1,
        "mark_missing_count": 0,
    }


def test_signal_registry_adapter_reads_only_registry_table() -> None:
    with _connect("signal_db") as connection:
        registry = BacktestStrategyRegistry(cast(ReadConnection, connection))
        entry = registry.get(VESSEL_STRATEGY_ID)
        assert isinstance(registry, StrategyRegistry)
        assert entry["class_name"] == "VesselReference"
        assert entry["module_path"] == VesselReference.__module__
        assert entry["supported_timeframes"] == ["1h"]
        assert entry["min_history"] == 21
        assert entry["is_active"] is True
        assert entry["is_deprecated"] is False
        assert VESSEL_STRATEGY_ID in [row["strategy_id"] for row in registry.list()]


def test_catalog_issues_run_id_then_records_prereg_and_evaluated_metadata() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    run_meta: dict[str, object] = {
        "run_name": "m9-integration",
        "strategy_id": "m9-fixture",
        "strategy_name": "M9Fixture",
        "strategy_version": "1.0.0",
        "params_json": {},
        "resolved_indicators_json": [{"name": "EMA", "params": {"period": 9}, "version": "1.0.0"}],
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
        source_data_hash = hashlib.sha256(run_id.encode()).hexdigest()
        reference = catalog.determinism_reference(
            run_id,
            str(run_meta["config_hash"]),
            source_data_hash,
        )
        assert reference.catalog_config_matches is True
        assert reference.catalog_source_matches is True
        assert isinstance(reference.same_config_run_exists, bool)
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
        same_source_run_id = catalog.register(run_meta)
        same_source_reference = catalog.determinism_reference(
            same_source_run_id,
            str(run_meta["config_hash"]),
            source_data_hash,
        )
        assert same_source_reference.comparison_run_id == run_id
        assert same_source_reference.comparison_hash == "b" * 64
        assert same_source_reference.same_config_run_exists is True

        different_source_run_id = catalog.register(run_meta)
        different_source_hash = hashlib.sha256(different_source_run_id.encode()).hexdigest()
        different_source_reference = catalog.determinism_reference(
            different_source_run_id,
            str(run_meta["config_hash"]),
            different_source_hash,
        )
        assert different_source_reference.comparison_run_id is None
        assert different_source_reference.comparison_hash is None
        assert different_source_reference.same_config_run_exists is True
        for completed_run_id, completed_evidence_hash in (
            (same_source_run_id, "b" * 64),
            (different_source_run_id, "c" * 64),
        ):
            catalog.upsert_summary(
                {
                    "run_id": completed_run_id,
                    "trade_count": 0,
                    "win_count": 0,
                    "loss_count": 0,
                    "r_excluded_count": 0,
                    "initial_capital": Decimal("10000"),
                    "integrity_passed": True,
                    "integrity_status": "passed",
                    "decision_route": "retest",
                    "evidence_hash": completed_evidence_hash,
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


def _orphan_sweep_run_meta() -> dict[str, object]:
    """Build one minimal catalog run header for the orphan-sweep regression."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    run_meta: dict[str, object] = {
        "run_name": "orphan-sweep-guard",
        "strategy_id": "orphan-sweep-fixture",
        "strategy_name": "OrphanSweepFixture",
        "strategy_version": "1.0.0",
        "params_json": {},
        "resolved_indicators_json": [{"name": "EMA", "params": {"period": 9}, "version": "1.0.0"}],
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
        "profile_ref": "orphan-sweep-profile",
        "strategy_profile_json": {"family": "fixture"},
        "envelope_status_declared": "provisional",
        "sweep_id": None,
        "fold_label": "integration",
    }
    run_meta["config_hash"] = normalized_config_hash(run_meta)
    return run_meta


def _finalize_orphan_sweep_run(catalog: BacktestCatalogStore, run_id: str, hash_seed: str) -> None:
    """Finalize one orphan-sweep fixture run through the production summary path."""
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
            "evidence_hash": hashlib.sha256(f"{run_id}:{hash_seed}".encode()).hexdigest(),
        }
    )


def test_orphan_sweep_spares_runs_registered_after_it_started() -> None:
    """Keep a concurrently registered run out of another run's startup orphan sweep."""
    with _connect_writer("backtest_db") as connection:
        catalog = BacktestCatalogStore(cast(WriteConnection, connection))
        crashed_run_id = catalog.register(_orphan_sweep_run_meta())
        inflight_run_id = catalog.register(_orphan_sweep_run_meta())
        # CURRENT_TIMESTAMP is the transaction start time, so a run that registers while a
        # sweep transaction is already open carries a started_at ahead of that sweep clock.
        connection.execute(
            """
            UPDATE public.backtest_run
            SET started_at = CURRENT_TIMESTAMP + INTERVAL '30 seconds'
            WHERE run_id = %s
            """,
            (inflight_run_id,),
        )
        connection.commit()

        swept = catalog.reconcile_orphaned()

        assert swept >= 1
        rows = connection.execute(
            """
            SELECT run_id, status, started_at, finished_at, error_message
            FROM public.backtest_run
            WHERE run_id IN (%s, %s)
            """,
            (crashed_run_id, inflight_run_id),
        ).fetchall()
        observed = {str(row[0]): row for row in rows}

        crashed = observed[crashed_run_id]
        crashed_started, crashed_finished = crashed[2], crashed[3]
        assert crashed[1] == "ORPHANED"
        assert isinstance(crashed_started, datetime)
        assert isinstance(crashed_finished, datetime)
        assert crashed_finished >= crashed_started
        assert crashed[4] == "registered run did not reach Evidence finalize"

        inflight = observed[inflight_run_id]
        assert inflight[1] == "RUNNING"
        assert inflight[3] is None
        assert inflight[4] is None

        _finalize_orphan_sweep_run(catalog, crashed_run_id, "swept")
        finalized = connection.execute(
            "SELECT status, error_message FROM public.backtest_run WHERE run_id = %s",
            (crashed_run_id,),
        ).fetchone()
        assert finalized is not None
        assert finalized[0] == "EVALUATED"
        assert finalized[1] is None

        # Leave no RUNNING row behind in the shared development catalog.
        connection.execute(
            "UPDATE public.backtest_run SET started_at = CURRENT_TIMESTAMP WHERE run_id = %s",
            (inflight_run_id,),
        )
        connection.commit()
        _finalize_orphan_sweep_run(catalog, inflight_run_id, "inflight")


_FUNDING_PROBE_ID = "funding-exhaustion-probe"
_FUNDING_PROBE_DECISION_OPEN = datetime(2025, 6, 22, 14, tzinfo=UTC)
_MATRIX_REVERSAL_ID = "real-data-reversal-probe"
_MATRIX_REVERSAL_OPEN = _MATRIX_START


class _FundingExhaustionProbe:
    """Hold one real-data long until measured funding consumes its margin."""

    VERSION: ClassVar[str] = "1.0.0"

    def __init__(self, config: ResolvedConfig) -> None:
        if config.strategy_id != _FUNDING_PROBE_ID:
            raise ValueError("funding probe received a mismatched strategy id")
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            required_indicators=[{"name": "EMA", "params": {"period": 9}}],
            min_history=9,
            supported_timeframes=["1h"],
            profile=StrategyProfile(
                id="funding-exhaustion-multi-boundary-v1",
                family="verification",
                bar="1h",
                expected_win_rate=(0.0, 1.0),
                expected_payoff=(0.0, 100.0),
                tail_shape="symmetric",
                holding_horizon="multi_boundary",
                primary_metric="calmar",
                risk_adjusted_pref="sortino",
                profit_structure_to_preserve="funding-accounting",
                envelope_tolerance=1.0,
                envelope_status="provisional",
            ),
        )

    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        return ParameterSchema(
            fields={
                "leverage": FieldSpec(
                    type="integer",
                    default=39,
                    range=(1, 100),
                ),
                "scenario": FieldSpec(
                    type="string",
                    default="natural-multi-boundary",
                ),
                "direction": FieldSpec(
                    type="string",
                    default="LONG",
                ),
            }
        )

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> TradingSignal | None:
        candle = market_data.get("candle")
        if not isinstance(candle, Candle):
            raise TypeError("market_data.candle must be Candle")
        if candle.open_time != _FUNDING_PROBE_DECISION_OPEN or current_position is not None:
            return None
        leverage = self.config.params["leverage"]
        if isinstance(leverage, bool) or not isinstance(leverage, int):
            raise TypeError("resolved leverage must be an int")
        direction = self.config.params["direction"]
        if not isinstance(direction, str) or direction not in {"LONG", "SHORT"}:
            raise ValueError("resolved direction must be LONG or SHORT")
        stop_loss = candle.close * (0.01 if direction == "LONG" else 10.0)
        take_profit = candle.close * (10.0 if direction == "LONG" else 0.01)
        return TradingSignal(
            symbol=candle.symbol,
            timestamp=candle.close_time,
            confidence=1.0,
            price=candle.close,
            stop_loss=stop_loss,
            take_profit=take_profit,
            market_type=MarketType.FUTURES,
            leverage=leverage,
            reason=f"measured-funding-probe-{direction.casefold()}",
            metadata={"adaptee": _FUNDING_PROBE_ID},
        )


class _FundingProbeCatalog(StrategyRegistry):
    def get(self, strategy_id: str) -> dict[str, object]:
        assert strategy_id == _FUNDING_PROBE_ID
        return {
            "strategy_id": strategy_id,
            "class_name": _FundingExhaustionProbe.__name__,
            "module_path": _FundingExhaustionProbe.__module__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get(_FUNDING_PROBE_ID)]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError("read-only fixture")


def _funding_probe_manager() -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    plugins.register(_FUNDING_PROBE_ID, _FundingExhaustionProbe)
    return AdapterManager(_FundingProbeCatalog(), plugins)


class _RealDataReversalProbe:
    """Drive the existing reversal intent over immutable real OHLCV."""

    VERSION: ClassVar[str] = "1.0.0"

    def __init__(self, config: ResolvedConfig) -> None:
        if config.strategy_id != _MATRIX_REVERSAL_ID:
            raise ValueError("reversal probe received a mismatched strategy id")
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            required_indicators=[{"name": "EMA", "params": {"period": 9}}],
            min_history=9,
            supported_timeframes=["1h"],
            profile=StrategyProfile(
                id="real-data-reversal-v1",
                family="verification",
                bar="1h",
                expected_win_rate=(0.0, 1.0),
                expected_payoff=(0.0, 100.0),
                tail_shape="symmetric",
                holding_horizon="multi_boundary",
                primary_metric="calmar",
                risk_adjusted_pref="sortino",
                profit_structure_to_preserve="reversal-accounting",
                envelope_tolerance=1.0,
                envelope_status="provisional",
            ),
        )

    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        return ParameterSchema(
            fields={
                "leverage": FieldSpec(type="integer", default=3, range=(1, 100)),
                "scenario": FieldSpec(type="string", default="real-price-reversal"),
            }
        )

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> TradingSignal | None:
        candle = market_data.get("candle")
        if not isinstance(candle, Candle):
            raise TypeError("market_data.candle must be Candle")
        leverage = self.config.params["leverage"]
        if isinstance(leverage, bool) or not isinstance(leverage, int):
            raise TypeError("resolved leverage must be an int")
        if candle.open_time == _MATRIX_REVERSAL_OPEN and current_position is None:
            return TradingSignal(
                symbol=candle.symbol,
                timestamp=candle.close_time,
                confidence=1.0,
                price=candle.close,
                stop_loss=candle.close * 0.01,
                take_profit=candle.close * 10.0,
                market_type=MarketType.FUTURES,
                leverage=leverage,
                reason="real-data-reversal-long",
                metadata={"adaptee": _MATRIX_REVERSAL_ID},
            )
        if (
            candle.open_time == _MATRIX_REVERSAL_OPEN + timedelta(days=1)
            and current_position is not None
            and current_position.side is PositionSide.LONG
        ):
            return TradingSignal(
                symbol=candle.symbol,
                timestamp=candle.close_time,
                confidence=1.0,
                price=candle.close,
                stop_loss=candle.close * 10.0,
                take_profit=candle.close * 0.01,
                market_type=MarketType.FUTURES,
                leverage=leverage,
                reason="real-data-reversal-short",
                metadata={"adaptee": _MATRIX_REVERSAL_ID},
            )
        return None


class _RealDataReversalCatalog(StrategyRegistry):
    def get(self, strategy_id: str) -> dict[str, object]:
        assert strategy_id == _MATRIX_REVERSAL_ID
        return {
            "strategy_id": strategy_id,
            "class_name": _RealDataReversalProbe.__name__,
            "module_path": _RealDataReversalProbe.__module__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get(_MATRIX_REVERSAL_ID)]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError("read-only fixture")


def _real_data_reversal_manager() -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    plugins.register(_MATRIX_REVERSAL_ID, _RealDataReversalProbe)
    return AdapterManager(_RealDataReversalCatalog(), plugins)


class _GapFreeVesselFeed(DataFeed):
    """Serve one immutable, explicitly contiguous fixture without future exposure."""

    def __init__(self, candles: list[Candle]) -> None:
        self._candles = list(candles)
        self._minute_candles = [
            Candle(
                symbol=candle.symbol,
                exchange=candle.exchange,
                timeframe="1m",
                open_time=candle.open_time + timedelta(minutes=index),
                close_time=candle.open_time + timedelta(minutes=index + 1),
                open=candle.open if index == 0 else candle.close,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume / 60,
                quote_volume=None,
                trade_count=None,
            )
            for candle in candles
            for index in range(60)
        ]

    def candles(self, symbol: str, tf: str, up_to: datetime) -> list[Candle]:
        assert symbol == "BTCUSDT"
        if tf == "1m":
            return [candle for candle in self._minute_candles if candle.close_time <= up_to]
        assert tf == "1h"
        return [candle for candle in self._candles if candle.close_time <= up_to]

    def source_candles(
        self,
        symbol: str,
        range_start: datetime,
        range_end: datetime,
    ) -> tuple[Candle, ...]:
        assert symbol == "BTCUSDT"
        return tuple(
            candle
            for candle in self._minute_candles
            if range_start <= candle.open_time and candle.close_time <= range_end
        )

    def funding(self, symbol: str, at: datetime) -> Decimal:
        del symbol, at
        raise LookupError("fixture deliberately uses the configured zero fallback")

    def mark_price(self, symbol: str, at: datetime) -> Decimal:
        del symbol, at
        return Decimal("100")


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


def _vessel_manager(registry: StrategyRegistry) -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    plugins.register(VESSEL_STRATEGY_ID, VesselReference)
    return AdapterManager(registry, plugins)


def _real_vessel_config(
    *,
    run_name: str,
    start: datetime,
    end: datetime,
    funding_fallback_rate: Decimal = Decimal("0.0001"),
) -> RunConfig:
    return RunConfig(
        run_name=run_name,
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
            "futures_taker_fee_rate": Decimal("0.0004"),
            "futures_entry_slippage_rate": Decimal("0.0005"),
            "exit_slippage_rate": Decimal("0.0001"),
            "funding_fallback_rate": funding_fallback_rate,
        },
        profile_ref="vessel-reference-v1",
    )


def _run_real_vessel(
    root: Path,
    config: RunConfig,
    feed_decorator: FeedDecorator | None = None,
) -> RunResult:
    prereg = {
        "hypothesis": "Vessel must survive real measured funding",
        "primary_metric": "pf",
        "success_threshold": 1.3,
        "failure_threshold": 1.0,
        "edge_distinguishable": True,
        "higher_is_better": True,
    }
    with (
        _connect("crypto_data") as crypto_connection,
        _connect_writer("backtest_db") as catalog_connection,
        _connect("signal_db") as signal_connection,
    ):
        feed: DataFeed = BacktestDataFeed(
            cast(ReadConnection, crypto_connection),
            exchange=config.exchange,
        )
        if feed_decorator is not None:
            feed = feed_decorator(feed)
        history = feed.candles(config.symbol, config.timeframe, config.end)
        costs = BacktestCostModel(config.cost_values)
        result = Engine(
            feed,
            BacktestBroker(costs),
            BacktestClock.from_candles(history),
            costs,
            BacktestEvidenceSink(root),
            BacktestCatalogStore(cast(WriteConnection, catalog_connection)),
            _vessel_manager(BacktestStrategyRegistry(cast(ReadConnection, signal_connection))),
            prereg=prereg,
        ).run(config)
        catalog_row = catalog_connection.execute(
            """
            SELECT r.status, s.integrity_status
            FROM public.backtest_run AS r
            JOIN public.backtest_summary AS s USING (run_id)
            WHERE r.run_id = %s
            """,
            (result.run_id,),
        ).fetchone()
    assert catalog_row == ("EVALUATED", "passed")
    assert result.integrity_status == "passed"
    return result


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
    prereg = {
        "hypothesis": "Vessel reference traverses the complete pipeline",
        "primary_metric": "pf",
        "success_threshold": 1.3,
        "failure_threshold": 1.0,
        "edge_distinguishable": True,
        "higher_is_better": True,
    }

    with (
        _connect_writer("backtest_db") as connection,
        _connect("signal_db") as signal_connection,
    ):
        catalog = BacktestCatalogStore(cast(WriteConnection, connection))
        registry = BacktestStrategyRegistry(cast(ReadConnection, signal_connection))
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
                BacktestClock.from_candles(candles),
                costs,
                BacktestEvidenceSink(tmp_path / label),
                catalog,
                _vessel_manager(registry),
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
            assert evidence.execute("SELECT COUNT(*) FROM BACKTEST_RUN_LOCAL").fetchone() == (1,)
            assert evidence.execute("SELECT COUNT(*) FROM TRADE").fetchone() == (1,)


def test_vessel_engine_traverses_real_crypto_data_feed(
    tmp_path: Path,
) -> None:
    """Complete a fee-bearing three-day run through both real input catalogs."""
    case = _matrix_case("baseline-3d")
    start = case.start
    end = case.end
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
            "futures_taker_fee_rate": Decimal("0.0004"),
            "futures_entry_slippage_rate": Decimal("0.0005"),
            "exit_slippage_rate": Decimal("0.0001"),
            "funding_fallback_rate": Decimal("0.0001"),
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
        _connect("signal_db") as signal_connection,
    ):
        feed = BacktestDataFeed(
            cast(ReadConnection, crypto_connection),
            exchange=config.exchange,
        )
        history = feed.candles(config.symbol, config.timeframe, config.end)
        evaluation = [
            candle for candle in history if candle.open_time >= start and candle.close_time <= end
        ]
        assert len(evaluation) == 72
        assert all(
            left.close_time == right.open_time
            for left, right in zip(evaluation, evaluation[1:], strict=False)
        )
        costs = BacktestCostModel(config.cost_values)
        result = Engine(
            feed,
            BacktestBroker(costs),
            BacktestClock.from_candles(history),
            costs,
            BacktestEvidenceSink(tmp_path / "real-data-feed"),
            BacktestCatalogStore(cast(WriteConnection, catalog_connection)),
            _vessel_manager(BacktestStrategyRegistry(cast(ReadConnection, signal_connection))),
            prereg=prereg,
        ).run(config)
        catalog_row = catalog_connection.execute(
            """
            SELECT r.status, r.evidence_hash, s.integrity_status
            FROM public.backtest_run AS r
            JOIN public.backtest_summary AS s USING (run_id)
            WHERE r.run_id = %s
            """,
            (result.run_id,),
        ).fetchone()
        unreconciled_count = catalog_connection.execute(
            """
            SELECT count(*)
            FROM public.backtest_run
            WHERE status = 'RUNNING'
              AND evidence_hash IS NULL
            """
        ).fetchone()

    assert result.integrity_status == "passed"
    assert catalog_row == ("EVALUATED", result.evidence_hash, "passed")
    assert unreconciled_count == (0,)
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
        assert source[2] == 93
        assert len(history) >= source[2]
        funding_source = evidence.execute(
            """
            SELECT row_count, fallback_used, fallback_count, note
            FROM SOURCE_DATA_SNAPSHOT
            WHERE source_kind = 'funding'
            """
        ).fetchone()
        assert funding_source == (
            9,
            0,
            0,
            "measured_exact=2; measured_jitter_normalized=7; measured_missing=0; "
            "mark_exact=0; mark_jitter_normalized=0; mark_missing=0; "
            "unobservable_boundaries=0",
        )
        first_entry = evidence.execute(
            """
            SELECT price, quantity, fee, qty_truncated
            FROM EXECUTION
            WHERE reduce_only = 0
            ORDER BY execution_id
            LIMIT 1
            """
        ).fetchone()
        assert first_entry is not None
        assert first_entry[0] >= 100_000 * 100_000_000
        assert first_entry[2] > 0
        assert first_entry[3] == 1
        assert evidence.execute("SELECT min(cash_balance) >= 0 FROM PORTFOLIO_PNL").fetchone() == (
            1,
        )
        # 72 evaluated bars plus the terminal row carrying the equity that remains after
        # the run closes what it still held.
        assert evidence.execute("SELECT COUNT(*) FROM PORTFOLIO_PNL").fetchone() == (73,)
        _assert_matrix_axes(evidence, case)


def test_real_data_matrix_reversal_closes_before_opposite_entry(
    tmp_path: Path,
) -> None:
    case = _matrix_case("reversal-3d")
    leverage = case.leverages[0]
    config = RunConfig(
        run_name="matrix-reversal-3d",
        strategy_id=_MATRIX_REVERSAL_ID,
        params={"leverage": leverage, "scenario": "real-price-reversal"},
        symbol="BTC/USDT:USDT",
        exchange="binance",
        timeframe="1h",
        market_type="futures",
        data_source="crypto_data.ohlcv_futures",
        start=case.start,
        end=case.end,
        initial_capital=Decimal("10000"),
        risk_per_trade=0.01,
        seed=17,
        cost_values={
            "futures_taker_fee_rate": Decimal("0.0004"),
            "futures_entry_slippage_rate": Decimal("0.0005"),
            "exit_slippage_rate": Decimal("0.0001"),
            "funding_fallback_rate": Decimal("0"),
        },
        profile_ref="real-data-reversal-v1",
    )
    prereg = {
        "hypothesis": "real-price reversal preserves ordering and accounting",
        "primary_metric": "pf",
        "success_threshold": 0.0,
        "failure_threshold": -1.0,
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
        costs = BacktestCostModel(config.cost_values)
        result = Engine(
            feed,
            BacktestBroker(costs),
            BacktestClock.from_candles(history),
            costs,
            BacktestEvidenceSink(tmp_path / case.case_id),
            BacktestCatalogStore(cast(WriteConnection, catalog_connection)),
            _real_data_reversal_manager(),
            prereg=prereg,
        ).run(config)

    assert result.integrity_status == "passed"
    with sqlite3.connect(result.evidence_path) as evidence:
        decision = evidence.execute(
            "SELECT decision_id, decision_ts FROM DECISION WHERE action = 'reverse'"
        ).fetchone()
        assert decision is not None
        fills = evidence.execute(
            """
            SELECT execution_ts, position_side, reduce_only, exit_reason,
                   reference_price, price, slippage
            FROM EXECUTION
            WHERE decision_id = ?
            ORDER BY execution_id
            """,
            (decision[0],),
        ).fetchall()
        assert len(fills) == 2
        execution_ts = fills[0][0]
        assert execution_ts - decision[1] == 1
        assert [fill[:4] for fill in fills] == [
            (execution_ts, "LONG", 1, "REVERSAL"),
            (execution_ts, "SHORT", 0, None),
        ]
        assert all(fill[6] > 0 for fill in fills)
        assert all(fill[5] < fill[4] for fill in fills)
        assert evidence.execute(
            "SELECT COUNT(*) FROM TRADE WHERE leverage = ?",
            (leverage,),
        ).fetchone() == (2,)
        _assert_matrix_axes(evidence, case)
        assert evidence.execute(
            """
            SELECT COUNT(*)
            FROM TRADE AS t
            JOIN EXECUTION AS entry ON entry.execution_id = t.entry_execution_id
            JOIN EXECUTION AS exit ON exit.execution_id = t.exit_execution_id
            WHERE t.total_fee <> entry.fee + exit.fee
               OR t.slippage <> entry.slippage + exit.slippage
               OR t.net_pnl <> (
                   t.gross_pnl - t.total_fee - t.slippage
                   - t.funding_cost - t.liquidation_penalty
               )
            """
        ).fetchone() == (0,)
        assert evidence.execute(
            "SELECT COUNT(*) FROM INTEGRITY_CHECK WHERE passed = 0"
        ).fetchone() == (0,)


@pytest.mark.real_data_long
def test_measured_funding_exhaustion_liquidates_a_natural_real_data_position(
    tmp_path: Path,
) -> None:
    case = _matrix_case("funding-exhaustion-135d")
    start = case.start
    end = case.end
    leverage = case.leverages[0]
    config = RunConfig(
        run_name="funding-exhaustion",
        strategy_id=_FUNDING_PROBE_ID,
        params={
            "leverage": leverage,
            "scenario": "natural-multi-boundary",
            "direction": "LONG",
        },
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
            "futures_taker_fee_rate": Decimal("0.0004"),
            "futures_entry_slippage_rate": Decimal("0.0005"),
            "exit_slippage_rate": Decimal("0.0001"),
            "funding_fallback_rate": Decimal("0"),
        },
        profile_ref="funding-exhaustion-multi-boundary-v1",
    )
    prereg = {
        "hypothesis": "measured funding exhausts an exchange-range leveraged long",
        "primary_metric": "pf",
        "success_threshold": 0.0,
        "failure_threshold": -1.0,
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
        costs = BacktestCostModel(config.cost_values)
        result = Engine(
            feed,
            BacktestBroker(costs),
            BacktestClock.from_candles(history),
            costs,
            BacktestEvidenceSink(tmp_path / "measured-funding-exhaustion"),
            BacktestCatalogStore(cast(WriteConnection, catalog_connection)),
            _funding_probe_manager(),
            prereg=prereg,
        ).run(config)

    assert result.integrity_status == "passed"
    with sqlite3.connect(result.evidence_path) as evidence:
        entry = evidence.execute(
            """
            SELECT execution_ts, notional, fee, reference_price, price, slippage
            FROM EXECUTION
            WHERE reduce_only = 0
            """
        ).fetchone()
        settlement = evidence.execute(
            """
            SELECT settled_at, funding_rate, rate_source, settle_price,
                   settle_price_source, payment_amount, theoretical_payment_amount
            FROM FUNDING_SETTLEMENT
            ORDER BY settled_at DESC
            LIMIT 1
            """
        ).fetchone()
        liquidation = evidence.execute(
            """
            SELECT d.decision_ts, e.execution_ts, e.reference_price,
                   e.price, e.slippage, e.fee, e.exit_reason, e.reduce_only
            FROM EXECUTION AS e
            JOIN DECISION AS d USING (decision_id)
            WHERE e.exit_reason = 'LIQUIDATION'
            """
        ).fetchone()
        trade = evidence.execute(
            """
            SELECT t.liquidated, t.exit_reason, t.total_fee,
                   entry.fee + exit.fee, t.funding_cost,
                   t.liquidation_penalty, t.slippage,
                   entry.slippage + exit.slippage, t.net_pnl,
                   t.gross_pnl - t.total_fee - t.slippage
                       - t.funding_cost - t.liquidation_penalty
            FROM TRADE AS t
            JOIN EXECUTION AS entry ON entry.execution_id = t.entry_execution_id
            JOIN EXECUTION AS exit ON exit.execution_id = t.exit_execution_id
            """
        ).fetchone()
        assert entry is not None
        assert settlement is not None
        assert liquidation is not None
        assert trade is not None

        assert entry[0] == int(datetime(2025, 6, 22, 15, tzinfo=UTC).timestamp() * 1_000) + 1
        assert entry[4] > entry[3]
        assert entry[5] > 0
        assert evidence.execute(
            """
            SELECT COUNT(*), SUM(rate_source = 'measured')
            FROM FUNDING_SETTLEMENT
            """
        ).fetchone() == (405, 405)
        settled_at, rate, rate_source, settle_price, price_source, payment, theoretical = settlement
        assert rate == pytest.approx(0.00005808)
        assert rate_source == "measured"
        assert price_source == "boundary_open"
        assert settled_at == int(datetime(2025, 11, 4, 8, tzinfo=UTC).timestamp() * 1_000)
        assert payment < 0
        assert theoretical < payment
        assert leverage <= 100

        assert liquidation == (
            settled_at,
            settled_at + 1,
            settle_price,
            liquidation[3],
            liquidation[4],
            liquidation[5],
            "LIQUIDATION",
            1,
        )
        assert liquidation[3] < liquidation[2]
        assert liquidation[4] > 0
        assert liquidation[5] > 0
        (
            liquidated,
            exit_reason,
            total_fee,
            execution_fees,
            funding_cost,
            liquidation_penalty,
            total_slippage,
            execution_slippage,
            net_pnl,
            recomputed_net,
        ) = trade
        assert (liquidated, exit_reason) == (1, "LIQUIDATION")
        assert total_fee == execution_fees
        assert funding_cost == round(entry[1] / leverage)
        assert liquidation_penalty == 0
        assert total_slippage == execution_slippage
        assert net_pnl == recomputed_net
        assert evidence.execute("SELECT min(cash_balance) >= 0 FROM PORTFOLIO_PNL").fetchone() == (
            1,
        )
        assert dict(
            evidence.execute("SELECT check_name, passed FROM INTEGRITY_CHECK").fetchall()
        ) == {
            "accounting_identity": 1,
            "timestamp_order": 1,
            "cost_once": 1,
            "net_of_cost": 1,
            "deterministic": 1,
            "evidence_complete": 1,
        }
        _assert_matrix_axes(evidence, case)


@pytest.mark.real_data_long
def test_negative_measured_funding_debits_a_high_leverage_short(
    tmp_path: Path,
) -> None:
    case = _matrix_case("funding-short-negative-20h-39x")
    leverage = case.leverages[0]
    config = RunConfig(
        run_name="fund-short-neg-39x",
        strategy_id=_FUNDING_PROBE_ID,
        params={
            "leverage": leverage,
            "scenario": "negative-measured-rate",
            "direction": "SHORT",
        },
        symbol="BTC/USDT:USDT",
        exchange="binance",
        timeframe="1h",
        market_type="futures",
        data_source="crypto_data.ohlcv_futures",
        start=case.start,
        end=case.end,
        initial_capital=Decimal("10000"),
        risk_per_trade=0.01,
        seed=17,
        cost_values={
            "futures_taker_fee_rate": Decimal("0.0004"),
            "futures_entry_slippage_rate": Decimal("0.0005"),
            "exit_slippage_rate": Decimal("0.0001"),
            "funding_fallback_rate": Decimal("0"),
        },
        profile_ref="funding-negative-high-leverage-v1",
    )
    prereg = {
        "hypothesis": "measured negative funding debits a real-price 39x short",
        "primary_metric": "pf",
        "success_threshold": 0.0,
        "failure_threshold": -1.0,
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
            if candle.open_time >= case.start and candle.close_time <= case.end
        ]
        assert len(evaluation) == 20
        costs = BacktestCostModel(config.cost_values)
        result = Engine(
            feed,
            BacktestBroker(costs),
            BacktestClock.from_candles(history),
            costs,
            BacktestEvidenceSink(tmp_path / case.case_id),
            BacktestCatalogStore(cast(WriteConnection, catalog_connection)),
            _funding_probe_manager(),
            prereg=prereg,
        ).run(config)

    assert result.integrity_status == "passed"
    with sqlite3.connect(result.evidence_path) as evidence:
        negative_stats = evidence.execute(
            """
            SELECT COUNT(*), min(funding_rate),
                   SUM(payment_amount < 0),
                   SUM(rate_source = 'measured')
            FROM FUNDING_SETTLEMENT
            WHERE position_side = 'SHORT' AND funding_rate < 0
            """
        ).fetchone()
        assert negative_stats is not None
        negative_count, minimum_rate, debit_count, measured_count = negative_stats
        assert negative_count == debit_count == measured_count == 1
        assert minimum_rate == pytest.approx(-0.00001061)
        assert evidence.execute(
            """
            SELECT COUNT(*), SUM(rate_source = 'measured')
            FROM FUNDING_SETTLEMENT
            """
        ).fetchone() == (2, 2)
        assert evidence.execute(
            "SELECT COUNT(*) FROM TRADE WHERE leverage = ?",
            (leverage,),
        ).fetchone() == (1,)
        assert evidence.execute(
            """
            SELECT COUNT(*)
            FROM TRADE AS t
            JOIN EXECUTION AS entry ON entry.execution_id = t.entry_execution_id
            JOIN EXECUTION AS exit ON exit.execution_id = t.exit_execution_id
            WHERE t.total_fee <> entry.fee + exit.fee
               OR t.slippage <> entry.slippage + exit.slippage
               OR t.net_pnl <> (
                   t.gross_pnl - t.total_fee - t.slippage
                   - t.funding_cost - t.liquidation_penalty
               )
            """
        ).fetchone() == (0,)
        assert dict(
            evidence.execute("SELECT check_name, passed FROM INTEGRITY_CHECK").fetchall()
        ) == {
            "accounting_identity": 1,
            "timestamp_order": 1,
            "cost_once": 1,
            "net_of_cost": 1,
            "deterministic": 1,
            "evidence_complete": 1,
        }
        _assert_matrix_axes(evidence, case)


@pytest.mark.real_data_long
@pytest.mark.parametrize(
    ("case_id", "run_name", "fallback", "target_sql"),
    (
        (
            "funding-short-negative-180d",
            "fund-short-neg-180d",
            Decimal("0.0001"),
            """
            SELECT COUNT(*)
            FROM FUNDING_SETTLEMENT
            WHERE position_side = 'SHORT'
              AND funding_rate < 0.0
              AND payment_amount < 0
            """,
        ),
        (
            "funding-long-positive-30d",
            "fund-long-pos-30d",
            Decimal("0.00001"),
            """
            SELECT COUNT(*)
            FROM FUNDING_SETTLEMENT
            WHERE position_side = 'LONG'
              AND funding_rate > 0.00001
              AND payment_amount < 0
            """,
        ),
    ),
    ids=("short-negative-180d", "long-positive-30d"),
)
def test_real_funding_sign_matrix_completes_without_negative_cash(
    tmp_path: Path,
    case_id: str,
    run_name: str,
    fallback: Decimal,
    target_sql: str,
) -> None:
    case = _matrix_case(case_id)
    result = _run_real_vessel(
        tmp_path / case.case_id,
        _real_vessel_config(
            run_name=run_name,
            start=case.start,
            end=case.end,
            funding_fallback_rate=fallback,
        ),
    )
    with sqlite3.connect(result.evidence_path) as evidence:
        assert evidence.execute(target_sql).fetchone()[0] > 0
        assert evidence.execute("SELECT min(cash_balance) >= 0 FROM PORTFOLIO_PNL").fetchone() == (
            1,
        )
        assert evidence.execute(
            """
            SELECT COUNT(*)
            FROM FUNDING_SETTLEMENT
            WHERE abs(payment_amount) > abs(theoretical_payment_amount)
            """
        ).fetchone() == (0,)
        assert evidence.execute(
            "SELECT COUNT(*) FROM INTEGRITY_CHECK WHERE passed = 0"
        ).fetchone() == (0,)
        _assert_matrix_axes(evidence, case)


@pytest.mark.real_data_long
def test_real_missing_candles_complete_330_day_evidence(
    tmp_path: Path,
    declared_gap_decorator: Callable[[frozenset[datetime]], FeedDecorator],
    missing_data_330d_withheld: frozenset[datetime],
) -> None:
    case = _matrix_case("missing-data-330d")
    result = _run_real_vessel(
        tmp_path / "cto-gap-330d",
        _real_vessel_config(
            run_name="cto-gap-330d",
            start=case.start,
            end=case.end,
        ),
        feed_decorator=declared_gap_decorator(missing_data_330d_withheld),
    )

    with sqlite3.connect(result.evidence_path) as evidence:
        hourly_count, hourly_gaps, hourly_note = evidence.execute(
            """
            SELECT row_count, gap_count, note
            FROM SOURCE_DATA_SNAPSHOT
            WHERE source_kind = 'ohlcv' AND timeframe = '1h'
            """
        ).fetchone()
        minute_count, minute_gaps, minute_note = evidence.execute(
            """
            SELECT row_count, gap_count, note
            FROM SOURCE_DATA_SNAPSHOT
            WHERE source_kind = 'ohlcv' AND timeframe = '1m'
            """
        ).fetchone()
        hourly_gap_evidence = json.loads(hourly_note)
        minute_gap_evidence = json.loads(minute_note)
        integrity = dict(
            evidence.execute("SELECT check_name, passed FROM INTEGRITY_CHECK").fetchall()
        )
        _assert_matrix_axes(evidence, case)

        # 7_901 evaluated bars plus the terminal equity row.
        assert evidence.execute("SELECT COUNT(*) FROM PORTFOLIO_PNL").fetchone() == (7_902,)
        assert evidence.execute("SELECT COUNT(*) FROM TRADE").fetchone() == (600,)
        assert evidence.execute(
            "SELECT COUNT(*) FROM EXECUTION WHERE exit_reason = 'DATA_GAP'"
        ).fetchone() == (6,)
        assert evidence.execute(
            "SELECT COUNT(*) FROM DECISION WHERE skip_reason = 'next_candle_gap'"
        ).fetchone() == (1,)
        assert evidence.execute(
            """
            SELECT max(e.execution_ts - d.decision_ts)
            FROM EXECUTION AS e
            JOIN DECISION AS d USING (decision_id)
            """
        ).fetchone() == (3_600_000,)

    assert hourly_count == 7_922
    assert hourly_gaps == 19
    assert hourly_gap_evidence["normal_gap_count"] == 15
    assert hourly_gap_evidence["partial_bucket_count"] == 4
    assert hourly_gap_evidence["evaluation_grid_gap_count"] == 19
    assert hourly_gap_evidence["origin_validation_status"] == "verified"
    assert minute_count == 475_440
    assert minute_gaps == 1_020
    assert minute_gap_evidence["normal_gap_count"] == 1_020
    assert minute_gap_evidence["partial_bucket_count"] == 0
    assert minute_gap_evidence["evaluation_grid_gap_count"] == 1_020
    assert minute_gap_evidence["origin_validation_status"] == "verified"
    assert integrity == {
        "accounting_identity": 1,
        "timestamp_order": 1,
        "cost_once": 1,
        "net_of_cost": 1,
        "deterministic": 1,
        "evidence_complete": 1,
    }
    with _connect("backtest_db") as catalog:
        coverage = catalog.execute(
            """
            SELECT expected_candle_count, observed_candle_count,
                   source_absent_gap_count, partial_bucket_count,
                   data_coverage_ratio, max_consecutive_gap_bars,
                   max_consecutive_gap_seconds, data_coverage_passed,
                   unobservable_funding_boundary_count, data_gap_exit_count,
                   gate_failed_json
            FROM public.backtest_summary
            WHERE run_id = %s
            """,
            (result.run_id,),
        ).fetchone()
    assert coverage is not None
    # 15 absent buckets (three five-hour blocks) plus 4 partial buckets = 19 omitted
    # of 7_920, so the declared gaps stay inside both coverage gates.
    assert coverage[:4] == (7_920, 7_901, 15, 4)
    assert coverage[4] == pytest.approx(7_901 / 7_920)
    assert coverage[5:10] == (5, 18_000, True, 1, 6)
    gate_failed = cast(list[str], coverage[10])
    assert {"data_coverage_ratio", "max_consecutive_gap"}.isdisjoint(gate_failed)
    assert result.integrity_status == "passed"
    assert result.decision.route == "retest"


@pytest.mark.real_data_long
def test_entry_quantity_is_independent_of_remaining_run_window(
    tmp_path: Path,
) -> None:
    first_case = _matrix_case("window-3d")
    middle_case = _matrix_case("window-10d")
    long_case = _matrix_case("window-45d")
    start = first_case.start
    assert middle_case.start == long_case.start == start
    first_entries: list[tuple[int, int, int]] = []
    for case in (first_case, middle_case, long_case):
        days = (case.end - case.start).days
        result = _run_real_vessel(
            tmp_path / f"window-{days}",
            _real_vessel_config(
                run_name=f"cto3-window-{days}d",
                start=case.start,
                end=case.end,
            ),
        )
        with sqlite3.connect(result.evidence_path) as evidence:
            entry = evidence.execute(
                """
                SELECT execution_ts, reference_price, quantity
                FROM EXECUTION
                WHERE reduce_only = 0
                ORDER BY execution_id
                LIMIT 1
                """
            ).fetchone()
            assert entry is not None
            first_entries.append(entry)
            _assert_matrix_axes(evidence, case)

    assert len(set(first_entries)) == 1
