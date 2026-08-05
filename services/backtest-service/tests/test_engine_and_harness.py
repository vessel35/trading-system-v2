"""Verify the deterministic Engine loop, timing Evidence, hash parity, and Harness."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path
from typing import ClassVar, cast

import pytest
from backtest_service.adapters.broker import BacktestBroker
from backtest_service.adapters.catalog_store import DeterminismReference
from backtest_service.adapters.clock import BacktestClock
from backtest_service.adapters.cost_model import BacktestCostModel
from backtest_service.adapters.evidence_schema import canonical_json
from backtest_service.adapters.evidence_sink import BacktestEvidenceSink
from backtest_service.config import RunConfig
from backtest_service.engine import Engine, RunResult
from backtest_service.harness import Harness
from core_lib.eval import MetricSet
from core_lib.eval import thresholds as evaluation_thresholds
from core_lib.indicators import DEFAULT_REGISTRY
from core_lib.patterns import TALIB_FUNCTIONS, TALIB_SOURCE_VERSION
from core_lib.ports import CatalogStore, DataFeed, StrategyRegistry
from core_lib.strategy import (
    AdapterManager,
    InProcessStrategyRegistry,
    ParameterSchema,
    ResolvedConfig,
    StrategyMetadata,
    StrategyProfile,
)
from core_lib.strategy.adaptees import STRATEGY_ID as VESSEL_STRATEGY_ID
from core_lib.strategy.adaptees import VesselReference
from core_lib.types import (
    Candle,
    Fill,
    MarketType,
    OrderRequest,
    Position,
    PositionSide,
    TradingSignal,
)

_BASE = datetime(2026, 1, 1, 1, tzinfo=UTC)


def _candles() -> list[Candle]:
    preload = tuple((100.0, 101.0, 99.0, 100.0) for _ in range(9))
    evaluation = (
        (100.0, 102.0, 99.0, 100.0),
        (101.0, 104.0, 95.0, 103.0),
        (104.0, 106.0, 96.0, 105.0),
        (106.0, 108.0, 97.0, 107.0),
    )
    prices = preload + evaluation
    return [
        Candle(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe="1h",
            open_time=_BASE - timedelta(hours=9) + timedelta(hours=index),
            close_time=_BASE - timedelta(hours=9) + timedelta(hours=index + 1),
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=100.0,
            quote_volume=10_000.0,
            trade_count=10,
        )
        for index, (open_price, high, low, close) in enumerate(prices)
    ]


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


class _Feed(DataFeed):
    def __init__(self, candles: list[Candle]) -> None:
        self._candles = list(candles)
        self._minute_candles = _minute_candles(candles)
        self.candle_calls = 0

    def candles(self, symbol: str, tf: str, up_to: datetime) -> list[Candle]:
        assert symbol == "BTCUSDT"
        self.candle_calls += 1
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
        raise LookupError("no boundary funding in this fixture")

    def mark_price(self, symbol: str, at: datetime) -> Decimal:
        del symbol, at
        return Decimal("100")


class _VesselTurtleFeed(_Feed):
    """Expose separate finalized daily candles for Turtle N."""

    def __init__(self, candles: list[Candle], daily: list[Candle]) -> None:
        super().__init__(candles)
        self._daily = daily

    def candles(self, symbol: str, tf: str, up_to: datetime) -> list[Candle]:
        if tf == "1d":
            assert symbol == "BTCUSDT"
            self.candle_calls += 1
            return [candle for candle in self._daily if candle.close_time <= up_to]
        return super().candles(symbol, tf, up_to)


class _OriginMismatchFeed(_Feed):
    def source_candles(
        self,
        symbol: str,
        range_start: datetime,
        range_end: datetime,
    ) -> tuple[Candle, ...]:
        observed = list(super().source_candles(symbol, range_start, range_end))
        observed[0] = replace(observed[0], close=observed[0].close + 0.25)
        return tuple(observed)


class _DailyFeed(DataFeed):
    def __init__(
        self,
        candles: list[Candle],
        *,
        funding_rate: Decimal = Decimal("0.001"),
    ) -> None:
        self._candles = candles
        self._minute_candles = _minute_candles(candles)
        self._funding_rate = funding_rate

    def candles(self, symbol: str, tf: str, up_to: datetime) -> list[Candle]:
        assert symbol == "BTCUSDT"
        if tf == "1m":
            return [candle for candle in self._minute_candles if candle.close_time <= up_to]
        assert tf == "1d"
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
        assert symbol == "BTCUSDT"
        assert at.hour in {0, 8, 16}
        return self._funding_rate

    def mark_price(self, symbol: str, at: datetime) -> Decimal:
        del symbol, at
        return Decimal("100")


class _Strategy:
    VERSION: ClassVar[str] = "1.0.0"

    def __init__(self, config: ResolvedConfig) -> None:
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            required_indicators=[{"name": "EMA", "params": {"period": 9}}],
            min_history=1,
            supported_timeframes=["1h"],
            profile=StrategyProfile(
                id="engine-profile",
                family="breakout",
                bar="1h",
                expected_win_rate=(0.0, 1.0),
                expected_payoff=(0.0, 100.0),
                tail_shape="right_fat",
                holding_horizon="intraday",
                primary_metric="calmar",
                risk_adjusted_pref="sortino",
                profit_structure_to_preserve="net-profit",
                envelope_tolerance=1.0,
                envelope_status="provisional",
            ),
        )

    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        return ParameterSchema(fields={})

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> TradingSignal | None:
        candle = market_data["candle"]
        candles = market_data["candles"]
        assert isinstance(candle, Candle)
        assert isinstance(candles, list)
        if candle.open_time == _BASE and current_position is None:
            return TradingSignal(
                symbol=candle.symbol,
                timestamp=candle.close_time,
                confidence=0.8,
                price=candle.close,
                stop_loss=90.0,
                take_profit=120.0,
                market_type=MarketType.FUTURES,
                leverage=1,
                reason="fixture-entry",
                metadata={"fixture": True},
            )
        if candle.open_time == _BASE + timedelta(hours=2) and current_position is not None:
            return TradingSignal(
                symbol=candle.symbol,
                timestamp=candle.close_time,
                confidence=0.8,
                price=candle.close,
                stop_loss=None,
                take_profit=None,
                market_type=MarketType.FUTURES,
                leverage=1,
                reason="fixture-exit",
                metadata={"fixture": True},
            )
        return None


class _PatternStrategy(_Strategy):
    observed_indicators: ClassVar[list[dict[str, object]]] = []

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        metadata = super().get_metadata()
        metadata.required_indicators = [
            {"name": "EMA", "params": {"period": 9}},
            {"name": "pat_doji", "params": {}},
        ]
        return metadata

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> TradingSignal | None:
        indicators = market_data["indicators"]
        assert isinstance(indicators, Mapping)
        type(self).observed_indicators.append(dict(indicators))
        return super().analyze(market_data, current_position)


class _StrategyCatalog(StrategyRegistry):
    def get(self, strategy_id: str) -> dict[str, object]:
        assert strategy_id == "engine-fixture"
        return {
            "strategy_id": strategy_id,
            "class_name": _Strategy.__name__,
            "module_path": _Strategy.__module__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get("engine-fixture")]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError("read-only fixture")


class _PatternStrategyCatalog(StrategyRegistry):
    def get(self, strategy_id: str) -> dict[str, object]:
        assert strategy_id == "pattern-fixture"
        return {
            "strategy_id": strategy_id,
            "class_name": _PatternStrategy.__name__,
            "module_path": _PatternStrategy.__module__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get("pattern-fixture")]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError("read-only fixture")


class _ReversalStrategy(_Strategy):
    """Exercise the §4.2 opposite-protection reversal contract."""

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> TradingSignal | None:
        candle = market_data["candle"]
        assert isinstance(candle, Candle)
        if candle.open_time == _BASE and current_position is None:
            return TradingSignal(
                symbol=candle.symbol,
                timestamp=candle.close_time,
                confidence=0.8,
                price=candle.close,
                stop_loss=candle.close - 1.0,
                take_profit=candle.close + 50.0,
                market_type=MarketType.FUTURES,
                leverage=1,
                reason="reversal-fixture-long",
                metadata={"fixture": True},
            )
        if (
            candle.open_time == _BASE + timedelta(hours=2)
            and current_position is not None
            and current_position.side is PositionSide.LONG
        ):
            return TradingSignal(
                symbol=candle.symbol,
                timestamp=candle.close_time,
                confidence=0.8,
                price=candle.close,
                stop_loss=candle.close + 1.0,
                take_profit=candle.close - 50.0,
                market_type=MarketType.FUTURES,
                leverage=1,
                reason="reversal-fixture-short",
                metadata={"fixture": True},
            )
        return None


class _ReversalStrategyCatalog(StrategyRegistry):
    def get(self, strategy_id: str) -> dict[str, object]:
        assert strategy_id == "reversal-fixture"
        return {
            "strategy_id": strategy_id,
            "class_name": _ReversalStrategy.__name__,
            "module_path": _ReversalStrategy.__module__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get("reversal-fixture")]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError("read-only fixture")


class _DailyStrategy(_Strategy):
    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        metadata = super().get_metadata()
        metadata.supported_timeframes = ["1d"]
        return metadata

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> TradingSignal | None:
        candle = market_data["candle"]
        assert isinstance(candle, Candle)
        evaluation_start = datetime(2026, 1, 1, tzinfo=UTC)
        if candle.open_time == evaluation_start and current_position is None:
            return TradingSignal(
                symbol=candle.symbol,
                timestamp=candle.close_time,
                confidence=0.8,
                price=candle.close,
                stop_loss=90.0,
                take_profit=130.0,
                market_type=MarketType.FUTURES,
                leverage=1,
                reason="daily-entry",
                metadata={"fixture": True},
            )
        if (
            candle.open_time == evaluation_start + timedelta(days=1)
            and current_position is not None
        ):
            return TradingSignal(
                symbol=candle.symbol,
                timestamp=candle.close_time,
                confidence=0.8,
                price=candle.close,
                stop_loss=None,
                take_profit=None,
                market_type=MarketType.FUTURES,
                leverage=1,
                reason="daily-exit",
                metadata={"fixture": True},
            )
        return None


class _DailyStrategyCatalog(StrategyRegistry):
    def get(self, strategy_id: str) -> dict[str, object]:
        assert strategy_id == "daily-fixture"
        return {
            "strategy_id": strategy_id,
            "class_name": _DailyStrategy.__name__,
            "module_path": _DailyStrategy.__module__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get("daily-fixture")]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError("read-only fixture")


def _manager() -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    plugins.register("engine-fixture", _Strategy)
    return AdapterManager(_StrategyCatalog(), plugins)


def _pattern_manager() -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    plugins.register("pattern-fixture", _PatternStrategy)
    return AdapterManager(_PatternStrategyCatalog(), plugins)


def _reversal_manager() -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    plugins.register("reversal-fixture", _ReversalStrategy)
    return AdapterManager(_ReversalStrategyCatalog(), plugins)


def _daily_manager() -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    plugins.register("daily-fixture", _DailyStrategy)
    return AdapterManager(_DailyStrategyCatalog(), plugins)


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
        raise PermissionError("read-only fixture")


def _vessel_manager() -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    plugins.register(VESSEL_STRATEGY_ID, VesselReference)
    return AdapterManager(_VesselCatalog(), plugins)


def _vessel_candles() -> list[Candle]:
    """Return 21 warm-up plus six gap-free hourly evaluation candles."""
    first = _BASE - timedelta(hours=21)
    candles = []
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
    return candles


def _vessel_config(*, run_name: str = "vessel-dry-run") -> RunConfig:
    return RunConfig(
        run_name=run_name,
        strategy_id=VESSEL_STRATEGY_ID,
        params={},
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="1h",
        market_type="futures",
        data_source="gap-free-fixture",
        start=_BASE,
        end=_BASE + timedelta(hours=6),
        initial_capital=Decimal("10000"),
        risk_per_trade=0.01,
        cost_values={
            "futures_taker_fee_rate": Decimal("0"),
            "futures_entry_slippage_rate": Decimal("0"),
            "exit_slippage_rate": Decimal("0"),
            "funding_fallback_rate": Decimal("0"),
        },
        profile_ref="vessel-reference-v1",
        seed=17,
    )


def _turtle_daily_candles() -> list[Candle]:
    first = datetime(2025, 12, 11, tzinfo=UTC)
    candles = [
        Candle(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe="1d",
            open_time=first + timedelta(days=index),
            close_time=first + timedelta(days=index + 1),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=100.0,
            quote_volume=None,
            trade_count=None,
        )
        for index in range(21)
    ]
    candles.append(
        Candle(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe="1d",
            open_time=datetime(2026, 1, 1, tzinfo=UTC),
            close_time=datetime(2026, 1, 2, tzinfo=UTC),
            open=100.0,
            high=1_000.0,
            low=1.0,
            close=500.0,
            volume=100.0,
            quote_volume=None,
            trade_count=None,
        )
    )
    return candles


def _vessel_engine(
    root: Path,
    catalog: _Catalog,
    *,
    prereg: Mapping[str, object] | None = None,
) -> Engine:
    candles = _vessel_candles()
    config = _vessel_config()
    costs = BacktestCostModel(config.cost_values)
    return Engine(
        _Feed(candles),
        BacktestBroker(costs),
        BacktestClock.from_candles(candles),
        costs,
        BacktestEvidenceSink(root),
        catalog,
        _vessel_manager(),
        prereg=_prereg() if prereg is None else prereg,
    )


class _Catalog(CatalogStore):
    def __init__(self) -> None:
        self.next_sequence = 1
        self.events: list[str] = []
        self.preregs: list[object] = []
        self.summaries: list[object] = []
        self.aggregates: dict[str, dict[str, object]] = {}
        self.runs: dict[str, Mapping[str, object]] = {}
        self.force_config_mismatch = False
        self.comparison_hash_override: str | None = None

    def register(self, run: object) -> str:
        assert isinstance(run, Mapping)
        self.events.append("register")
        sequence = self.next_sequence
        self.next_sequence += 1
        run_id = f"BT_20260101_{sequence:06d}_{run['run_name']}"
        self.runs[run_id] = dict(run)
        return run_id

    def save_prereg(self, prereg: object) -> None:
        self.events.append("prereg")
        self.preregs.append(prereg)

    def upsert_summary(self, summary: object) -> None:
        self.events.append("summary")
        self.summaries.append(summary)

    def record_harness_aggregate(
        self,
        run_id: str,
        *,
        oos_degradation: float | None,
        psr: float | None,
        harness_json: object,
    ) -> None:
        self.aggregates[run_id] = {
            "oos_degradation": oos_degradation,
            "psr": psr,
            "harness_json": harness_json,
        }

    def reconcile_orphaned(self) -> int:
        self.events.append("reconcile")
        return 0

    def determinism_reference(
        self,
        run_id: str,
        config_hash: str,
        source_data_hash: str,
        evidence_schema_version: str,
    ) -> DeterminismReference:
        current_matches = (
            self.runs[run_id]["config_hash"] == config_hash and not self.force_config_mismatch
        )
        self.runs[run_id] = {
            **self.runs[run_id],
            "source_data_hash": source_data_hash,
        }
        for summary in reversed(self.summaries):
            assert isinstance(summary, Mapping)
            previous_id = summary["run_id"]
            if (
                previous_id != run_id
                and self.runs[str(previous_id)]["config_hash"] == config_hash
                and self.runs[str(previous_id)].get("source_data_hash") == source_data_hash
                and self.runs[str(previous_id)]["evidence_schema_version"]
                == evidence_schema_version
            ):
                return DeterminismReference(
                    current_matches,
                    True,
                    True,
                    True,
                    str(previous_id),
                    self.comparison_hash_override or str(summary["evidence_hash"]),
                )
        same_config_run_exists = any(
            previous_id != run_id and self.runs[str(previous_id)]["config_hash"] == config_hash
            for summary in self.summaries
            if isinstance(summary, Mapping)
            for previous_id in (summary["run_id"],)
        )
        same_schema_run_exists = any(
            previous_id != run_id
            and self.runs[str(previous_id)]["config_hash"] == config_hash
            and self.runs[str(previous_id)]["evidence_schema_version"] == evidence_schema_version
            for summary in self.summaries
            if isinstance(summary, Mapping)
            for previous_id in (summary["run_id"],)
        )
        return DeterminismReference(
            current_matches,
            True,
            same_config_run_exists,
            same_schema_run_exists,
            None,
            None,
        )


class _Broker(BacktestBroker):
    def __init__(self, cost_model: BacktestCostModel) -> None:
        super().__init__(cost_model)
        self.call_order: list[str] = []
        self.fills: list[Fill] = []
        self.available_margins: list[Decimal | None] = []

    def configure_execution(
        self,
        decision_candle: Candle,
        history: list[Candle],
        *,
        fill_timing: str = "next_bar",
        risk_budget: Decimal | None = None,
        available_margin: Decimal | None = None,
        leverage: int = 1,
    ) -> None:
        self.call_order.append("configure")
        self.available_margins.append(available_margin)
        super().configure_execution(
            decision_candle,
            history,
            fill_timing=fill_timing,
            risk_budget=risk_budget,
            available_margin=available_margin,
            leverage=leverage,
        )

    def submit(self, request: OrderRequest) -> Fill:
        self.call_order.append("submit")
        fill = super().submit(request)
        self.fills.append(fill)
        return fill


def _config(*, run_name: str = "engine") -> RunConfig:
    return RunConfig(
        run_name=run_name,
        strategy_id="engine-fixture",
        params={},
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="1h",
        market_type="futures",
        data_source="fixture",
        start=_BASE,
        end=_BASE + timedelta(hours=4),
        initial_capital=Decimal("10000"),
        risk_per_trade=0.01,
        cost_values={
            "futures_taker_fee_rate": Decimal("0"),
            "futures_entry_slippage_rate": Decimal("0"),
            "exit_slippage_rate": Decimal("0"),
            "funding_fallback_rate": Decimal("0"),
        },
        profile_ref="engine-profile",
    )


def _prereg() -> dict[str, object]:
    return {
        "hypothesis": "fixture should trade deterministically",
        "primary_metric": "pf",
        "success_threshold": 1.3,
        "failure_threshold": 1.0,
        "edge_distinguishable": True,
        "higher_is_better": True,
    }


def _engine(
    root: Path,
    catalog: _Catalog,
    brokers: list[_Broker],
    feeds: list[_Feed] | None = None,
    sinks: list[BacktestEvidenceSink] | None = None,
    *,
    candles: list[Candle] | None = None,
) -> Engine:
    history = _candles() if candles is None else candles
    costs = BacktestCostModel(_config().cost_values)
    broker = _Broker(costs)
    brokers.append(broker)
    feed = _Feed(history)
    if feeds is not None:
        feeds.append(feed)
    sink = BacktestEvidenceSink(root)
    if sinks is not None:
        sinks.append(sink)
    return Engine(
        feed,
        broker,
        BacktestClock.from_candles(history),
        costs,
        sink,
        catalog,
        _manager(),
        prereg=_prereg(),
    )


def _daily_engine(
    root: Path,
    catalog: _Catalog,
    sinks: list[BacktestEvidenceSink],
    *,
    funding_rate: Decimal = Decimal("0.001"),
    fee_rate: Decimal = Decimal("0"),
) -> tuple[Engine, RunConfig]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    history_start = start - timedelta(days=9)
    candles = [
        Candle(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe="1d",
            open_time=history_start + timedelta(days=index),
            close_time=history_start + timedelta(days=index + 1),
            open=100.0,
            high=105.0,
            low=95.0,
            close=100.0,
            volume=100.0,
            quote_volume=10_000.0,
            trade_count=10,
        )
        for index in range(12)
    ]
    config = RunConfig(
        run_name="daily",
        strategy_id="daily-fixture",
        params={},
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="1d",
        market_type="futures",
        data_source="fixture",
        start=start,
        end=start + timedelta(days=3),
        initial_capital=Decimal("10000"),
        risk_per_trade=0.01,
        cost_values={
            "futures_taker_fee_rate": fee_rate,
            "futures_entry_slippage_rate": Decimal("0"),
            "exit_slippage_rate": Decimal("0"),
            "funding_fallback_rate": Decimal("0"),
        },
        profile_ref="engine-profile",
    )
    costs = BacktestCostModel(config.cost_values)
    sink = BacktestEvidenceSink(root)
    sinks.append(sink)
    return (
        Engine(
            _DailyFeed(candles, funding_rate=funding_rate),
            _Broker(costs),
            BacktestClock.from_candles(candles),
            costs,
            sink,
            catalog,
            _daily_manager(),
            prereg=_prereg(),
        ),
        config,
    )


def _reversal_candles() -> list[Candle]:
    prices = [
        *((100.0, 100.5, 99.5, 100.0) for _ in range(9)),
        (100.0, 100.5, 99.5, 100.0),
        (101.0, 102.0, 100.5, 101.5),
        (102.0, 103.0, 101.0, 102.5),
        (103.0, 103.8, 102.5, 103.5),
    ]
    return [
        Candle(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe="1h",
            open_time=_BASE - timedelta(hours=9) + timedelta(hours=index),
            close_time=_BASE - timedelta(hours=8) + timedelta(hours=index),
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=100.0,
            quote_volume=10_000.0,
            trade_count=10,
        )
        for index, (open_price, high, low, close) in enumerate(prices)
    ]


def test_reversal_closes_then_enters_with_separate_once_only_costs_and_margin(
    tmp_path: Path,
) -> None:
    candles = _reversal_candles()
    config = RunConfig(
        run_name="reversal",
        strategy_id="reversal-fixture",
        params={},
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="1h",
        market_type="futures",
        data_source="fixture",
        start=_BASE,
        end=_BASE + timedelta(hours=4),
        initial_capital=Decimal("10000"),
        risk_per_trade=0.01,
        cost_values={
            "futures_taker_fee_rate": Decimal("0.0004"),
            "futures_entry_slippage_rate": Decimal("0"),
            "exit_slippage_rate": Decimal("0"),
            "funding_fallback_rate": Decimal("0"),
        },
        profile_ref="engine-profile",
    )
    costs = BacktestCostModel(config.cost_values)
    broker = _Broker(costs)
    result = Engine(
        _Feed(candles),
        broker,
        BacktestClock.from_candles(candles),
        costs,
        BacktestEvidenceSink(tmp_path),
        _Catalog(),
        _reversal_manager(),
        prereg=_prereg(),
    ).run(config)

    assert result.integrity_status == "passed"
    assert len(broker.fills) == 4
    assert broker.fills[2].qty_truncated is True
    cash_before_exit = broker.available_margins[1]
    cash_after_exit = broker.available_margins[2]
    assert cash_before_exit is not None
    assert cash_after_exit is not None
    assert cash_after_exit > cash_before_exit
    reverse_entry = broker.fills[2]
    amount_quantum = Decimal("0.00000001")
    reverse_notional = (reverse_entry.price * reverse_entry.quantity).quantize(amount_quantum)
    reverse_requirement = (reverse_notional + reverse_entry.fee * 2).quantize(amount_quantum)
    next_notional = (reverse_entry.price * (reverse_entry.quantity + amount_quantum)).quantize(
        amount_quantum
    )
    next_fee = (next_notional * Decimal("0.0004")).quantize(amount_quantum)
    next_requirement = (next_notional + next_fee * 2).quantize(amount_quantum)
    assert reverse_requirement <= cash_after_exit < next_requirement

    with sqlite3.connect(result.evidence_path) as connection:
        assert connection.execute(
            """
            SELECT action, intended_side
            FROM DECISION
            WHERE action IN ('enter', 'reverse')
            ORDER BY decision_id
            """
        ).fetchall() == [("enter", "LONG"), ("reverse", "SHORT")]
        reversal = connection.execute(
            """
            SELECT decision_id, decision_ts
            FROM DECISION
            WHERE action = 'reverse'
            """
        ).fetchone()
        assert reversal is not None
        reversal_id, decision_ts = reversal
        reversal_fills = connection.execute(
            """
            SELECT execution_ts, reduce_only, position_side, exit_reason
            FROM EXECUTION
            WHERE decision_id = ?
            ORDER BY execution_id
            """,
            (reversal_id,),
        ).fetchall()
        assert len(reversal_fills) == 2
        execution_ts = reversal_fills[0][0]
        assert reversal_fills == [
            (execution_ts, 1, "LONG", "REVERSAL"),
            (execution_ts, 0, "SHORT", None),
        ]
        assert decision_ts < execution_ts

        trades = connection.execute(
            """
            SELECT t.exit_reason, t.total_fee, entry.fee + exit.fee,
                   t.net_pnl,
                   t.gross_pnl - t.total_fee - t.slippage
                       - t.funding_cost - t.liquidation_penalty
            FROM TRADE AS t
            JOIN EXECUTION AS entry ON entry.execution_id = t.entry_execution_id
            JOIN EXECUTION AS exit ON exit.execution_id = t.exit_execution_id
            ORDER BY t.trade_id
            """
        ).fetchall()
        assert [row[0] for row in trades] == ["REVERSAL", "END_OF_DATA"]
        assert all(total_fee == execution_fees for _, total_fee, execution_fees, _, _ in trades)
        assert all(net_pnl == recomputed_net for *_, net_pnl, recomputed_net in trades)
        assert connection.execute(
            "SELECT min(cash_balance) >= 0 FROM PORTFOLIO_PNL"
        ).fetchone() == (1,)
        assert dict(
            connection.execute("SELECT check_name, passed FROM INTEGRITY_CHECK").fetchall()
        ) == {
            "accounting_identity": 1,
            "timestamp_order": 1,
            "cost_once": 1,
            "net_of_cost": 1,
            "deterministic": 1,
            "evidence_complete": 1,
        }


def test_engine_defaults_come_from_installed_package_metadata(tmp_path: Path) -> None:
    engine = _engine(tmp_path, _Catalog(), [])

    assert engine.engine_version == version("backtest-service")
    assert engine.core_lib_version == version("core-lib")


def test_engine_orders_configure_before_submit_and_persists_timing(
    tmp_path: Path,
) -> None:
    catalog = _Catalog()
    brokers: list[_Broker] = []
    feeds: list[_Feed] = []
    result = _engine(tmp_path, catalog, brokers, feeds).run(_config())

    broker = brokers[0]
    assert broker.call_order == ["configure", "submit", "configure", "submit"]
    assert [fill.timestamp for fill in broker.fills] == [
        _BASE + timedelta(hours=1, milliseconds=1),
        _BASE + timedelta(hours=3, milliseconds=1),
    ]
    with sqlite3.connect(result.evidence_path) as connection:
        order_rows = connection.execute(
            """
            SELECT s.feature_ts, d.decision_ts, e.execution_ts
            FROM SIGNAL AS s
            JOIN DECISION AS d ON d.signal_id = s.signal_id
            JOIN EXECUTION AS e ON e.decision_id = d.decision_id
            ORDER BY e.execution_id
            """
        ).fetchall()
        assert order_rows
        assert all(feature <= decision < execution for feature, decision, execution in order_rows)
        checks = dict(
            connection.execute("SELECT check_name, passed FROM INTEGRITY_CHECK").fetchall()
        )
        assert checks == {
            "accounting_identity": 1,
            "timestamp_order": 1,
            "cost_once": 1,
            "net_of_cost": 1,
            "deterministic": 1,
            "evidence_complete": 1,
        }
        assert connection.execute("SELECT COUNT(*) FROM DRAWDOWN_RUNUP_EPISODE").fetchone()[0] >= 1
        assert connection.execute("SELECT COUNT(*) FROM INDICATOR_DEFINITION").fetchone() == (1,)
        assert connection.execute("SELECT COUNT(*) FROM INDICATOR_SNAPSHOT").fetchone() == (4,)
        assert connection.execute(
            """
            SELECT COUNT(*)
            FROM TRADE_FEATURE_SNAPSHOT
            WHERE features_json <> '{}'
            """
        ).fetchone() == (4,)
        assert connection.execute(
            """
            SELECT COUNT(*)
            FROM SOURCE_DATA_SNAPSHOT
            WHERE source_kind = 'funding'
            """
        ).fetchone() == (1,)
        prereg = json.loads(
            connection.execute("SELECT prereg_json FROM BACKTEST_RUN_LOCAL").fetchone()[0]
        )
        assert "data_quality_criteria" not in prereg
        criteria = json.loads(
            connection.execute(
                "SELECT data_quality_criteria_json FROM BACKTEST_RUN_LOCAL"
            ).fetchone()[0]
        )
        assert criteria == {
            "min_coverage_ratio": 0.95,
            "max_consecutive_gap_seconds": 86_400,
        }
    assert result.integrity_status == "passed"
    assert feeds[0].candle_calls == 2
    assert catalog.events == ["reconcile", "register", "prereg", "summary"]


def test_declared_source_gap_passes_but_an_evidence_record_gap_fails(
    tmp_path: Path,
) -> None:
    history = [candle for candle in _candles() if candle.open_time != _BASE + timedelta(hours=1)]
    catalog = _Catalog()
    brokers: list[_Broker] = []
    sinks: list[BacktestEvidenceSink] = []

    result = _engine(
        tmp_path,
        catalog,
        brokers,
        sinks=sinks,
        candles=history,
    ).run(_config())

    assert result.integrity_status == "passed"
    sink = sinks[0]
    gap_count, note = sink.connection.execute(
        """
        SELECT gap_count, note
        FROM SOURCE_DATA_SNAPSHOT
        WHERE source_kind = 'ohlcv' AND timeframe = '1h'
        """
    ).fetchone()
    gap_evidence = json.loads(note)
    assert gap_count == 1
    assert gap_evidence["normal_gap_count"] == 1
    assert gap_evidence["evaluation_grid_gap_count"] == 1
    # Three evaluated bars plus the terminal row that carries the equity remaining
    # after the run closes what it still held.
    assert sink.connection.execute("SELECT COUNT(*) FROM PORTFOLIO_PNL").fetchone() == (4,)
    assert sink.connection.execute(
        "SELECT action, skip_reason FROM DECISION ORDER BY decision_id"
    ).fetchall() == [("skip", "next_candle_gap")]
    assert sink.connection.execute("SELECT COUNT(*) FROM EXECUTION").fetchone() == (0,)
    summary = cast(Mapping[str, object], catalog.summaries[-1])
    assert summary["data_coverage_ratio"] == 0.75
    assert summary["max_consecutive_gap_seconds"] == 3600
    assert summary["data_coverage_passed"] is False
    assert result.decision.route == "retest"

    sink.connection.execute(
        "DELETE FROM PORTFOLIO_PNL WHERE ts = ?",
        (int((_BASE + timedelta(hours=3)).timestamp() * 1_000),),
    )
    sink.connection.commit()
    audit = sink.audit(require_eval_decision=True)

    assert audit["evidence_complete"] is False
    assert sink.integrity_details["evidence_complete"]["grid_failures"] == [
        "portfolio_grid_mismatch:expected=3:actual=2:declared_gaps=1"
    ]


def test_execution_lag_over_one_timeframe_fails_timestamp_integrity(
    tmp_path: Path,
) -> None:
    catalog = _Catalog()
    sinks: list[BacktestEvidenceSink] = []
    _engine(tmp_path, catalog, [], sinks=sinks).run(_config())
    sink = sinks[0]
    sink.connection.execute(
        "UPDATE EXECUTION SET execution_ts = execution_ts + ? WHERE execution_id = 1",
        (2 * 60 * 60 * 1_000,),
    )
    sink.connection.commit()

    assert sink.audit()["timestamp_order"] is False
    failures = cast(
        Sequence[Sequence[object]],
        sink.integrity_details["timestamp_order"]["failures"],
    )
    assert any(failure[0] == "execution_lag" for failure in failures)


def test_open_position_is_closed_before_unobservable_gap_boundaries(
    tmp_path: Path,
) -> None:
    history = [candle for candle in _candles() if candle.open_time != _BASE + timedelta(hours=2)]
    sinks: list[BacktestEvidenceSink] = []
    result = _engine(
        tmp_path,
        _Catalog(),
        [],
        sinks=sinks,
        candles=history,
    ).run(_config())

    assert result.integrity_status == "passed"
    sink = sinks[0]
    assert sink.connection.execute(
        """
        SELECT exit_reason, execution_ts - decision_ts
        FROM EXECUTION
        JOIN DECISION USING (decision_id)
        WHERE exit_reason = 'DATA_GAP'
        """
    ).fetchone() == ("DATA_GAP", 1)
    assert sink.connection.execute("SELECT COUNT(*) FROM FUNDING_SETTLEMENT").fetchone() == (0,)


def test_crypto_data_snapshot_rejects_origin_query_divergence(tmp_path: Path) -> None:
    config = _config().model_copy(update={"data_source": "crypto_data.ohlcv_futures"})
    costs = BacktestCostModel(config.cost_values)
    history = _candles()
    engine = Engine(
        _OriginMismatchFeed(history),
        _Broker(costs),
        BacktestClock.from_candles(history),
        costs,
        BacktestEvidenceSink(tmp_path),
        _Catalog(),
        _manager(),
        prereg=_prereg(),
    )

    with pytest.raises(
        ValueError,
        match="1m OHLCV Evidence diverges from independent origin query",
    ):
        engine.run(config)


def test_engine_hash_parity_uses_different_catalog_run_ids(tmp_path: Path) -> None:
    catalog = _Catalog()
    brokers: list[_Broker] = []

    first = _engine(tmp_path / "one", catalog, brokers).run(_config())
    second = _engine(tmp_path / "two", catalog, brokers).run(_config())

    assert first.run_id != second.run_id
    assert Path(first.evidence_path).name == f"{first.run_id}.sqlite"
    assert Path(second.evidence_path).name == f"{second.run_id}.sqlite"
    with sqlite3.connect(first.evidence_path) as connection:
        assert connection.execute("SELECT run_id FROM BACKTEST_RUN_LOCAL").fetchone() == (
            first.run_id,
        )
    assert first.evidence_hash == second.evidence_hash
    with sqlite3.connect(first.evidence_path) as connection:
        detail = connection.execute(
            """
            SELECT detail_json
            FROM INTEGRITY_CHECK
            WHERE check_name = 'deterministic'
            """
        ).fetchone()[0]
        assert '"status":"no_prior_config_run"' in detail
    with sqlite3.connect(second.evidence_path) as connection:
        detail = connection.execute(
            """
            SELECT detail_json
            FROM INTEGRITY_CHECK
            WHERE check_name = 'deterministic'
            """
        ).fetchone()[0]
        assert '"status":"matched"' in detail


def test_same_config_with_different_source_is_not_a_determinism_target(
    tmp_path: Path,
) -> None:
    catalog = _Catalog()
    brokers: list[_Broker] = []
    first = _engine(tmp_path / "one", catalog, brokers).run(_config())
    changed = _candles()
    original = changed[0]
    changed[0] = replace(
        original,
        open=original.open + 0.25,
        high=original.high + 0.25,
        low=original.low + 0.25,
        close=original.close + 0.25,
    )

    second = _engine(
        tmp_path / "two",
        catalog,
        brokers,
        candles=changed,
    ).run(_config())

    assert first.evidence_hash != second.evidence_hash
    assert first.integrity_status == second.integrity_status == "passed"
    assert (
        catalog.runs[first.run_id]["source_data_hash"]
        != catalog.runs[second.run_id]["source_data_hash"]
    )
    with sqlite3.connect(second.evidence_path) as connection:
        passed, detail = connection.execute(
            """
            SELECT passed, detail_json
            FROM INTEGRITY_CHECK
            WHERE check_name = 'deterministic'
            """
        ).fetchone()
    assert passed == 1
    assert '"status":"source_changed"' in detail


def test_different_evidence_schema_is_not_a_determinism_target(
    tmp_path: Path,
) -> None:
    catalog = _Catalog()
    brokers: list[_Broker] = []
    first = _engine(tmp_path / "one", catalog, brokers).run(_config())
    catalog.runs[first.run_id] = {
        **catalog.runs[first.run_id],
        "evidence_schema_version": "1.4.0",
    }

    second = _engine(tmp_path / "two", catalog, brokers).run(_config())

    assert second.integrity_status == "passed"
    with sqlite3.connect(second.evidence_path) as connection:
        passed, detail_json = connection.execute(
            """
            SELECT passed, detail_json
            FROM INTEGRITY_CHECK
            WHERE check_name = 'deterministic'
            """
        ).fetchone()
    detail = json.loads(detail_json)
    assert passed == 1
    assert detail["status"] == "evidence_schema_changed"
    assert detail["comparison_hash"] is None
    assert detail["same_config_run_exists"] is True
    assert detail["same_schema_run_exists"] is False


def test_vessel_reference_end_to_end_dry_run_is_complete_and_deterministic(
    tmp_path: Path,
) -> None:
    """Exercise the first real Adaptee over an explicitly gap-free fixture."""
    catalog = _Catalog()
    first_prereg = _prereg()
    second_prereg = {
        **first_prereg,
        "hypothesis": "same criteria, independently reworded declaration",
    }
    first = _vessel_engine(
        tmp_path / "first",
        catalog,
        prereg=first_prereg,
    ).run(_vessel_config())
    second = _vessel_engine(
        tmp_path / "second",
        catalog,
        prereg=second_prereg,
    ).run(_vessel_config())

    assert first.run_id != second.run_id
    assert first.evidence_hash == second.evidence_hash
    assert first.integrity_status == second.integrity_status == "passed"
    with sqlite3.connect(first.evidence_path) as connection:
        local = connection.execute(
            """
            SELECT resolved_indicators_json, warmup_candles
            FROM BACKTEST_RUN_LOCAL
            """
        ).fetchone()
        assert local is not None
        assert local[1] == 21
        assert '"ATR"' in local[0]
        assert connection.execute("SELECT COUNT(*) FROM TRADE").fetchone() == (1,)
        assert connection.execute("SELECT COUNT(*) FROM INDICATOR_SNAPSHOT").fetchone() == (18,)
        # Six evaluated bars plus the terminal equity row.
        assert connection.execute("SELECT COUNT(*) FROM PORTFOLIO_PNL").fetchone() == (7,)
        snapshots = connection.execute(
            """
            SELECT indicator_key, value
            FROM INDICATOR_SNAPSHOT
            ORDER BY snapshot_seq
            """
        ).fetchall()
        assert [key for key, _ in snapshots] == [
            key for _ in range(6) for key in ("atr:period=14", "ema:period=21", "ema:period=9")
        ]
        assert [value for _, value in snapshots] == pytest.approx(
            [
                1.2401296056108868,
                111.5,
                117.5,
                1.2408346337815377,
                112.5,
                118.5,
                1.241489302797142,
                113.5,
                119.5,
                1.2420972097402034,
                114.5,
                120.5,
                1.2426616947587603,
                115.5,
                121.5,
                1.243185859418849,
                116.5,
                122.5,
            ]
        )
        assert connection.execute(
            "SELECT DISTINCT computation_mode FROM INDICATOR_DEFINITION"
        ).fetchall() == [("incremental",)]
    with sqlite3.connect(second.evidence_path) as connection:
        detail = json.loads(
            connection.execute(
                """
                SELECT detail_json
                FROM INTEGRITY_CHECK
                WHERE check_name = 'deterministic'
                """
            ).fetchone()[0]
        )
        assert detail["status"] == "matched"
        assert detail["comparison_run_id"] == first.run_id


def test_vessel_turtle_uses_only_prior_finalized_daily_n_and_records_plan(
    tmp_path: Path,
) -> None:
    """Keep the current incomplete daily candle out of Turtle sizing Evidence."""
    config = RunConfig.model_validate(
        {
            **_vessel_config(run_name="vessel-turtle").model_dump(),
            "money_management": {
                "mode": "turtle",
                "n_period": 20,
                "n_timeframe": "1d",
                "stop_n_multiple": 2.0,
                "leverage_cap": 10,
            },
        }
    )
    candles = _vessel_candles()
    costs = BacktestCostModel(config.cost_values)
    result = Engine(
        _VesselTurtleFeed(candles, _turtle_daily_candles()),
        BacktestBroker(costs),
        BacktestClock.from_candles(candles),
        costs,
        BacktestEvidenceSink(tmp_path),
        _Catalog(),
        _vessel_manager(),
        prereg=_prereg(),
    ).run(config)

    with sqlite3.connect(result.evidence_path) as connection:
        (
            params_json,
            submitted_money_management_json,
            money_management_json,
            indicators_json,
        ) = connection.execute(
            """
            SELECT params_json, submitted_money_management_json,
                   money_management_json, resolved_indicators_json
            FROM BACKTEST_RUN_LOCAL
            """
        ).fetchone()
        params = json.loads(params_json)
        assert params["_money_management"]["policy_id"] == "turtle"
        assert params["_money_management"]["policy_version"] == "1.0.0"
        assert json.loads(submitted_money_management_json)["mode"] == "turtle"
        assert json.loads(money_management_json) == params["_money_management"]
        assert '"TURTLE_N"' in indicators_json
        assert '"ATR"' not in indicators_json
        signal = connection.execute(
            """
            SELECT decision_ts, stop_loss, take_profit, leverage, metadata_json
            FROM SIGNAL
            WHERE derived_intent = 'enter'
            """
        ).fetchone()
        assert signal is not None
        decision_ts, stop_loss, take_profit, leverage, metadata_json = signal
        metadata = json.loads(metadata_json)["money_management"]
        assert stop_loss == pytest.approx(117.5)
        assert take_profit is None
        assert leverage == 1
        assert metadata["volatility"] == 2.0
        assert metadata["stop_distance"] == 4.0
        assert metadata["requested_quantity"] == 25.0
        assert metadata["initial_risk_amount"] == 100.0
        assert (
            datetime.fromisoformat(metadata["volatility_timestamp"]).timestamp() * 1_000
            <= decision_ts
        )
        assert connection.execute("SELECT COUNT(*) FROM INDICATOR_SNAPSHOT").fetchone() == (12,)


def test_resolved_manual_policy_has_stable_config_and_evidence_hash(
    tmp_path: Path,
) -> None:
    """Keep omitted defaults and explicit defaults reproducibly equivalent."""
    base = _vessel_config().model_dump()
    compact = RunConfig.model_validate(
        {
            **base,
            "run_name": "manual-compact",
            "money_management": {"mode": "manual"},
        }
    )
    explicit = RunConfig.model_validate(
        {
            **base,
            "run_name": "manual-explicit",
            "money_management": {
                "mode": "manual",
                "leverage": 1,
                "reward_risk": 2.0,
                "atr_stop_multiple": 2.0,
            },
        }
    )
    catalog = _Catalog()
    first = _vessel_engine(tmp_path / "compact", catalog).run(compact)
    second = _vessel_engine(tmp_path / "explicit", catalog).run(explicit)

    assert catalog.runs[first.run_id]["config_hash"] == catalog.runs[second.run_id]["config_hash"]
    assert first.evidence_hash == second.evidence_hash
    with sqlite3.connect(first.evidence_path) as connection:
        submitted = json.loads(
            connection.execute(
                "SELECT submitted_money_management_json FROM BACKTEST_RUN_LOCAL"
            ).fetchone()[0]
        )
    with sqlite3.connect(second.evidence_path) as connection:
        explicit_submitted = json.loads(
            connection.execute(
                "SELECT submitted_money_management_json FROM BACKTEST_RUN_LOCAL"
            ).fetchone()[0]
        )
    assert submitted == {"mode": "manual"}
    assert explicit_submitted == {
        "mode": "manual",
        "leverage": 1,
        "reward_risk": 2.0,
        "atr_stop_multiple": 2.0,
    }


def test_deterministic_check_fails_on_catalog_config_or_previous_hash_mismatch(
    tmp_path: Path,
) -> None:
    catalog = _Catalog()
    brokers: list[_Broker] = []
    first = _engine(tmp_path / "one", catalog, brokers).run(_config())
    assert first.integrity_status == "passed"

    catalog.comparison_hash_override = "f" * 64
    second = _engine(tmp_path / "two", catalog, brokers).run(_config())
    assert second.integrity_status == "diagnostic_only"
    assert (
        catalog.runs[first.run_id]["source_data_hash"]
        == catalog.runs[second.run_id]["source_data_hash"]
    )
    with sqlite3.connect(second.evidence_path) as connection:
        passed, detail = connection.execute(
            """
            SELECT passed, detail_json
            FROM INTEGRITY_CHECK
            WHERE check_name = 'deterministic'
            """
        ).fetchone()
        assert passed == 0
        assert '"status":"mismatched"' in detail

    catalog.comparison_hash_override = None
    catalog.force_config_mismatch = True
    third = _engine(tmp_path / "three", catalog, brokers).run(_config())
    assert third.integrity_status == "diagnostic_only"
    with sqlite3.connect(third.evidence_path) as connection:
        detail = connection.execute(
            """
            SELECT detail_json
            FROM INTEGRITY_CHECK
            WHERE check_name = 'deterministic'
            """
        ).fetchone()[0]
        assert '"catalog_config_matches":false' in detail


def test_missing_minute_source_snapshot_fails_evidence_completeness(
    tmp_path: Path,
) -> None:
    sinks: list[BacktestEvidenceSink] = []
    _engine(tmp_path, _Catalog(), [], sinks=sinks).run(_config())
    sink = sinks[0]
    sink.connection.execute("DELETE FROM SOURCE_DATA_SNAPSHOT WHERE timeframe = '1m'")
    sink.connection.commit()

    assert sink.audit(require_eval_decision=True)["evidence_complete"] is False
    source_failures = cast(
        Sequence[str],
        sink.integrity_details["evidence_complete"]["source_failures"],
    )
    assert "minute_ohlcv_snapshot_count" in source_failures


def test_missing_ohlcv_origin_contract_fails_evidence_completeness(
    tmp_path: Path,
) -> None:
    sinks: list[BacktestEvidenceSink] = []
    _engine(tmp_path, _Catalog(), [], sinks=sinks).run(_config())
    sink = sinks[0]
    sink.connection.execute("UPDATE SOURCE_DATA_SNAPSHOT SET note = NULL WHERE timeframe = '1m'")
    sink.connection.commit()

    assert sink.audit(require_eval_decision=True)["evidence_complete"] is False
    source_failures = cast(
        Sequence[str],
        sink.integrity_details["evidence_complete"]["source_failures"],
    )
    assert any(failure.startswith("ohlcv_gap_contract_missing:") for failure in source_failures)


def test_integrity_audit_is_fail_closed_for_grid_indicator_source_and_slippage(
    tmp_path: Path,
) -> None:
    catalog = _Catalog()
    brokers: list[_Broker] = []
    sinks: list[BacktestEvidenceSink] = []
    _engine(tmp_path, catalog, brokers, sinks=sinks).run(_config())
    sink = sinks[0]

    sink.connection.execute("UPDATE EXECUTION SET slippage = 100 WHERE execution_id = 1")
    sink.connection.execute(
        """
        UPDATE TRADE
        SET slippage = 100, net_pnl = net_pnl - 100
        WHERE trade_id = 1
        """
    )
    sink.connection.execute(
        """
        DELETE FROM INDICATOR_SNAPSHOT
        WHERE snapshot_seq = (SELECT min(snapshot_seq) FROM INDICATOR_SNAPSHOT)
        """
    )
    sink.connection.execute("DELETE FROM SOURCE_DATA_SNAPSHOT WHERE source_kind = 'funding'")
    # Remove an evaluated bar's equity row rather than the terminal one: the terminal
    # row sits outside the bar grid, so dropping it would leave the grid intact and the
    # check would have nothing to catch.
    sink.connection.execute(
        """
        DELETE FROM PORTFOLIO_PNL
        WHERE equity_seq = (SELECT max(equity_seq) - 1 FROM PORTFOLIO_PNL)
        """
    )
    sink.connection.commit()

    audit = sink.audit(require_eval_decision=True)
    assert audit["cost_once"] is False
    assert audit["evidence_complete"] is False
    details = sink.integrity_details
    assert details["cost_once"]["slippage_failure_count"] == 1
    complete = details["evidence_complete"]
    assert complete["grid_failures"]
    assert complete["indicator_failures"]
    assert complete["source_failures"]


def test_indicator_mode_changes_selection_and_longest_history_owns_warmup(
    tmp_path: Path,
) -> None:
    catalog = _Catalog()
    brokers: list[_Broker] = []
    oldest = _candles()[0]
    extended_history = [
        replace(
            oldest,
            open_time=oldest.open_time - timedelta(hours=offset),
            close_time=oldest.close_time - timedelta(hours=offset),
        )
        for offset in range(12, 0, -1)
    ] + _candles()
    explicit = RunConfig.model_validate(
        {
            **_config().model_dump(),
            "indicator_mode": "explicit",
            "explicit_indicators": [
                {"name": "EMA", "params": {"period": 9}},
                {"name": "EMA", "params": {"period": 21}},
            ],
        }
    )
    result = _engine(
        tmp_path / "explicit",
        catalog,
        brokers,
        candles=extended_history,
    ).run(explicit)
    with sqlite3.connect(result.evidence_path) as connection:
        resolved_json, warmup_candles = connection.execute(
            """
            SELECT resolved_indicators_json, warmup_candles
            FROM BACKTEST_RUN_LOCAL
            """
        ).fetchone()
        assert json.loads(resolved_json) == [
            {"name": "EMA", "params": {"period": 21}, "version": "1.0.0"},
            {"name": "EMA", "params": {"period": 9}, "version": "1.0.0"},
        ]
        assert warmup_candles == 21

    insufficient = RunConfig.model_validate(
        {
            **_config().model_dump(),
            "indicator_mode": "explicit",
            "explicit_indicators": [
                {"name": "EMA", "params": {"period": 9}},
                {"name": "EMA", "params": {"period": 21}},
            ],
        }
    )
    with pytest.raises(ValueError, match="requires 21"):
        _engine(tmp_path / "insufficient", catalog, brokers).run(insufficient)

    all_indicators = RunConfig.model_validate({**_config().model_dump(), "indicator_mode": "all"})
    with pytest.raises(ValueError, match="requires 200"):
        _engine(tmp_path / "all", catalog, brokers).run(all_indicators)


def test_patternless_strategy_keeps_resolved_indicators_and_values_unchanged(
    tmp_path: Path,
) -> None:
    catalog = _Catalog()
    brokers: list[_Broker] = []
    values = _candles()

    result = _engine(tmp_path, catalog, brokers, candles=values).run(
        _config(run_name="patternless-regression")
    )

    spec = DEFAULT_REGISTRY.get("EMA", {"period": 9})
    state = spec.make_state()
    state.seed(values[:9])
    expected_values = [state.update(candle) for candle in values[9:]]
    with sqlite3.connect(result.evidence_path) as connection:
        (resolved_indicators_json,) = connection.execute(
            "SELECT resolved_indicators_json FROM BACKTEST_RUN_LOCAL"
        ).fetchone()
        assert (
            resolved_indicators_json == '[{"name":"EMA","params":{"period":9},"version":"1.0.0"}]'
        )
        definitions = connection.execute(
            """
            SELECT indicator_key, indicator_name, params_json, impl_version
            FROM INDICATOR_DEFINITION
            ORDER BY indicator_key
            """
        ).fetchall()
        assert definitions == [
            ("ema:period=9", "EMA", '{"period":9}', "1.0.0"),
        ]
        snapshots = connection.execute(
            """
            SELECT indicator_key, value, value_json
            FROM INDICATOR_SNAPSHOT
            ORDER BY snapshot_seq
            """
        ).fetchall()
        assert snapshots == [("ema:period=9", expected, None) for expected in expected_values]


def test_declared_pattern_reaches_backtest_strategy_and_evidence(
    tmp_path: Path,
) -> None:
    catalog = _Catalog()
    brokers: list[_Broker] = []
    base_history = _candles()
    oldest = base_history[0]
    history = [
        replace(
            oldest,
            open_time=oldest.open_time - timedelta(hours=offset),
            close_time=oldest.close_time - timedelta(hours=offset),
        )
        for offset in range(2, 0, -1)
    ] + base_history
    config = RunConfig.model_validate(
        {
            **_config(run_name="pattern-series").model_dump(),
            "strategy_id": "pattern-fixture",
        }
    )
    costs = BacktestCostModel(config.cost_values)
    broker = _Broker(costs)
    brokers.append(broker)
    sink = BacktestEvidenceSink(tmp_path)
    _PatternStrategy.observed_indicators.clear()
    engine = Engine(
        _Feed(history),
        broker,
        BacktestClock.from_candles(history),
        costs,
        sink,
        catalog,
        _pattern_manager(),
        prereg=_prereg(),
    )

    result = engine.run(config)

    assert _PatternStrategy.observed_indicators
    first_indicators = _PatternStrategy.observed_indicators[0]
    assert set(first_indicators) == {"ema:period=9", "pat_doji"}
    pattern_value = first_indicators["pat_doji"]
    assert isinstance(pattern_value, dict)
    assert set(pattern_value) == {
        "pat_doji",
        "pat_doji_confirm",
        "pat_doji_dir",
        "pat_doji_strength",
    }
    with sqlite3.connect(result.evidence_path) as connection:
        resolved_json, warmup_candles = connection.execute(
            "SELECT resolved_indicators_json, warmup_candles FROM BACKTEST_RUN_LOCAL"
        ).fetchone()
        assert warmup_candles == 11
        assert json.loads(resolved_json) == [
            {"name": "EMA", "params": {"period": 9}, "version": "1.0.0"},
            {"name": "pat_doji", "params": {}, "version": "2.0.0+talib.0.7.1"},
        ]
        definitions = connection.execute(
            """
            SELECT indicator_key, pinned_impl, series_kind, category, impl_note
            FROM INDICATOR_DEFINITION
            ORDER BY indicator_key
            """
        ).fetchall()
        assert definitions == [
            (
                "ema:period=9",
                1,
                "indicator",
                "trend",
                "technical_indicators_calc_spec.md §0.3 (SMA seed, recursive)",
            ),
            (
                "pat_doji",
                1,
                "pattern",
                "candlestick",
                f"TA-Lib v{TALIB_SOURCE_VERSION} {TALIB_FUNCTIONS['pat_doji']}",
            ),
        ]
        pattern_snapshot = connection.execute(
            """
            SELECT value, value_json
            FROM INDICATOR_SNAPSHOT
            WHERE indicator_key = 'pat_doji'
            ORDER BY snapshot_seq
            LIMIT 1
            """
        ).fetchone()
        assert pattern_snapshot is not None
        value, value_json = pattern_snapshot
        assert value is None
        assert isinstance(value_json, str)
        assert set(json.loads(value_json)) == {
            "pat_doji",
            "pat_doji_confirm",
            "pat_doji_dir",
            "pat_doji_strength",
        }


def test_explicit_indicator_mode_rejects_missing_strategy_requirement(
    tmp_path: Path,
) -> None:
    catalog = _Catalog()
    brokers: list[_Broker] = []
    oldest = _candles()[0]
    extended_history = [
        replace(
            oldest,
            open_time=oldest.open_time - timedelta(hours=offset),
            close_time=oldest.close_time - timedelta(hours=offset),
        )
        for offset in range(12, 0, -1)
    ] + _candles()
    missing_required = RunConfig.model_validate(
        {
            **_config().model_dump(),
            "indicator_mode": "explicit",
            "explicit_indicators": [
                {"name": "EMA", "params": {"period": 21}},
            ],
        }
    )

    with pytest.raises(
        ValueError,
        match=r"missing strategy-required indicators: EMA\(period=9\)",
    ):
        _engine(
            tmp_path,
            catalog,
            brokers,
            candles=extended_history,
        ).run(missing_required)


def test_coarse_candle_funding_charges_every_crossed_boundary_with_payment_sign(
    tmp_path: Path,
) -> None:
    catalog = _Catalog()
    sinks: list[BacktestEvidenceSink] = []
    engine, config = _daily_engine(tmp_path, catalog, sinks)

    result = engine.run(config)

    with sqlite3.connect(result.evidence_path) as connection:
        settlements = connection.execute(
            """
            SELECT settled_at, payment_amount, settle_price_source
            FROM FUNDING_SETTLEMENT
            ORDER BY settled_at
            """
        ).fetchall()
        funding_cost = connection.execute("SELECT funding_cost FROM TRADE").fetchone()[0]
        assert len(settlements) == 3
        assert all(payment < 0 for _, payment, _ in settlements)
        assert -sum(payment for _, payment, _ in settlements) == funding_cost
        assert {source for _, _, source in settlements} == {"boundary_open"}
        assert connection.execute(
            """
            SELECT passed
            FROM INTEGRITY_CHECK
            WHERE check_name = 'cost_once'
            """
        ).fetchone() == (1,)

    sink = sinks[0]
    sink.connection.execute(
        """
        DELETE FROM FUNDING_SETTLEMENT
        WHERE settlement_id = (SELECT min(settlement_id) FROM FUNDING_SETTLEMENT)
        """
    )
    sink.connection.commit()
    assert sink.audit(require_eval_decision=True)["cost_once"] is False
    assert sink.integrity_details["cost_once"]["funding_failure_count"] == 1


def test_funding_margin_exhaustion_liquidates_without_negative_cash(
    tmp_path: Path,
) -> None:
    catalog = _Catalog()
    sinks: list[BacktestEvidenceSink] = []
    engine, config = _daily_engine(
        tmp_path,
        catalog,
        sinks,
        funding_rate=Decimal("2"),
        fee_rate=Decimal("0.0004"),
    )

    result = engine.run(config)

    assert result.integrity_status == "passed"
    with sqlite3.connect(result.evidence_path) as connection:
        trade = connection.execute(
            """
            SELECT exit_reason, liquidated, funding_cost, total_fee,
                   liquidation_penalty, net_pnl
            FROM TRADE
            """
        ).fetchone()
        assert trade == (
            "LIQUIDATION",
            1,
            100_000_000_000,
            80_000_000,
            0,
            -100_080_000_000,
        )
        settlement = connection.execute(
            """
            SELECT payment_amount, theoretical_payment_amount
            FROM FUNDING_SETTLEMENT
            """
        ).fetchone()
        assert settlement == (-100_000_000_000, -200_000_000_000)
        execution = connection.execute(
            """
            SELECT d.decision_ts, e.execution_ts, e.reference_price,
                   e.exit_reason, e.reduce_only
            FROM EXECUTION AS e
            JOIN DECISION AS d USING (decision_id)
            WHERE e.exit_reason = 'LIQUIDATION'
            """
        ).fetchone()
        boundary_ms = int(datetime(2026, 1, 2, 8, tzinfo=UTC).timestamp() * 1_000)
        assert execution == (
            boundary_ms,
            boundary_ms + 1,
            10_000_000_000,
            "LIQUIDATION",
            1,
        )
        assert connection.execute(
            "SELECT min(cash_balance), min(position_value), min(total_equity) FROM PORTFOLIO_PNL"
        ).fetchone() == (
            899_920_000_000,
            0,
            899_920_000_000,
        )
        assert set(
            connection.execute("SELECT check_name FROM INTEGRITY_CHECK WHERE passed = 1").fetchall()
        ) == {
            ("accounting_identity",),
            ("timestamp_order",),
            ("cost_once",),
            ("net_of_cost",),
            ("deterministic",),
            ("evidence_complete",),
        }


def _metrics(pf: float) -> MetricSet:
    return MetricSet(
        pf=pf,
        sortino=1.0,
        calmar_or_mar=1.0,
        sqn=2.0,
        mdd=-0.1,
        ror=0.0,
        sharpe=1.0,
        win_rate=0.5,
        payoff=2.0,
        expectancy_r=0.2,
        ulcer=1.0,
        kelly=0.2,
        trade_count=30,
    )


class _HarnessEngine:
    def __init__(self, results: list[RunResult]) -> None:
        self._results = results

    def run(self, config: RunConfig) -> RunResult:
        del config
        return self._results.pop(0)


def _run_result(run_id: str, pf: float) -> RunResult:
    from core_lib.eval import DecisionResult

    return RunResult(
        run_id=run_id,
        evidence_path=f"{run_id}.sqlite",
        evidence_hash="a" * 64,
        integrity_status="passed",
        metrics=_metrics(pf),
        decision=DecisionResult(route="promote", rationale="fixture"),
        r_multiples=(1.0, -0.5, 0.75),
        period_returns=(0.03, 0.02, -0.01, 0.025),
    )


def test_harness_is_fixed_seed_and_applies_cross_run_boundaries() -> None:
    results = [_run_result("is", 2.0), _run_result("oos", 1.2)]
    engine = _HarnessEngine(results)
    catalog = _Catalog()
    harness = Harness(catalog, lambda: cast(Engine, engine))

    oos = harness.is_oos(_config(run_name="validation"), 0.5)
    first = harness.monte_carlo([1.0, -1.0, 2.0], 100)
    second = harness.monte_carlo([1.0, -1.0, 2.0], 100)

    assert oos["oos_degradation"] == pytest.approx(0.4)
    assert oos["passed"] is True
    assert catalog.aggregates["oos"] == {
        "oos_degradation": pytest.approx(0.4),
        "psr": None,
        "harness_json": {
            "workflow": "is_oos",
            "metric": "pf",
            "split": 0.5,
            "boundary": (_BASE + timedelta(hours=2)).isoformat(),
            "in_sample_run_id": "is",
            "out_of_sample_run_id": "oos",
            "in_sample_value": 2.0,
            "out_of_sample_value": 1.2,
            "oos_degradation": pytest.approx(0.4),
            "passed": True,
        },
    }
    assert catalog.events == ["reconcile"]
    assert (
        first
        == second
        == {
            "iterations": 100,
            "seed": 0,
            "terminal_r_p05": -1.0,
            "terminal_r_p95": 5.0,
            "ruin_probability": 0.0,
            "passed": True,
        }
    )
    assert harness.overfit_gate(degradation=0.499, psr=0.95)["passed"] is True
    failed = harness.overfit_gate(degradation=0.5, psr=0.949)
    assert failed["failed"] == ["oos_degradation", "psr"]
    assert harness.psr([0.01, 0.02, -0.005, 0.03, 0.015]) == pytest.approx(0.9345141116427946)

    walk_engine = _HarnessEngine(
        [
            _run_result("wf-1", 2.0),
            _run_result("wf-2", 1.2),
            _run_result("wf-3", 1.0),
        ]
    )
    walk_catalog = _Catalog()
    walk_harness = Harness(walk_catalog, lambda: cast(Engine, walk_engine))
    walk = walk_harness.walk_forward(
        _config(run_name="walk"),
        3,
    )
    assert walk["degradations"] == pytest.approx([0.4, 1.0 / 6.0])
    assert walk["maximum_degradation"] == pytest.approx(0.4)
    assert walk["passed"] is True
    assert walk_catalog.aggregates["wf-3"]["oos_degradation"] == pytest.approx(0.4)
    assert walk_catalog.aggregates["wf-3"]["psr"] is None

    bundle_engine = _HarnessEngine(
        [
            _run_result("bundle-1", 2.0),
            _run_result("bundle-2", 1.2),
            _run_result("bundle-3", 1.0),
        ]
    )
    bundle_catalog = _Catalog()
    bundle_harness = Harness(bundle_catalog, lambda: cast(Engine, bundle_engine), seed=7)
    bundle = bundle_harness.evaluate_overfit_defense(
        _config(run_name="bundle"),
        folds=3,
        mc_iters=50,
    )
    aggregate = bundle_catalog.aggregates["bundle-3"]
    assert bundle["representative_run_id"] == "bundle-3"
    assert aggregate["oos_degradation"] == pytest.approx(0.4)
    assert aggregate["psr"] == bundle["psr"]
    assert cast(dict[str, object], aggregate["harness_json"])["monte_carlo"] is not None


def test_harness_reads_every_overfit_limit_from_shared_eval_thresholds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert evaluation_thresholds.overfit() == {
        "oos_degradation_limit": 0.50,
        "psr_minimum": 0.95,
        "ruin_drawdown": 0.60,
        "risk_fraction": 0.01,
    }

    class TrackingLimits(dict[str, float]):
        def __init__(self) -> None:
            super().__init__(
                oos_degradation_limit=0.25,
                psr_minimum=0.90,
                ruin_drawdown=0.60,
                risk_fraction=0.01,
            )
            self.accessed: set[str] = set()

        def __getitem__(self, key: str) -> float:
            self.accessed.add(key)
            return super().__getitem__(key)

    limits = TrackingLimits()
    monkeypatch.setattr(evaluation_thresholds, "overfit", lambda: limits)
    harness = Harness(_Catalog(), lambda: cast(Engine, _HarnessEngine([])))

    gate = harness.overfit_gate(degradation=0.40, psr=0.91)
    monte_carlo = harness.monte_carlo([1.0, -1.0, 2.0], 10)

    assert gate == {
        "passed": False,
        "failed": ["oos_degradation"],
        "oos_degradation_limit": 0.25,
        "psr_minimum": 0.90,
    }
    assert monte_carlo["passed"] is True
    assert {
        "oos_degradation_limit",
        "psr_minimum",
        "ruin_drawdown",
        "risk_fraction",
    } <= limits.accessed


def test_engine_accepts_a_standard_undefined_indicator_output_and_records_null() -> None:
    """A NaN is refused unless the registry says the standard leaves it undefined.

    The engine stops a run when an indicator turns non-finite after warm-up,
    because a NaN there usually means the calculation broke. Bollinger %B is the
    exception the standard itself creates (§3.10, "분모 0 → 미정의"): a flat window
    collapses the band and there is no relative position to report. The value
    reaches the strategy as NaN and reaches Evidence as JSON null, since canonical
    JSON has no NaN.
    """

    Engine._assert_finite_indicator(
        {"middle": 100.0, "percent_b": float("nan")},
        "Bollinger Bands(multiplier=2.0,period=20)",
        ("percent_b",),
    )

    with pytest.raises(ValueError, match="non-finite"):
        Engine._assert_finite_indicator(
            {"middle": float("nan"), "percent_b": 0.5},
            "Bollinger Bands(multiplier=2.0,period=20)",
            ("percent_b",),
        )

    with pytest.raises(ValueError, match="non-finite"):
        Engine._assert_finite_indicator(float("nan"), "EMA(period=9)", ())

    recordable = Engine._recordable_indicator_value({"middle": 100.0, "percent_b": float("nan")})
    assert recordable == {"middle": 100.0, "percent_b": None}
    assert canonical_json(recordable) == '{"middle":100,"percent_b":null}'
