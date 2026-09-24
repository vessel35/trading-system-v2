"""Run the three document-sourced strategies through the Engine on a synthetic feed.

This is the stage 3-1 acceptance regression: a strategy placed as a file, with the policy it
declares, must load through the deployed-plugin registry, trade, and leave complete Evidence,
without touching a database.
"""

from __future__ import annotations

import math
import random
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from backtest_service.adapters.broker import BacktestBroker
from backtest_service.adapters.catalog_store import DeterminismReference
from backtest_service.adapters.clock import BacktestClock
from backtest_service.adapters.cost_model import BacktestCostModel
from backtest_service.adapters.evidence_sink import BacktestEvidenceSink
from backtest_service.config import RunConfig
from backtest_service.engine import Engine, RunResult
from core_lib.ports import CatalogStore, DataFeed, StrategyRegistry
from core_lib.strategy import AdapterManager, InProcessStrategyRegistry, StrategyAdapter
from core_lib.types import Candle
from trading_plugins import registered_money_management
from trading_plugins.strategies.bollinger_rsi_reversion import BollingerRsiReversion
from trading_plugins.strategies.donchian_breakout_atr import DonchianBreakoutAtr
from trading_plugins.strategies.macd_ema200_zero_line import MacdEma200ZeroLine
from trading_plugins.strategies.supertrend_ema200_flip import SupertrendEma200Flip

_BASE = datetime(2026, 1, 1, 1, tzinfo=UTC)
_WARMUP_HOURS = 320
_EVALUATION_HOURS = 240
_SYMBOL = "BTCUSDT"

_STRATEGIES: dict[str, type[StrategyAdapter]] = {
    "supertrend-ema200-flip": SupertrendEma200Flip,
    "macd-ema200-zero-line": MacdEma200ZeroLine,
    "bollinger-rsi-reversion": BollingerRsiReversion,
    "donchian-breakout-atr": DonchianBreakoutAtr,
}
# The longest declared warm-up: EMA 200 for the two trend strategies, Bollinger 20 for the
# reversion strategy, and the 21 bars the breakout strategy reads back from the candles.
_EXPECTED_WARMUP = {
    "supertrend-ema200-flip": 200,
    "macd-ema200-zero-line": 200,
    "bollinger-rsi-reversion": 20,
    "donchian-breakout-atr": 21,
}
# Strategies whose document leaves every exit to the policy's stop and target.
_PROTECTION_ONLY = {"macd-ema200-zero-line", "donchian-breakout-atr"}
_MONEY_MANAGEMENT: dict[str, dict[str, object]] = {
    "supertrend-ema200-flip": {
        "mode": "signal-exit-atr",
        "atr_period": 14,
        "atr_stop_multiple": 2.5,
        "leverage_cap": 5,
    },
    "macd-ema200-zero-line": {
        "mode": "manual",
        "leverage": 1,
        "reward_risk": 1.5,
        "atr_stop_multiple": 2.5,
    },
    "bollinger-rsi-reversion": {
        "mode": "signal-exit-atr",
        "atr_period": 14,
        "atr_stop_multiple": 2.5,
        "leverage_cap": 5,
    },
    "donchian-breakout-atr": {
        "mode": "manual",
        "leverage": 1,
        "reward_risk": 2.0,
        "atr_stop_multiple": 1.5,
    },
}
_DECLARED_KEYS: dict[str, set[str]] = {
    "supertrend-ema200-flip": {"supertrend:multiplier=3,period=10@1h", "ema:period=200@1h"},
    "macd-ema200-zero-line": {
        "macd:fast_period=12,signal_period=9,slow_period=26@1h",
        "ema:period=200@1h",
    },
    "bollinger-rsi-reversion": {
        "bollinger_bands:multiplier=2,period=20@1h",
        "rsi:period=14@1h",
    },
    # The breakout strategy declares no series; only the policy's ATR reaches the run.
    "donchian-breakout-atr": set(),
}


