"""Assemble the production backtest adapters behind operator-facing entry points."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import cast

import psycopg
from core_lib.strategy import AdapterManager, InProcessStrategyRegistry
from core_lib.strategy.adaptees import STRATEGY_ID as VESSEL_STRATEGY_ID
from core_lib.strategy.adaptees import VesselReference
from core_lib.types import MarketType

from backtest_service.adapters.broker import BacktestBroker
from backtest_service.adapters.catalog_store import BacktestCatalogStore, WriteConnection
from backtest_service.adapters.clock import BacktestClock
from backtest_service.adapters.cost_model import BacktestCostModel
from backtest_service.adapters.data_feed import BacktestDataFeed, ReadConnection
from backtest_service.adapters.evidence_sink import BacktestEvidenceSink
from backtest_service.adapters.strategy_registry import BacktestStrategyRegistry
from backtest_service.config import RunConfig
from backtest_service.engine import Engine, RunResult
from backtest_service.harness import Harness

_REQUIRED_POSTGRES_KEYS = ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD")
ManagerFactory = Callable[[ReadConnection], AdapterManager]


def _connection(
    env: Mapping[str, str],
    database: str,
    *,
    read_only: bool,
) -> psycopg.Connection[tuple[object, ...]]:
    missing = [name for name in _REQUIRED_POSTGRES_KEYS if not env.get(name)]
    if missing:
        raise ValueError(f"env is missing PostgreSQL connection keys: {missing}")
    try:
        port = int(env["PGPORT"])
    except ValueError as error:
        raise ValueError("env.PGPORT must be an integer") from error
    options = "-c default_transaction_read_only=on" if read_only else ""
    return psycopg.connect(
        host=env["PGHOST"],
        port=port,
        user=env["PGUSER"],
        password=env["PGPASSWORD"],
        dbname=database,
        options=options,
        # A read holds one lock per hypertable chunk it touches, and a chunk-per-day
        # table reaches four figures over a few years. Without autocommit those locks
        # are kept for the life of the connection, which spans a whole run, and
        # concurrent runs then exhaust the server's shared lock table. Historical
        # candles are immutable, so per-statement transactions lose no consistency.
        autocommit=read_only,
    )


def _manager(signal_connection: ReadConnection) -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    plugins.register(VESSEL_STRATEGY_ID, VesselReference)
    return AdapterManager(
        BacktestStrategyRegistry(signal_connection),
        plugins,
    )


def _engine(
    config: RunConfig,
    prereg: Mapping[str, object],
    *,
    evidence: BacktestEvidenceSink,
    crypto_connection: ReadConnection,
    signal_connection: ReadConnection,
    catalog: BacktestCatalogStore,
    manager_factory: ManagerFactory,
) -> Engine:
    feed = BacktestDataFeed(crypto_connection, exchange=config.exchange)
    history = feed.candles(config.symbol, config.timeframe, config.end)
    costs = BacktestCostModel(
        config.cost_values,
        market_type=MarketType(config.market_type),
    )
    return Engine(
        feed,
        BacktestBroker(costs),
        BacktestClock.from_candles(history),
        costs,
        evidence,
        catalog,
        manager_factory(signal_connection),
        prereg=prereg,
    )


def run_backtest(
    config: RunConfig,
    prereg: Mapping[str, object],
    *,
    evidence_root: Path,
    env: Mapping[str, str],
    manager_factory: ManagerFactory | None = None,
) -> RunResult:
    """Run one fully assembled backtest and close every database/file handle."""
    evidence = BacktestEvidenceSink(evidence_root)
    try:
        with (
            _connection(env, "crypto_data", read_only=True) as crypto_connection,
            _connection(env, "signal_db", read_only=True) as signal_connection,
            _connection(env, "backtest_db", read_only=False) as catalog_connection,
        ):
            catalog = BacktestCatalogStore(cast(WriteConnection, catalog_connection))
            engine = _engine(
                config,
                prereg,
                evidence=evidence,
                crypto_connection=cast(ReadConnection, crypto_connection),
                signal_connection=cast(ReadConnection, signal_connection),
                catalog=catalog,
                manager_factory=_manager if manager_factory is None else manager_factory,
            )
            return engine.run(config)
    finally:
        evidence.close()


@contextmanager
def build_harness(
    config: RunConfig,
    prereg: Mapping[str, object],
    *,
    evidence_root: Path,
    env: Mapping[str, str],
    seed: int = 0,
    manager_factory: ManagerFactory | None = None,
) -> Iterator[Harness]:
    """Keep shared catalog sequencing alive while yielding fresh Engines per run."""
    evidence_sinks: list[BacktestEvidenceSink] = []
    with ExitStack() as stack:
        crypto_connection = stack.enter_context(_connection(env, "crypto_data", read_only=True))
        signal_connection = stack.enter_context(_connection(env, "signal_db", read_only=True))
        catalog_connection = stack.enter_context(_connection(env, "backtest_db", read_only=False))
        crypto_reader = cast(ReadConnection, crypto_connection)
        signal_reader = cast(ReadConnection, signal_connection)
        catalog = BacktestCatalogStore(cast(WriteConnection, catalog_connection))

        def engine_factory() -> Engine:
            evidence = BacktestEvidenceSink(evidence_root)
            evidence_sinks.append(evidence)
            return _engine(
                config,
                prereg,
                evidence=evidence,
                crypto_connection=crypto_reader,
                signal_connection=signal_reader,
                catalog=catalog,
                manager_factory=_manager if manager_factory is None else manager_factory,
            )

        try:
            yield Harness(catalog, engine_factory, seed=seed)
        finally:
            for evidence in evidence_sinks:
                evidence.close()


__all__ = ["ManagerFactory", "build_harness", "run_backtest"]
