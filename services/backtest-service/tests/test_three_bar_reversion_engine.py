"""Run the three-bar mean-reversion strategy through the Engine on a synthetic feed.

This is the stage 3-1 acceptance regression for the fifth document-sourced strategy: the
file placed under ``trading_plugins.strategies``, with the manual policy it declares and
the settings its source fixes (1.5 ATR stop, 1.5R target), must load through the deployed
registry, trade, exit only through the policy's stop and target, and leave complete
Evidence without touching a database.

The fixture is self-contained. This service runs pytest with ``--import-mode=importlib``,
under which test modules cannot import each other, so the synthetic path and the in-memory
ports are written here rather than shared with the earlier acceptance module.
"""

from __future__ import annotations

import json
import math
import random
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from backtest_service.adapters.broker import BacktestBroker
from backtest_service.adapters.catalog_store import DeterminismReference
from backtest_service.adapters.clock import BacktestClock
from backtest_service.adapters.cost_model import BacktestCostModel
from backtest_service.adapters.evidence_sink import BacktestEvidenceSink
from backtest_service.config import RunConfig
from backtest_service.engine import Engine, RunResult
from core_lib.ports import CatalogStore, DataFeed, StrategyRegistry
from core_lib.strategy import AdapterManager, InProcessStrategyRegistry
from core_lib.types import Candle
from trading_plugins import registered_money_management
from trading_plugins.strategies.three_bar_reversion import STRATEGY_ID, ThreeBarReversion

_BASE = datetime(2026, 1, 1, 1, tzinfo=UTC)
_WARMUP_HOURS = 48
_EVALUATION_HOURS = 240
_SYMBOL = "BTCUSDT"
# The strategy declares no series and reads three bars; the manual policy's ATR(14) is the
# longest requirement, so the engine must prepare fourteen bars.
_EXPECTED_WARMUP = 14
# The settings the source document fixes; the strategy cannot carry them itself.
_MONEY_MANAGEMENT: dict[str, object] = {
    "mode": "manual",
    "leverage": 1,
    "reward_risk": 1.5,
    "atr_stop_multiple": 1.5,
}


def synthetic_hourly_candles(seed: int = 20260925) -> list[Candle]:
    """Return a deterministic hourly path with alternating regimes and volatility shocks."""
    rng = random.Random(seed)
    first_open = _BASE - timedelta(hours=_WARMUP_HOURS)
    candles: list[Candle] = []
    price = 100.0
    for index in range(_WARMUP_HOURS + _EVALUATION_HOURS):
        drift = 0.0012 * math.sin(2.0 * math.pi * index / 160.0)
        shock = rng.gauss(0.0, 0.008)
        open_price = price
        price = price * math.exp(drift + shock)
        high = max(open_price, price) * (1.0 + abs(rng.gauss(0.0, 0.002)))
        low = min(open_price, price) * (1.0 - abs(rng.gauss(0.0, 0.002)))
        opened = first_open + timedelta(hours=index)
        candles.append(
            Candle(
                symbol=_SYMBOL,
                exchange="binance",
                timeframe="1h",
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


def _minute_candles(candles: list[Candle]) -> list[Candle]:
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
    """Serve the hourly path, its synthesized minutes, and a mark price from the last close."""

    def __init__(self, candles: list[Candle]) -> None:
        self._candles = list(candles)
        self._minutes = _minute_candles(candles)

    def candles(self, symbol: str, tf: str, up_to: datetime) -> list[Candle]:
        assert symbol == _SYMBOL
        source = self._minutes if tf == "1m" else self._candles
        assert tf in {"1m", "1h"}
        return [candle for candle in source if candle.close_time <= up_to]

    def source_candles(
        self, symbol: str, range_start: datetime, range_end: datetime
    ) -> tuple[Candle, ...]:
        assert symbol == _SYMBOL
        return tuple(
            candle
            for candle in self._minutes
            if range_start <= candle.open_time and candle.close_time <= range_end
        )

    def funding(self, symbol: str, at: datetime) -> Decimal:
        del symbol, at
        raise LookupError("no boundary funding in this fixture")

    def mark_price(self, symbol: str, at: datetime) -> Decimal:
        assert symbol == _SYMBOL
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
        assert isinstance(run, Mapping)
        sequence = self.next_sequence
        self.next_sequence += 1
        run_id = f"BT_20260925_{sequence:06d}_{run['run_name']}"
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


class DeployedRow(StrategyRegistry):
    """Return the registration row the 20260923/06 script would insert, minus lifecycle."""

    def get(self, strategy_id: str) -> dict[str, object]:
        if strategy_id != STRATEGY_ID:
            raise KeyError(strategy_id)
        return {
            "strategy_id": STRATEGY_ID,
            "class_name": ThreeBarReversion.__name__,
            "module_path": ThreeBarReversion.__module__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get(STRATEGY_ID)]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError("read-only fixture")


def _manager() -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    plugins.register(STRATEGY_ID, ThreeBarReversion)
    return AdapterManager(
        DeployedRow(), plugins, money_management_policies=registered_money_management()
    )


def run_config(*, run_name: str) -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_name": run_name,
            "strategy_id": STRATEGY_ID,
            "params": {},
            "symbol": _SYMBOL,
            "exchange": "binance",
            "timeframe": "1h",
            "market_type": "futures",
            "data_source": "synthetic-regime-fixture",
            "start": _BASE,
            "end": _BASE + timedelta(hours=_EVALUATION_HOURS),
            "initial_capital": Decimal("10000"),
            "risk_per_trade": 0.01,
            "money_management": _MONEY_MANAGEMENT,
            "cost_values": {
                "futures_taker_fee_rate": Decimal("0.0005"),
                "futures_entry_slippage_rate": Decimal("0"),
                "exit_slippage_rate": Decimal("0"),
                "funding_fallback_rate": Decimal("0"),
            },
            "profile_ref": ThreeBarReversion.get_metadata().profile.id,
            "seed": 7,
        }
    )