def synthetic_hourly_candles(seed: int = 20260923) -> list[Candle]:
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


class DeployedRows(StrategyRegistry):
    """Return the registration rows the 20260923 scripts would insert, minus lifecycle."""

    def get(self, strategy_id: str) -> dict[str, object]:
        adaptee = _STRATEGIES[strategy_id]
        return {
            "strategy_id": strategy_id,
            "class_name": adaptee.__name__,
            "module_path": adaptee.__module__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get(strategy_id) for strategy_id in _STRATEGIES]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError("read-only fixture")


def _manager() -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    for strategy_id, adaptee in _STRATEGIES.items():
        plugins.register(strategy_id, adaptee)
    return AdapterManager(
        DeployedRows(), plugins, money_management_policies=registered_money_management()
    )


def run_config(strategy_id: str, *, run_name: str | None = None) -> RunConfig:
    adaptee = _STRATEGIES[strategy_id]
    return RunConfig.model_validate(
        {
            "run_name": run_name or f"acceptance-{strategy_id}",
            "strategy_id": strategy_id,
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
            "money_management": _MONEY_MANAGEMENT[strategy_id],
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


def run_strategy(strategy_id: str, root: Path, *, run_name: str | None = None) -> RunResult:
    candles = synthetic_hourly_candles()
    config = run_config(strategy_id, run_name=run_name)
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
            "hypothesis": f"{strategy_id} trades its document rules on the synthetic path",
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


@pytest.mark.parametrize("strategy_id", sorted(_STRATEGIES))
def test_document_sourced_strategy_runs_end_to_end_with_complete_evidence(
    tmp_path: Path, strategy_id: str
) -> None:
    result = run_strategy(strategy_id, tmp_path / "first")
    assert result.integrity_status == "passed"

    definitions = _rows(result.evidence_path, "SELECT indicator_key FROM INDICATOR_DEFINITION")
    defined = {row[0] for row in definitions}
    assert _DECLARED_KEYS[strategy_id] <= defined
    assert "atr:period=14@1h" in defined

    (local,) = _rows(
        result.evidence_path,
        "SELECT strategy_id, money_management_json, warmup_candles FROM BACKTEST_RUN_LOCAL",
    )
    assert local[0] == strategy_id
    assert str(_MONEY_MANAGEMENT[strategy_id]["mode"]) in str(local[1])
    assert local[2] == _EXPECTED_WARMUP[strategy_id]

    trades = _rows(
        result.evidence_path,
        "SELECT side, exit_reason, entry_price, exit_price, net_pnl FROM TRADE ORDER BY entry_time",
    )
    assert trades, "the synthetic path must produce at least one trade"
    exit_reasons = {row[1] for row in trades}
    if strategy_id in _PROTECTION_ONLY:
        assert exit_reasons <= {"STOP_LOSS", "TAKE_PROFIT", "END_OF_DATA"}
        assert exit_reasons & {"STOP_LOSS", "TAKE_PROFIT"}
    else:
        assert "SIGNAL_EXIT" in exit_reasons

    skip_reasons = {
        row[0]
        for row in _rows(
            result.evidence_path,
            "SELECT DISTINCT skip_reason FROM DECISION WHERE action = 'skip'",
        )
    }
    assert skip_reasons, "held and filtered bars must leave their reasons"

    again = run_strategy(strategy_id, tmp_path / "second", run_name=f"again-{strategy_id}")
    assert again.evidence_hash == result.evidence_hash
    assert again.integrity_status == "passed"


def test_the_three_strategies_trade_differently_on_the_same_path(tmp_path: Path) -> None:
    counts = {}
    for strategy_id in _STRATEGIES:
        result = run_strategy(strategy_id, tmp_path / strategy_id)
        counts[strategy_id] = len(_rows(result.evidence_path, "SELECT trade_id FROM TRADE"))
    assert all(count >= 1 for count in counts.values()), counts
    assert len(set(counts.values())) >= 2, counts
