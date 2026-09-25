"""Run the Bollinger band bounce strategy through the Engine on a synthetic feed.

This is the stage 3-1 acceptance regression for the sixth document-sourced strategy: the
file placed under ``trading_plugins.strategies``, with the manual policy it declares and
the settings its source fixes (1.5 ATR stop, 1.5R target) carried in its own
``default_settings``, must load through the deployed registry, fill a run submitted with
no settings from that declaration, trade, exit only through the policy's stop and target,
and leave complete Evidence without touching a database.

The fixture is self-contained. This service runs pytest with ``--import-mode=importlib``,
under which test modules cannot import each other, so the synthetic path and the in-memory
ports are written here rather than shared with the earlier acceptance modules.
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
from trading_plugins.strategies.bollinger_band_bounce import STRATEGY_ID, BollingerBandBounce

_BASE = datetime(2026, 1, 1, 1, tzinfo=UTC)
_WARMUP_HOURS = 48
_EVALUATION_HOURS = 240
_SYMBOL = "BTCUSDT"
_BANDS_KEY = "bollinger_bands:multiplier=2,period=20@1h"
_ATR_KEY = "atr:period=14@1h"
# The strategy's Bollinger Bands need twenty bars and the manual policy's ATR(14) fourteen;
# the engine must prepare the larger of the two.
_EXPECTED_WARMUP = 20
# The submission names only the mode. The stop multiple and the reward ratio the source
# fixes must come from the strategy's own declaration, not from this test.
_SUBMITTED_MONEY_MANAGEMENT: dict[str, object] = {"mode": "manual"}
_ENTRY_REASONS = {"bounce-lower-band-touch-long": "LONG", "bounce-upper-band-touch-short": "SHORT"}


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
    """Return the registration row the 20260923/07 script would insert, minus lifecycle."""

    def get(self, strategy_id: str) -> dict[str, object]:
        if strategy_id != STRATEGY_ID:
            raise KeyError(strategy_id)
        return {
            "strategy_id": STRATEGY_ID,
            "class_name": BollingerBandBounce.__name__,
            "module_path": BollingerBandBounce.__module__,
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
    plugins.register(STRATEGY_ID, BollingerBandBounce)
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
            "money_management": _SUBMITTED_MONEY_MANAGEMENT,
            "cost_values": {
                "futures_taker_fee_rate": Decimal("0.0005"),
                "futures_entry_slippage_rate": Decimal("0"),
                "exit_slippage_rate": Decimal("0"),
                "funding_fallback_rate": Decimal("0"),
            },
            "profile_ref": BollingerBandBounce.get_metadata().profile.id,
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


def _epoch_ms_to_datetime(raw: object) -> datetime:
    # The sink stores every datetime as epoch milliseconds.
    assert isinstance(raw, int)
    return datetime.fromtimestamp(raw / 1_000, tz=UTC)


def test_a_run_submitted_with_only_the_mode_reproduces_the_source_settings() -> None:
    config = run_config(run_name="declared-settings")
    assert config.money_management.model_dump() == {
        "mode": "manual",
        "leverage": 1,
        "reward_risk": 1.5,
        "atr_stop_multiple": 1.5,
    }
    assert dict(config.money_management_submitted) == {"mode": "manual"}


def test_bollinger_band_bounce_runs_end_to_end_with_complete_evidence(tmp_path: Path) -> None:
    result = run_strategy(tmp_path / "first", run_name="acceptance-bollinger-band-bounce")
    assert result.integrity_status == "passed"

    # The strategy's bands and the manual policy's ATR(14) are the whole series union.
    definitions = _rows(result.evidence_path, "SELECT indicator_key FROM INDICATOR_DEFINITION")
    assert {row[0] for row in definitions} == {_BANDS_KEY, _ATR_KEY}

    (local,) = _rows(
        result.evidence_path,
        "SELECT strategy_id, money_management_json, submitted_money_management_json, "
        "warmup_candles FROM BACKTEST_RUN_LOCAL",
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
    assert money_management["declared_by_strategy"] == {
        "atr_stop_multiple": 1.5,
        "reward_risk": 1.5,
    }
    assert json.loads(str(local[2])) == {"mode": "manual"}
    assert local[3] == _EXPECTED_WARMUP

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
    assert "bounce-inside-bands" in skip_reasons
    assert "bounce-protection-owns-exit" in skip_reasons

    again = run_strategy(tmp_path / "second", run_name="again-bollinger-band-bounce")
    assert again.evidence_hash == result.evidence_hash
    assert again.integrity_status == "passed"


def test_every_entry_follows_a_close_at_or_beyond_its_band(tmp_path: Path) -> None:
    """Reconcile each recorded entry with the band values and the candle it was decided on."""
    result = run_strategy(tmp_path / "reconcile", run_name="reconcile-bollinger-band-bounce")
    by_close_time = {candle.close_time: candle for candle in synthetic_hourly_candles()}
    snapshots = {
        (row[0], row[1]): row[2]
        for row in _rows(
            result.evidence_path,
            "SELECT indicator_key, feature_ts, COALESCE(value_json, value) "
            "FROM INDICATOR_SNAPSHOT WHERE is_warmup = 0",
        )
    }
    entries = _rows(
        result.evidence_path,
        "SELECT decision_ts, reason, price, derived_side FROM SIGNAL WHERE reason IN "
        "('bounce-lower-band-touch-long', 'bounce-upper-band-touch-short') ORDER BY decision_ts",
    )
    assert entries
    for raw_ts, reason, price, side in entries:
        assert isinstance(reason, str) and isinstance(price, float)
        assert side == _ENTRY_REASONS[reason]
        decided = _epoch_ms_to_datetime(raw_ts)
        assert math.isclose(price, by_close_time[decided].close, rel_tol=1e-12)
        bands = json.loads(str(snapshots[(_BANDS_KEY, raw_ts)]))
        if reason == "bounce-lower-band-touch-long":
            assert price <= bands["lower"]
        else:
            assert price >= bands["upper"]


def test_every_entry_carries_the_source_stop_and_target(tmp_path: Path) -> None:
    """The stop sits 1.5 ATR(14) from the deciding close and the target 1.5 stop distances."""
    result = run_strategy(tmp_path / "protection", run_name="protection-bollinger-band-bounce")
    atr_by_ts = {
        row[0]: row[1]
        for row in _rows(
            result.evidence_path,
            f"SELECT feature_ts, value FROM INDICATOR_SNAPSHOT "
            f"WHERE indicator_key = '{_ATR_KEY}' AND is_warmup = 0",
        )
    }
    entries = _rows(
        result.evidence_path,
        "SELECT decision_ts, price, stop_loss, take_profit, derived_side FROM SIGNAL "
        "WHERE derived_intent = 'enter' ORDER BY decision_ts",
    )
    assert entries
    for raw_ts, price, stop_loss, take_profit, side in entries:
        assert isinstance(price, float)
        assert isinstance(stop_loss, float) and isinstance(take_profit, float)
        atr = atr_by_ts[raw_ts]
        assert isinstance(atr, float)
        direction = 1.0 if side == "LONG" else -1.0
        stop_distance = 1.5 * atr
        assert math.isclose(stop_loss, price - direction * stop_distance, rel_tol=1e-9)
        assert math.isclose(take_profit, price + direction * 1.5 * stop_distance, rel_tol=1e-9)