def run_strategy(root: Path, *, run_name: str) -> RunResult:
    candles = synthetic_hourly_candles()
    config = run_config(run_name=run_name)
    costs = BacktestCostModel(config.cost_values)
    engine = Engine(
        SyntheticFeed(candles),
        BacktestBroker(costs),
        BacktestClock.from_candles(candles),
        costs,
        BacktestEvidenceSink(root),
        MemoryCatalog(),
        _manager(),
        prereg={
            "hypothesis": f"{STRATEGY_ID} trades its document rule on the synthetic path",
            "primary_metric": "pf",
            "success_threshold": 1.3,
            "failure_threshold": 1.0,
            "edge_distinguishable": True,
            "higher_is_better": True,
        },
    )
    return engine.run(config)


def _rows(path: str, query: str) -> list[tuple[object, ...]]:
    with sqlite3.connect(path) as connection:
        return connection.execute(query).fetchall()


def test_three_bar_reversion_runs_end_to_end_with_complete_evidence(tmp_path: Path) -> None:
    result = run_strategy(tmp_path / "first", run_name="acceptance-three-bar-reversion")
    assert result.integrity_status == "passed"

    # The strategy declares no series; only the manual policy's ATR(14) reaches the run.
    definitions = _rows(result.evidence_path, "SELECT indicator_key FROM INDICATOR_DEFINITION")
    assert {row[0] for row in definitions} == {"atr:period=14@1h"}

    (local,) = _rows(
        result.evidence_path,
        "SELECT strategy_id, money_management_json, warmup_candles FROM BACKTEST_RUN_LOCAL",
    )
    assert local[0] == STRATEGY_ID
    money_management = json.loads(str(local[1]))
    assert money_management["policy_id"] == "manual"
    assert money_management["policy_version"] == "1.0.0"
    assert money_management["resolved_config"] == {
        "mode": "manual",
        "leverage": 1,
        "reward_risk": 1.5,
        "atr_stop_multiple": 1.5,
    }
    assert local[2] == _EXPECTED_WARMUP

    trades = _rows(
        result.evidence_path,
        "SELECT side, exit_reason, entry_price, exit_price, net_pnl FROM TRADE ORDER BY entry_time",
    )
    assert trades, "the synthetic path must produce at least one trade"
    assert {row[0] for row in trades} == {"LONG", "SHORT"}, "both directions must trade"
    exit_reasons = {row[1] for row in trades}
    assert exit_reasons <= {"STOP_LOSS", "TAKE_PROFIT", "END_OF_DATA"}
    assert exit_reasons & {"STOP_LOSS", "TAKE_PROFIT"}

    skip_reasons = {
        row[0]
        for row in _rows(
            result.evidence_path,
            "SELECT DISTINCT skip_reason FROM DECISION WHERE action = 'skip'",
        )
    }
    assert "three-bar-no-streak" in skip_reasons
    assert "three-bar-protection-owns-exit" in skip_reasons

    again = run_strategy(tmp_path / "second", run_name="again-three-bar-reversion")
    assert again.evidence_hash == result.evidence_hash
    assert again.integrity_status == "passed"


def test_every_entry_follows_three_same_coloured_bars(tmp_path: Path) -> None:
    """Reconcile each recorded entry decision with the raw candles it was decided on."""
    result = run_strategy(tmp_path / "reconcile", run_name="reconcile-three-bar-reversion")
    by_close_time = {candle.close_time: candle for candle in synthetic_hourly_candles()}
    ordered = sorted(by_close_time)
    entries = _rows(
        result.evidence_path,
        "SELECT decision_ts, reason FROM SIGNAL WHERE reason IN "
        "('three-red-bars-buy', 'three-green-bars-sell-short') ORDER BY decision_ts",
    )
    assert entries
    for raw_ts, reason in entries:
        # The sink stores every datetime as epoch milliseconds.
        assert isinstance(raw_ts, int)
        decided = datetime.fromtimestamp(raw_ts / 1_000, tz=UTC)
        position = ordered.index(decided)
        last_three = [by_close_time[ordered[position - offset]] for offset in (2, 1, 0)]
        if reason == "three-red-bars-buy":
            assert all(candle.close < candle.open for candle in last_three)
        else:
            assert all(candle.close > candle.open for candle in last_three)
