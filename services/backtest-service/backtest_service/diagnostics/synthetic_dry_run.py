"""Run one deployed strategy on a fixed synthetic candle path, twice, with no database.

Design: ``docs/fullspec/author_check_and_scaffold_design.md`` section 3.4.1. This is step 6 of
the pre-deployment check: the strategy, composed with one money-management mode, goes through
the real ``Engine`` on a fixed regime path (320 warm-up hours, 240 evaluated hours, one seed),
and the report says whether the run completed, whether Evidence integrity passed, how many
trades it made and how they ended, the warm-up the Engine reported, and whether two runs of the
same configuration hashed the same. Zero trades is a warning, not a failure: the rule did not
fire on this path, which the path does not promise.

The feed, the catalog, and the registration rows are stand-ins for the operational adapters in
``backtest_service.adapters``. They share no name or place with them, and the registration rows
are made from what ``trading_plugins`` discovers, so every deployed strategy and every strategy
added later is reachable by id. The candle path is fixed on purpose: changing its length per
strategy would change the random sequence and with it every judgment the acceptance tests make
on it.

Evidence files are written to a temporary directory and removed when the report is built.
"""

from __future__ import annotations

import json
import math
import random
import sqlite3
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from core_lib.ports import CatalogStore, DataFeed, StrategyRegistry
from core_lib.strategy import AdapterClass, AdapterManager, InProcessStrategyRegistry
from core_lib.types import Candle
from trading_plugins import discover_strategies, registered_money_management

from backtest_service.adapters.broker import BacktestBroker
from backtest_service.adapters.catalog_store import DeterminismReference
from backtest_service.adapters.clock import BacktestClock
from backtest_service.adapters.cost_model import BacktestCostModel
from backtest_service.adapters.evidence_sink import BacktestEvidenceSink
from backtest_service.config import RunConfig
from backtest_service.engine import Engine, RunResult

__all__ = [
    "BASE",
    "EVALUATION_HOURS",
    "SEED",
    "SYMBOL",
    "WARMUP_HOURS",
    "DiscoveredRows",
    "DryRunReport",
    "MemoryCatalog",
    "SyntheticFeed",
    "dry_run",
    "main",
    "manager",
    "minute_candles",
    "run_config",
    "run_strategy",
    "synthetic_daily_candles",
    "synthetic_hourly_candles",
]

SYMBOL = "BTCUSDT"
EXCHANGE = "binance"
TIMEFRAME = "1h"
BASE = datetime(2026, 1, 1, 1, tzinfo=UTC)
WARMUP_HOURS = 320
EVALUATION_HOURS = 240
SEED = 20260923
DAILY_SEED = 20260927
DAILY_HISTORY_DAYS = 60
DATA_SOURCE = "synthetic-regime-fixture"


def synthetic_hourly_candles(seed: int = SEED) -> list[Candle]:
    """Return a deterministic hourly path with alternating regimes and volatility shocks."""
    rng = random.Random(seed)
    first_open = BASE - timedelta(hours=WARMUP_HOURS)
    candles: list[Candle] = []
    price = 100.0
    for index in range(WARMUP_HOURS + EVALUATION_HOURS):
        drift = 0.0012 * math.sin(2.0 * math.pi * index / 160.0)
        shock = rng.gauss(0.0, 0.008)
        open_price = price
        price = price * math.exp(drift + shock)
        high = max(open_price, price) * (1.0 + abs(rng.gauss(0.0, 0.002)))
        low = min(open_price, price) * (1.0 - abs(rng.gauss(0.0, 0.002)))
        opened = first_open + timedelta(hours=index)
        candles.append(
            Candle(
                symbol=SYMBOL,
                exchange=EXCHANGE,
                timeframe=TIMEFRAME,
                open_time=opened,
                close_time=opened + timedelta(hours=1),
                open=open_price,
                high=high,
                low=low,
                close=price,
                volume=100.0,
                quote_volume=10_000.0,
                trade_count=100,
            )
        )
    return candles


