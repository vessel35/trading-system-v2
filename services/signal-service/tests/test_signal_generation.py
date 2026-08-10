"""Verify the finalized-candle vertical slice with core-lib implementations."""

from __future__ import annotations

import inspect
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Event
from typing import ClassVar, cast

import pytest
from core_lib.indicators import DEFAULT_REGISTRY, IndicatorRegistry, IndicatorSpec
from core_lib.ports import StrategyRegistry
from core_lib.strategy import (
    AdapterManager,
    InProcessStrategyRegistry,
    ParameterSchema,
    ResolvedConfig,
    StrategyDecisionContract,
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
_PATTERN_STRATEGY_ID = "pattern-probe"


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
    def __init__(self, class_name: str = "_ProbeStrategy") -> None:
        self._class_name = class_name

    def get(self, strategy_id: str) -> dict[str, object]:
        if strategy_id != _STRATEGY_ID:
            raise KeyError(strategy_id)
        return {
            "strategy_id": _STRATEGY_ID,
            "class_name": self._class_name,
            "module_path": __name__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get(_STRATEGY_ID)]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError


class _PatternCatalog(StrategyRegistry):
    def get(self, strategy_id: str) -> dict[str, object]:
        if strategy_id != _PATTERN_STRATEGY_ID:
            raise KeyError(strategy_id)
        return {
            "strategy_id": _PATTERN_STRATEGY_ID,
            "class_name": "_PatternProbeStrategy",
            "module_path": __name__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get(_PATTERN_STRATEGY_ID)]

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
        assert "ema:period=9@1h" in indicators
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


class _PatternProbeStrategy(_ProbeStrategy):
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


class _MultiTimeframeProbeStrategy(_ProbeStrategy):
    observed_market_data: ClassVar[list[dict[str, object]]] = []

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        metadata = super().get_metadata()
        metadata.required_indicators = [{"name": "EMA", "params": {"period": 9}, "timeframe": "4h"}]
        return metadata

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> None:
        del current_position
        type(self).observed_market_data.append(dict(market_data))
        return None


class _MultiTimeframeFeed(_Feed):
    def __init__(self, candles: list[Candle], upper: list[Candle]) -> None:
        super().__init__(candles)
        self.upper = upper

    def candles(self, symbol: str, tf: str, up_to: datetime) -> list[Candle]:
        if tf == "4h":
            assert symbol == "BTCUSDT"
            return [candle for candle in self.upper if candle.close_time <= up_to]
        return super().candles(symbol, tf, up_to)

    def candles_after(
        self,
        symbol: str,
        tf: str,
        after: datetime,
        up_to: datetime,
    ) -> list[Candle]:
        if tf == "4h":
            assert symbol == "BTCUSDT"
            return [
                candle
                for candle in self.upper
                if candle.open_time >= after and candle.close_time <= up_to
            ]
        return super().candles_after(symbol, tf, after, up_to)


class _PairedProbeState:
    def __init__(self) -> None:
        self.samples = 0
        self.reference_close = 0.0

    @property
    def warmed_up(self) -> bool:
        return self.samples >= 2

    def seed(
        self,
        candles: Sequence[Candle],
        reference_candles: Sequence[Candle],
    ) -> None:
        assert len(candles) == len(reference_candles)
        assert all(
            candle.close_time == reference.close_time
            for candle, reference in zip(candles, reference_candles, strict=True)
        )
        self.samples = len(candles)
        if reference_candles:
            self.reference_close = reference_candles[-1].close

    def update(self, candle: Candle, reference_candle: Candle) -> dict[str, float]:
        assert candle.close_time == reference_candle.close_time
        self.samples += 1
        self.reference_close = reference_candle.close
        return {
            "reference_close": self.reference_close,
            "samples": float(self.samples),
        }


_PAIRED_PROBE_SPEC = IndicatorSpec(
    name="PAIRED_PROBE",
    params={},
    version="1.0.0",
    pinned_impl="test-only paired input contract probe",
    min_history=2,
    category="statistics",
    required_inputs=(),
    _vectorized=lambda candles: [
        {"reference_close": candle.close, "samples": float(index + 1)}
        for index, candle in enumerate(candles)
    ],
    _state_factory=_PairedProbeState,
    needs_reference_series=True,
)


def _paired_registry() -> IndicatorRegistry:
    registry = IndicatorRegistry()
    for spec in DEFAULT_REGISTRY.list():
        registry.register(spec)
    registry.register(_PAIRED_PROBE_SPEC)
    return registry


class _PairedProbeStrategy(_ProbeStrategy):
    observed_market_data: ClassVar[list[dict[str, object]]] = []

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        metadata = super().get_metadata()
        metadata.required_indicators = [{"name": "PAIRED_PROBE", "params": {}, "timeframe": "4h"}]
        metadata.min_history = 1
        return metadata

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> None:
        del current_position
        type(self).observed_market_data.append(dict(market_data))
        return None


class _PairedFeed(_MultiTimeframeFeed):
    def __init__(
        self,
        candles: list[Candle],
        primary: list[Candle],
        reference: list[Candle],
    ) -> None:
        super().__init__(candles, primary)
        self.reference = reference

    def candles(self, symbol: str, tf: str, up_to: datetime) -> list[Candle]:
        if symbol == "ETHUSDT":
            assert tf == "4h"
            return [candle for candle in self.reference if candle.close_time <= up_to]
        return super().candles(symbol, tf, up_to)

    def candles_after(
        self,
        symbol: str,
        tf: str,
        after: datetime,
        up_to: datetime,
    ) -> list[Candle]:
        if symbol == "ETHUSDT":
            assert tf == "4h"
            return [
                candle
                for candle in self.reference
                if candle.open_time >= after and candle.close_time <= up_to
            ]
        return super().candles_after(symbol, tf, after, up_to)


class _TargetLegacyProbeStrategy(_ProbeStrategy):
    """Break a target declaration by returning the legacy value."""

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        metadata = super().get_metadata()
        metadata.decision_contract = StrategyDecisionContract.DECISION_INTENT
        return metadata


class _TargetNoneProbeStrategy(_TargetLegacyProbeStrategy):
    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> None:
        del market_data, current_position
        return None


class _InvalidProbeStrategy(_TargetLegacyProbeStrategy):
    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> TradingSignal:
        del market_data, current_position
        return cast(TradingSignal, object())


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


def _manager(adaptee: type[_ProbeStrategy] = _ProbeStrategy) -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    plugins.register(_STRATEGY_ID, adaptee)
    return AdapterManager(_Catalog(adaptee.__name__), plugins)


def _pattern_manager() -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    plugins.register(_PATTERN_STRATEGY_ID, _PatternProbeStrategy)
    return AdapterManager(_PatternCatalog(), plugins)


def _config() -> SignalGenerationConfig:
    return SignalGenerationConfig(
        strategy_id=_STRATEGY_ID,
        symbol="BTCUSDT",
        timeframe="1h",
        market_type=MarketType.FUTURES,
        mode=SignalMode.PAPER,
    )


def _pattern_config() -> SignalGenerationConfig:
    return SignalGenerationConfig(
        strategy_id=_PATTERN_STRATEGY_ID,
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
    assert observed_indicators == {"ema:period=9@1h": expected}

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


def test_live_multi_timeframe_alignment_uses_the_same_resolved_key() -> None:
    execution = _candles(40)
    upper = [
        Candle(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe="4h",
            open_time=_BASE + timedelta(hours=4 * index),
            close_time=_BASE + timedelta(hours=4 * (index + 1)),
            open=200.0 + index,
            high=201.0 + index,
            low=199.0 + index,
            close=200.5 + index,
            volume=40.0,
            quote_volume=None,
            trade_count=None,
        )
        for index in range(10)
    ]
    feed = _MultiTimeframeFeed(execution, upper)
    _MultiTimeframeProbeStrategy.observed_market_data.clear()
    service = SignalGenerationService(
        feed,
        _manager(_MultiTimeframeProbeStrategy),
        _Sink(),
    )

    assert service.start(_config(), execution[36].close_time).signal is None
    assert service.poll(execution[37].close_time).signal is None
    assert service.poll(execution[38].close_time).signal is None
    assert service.poll(execution[39].close_time).signal is None

    observed = _MultiTimeframeProbeStrategy.observed_market_data
    values = [
        cast(Mapping[str, object], item["indicators"])["ema:period=9@4h"] for item in observed
    ]
    assert values[:3] == [values[0]] * 3
    assert values[3] != values[2]
    assert all(
        set(cast(Mapping[str, object], item["indicators"])) == {"ema:period=9@4h"}
        for item in observed
    )
    assert all(
        all(candle.timeframe == "1h" for candle in cast(list[Candle], item["candles"]))
        for item in observed
    )


def _live_paired_values(
    *,
    changed_unfinished_tail: bool,
    missing_tail: bool = False,
) -> list[dict[str, float]]:
    execution = _candles(40)
    primary = [
        Candle(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe="4h",
            open_time=_BASE + timedelta(hours=4 * index),
            close_time=_BASE + timedelta(hours=4 * (index + 1)),
            open=200.0 + index,
            high=201.0 + index,
            low=199.0 + index,
            close=200.5 + index,
            volume=40.0,
            quote_volume=None,
            trade_count=None,
        )
        for index in range(10)
    ]
    reference = []
    for index, candle in enumerate(primary):
        close = 300.0 + index
        if changed_unfinished_tail and index == 9:
            close += 100.0
        reference.append(
            Candle(
                symbol="ETHUSDT",
                exchange=candle.exchange,
                timeframe=candle.timeframe,
                open_time=candle.open_time,
                close_time=candle.close_time,
                open=300.0 + index,
                high=max(301.0 + index, close),
                low=299.0 + index,
                close=close,
                volume=candle.volume,
                quote_volume=None,
                trade_count=None,
            )
        )
    if missing_tail:
        reference = reference[:-1]
    _PairedProbeStrategy.observed_market_data.clear()
    service = SignalGenerationService(
        _PairedFeed(execution, primary, reference),
        _manager(_PairedProbeStrategy),
        _Sink(),
        indicators=_paired_registry(),
    )
    config = SignalGenerationConfig(
        strategy_id=_STRATEGY_ID,
        symbol="BTCUSDT",
        reference_symbol="ETHUSDT",
        timeframe="1h",
        market_type=MarketType.FUTURES,
        mode=SignalMode.PAPER,
    )
    assert service.start(config, execution[36].close_time).signal is None
    assert service.poll(execution[37].close_time).signal is None
    assert service.poll(execution[38].close_time).signal is None
    assert service.poll(execution[39].close_time).signal is None
    return [
        cast(
            dict[str, float],
            cast(Mapping[str, object], item["indicators"])["paired_probe@4h"],
        )
        for item in _PairedProbeStrategy.observed_market_data
    ]


def test_live_paired_series_matches_backtest_alignment_and_never_reuses_a_reference_bar() -> None:
    unchanged = _live_paired_values(changed_unfinished_tail=False)
    changed = _live_paired_values(changed_unfinished_tail=True)
    missing = _live_paired_values(
        changed_unfinished_tail=False,
        missing_tail=True,
    )

    assert unchanged[:3] == changed[:3]
    assert unchanged[3] != changed[3]
    assert [value["samples"] for value in changed] == [2.0, 2.0, 2.0, 3.0]
    assert [value["reference_close"] for value in unchanged[:3]] == [308.0] * 3
    assert unchanged[3]["reference_close"] == 309.0
    assert changed[3]["reference_close"] == 409.0
    assert [value["samples"] for value in missing] == [2.0] * 4
    assert [value["reference_close"] for value in missing] == [308.0] * 4


def test_live_reference_symbol_is_required_only_by_a_paired_series() -> None:
    values = _candles(10)
    paired_service = SignalGenerationService(
        _Feed(values),
        _manager(_PairedProbeStrategy),
        _Sink(),
        indicators=_paired_registry(),
    )
    with pytest.raises(ValueError, match="reference_symbol is required"):
        paired_service.start(_config(), values[-1].close_time)

    unpaired_service = SignalGenerationService(_Feed(values), _manager(), _Sink())
    with pytest.raises(ValueError, match="no paired series requires it"):
        unpaired_service.start(
            SignalGenerationConfig(
                strategy_id=_STRATEGY_ID,
                symbol="BTCUSDT",
                reference_symbol="ETHUSDT",
                timeframe="1h",
                market_type=MarketType.FUTURES,
                mode=SignalMode.PAPER,
            ),
            values[-1].close_time,
        )


def test_live_config_rejects_the_primary_symbol_as_its_reference() -> None:
    with pytest.raises(ValueError, match="reference_symbol must differ"):
        SignalGenerationConfig(
            strategy_id=_STRATEGY_ID,
            symbol="BTCUSDT",
            reference_symbol="BTCUSDT",
            timeframe="1h",
            market_type=MarketType.FUTURES,
        )


def test_target_contract_rejects_a_legacy_signal_before_signal_service_uses_it() -> None:
    values = _candles(10)
    service = SignalGenerationService(_Feed(values), _manager(_TargetLegacyProbeStrategy), _Sink())

    with pytest.raises(TypeError, match="declared DecisionIntent but returned TradingSignal"):
        service.start(_config(), values[-1].close_time)


def test_signal_service_accepts_none_from_a_target_contract_strategy() -> None:
    values = _candles(10)
    service = SignalGenerationService(_Feed(values), _manager(_TargetNoneProbeStrategy), _Sink())

    assert service.start(_config(), values[-1].close_time).signal is None


def test_signal_service_rejects_a_third_return_type_before_using_it() -> None:
    values = _candles(10)
    service = SignalGenerationService(_Feed(values), _manager(_InvalidProbeStrategy), _Sink())

    with pytest.raises(TypeError, match="must return DecisionIntent, TradingSignal, or None"):
        service.start(_config(), values[-1].close_time)


def test_declared_pattern_reaches_signal_strategy_input() -> None:
    values = _candles(12)
    feed = _Feed(values)
    sink = _Sink()
    _PatternProbeStrategy.observed_indicators.clear()
    service = SignalGenerationService(feed, _pattern_manager(), sink)

    cycle = service.start(_pattern_config(), values[-1].close_time)

    assert cycle.signal is not None
    pattern_spec = next(spec for spec in service._specs if spec.name == "pat_doji")
    assert pattern_spec.min_history == 11
    assert pattern_spec.version == "2.0.0+talib.0.7.1"
    assert _PatternProbeStrategy.observed_indicators
    observed = _PatternProbeStrategy.observed_indicators[0]
    assert set(observed) == {"ema:period=9@1h", "pat_doji@1h"}
    pattern_value = observed["pat_doji@1h"]
    assert isinstance(pattern_value, dict)
    assert set(pattern_value) == {
        "occurred",
        "direction",
        "strength",
        "confirmed",
    }


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
