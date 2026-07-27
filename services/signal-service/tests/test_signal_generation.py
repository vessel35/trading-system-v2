"""Verify the finalized-candle vertical slice with core-lib implementations."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Event
from typing import ClassVar

import pytest
from core_lib.indicators import DEFAULT_REGISTRY
from core_lib.ports import StrategyRegistry
from core_lib.strategy import (
    AdapterManager,
    InProcessStrategyRegistry,
    ParameterSchema,
    ResolvedConfig,
    StrategyMetadata,
    StrategyProfile,
)
from core_lib.types import Candle, MarketType, Position, TradingSignal
from signal_service.application import (
    SignalDataFeed,
    SignalGenerationService,
    SignalPollingRunner,
    SignalQueue,
    SignalSink,
    SignalStateRecoveryRequired,
)
from signal_service.core import SignalGenerationConfig
from signal_service.domain import PersistedSignal, SignalIntent, SignalMode

_BASE = datetime(2026, 1, 1, tzinfo=UTC)
_STRATEGY_ID = "probe"


def _candles(count: int) -> list[Candle]:
    result: list[Candle] = []
    for index in range(count):
        price = 100.0 + index
        result.append(
            Candle(
                symbol="BTCUSDT",
                exchange="binance",
                timeframe="1h",
                open_time=_BASE + timedelta(hours=index),
                close_time=_BASE + timedelta(hours=index + 1),
                open=price,
                high=price + 2.0,
                low=price - 1.0,
                close=price + 1.0,
                volume=10.0,
                quote_volume=1_000.0,
                trade_count=5,
            )
        )
    return result


class _Feed(SignalDataFeed):
    def __init__(self, candles: list[Candle], *, enforce_boundary: bool = True) -> None:
        self.values = list(candles)
        self.enforce_boundary = enforce_boundary
        self.calls: list[datetime] = []
        self.incremental_calls: list[tuple[datetime, datetime]] = []

    def candles(self, symbol: str, tf: str, up_to: datetime) -> list[Candle]:
        assert symbol == "BTCUSDT"
        assert tf == "1h"
        self.calls.append(up_to)
        if not self.enforce_boundary:
            return list(self.values)
        return [candle for candle in self.values if candle.close_time <= up_to]

    def candles_after(
        self,
        symbol: str,
        tf: str,
        after: datetime,
        up_to: datetime,
    ) -> list[Candle]:
        assert symbol == "BTCUSDT"
        assert tf == "1h"
        self.incremental_calls.append((after, up_to))
        if not self.enforce_boundary:
            return list(self.values)
        return [
            candle
            for candle in self.values
            if candle.open_time >= after and candle.close_time <= up_to
        ]

    def funding(self, symbol: str, at: datetime) -> Decimal:
        del symbol, at
        raise LookupError

    def mark_price(self, symbol: str, at: datetime) -> Decimal:
        del symbol, at
        raise LookupError


class _Catalog(StrategyRegistry):
    def get(self, strategy_id: str) -> dict[str, object]:
        if strategy_id != _STRATEGY_ID:
            raise KeyError(strategy_id)
        return {
            "strategy_id": _STRATEGY_ID,
            "class_name": "_ProbeStrategy",
            "module_path": __name__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get(_STRATEGY_ID)]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError


class _ProbeStrategy:
    calls: ClassVar[list[tuple[dict[str, object], Position | None]]] = []

    def __init__(self, config: ResolvedConfig) -> None:
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            required_indicators=[{"name": "EMA", "params": {"period": 9}}],
            min_history=9,
            supported_timeframes=["1h"],
            profile=StrategyProfile(
                id="probe-v1",
                family="test",
                bar="1h",
                expected_win_rate=(0.0, 1.0),
                expected_payoff=(0.0, 10.0),
                tail_shape="symmetric",
                holding_horizon="intraday",
                primary_metric="calmar",
                risk_adjusted_pref="sortino",
                profit_structure_to_preserve="contract",
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
        self.calls.append((dict(market_data), current_position))
        candle = market_data["candle"]
        indicators = market_data["indicators"]
        assert isinstance(candle, Candle)
        assert isinstance(indicators, Mapping)
        assert "ema:period=9" in indicators
        return TradingSignal(
            symbol=candle.symbol,
            timestamp=candle.close_time,
            confidence=0.8,
            price=candle.close,
            stop_loss=candle.close - 5.0,
            take_profit=candle.close + 10.0,
            market_type=MarketType.FUTURES,
            leverage=2,
            reason="probe-entry",
            metadata={"fixture": True},
        )


class _Sink(SignalSink):
    def __init__(self, *, inserted: bool = True) -> None:
        self.inserted = inserted
        self.values: list[PersistedSignal] = []

    def store(self, signal: PersistedSignal) -> bool:
        self.values.append(signal)
        return self.inserted


class _Queue(SignalQueue):
    def __init__(self) -> None:
        self.values: list[PersistedSignal] = []

    def publish(self, signal: PersistedSignal) -> None:
        self.values.append(signal)


def _manager() -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    plugins.register(_STRATEGY_ID, _ProbeStrategy)
    return AdapterManager(_Catalog(), plugins)


def _config() -> SignalGenerationConfig:
    return SignalGenerationConfig(
        strategy_id=_STRATEGY_ID,
        symbol="BTCUSDT",
        timeframe="1h",
        market_type=MarketType.FUTURES,
        mode=SignalMode.PAPER,
    )


def test_finalized_candle_uses_core_incremental_state_and_adaptee_contract() -> None:
    values = _candles(10)
    feed = _Feed(values)
    sink = _Sink()
    queue = _Queue()
    _ProbeStrategy.calls.clear()
    service = SignalGenerationService(feed, _manager(), sink, queue=queue)

    cycle = service.start(_config(), values[-1].close_time)
    persisted = cycle.signal

    assert persisted is not None
    assert cycle.gaps == ()
    assert dict(persisted.params) == {}
    assert persisted.intent is SignalIntent.ENTER
    assert persisted.signal_type.value == "BUY"
    assert persisted.side is not None and persisted.side.value == "long"
    assert sink.values == [persisted]
    assert queue.values == [persisted]
    market_data, observed_position = _ProbeStrategy.calls[0]
    assert observed_position is None
    assert set(market_data) == {
        "candles",
        "candle",
        "symbol",
        "timeframe",
        "market_type",
        "indicators",
    }
    observed_indicators = market_data["indicators"]
    assert isinstance(observed_indicators, dict)
    spec = DEFAULT_REGISTRY.get("EMA", {"period": 9})
    state = spec.make_state()
    state.seed(values[:9])
    expected = state.update(values[9])
    assert observed_indicators == {"ema:period=9": expected}

    feed.values.extend(_candles(11)[10:])
    next_cycle = service.poll(feed.values[-1].close_time)
    next_persisted = next_cycle.signal
    assert next_persisted is not None
    assert next_cycle.gaps == ()
    assert feed.incremental_calls == [(values[-1].close_time, feed.values[-1].close_time)]
    assert len(_ProbeStrategy.calls) == 2
    next_market_data, _ = _ProbeStrategy.calls[-1]
    assert isinstance(next_market_data["candles"], list)
    assert len(next_market_data["candles"]) == 11


def test_unfinalized_mock_candle_is_rejected_before_indicator_update() -> None:
    values = _candles(11)
    feed = _Feed(values, enforce_boundary=False)
    service = SignalGenerationService(feed, _manager(), _Sink())

    with pytest.raises(ValueError, match="after decision time"):
        service.start(_config(), values[-2].close_time)


def test_poll_marks_multi_candle_backlog_as_recoverable_state() -> None:
    values = _candles(10)
    feed = _Feed(values)
    service = SignalGenerationService(feed, _manager(), _Sink())
    service.start(_config(), values[-1].close_time)
    feed.values.extend(_candles(12)[10:])

    with pytest.raises(SignalStateRecoveryRequired, match="state recovery"):
        service.poll(feed.values[-1].close_time)


def test_runner_rewarms_multi_candle_backlog_and_resumes_signals(
    caplog: pytest.LogCaptureFixture,
) -> None:
    initial = _candles(10)
    available = _candles(13)
    feed = _Feed(initial)
    stop_event = Event()

    class _StoppingSink(_Sink):
        def store(self, signal: PersistedSignal) -> bool:
            inserted = super().store(signal)
            if signal.candle.close_time == available[-1].close_time:
                stop_event.set()
            return inserted

    class _LagClock:
        def __init__(self) -> None:
            self.now = initial[-1].close_time.timestamp()
            self.batches = [available[10:12], available[12:]]
            self.sleeps: list[float] = []

        def __call__(self) -> float:
            return self.now

        def sleep(self, delay: float) -> None:
            self.sleeps.append(delay)
            if not self.batches:
                stop_event.set()
                return
            batch = self.batches.pop(0)
            feed.values.extend(batch)
            self.now = batch[-1].close_time.timestamp()

    sink = _StoppingSink()
    clock = _LagClock()
    service = SignalGenerationService(feed, _manager(), sink)
    runner = SignalPollingRunner(
        service,
        _config(),
        wall_clock=clock,
        sleep=clock.sleep,
        stop_event=stop_event,
    )

    with caplog.at_level("WARNING"):
        runner.run()

    assert [signal.candle.close_time for signal in sink.values] == [
        initial[-1].close_time,
        available[11].close_time,
        available[12].close_time,
    ]
    assert feed.calls == [
        initial[-1].close_time,
        available[11].close_time,
    ]
    assert feed.incremental_calls == [
        (initial[-1].close_time, available[11].close_time),
        (available[11].close_time, available[12].close_time),
    ]
    assert clock.sleeps == [2.0, 2.0]
    assert "signal_poll_rewarmed" in caplog.text


def test_duplicate_sink_result_does_not_publish_to_queue() -> None:
    values = _candles(10)
    sink = _Sink(inserted=False)
    queue = _Queue()
    service = SignalGenerationService(_Feed(values), _manager(), sink, queue=queue)

    persisted = service.start(_config(), values[-1].close_time).signal

    assert persisted is not None
    assert sink.values == [persisted]
    assert queue.values == []


def test_missing_candle_is_reported_in_result_and_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    values = _candles(11)
    del values[9]
    service = SignalGenerationService(_Feed(values), _manager(), _Sink())

    with caplog.at_level("WARNING"):
        cycle = service.start(_config(), values[-1].close_time)

    assert cycle.signal is not None
    assert len(cycle.gaps) == 1
    assert cycle.gaps[0].missing_candles == 1
    assert service.gap_reports == cycle.gaps
    assert "detected 1 missing finalized candle" in caplog.text


def test_poll_reports_missing_expected_candle_without_filling_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    values = _candles(10)
    feed = _Feed(values)
    service = SignalGenerationService(feed, _manager(), _Sink())
    service.start(_config(), values[-1].close_time)

    with caplog.at_level("WARNING"):
        cycle = service.poll(values[-1].close_time + timedelta(hours=1))

    assert cycle.signal is None
    assert len(cycle.gaps) == 1
    assert cycle.gaps[0].next_open is None
    assert cycle.gaps[0].missing_candles == 1
    assert feed.values == values
    assert "missing finalized candle" in caplog.text


def test_slice_has_no_order_exchange_or_wallet_database_surface() -> None:
    package = Path(__file__).resolve().parents[1] / "signal_service"
    source = "\n".join(path.read_text() for path in package.rglob("*.py"))

    assert inspect.isabstract(SignalQueue)
    assert "OrderRequest" not in source
    assert "Broker" not in source
    assert "wallet_db" not in source