def synthetic_daily_candles(seed: int = DAILY_SEED) -> list[Candle]:
    """A separate finalized daily series on UTC day boundaries, for policies that read one.

    Turtle's daily N is prepared outside the bar loop from this series. It is generated on its
    own seed rather than aggregated from the hourly path, because the hourly path covers only
    thirteen days of warm-up and the policy asks for twenty daily bars before the first
    evaluated bar. The hourly path itself is unchanged, so every judgment made on it stands.
    """
    rng = random.Random(seed)
    first_open = BASE.replace(hour=0) - timedelta(days=DAILY_HISTORY_DAYS)
    last_close = BASE + timedelta(hours=EVALUATION_HOURS)
    candles: list[Candle] = []
    opened = first_open
    while opened + timedelta(days=1) <= last_close:
        open_price = 100.0 + rng.uniform(-3.0, 3.0)
        close = open_price + rng.uniform(-2.0, 2.0)
        candles.append(
            Candle(
                symbol=SYMBOL,
                exchange=EXCHANGE,
                timeframe="1d",
                open_time=opened,
                close_time=opened + timedelta(days=1),
                open=open_price,
                high=max(open_price, close) + rng.uniform(1.0, 4.0),
                low=min(open_price, close) - rng.uniform(1.0, 4.0),
                close=close,
                volume=1000.0,
                quote_volume=None,
                trade_count=None,
            )
        )
        opened += timedelta(days=1)
    return candles


def minute_candles(candles: Sequence[Candle]) -> list[Candle]:
    """Split each bar into flat minutes, the 1m origin the Engine validates against."""
    result: list[Candle] = []
    for candle in candles:
        minute_count = int((candle.close_time - candle.open_time) / timedelta(minutes=1))
        for index in range(minute_count):
            opened = candle.open_time + timedelta(minutes=index)
            result.append(
                Candle(
                    symbol=candle.symbol,
                    exchange=candle.exchange,
                    timeframe="1m",
                    open_time=opened,
                    close_time=opened + timedelta(minutes=1),
                    open=candle.open if index == 0 else candle.close,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume / minute_count,
                    quote_volume=None,
                    trade_count=None,
                )
            )
    return result


class SyntheticFeed(DataFeed):
    """Serve the hourly path, its minutes, the daily series, and the last close as mark price."""

    def __init__(self, candles: Sequence[Candle], daily: Sequence[Candle] | None = None) -> None:
        self._candles = list(candles)
        self._minutes = minute_candles(candles)
        self._daily = list(synthetic_daily_candles() if daily is None else daily)

    def candles(self, symbol: str, tf: str, up_to: datetime) -> list[Candle]:
        if symbol != SYMBOL:
            raise LookupError(f"the synthetic feed serves {SYMBOL} only")
        if tf == "1m":
            source = self._minutes
        elif tf == TIMEFRAME:
            source = self._candles
        elif tf == "1d":
            source = self._daily
        else:
            raise LookupError(f"the synthetic feed serves {TIMEFRAME}, 1m, and 1d only")
        return [candle for candle in source if candle.close_time <= up_to]

    def source_candles(
        self, symbol: str, range_start: datetime, range_end: datetime
    ) -> tuple[Candle, ...]:
        if symbol != SYMBOL:
            raise LookupError(f"the synthetic feed serves {SYMBOL} only")
        return tuple(
            candle
            for candle in self._minutes
            if range_start <= candle.open_time and candle.close_time <= range_end
        )

    def funding(self, symbol: str, at: datetime) -> Decimal:
        del symbol, at
        raise LookupError("no boundary funding on the synthetic path")

    def mark_price(self, symbol: str, at: datetime) -> Decimal:
        if symbol != SYMBOL:
            raise LookupError(f"the synthetic feed serves {SYMBOL} only")
        closed = [candle for candle in self._candles if candle.close_time <= at]
        last = closed[-1] if closed else self._candles[0]
        return Decimal(str(last.close))


