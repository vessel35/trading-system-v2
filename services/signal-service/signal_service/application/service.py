"""Run the shared finalized-candle indicator and Adaptee call contract."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime

from core_lib.indicators import (
    DEFAULT_REGISTRY,
    IndicatorRegistry,
    IndicatorSpec,
    IndicatorState,
    assert_finalized,
)
from core_lib.ports import DataFeed
from core_lib.strategy import AdapterManager, StrategyAdapter
from core_lib.types import Candle, Position, PositionSide, SignalType, TradingSignal

from signal_service.core import SignalGenerationConfig
from signal_service.domain import PersistedSignal, SignalIntent

from .ports import SignalQueue, SignalSink


class SignalGenerationService:
    """Keep incremental indicator state and judge exactly one new confirmed candle."""

    def __init__(
        self,
        feed: DataFeed,
        manager: AdapterManager,
        sink: SignalSink,
        *,
        indicators: IndicatorRegistry = DEFAULT_REGISTRY,
        queue: SignalQueue | None = None,
    ) -> None:
        self._feed = feed
        self._manager = manager
        self._sink = sink
        self._indicators = indicators
        self._queue = queue
        self._config: SignalGenerationConfig | None = None
        self._strategy: StrategyAdapter | None = None
        self._specs: list[IndicatorSpec] = []
        self._states: dict[str, IndicatorState] = {}
        self._confirmed: list[Candle] = []
        self._last_close: datetime | None = None

    def start(
        self,
        config: SignalGenerationConfig,
        decision_time: datetime,
        *,
        current_position: Position | None = None,
    ) -> PersistedSignal | None:
        """Warm from prior candles and judge only the latest finalized candle."""
        if self._config is not None:
            raise RuntimeError("signal generation session is already started")
        boundary = self._utc(decision_time, name="decision_time")
        strategy = self._manager.create(
            config.strategy_id,
            {"strategy_id": config.strategy_id, "params": dict(config.params)},
        )
        self._manager.activate(config.strategy_id)
        metadata = strategy.get_metadata()
        if config.timeframe not in metadata.supported_timeframes:
            raise ValueError("strategy does not support the configured timeframe")
        specs = self._indicators.resolve_specs(
            "auto",
            metadata.required_indicators,
            (),
        )
        required_warmup = max(
            metadata.min_history,
            max(spec.min_history for spec in specs),
        )
        history = self._confirmed_history(config, boundary)
        if len(history) < required_warmup + 1:
            raise ValueError(
                "insufficient finalized history: "
                f"requires {required_warmup + 1}, got {len(history)}"
            )

        self._config = config
        self._strategy = strategy
        self._specs = specs
        self._states = {spec.identifier: spec.make_state() for spec in specs}
        self._confirmed = history[-(required_warmup + 1) : -1]
        for state in self._states.values():
            state.seed(self._confirmed)
            if not state.warmed_up:
                raise ValueError("indicator state did not warm up after required preload")
        return self._process(history[-1], boundary, current_position)

    def poll(
        self,
        decision_time: datetime,
        *,
        current_position: Position | None = None,
    ) -> PersistedSignal | None:
        """Judge the next finalized candle, rejecting deferred state recovery."""
        config = self._require_config()
        boundary = self._utc(decision_time, name="decision_time")
        last_close = self._last_close
        if last_close is None:
            raise RuntimeError("signal generation session has no processed candle")
        history = self._confirmed_history(config, boundary)
        fresh = [candle for candle in history if candle.close_time > last_close]
        if not fresh:
            return None
        if len(fresh) > 1:
            raise RuntimeError(
                "multiple unprocessed candles require state recovery, which is outside this slice"
            )
        return self._process(fresh[0], boundary, current_position)

    def _confirmed_history(
        self,
        config: SignalGenerationConfig,
        boundary: datetime,
    ) -> list[Candle]:
        history = sorted(
            self._feed.candles(config.symbol, config.timeframe, boundary),
            key=lambda candle: candle.open_time,
        )
        if any(
            right.open_time <= left.open_time
            for left, right in zip(history, history[1:], strict=False)
        ):
            raise ValueError("DataFeed candles must have strictly increasing open_time")
        for candle in history:
            assert_finalized(candle, boundary)
            if candle.symbol != config.symbol or candle.timeframe != config.timeframe:
                raise ValueError("DataFeed returned a candle outside the configured series")
        return history

    def _process(
        self,
        candle: Candle,
        boundary: datetime,
        current_position: Position | None,
    ) -> PersistedSignal | None:
        assert_finalized(candle, boundary)
        self._confirmed.append(candle)
        indicator_values: dict[str, object] = {}
        for spec in self._specs:
            value = self._states[spec.identifier].update(candle)
            self._assert_finite_indicator(value, spec.identifier)
            indicator_values[self._indicator_key(spec)] = value

        config = self._require_config()
        signal = self._require_strategy().analyze(
            {
                "candles": list(self._confirmed),
                "candle": candle,
                "symbol": config.symbol,
                "timeframe": config.timeframe,
                "market_type": config.market_type.value,
                "indicators": dict(indicator_values),
            },
            current_position,
        )
        self._last_close = candle.close_time
        if signal is None:
            return None
        if signal.timestamp > candle.close_time:
            raise ValueError("strategy signal cannot be later than the confirmed candle")
        persisted = self._persisted_signal(signal, candle, current_position)
        if self._sink.store(persisted) and self._queue is not None:
            self._queue.publish(persisted)
        return persisted

    def _persisted_signal(
        self,
        signal: TradingSignal,
        candle: Candle,
        current_position: Position | None,
    ) -> PersistedSignal:
        intent, side = self._derive_intent(signal, current_position)
        signal_type = self._signal_type(intent, side, current_position)
        config = self._require_config()
        return PersistedSignal(
            strategy_id=config.strategy_id,
            mode=config.mode,
            timeframe=config.timeframe,
            candle=candle,
            signal=signal,
            signal_type=signal_type,
            intent=intent,
            side=side,
        )

    @staticmethod
    def _derive_intent(
        signal: TradingSignal,
        position: Position | None,
    ) -> tuple[SignalIntent, PositionSide | None]:
        if signal.stop_loss is None and signal.take_profit is None:
            return SignalIntent.EXIT, None
        protection = signal.stop_loss if signal.stop_loss is not None else signal.take_profit
        assert protection is not None
        if protection == signal.price:
            raise ValueError("protection level cannot equal signal price")
        if signal.stop_loss is not None:
            side = PositionSide.LONG if protection < signal.price else PositionSide.SHORT
        else:
            side = PositionSide.LONG if protection > signal.price else PositionSide.SHORT
        intent = (
            SignalIntent.REVERSE
            if position is not None and position.side is not side
            else SignalIntent.ENTER
        )
        return intent, side

    @staticmethod
    def _signal_type(
        intent: SignalIntent,
        side: PositionSide | None,
        position: Position | None,
    ) -> SignalType:
        if side is PositionSide.LONG:
            return SignalType.BUY
        if side is PositionSide.SHORT:
            return SignalType.SELL
        if intent is not SignalIntent.EXIT:
            raise RuntimeError("non-exit signals require a derived side")
        if position is None:
            return SignalType.HOLD
        if position.side is PositionSide.LONG:
            return SignalType.SELL
        if position.side is PositionSide.SHORT:
            return SignalType.BUY
        raise ValueError("cannot derive an exit direction for a BOTH position")

    @staticmethod
    def _assert_finite_indicator(value: object, identifier: str) -> None:
        scalars = value.values() if isinstance(value, Mapping) else (value,)
        if any(
            isinstance(item, bool)
            or not isinstance(item, float | int)
            or not math.isfinite(float(item))
            for item in scalars
        ):
            raise ValueError(f"indicator {identifier} emitted a non-finite value")

    @staticmethod
    def _indicator_key(spec: IndicatorSpec) -> str:
        name = re.sub(r"[^a-z0-9]+", "_", spec.name.casefold()).strip("_")
        params = ",".join(
            f"{key}={SignalGenerationService._indicator_param(value)}"
            for key, value in sorted(spec.params.items())
        )
        return name if not params else f"{name}:{params}"

    @staticmethod
    def _indicator_param(value: object) -> str:
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    @staticmethod
    def _utc(value: datetime, *, name: str) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{name} must be timezone-aware")
        return value.astimezone(UTC)

    def _require_config(self) -> SignalGenerationConfig:
        if self._config is None:
            raise RuntimeError("signal generation session is not started")
        return self._config

    def _require_strategy(self) -> StrategyAdapter:
        if self._strategy is None:
            raise RuntimeError("signal generation session has no Adaptee")
        return self._strategy