class MemoryCatalog(CatalogStore):
    """Hold run registrations in memory and never claim a determinism reference."""

    def __init__(self) -> None:
        self.next_sequence = 1
        self.runs: dict[str, Mapping[str, object]] = {}
        self.summaries: list[object] = []
        self.preregs: list[object] = []

    def register(self, run: object) -> str:
        if not isinstance(run, Mapping):
            raise TypeError("a run registration must be a mapping")
        sequence = self.next_sequence
        self.next_sequence += 1
        run_id = f"BT_20260923_{sequence:06d}_{run['run_name']}"
        self.runs[run_id] = dict(run)
        return run_id

    def save_prereg(self, prereg: object) -> None:
        self.preregs.append(prereg)

    def upsert_summary(self, summary: object) -> None:
        self.summaries.append(summary)

    def record_harness_aggregate(
        self,
        run_id: str,
        *,
        oos_degradation: float | None,
        psr: float | None,
        harness_json: object,
    ) -> None:
        del run_id, oos_degradation, psr, harness_json

    def reconcile_orphaned(self) -> int:
        return 0

    def determinism_reference(
        self,
        run_id: str,
        config_hash: str,
        source_data_hash: str,
        evidence_schema_version: str,
    ) -> DeterminismReference:
        del source_data_hash, evidence_schema_version
        matches = self.runs[run_id]["config_hash"] == config_hash
        return DeterminismReference(matches, True, False, False, None, None)


class DiscoveredRows(StrategyRegistry):
    """The registration row each discovered class would carry, minus lifecycle.

    Made from discovery rather than written per strategy, so the same diagnostic reaches every
    deployed strategy and any added later.
    """

    def __init__(self, strategies: Mapping[str, AdapterClass]) -> None:
        self._strategies = dict(strategies)

    def get(self, strategy_id: str) -> dict[str, object]:
        adaptee = self._strategies[strategy_id]
        return {
            "strategy_id": strategy_id,
            "class_name": adaptee.__name__,
            "module_path": adaptee.__module__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get(strategy_id) for strategy_id in self._strategies]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError("the diagnostic rows are read-only")


def _discovered() -> Mapping[str, AdapterClass]:
    found, _ = discover_strategies()
    return found


def _strategy_class(strategy_id: str, strategies: Mapping[str, AdapterClass]) -> AdapterClass:
    try:
        return strategies[strategy_id]
    except KeyError as error:
        raise LookupError(f"unknown strategy: {strategy_id}") from error


def manager(strategies: Mapping[str, AdapterClass] | None = None) -> AdapterManager:
    """Compose every discovered strategy with the deployed policies, on diagnostic rows."""
    found = _discovered() if strategies is None else strategies
    plugins = InProcessStrategyRegistry()
    for strategy_id, adaptee in found.items():
        plugins.register(strategy_id, adaptee)
    return AdapterManager(
        DiscoveredRows(found), plugins, money_management_policies=registered_money_management()
    )


def run_config(
    strategy_id: str,
    money_management: Mapping[str, object],
    *,
    run_name: str | None = None,
    strategies: Mapping[str, AdapterClass] | None = None,
) -> RunConfig:
    """The fixed run configuration: one hour bars, the evaluation window, one seed."""
    found = _discovered() if strategies is None else strategies
    adaptee = _strategy_class(strategy_id, found)
    return RunConfig.model_validate(
        {
            "run_name": run_name or f"acceptance-{strategy_id}",
            "strategy_id": strategy_id,
            "params": {},
            "symbol": SYMBOL,
            "exchange": EXCHANGE,
            "timeframe": TIMEFRAME,
            "market_type": "futures",
            "data_source": DATA_SOURCE,
            "start": BASE,
            "end": BASE + timedelta(hours=EVALUATION_HOURS),
            "initial_capital": Decimal("10000"),
            "risk_per_trade": 0.01,
            "money_management": dict(money_management),
            "cost_values": {
                "futures_taker_fee_rate": Decimal("0.0004"),
                "futures_entry_slippage_rate": Decimal("0"),
                "exit_slippage_rate": Decimal("0"),
                "funding_fallback_rate": Decimal("0"),
            },
            "profile_ref": adaptee.get_metadata().profile.id,
            "seed": 7,
        }
    )


def run_strategy(
    strategy_id: str,
    money_management: Mapping[str, object],
    root: Path,
    *,
    run_name: str | None = None,
) -> RunResult:
    """Run one strategy under one policy configuration on the synthetic path."""
    found = _discovered()
    candles = synthetic_hourly_candles()
    config = run_config(strategy_id, money_management, run_name=run_name, strategies=found)
    costs = BacktestCostModel(config.cost_values)
    engine = Engine(
        SyntheticFeed(candles),
        BacktestBroker(costs),
        BacktestClock.from_candles(candles),
        costs,
        BacktestEvidenceSink(root),
        MemoryCatalog(),
        manager(found),
        prereg={
            "hypothesis": f"{strategy_id} trades its document rules on the synthetic path",
            "primary_metric": "pf",
            "success_threshold": 1.3,
            "failure_threshold": 1.0,
            "edge_distinguishable": True,
            "higher_is_better": True,
        },
    )
    return engine.run(config)


@dataclass(frozen=True)
class DryRunReport:
    """What step 6 of the pre-deployment check reports for one strategy and mode."""

    strategy_id: str
    mode: str
    integrity_status: str
    trade_count: int
    exit_reasons: Mapping[str, int]
    warmup_candles: int
    evidence_hash: str
    hashes_match: bool
    warning: str | None


def _read_report(strategy_id: str, mode: str, first: RunResult, second: RunResult) -> DryRunReport:
    with sqlite3.connect(first.evidence_path) as connection:
        (warmup_candles,) = connection.execute(
            "SELECT warmup_candles FROM BACKTEST_RUN_LOCAL"
        ).fetchone()
        exit_rows = connection.execute(
            "SELECT exit_reason, COUNT(*) FROM TRADE GROUP BY exit_reason ORDER BY exit_reason"
        ).fetchall()
    exit_reasons = {str(reason): int(count) for reason, count in exit_rows}
    trade_count = sum(exit_reasons.values())
    return DryRunReport(
        strategy_id=strategy_id,
        mode=mode,
        integrity_status=first.integrity_status,
        trade_count=trade_count,
        exit_reasons=exit_reasons,
        warmup_candles=int(warmup_candles),
        evidence_hash=first.evidence_hash,
        hashes_match=first.evidence_hash == second.evidence_hash,
        warning=None if trade_count else "no trade on the synthetic path",
    )


def dry_run(
    strategy_id: str,
    mode: str,
    settings: Mapping[str, object] | None = None,
) -> DryRunReport:
    """Run the strategy twice under ``mode`` and report; Evidence files are removed.

    The mode given here is the mode that runs. A ``mode`` inside ``settings`` is refused
    rather than allowed to select another policy behind the report's label.
    """
    extra = dict(settings or {})
    if "mode" in extra:
        raise ValueError("settings must not carry 'mode'; the mode is given separately")
    money_management = {"mode": mode, **extra}
    with tempfile.TemporaryDirectory(prefix="synthetic-dry-run-") as directory:
        root = Path(directory)
        first = run_strategy(strategy_id, money_management, root / "first")
        second = run_strategy(
            strategy_id, money_management, root / "second", run_name=f"again-{strategy_id}"
        )
        return _read_report(strategy_id, mode, first, second)


_USAGE = (
    "usage: python -m backtest_service.diagnostics.synthetic_dry_run "
    "<strategy-id> <mode> [<settings.json>]"
)


def main(argv: Sequence[str] | None = None) -> int:
    """Print one JSON report, or one JSON error with exit code 1."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) not in {2, 3}:
        print(json.dumps({"error": _USAGE}))
        return 1
    strategy_id, mode, *rest = arguments
    try:
        settings: Mapping[str, object] | None = None
        if rest:
            loaded = json.loads(Path(rest[0]).read_text())
            if not isinstance(loaded, dict):
                raise ValueError("settings file must hold a JSON object")
            settings = loaded
        report = dry_run(strategy_id, mode, settings)
    except (Exception, SystemExit) as error:  # noqa: BLE001 - a diagnostic reports, never raises
        print(json.dumps({"error": f"{type(error).__name__}: {error}"}))
        return 1
    print(json.dumps(asdict(report), sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through main() in tests
    sys.exit(main())
