"""Run the shared finalized-candle indicator and Adaptee call contract."""

from __future__ import annotations

import logging
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

from core_lib.indicators import (
    DEFAULT_REGISTRY,
    IndicatorRegistry,
    assert_finalized,
)
from core_lib.money_management import (
    AccountRiskSnapshot,
    ManualMoneyManagement,
    MarketSnapshot,
    MoneyManagementBase,
    RiskLimits,
)
from core_lib.patterns import DEFAULT_PATTERN_REGISTRY, PatternRegistry
from core_lib.series import PairedSeriesState, SeriesState, series_key_of
from core_lib.series_resolution import ResolvedSeriesSpec, resolve_series_specs, series_key
from core_lib.strategy import (
    AdapterManager,
    StrategyAdapter,
    StrategyConfig,
    validate_strategy_result,
)
from core_lib.types import (
    Candle,
    DecisionAction,
    DecisionIntent,
    MarketType,
    Position,
    PositionSide,
    SignalType,
    TradingSignal,
)

from signal_service.core import SignalGenerationConfig
from signal_service.domain import DataGap, PersistedSignal, SignalIntent

from .ports import SignalDataFeed, SignalQueue, SignalSink

_LOGGER = logging.getLogger(__name__)
CandleStream = tuple[str, str]


class SignalStateRecoveryRequired(RuntimeError):
    """A finalized-candle discontinuity requires a fresh indicator seed."""


@dataclass(frozen=True, slots=True)
class SignalCycleResult:
    """Return one cycle's optional signal and explicit missing-candle reports."""

    signal: PersistedSignal | None
    gaps: tuple[DataGap, ...] = ()


class SignalGenerationService:
    """Keep incremental indicator state and judge exactly one new confirmed candle."""

    def __init__(
        self,
        feed: SignalDataFeed,
        manager: AdapterManager,
        sink: SignalSink,
        *,
        indicators: IndicatorRegistry = DEFAULT_REGISTRY,
        patterns: PatternRegistry = DEFAULT_PATTERN_REGISTRY,
        queue: SignalQueue | None = None,
    ) -> None:
        self._feed = feed
        self._manager = manager
        self._sink = sink
        self._indicators = indicators
        self._patterns = patterns
        self._queue = queue
        self._config: SignalGenerationConfig | None = None
        self._strategy: StrategyAdapter | None = None
        self._money_management: MoneyManagementBase | None = None
        self._specs: list[ResolvedSeriesSpec] = []
        self._states: dict[str, SeriesState | PairedSeriesState] = {}
        self._series_values: dict[str, object] = {}
        self._series_last_close: dict[CandleStream, datetime] = {}
        self._paired_last_close: dict[str, datetime] = {}
        self._confirmed: list[Candle] = []
        self._last_close: datetime | None = None
        self._resolved_params: dict[str, object] = {}
        self._gap_reports: list[DataGap] = []
        self._reported_missing_until: datetime | None = None

    @property
    def gap_reports(self) -> tuple[DataGap, ...]:
        """Return every gap reported by this in-memory session."""
        return tuple(self._gap_reports)

    def start(
        self,
        config: SignalGenerationConfig,
        decision_time: datetime,
        *,
        current_position: Position | None = None,
    ) -> SignalCycleResult:
        """Warm from prior candles and judge only the latest finalized candle."""
        if self._config is not None:
            raise RuntimeError("signal generation session is already started")
        boundary = self._utc(decision_time, name="decision_time")
        manual_config = {
            "mode": "manual",
            "leverage": config.params.get("leverage", 1),
            "reward_risk": config.params.get("reward_risk", 2.0),
            "atr_stop_multiple": config.params.get("atr_stop_multiple", 2.0),
        }
        strategy_params = dict(config.params)
        for name in ("leverage", "reward_risk", "atr_stop_multiple"):
            strategy_params.pop(name, None)
        runtime = self._manager.create_runtime(
            config.strategy_id,
            {"strategy_id": config.strategy_id, "params": strategy_params},
            manual_config,
        )
        strategy = runtime.strategy
        self._manager.activate(config.strategy_id)
        metadata = strategy.get_metadata()
        if config.timeframe not in metadata.supported_timeframes:
            raise ValueError("strategy does not support the configured timeframe")
        policy_indicators = (
            []
            if runtime.money_management is None
            else [
                {
                    "name": requirement.name,
                    "params": dict(requirement.params),
                    "timeframe": requirement.timeframe,
                }
                for requirement in runtime.money_management.required_indicators()
                if requirement.timeframe == "strategy"
            ]
        )
        specs = resolve_series_specs(
            "auto",
            [*metadata.required_indicators, *policy_indicators],
            (),
            self._indicators,
            self._patterns,
            execution_timeframe=config.timeframe,
        )
        needs_reference = any(spec.needs_reference_series for spec in specs)
        if needs_reference:
            if config.reference_symbol is None:
                raise ValueError("reference_symbol is required by a paired series")
        elif config.reference_symbol is not None:
            raise ValueError("reference_symbol was supplied but no paired series requires it")
        required_warmups = {(config.symbol, config.timeframe): metadata.min_history}
        for spec in specs:
            primary = (config.symbol, spec.timeframe)
            required_warmups[primary] = max(required_warmups.get(primary, 0), spec.min_history)
            if spec.needs_reference_series:
                assert config.reference_symbol is not None
                reference = (config.reference_symbol, spec.timeframe)
                required_warmups[reference] = max(
                    required_warmups.get(reference, 0), spec.min_history
                )
        if runtime.money_management is not None:
            for requirement in runtime.money_management.required_indicators():
                timeframe = (
                    config.timeframe
                    if requirement.timeframe == "strategy"
                    else requirement.timeframe
                )
                stream = (config.symbol, timeframe)
                required_warmups[stream] = max(
                    required_warmups.get(stream, 0), requirement.min_history
                )
        resolved = StrategyConfig.resolve(
            strategy.get_parameter_schema(),
            {"strategy_id": config.strategy_id, "params": strategy_params},
        )
        serialized_params = StrategyConfig.serialize(resolved)["params"]
        if not isinstance(serialized_params, dict):
            raise TypeError("core_lib resolved strategy params must serialize to a dict")
        history = self._confirmed_history(config, boundary)
        required_warmup = required_warmups[(config.symbol, config.timeframe)]
        if len(history) < required_warmup + 1:
            raise ValueError(
                "insufficient finalized history: "
                f"requires {required_warmup + 1}, got {len(history)}"
            )

        self._config = config
        self._strategy = strategy
        self._money_management = runtime.money_management
        self._specs = specs
        self._states = {
            series_key(spec.spec, spec.timeframe): (
                spec.make_paired_state() if spec.needs_reference_series else spec.make_state()
            )
            for spec in specs
        }
        self._series_values = {}
        self._series_last_close = {}
        self._paired_last_close = {}
        self._resolved_params = dict(serialized_params)
        decision_window = history[-(required_warmup + 1) :]
        gaps = self._report_series_gaps(decision_window, boundary)
        self._confirmed = decision_window[:-1]
        for spec in specs:
            key = series_key(spec.spec, spec.timeframe)
            state = self._states[key]
            if spec.needs_reference_series:
                assert config.reference_symbol is not None
                primary_history = (
                    history
                    if spec.timeframe == config.timeframe
                    else self._series_history(
                        config,
                        config.symbol,
                        spec.timeframe,
                        boundary,
                    )
                )
                reference_history = self._series_history(
                    config,
                    config.reference_symbol,
                    spec.timeframe,
                    boundary,
                )
                pairs = self._match_candles(primary_history, reference_history)
                if spec.timeframe == config.timeframe:
                    decision_close = decision_window[-1].close_time
                    pairs = [pair for pair in pairs if pair[0].close_time < decision_close]
                if len(pairs) < spec.min_history:
                    raise ValueError(
                        "insufficient finalized history: "
                        f"{config.symbol}/{config.reference_symbol} {spec.timeframe} "
                        f"requires {spec.min_history} matched pairs, got {len(pairs)}"
                    )
                warm_pairs = pairs[-spec.min_history :]
                primary_candles = [pair[0] for pair in warm_pairs]
                reference_candles = [pair[1] for pair in warm_pairs]
                paired_state = cast(PairedSeriesState, state)
                paired_state.seed(primary_candles[:-1], reference_candles[:-1])
                value = paired_state.update(primary_candles[-1], reference_candles[-1])
                self._assert_finite_indicator(value, spec.identifier)
                self._series_values[key] = value
                self._paired_last_close[key] = primary_candles[-1].close_time
            elif spec.timeframe == config.timeframe:
                cast(SeriesState, state).seed(self._confirmed)
            else:
                series_history = self._series_history(
                    config,
                    config.symbol,
                    spec.timeframe,
                    boundary,
                )
                required = required_warmups[(config.symbol, spec.timeframe)]
                if len(series_history) < required:
                    raise ValueError(
                        "insufficient finalized history: "
                        f"{config.symbol} {spec.timeframe} requires {required}, "
                        f"got {len(series_history)}"
                    )
                single_state = cast(SeriesState, state)
                single_state.seed(series_history[:-1])
                value = single_state.update(series_history[-1])
                self._assert_finite_indicator(value, spec.identifier)
                self._series_values[key] = value
                self._series_last_close[(config.symbol, spec.timeframe)] = series_history[
                    -1
                ].close_time
            if not state.warmed_up:
                raise ValueError("indicator state did not warm up after required preload")
        persisted = self._process(decision_window[-1], boundary, current_position)
        return SignalCycleResult(persisted, gaps)

    def rewarm(
        self,
        decision_time: datetime,
        *,
        current_position: Position | None = None,
    ) -> SignalCycleResult:
        """Discard incremental state and warm again at the latest finalized candle."""

        config = self._require_config()
        self._config = None
        self._strategy = None
        self._money_management = None
        self._specs = []
        self._states = {}
        self._series_values = {}
        self._series_last_close = {}
        self._paired_last_close = {}
        self._confirmed = []
        self._last_close = None
        self._resolved_params = {}
        self._reported_missing_until = None
        return self.start(config, decision_time, current_position=current_position)

    def poll(
        self,
        decision_time: datetime,
        *,
        current_position: Position | None = None,
    ) -> SignalCycleResult:
        """Judge the next finalized candle, rejecting deferred state recovery."""
        config = self._require_config()
        boundary = self._utc(decision_time, name="decision_time")
        last_close = self._last_close
        if last_close is None:
            raise RuntimeError("signal generation session has no processed candle")
        fresh = self._confirmed_increment(config, last_close, boundary)
        gaps = self._report_poll_gaps(config, last_close, fresh, boundary)
        if not fresh:
            return SignalCycleResult(None, gaps)
        if gaps:
            raise SignalStateRecoveryRequired(
                "finalized candle gap requires indicator state recovery"
            )
        if len(fresh) > 1:
            raise SignalStateRecoveryRequired(
                "multiple unprocessed candles require indicator state recovery"
            )
        persisted = self._process(fresh[0], boundary, current_position)
        return SignalCycleResult(persisted, gaps)

    def _confirmed_history(
        self,
        config: SignalGenerationConfig,
        boundary: datetime,
    ) -> list[Candle]:
        history = sorted(
            self._feed.candles(config.symbol, config.timeframe, boundary),
            key=lambda candle: candle.open_time,
        )
        self._validate_sequence(history, boundary, config)
        return history

    def _series_history(
        self,
        config: SignalGenerationConfig,
        symbol: str,
        timeframe: str,
        boundary: datetime,
    ) -> list[Candle]:
        history = sorted(
            self._feed.candles(symbol, timeframe, boundary),
            key=lambda candle: candle.open_time,
        )
        self._validate_series_sequence(
            history,
            boundary,
            symbol=symbol,
            timeframe=timeframe,
        )
        return history

    def _confirmed_increment(
        self,
        config: SignalGenerationConfig,
        after: datetime,
        boundary: datetime,
    ) -> list[Candle]:
        fresh = sorted(
            self._feed.candles_after(
                config.symbol,
                config.timeframe,
                after,
                boundary,
            ),
            key=lambda candle: candle.open_time,
        )
        self._validate_sequence(fresh, boundary, config)
        if any(candle.open_time < after for candle in fresh):
            raise ValueError("incremental DataFeed returned a candle before the cursor")
        return fresh

    @staticmethod
    def _validate_sequence(
        candles: list[Candle],
        boundary: datetime,
        config: SignalGenerationConfig,
    ) -> None:
        if any(
            right.open_time <= left.open_time
            for left, right in zip(candles, candles[1:], strict=False)
        ):
            raise ValueError("DataFeed candles must have strictly increasing open_time")
        if any(
            right.open_time < left.close_time
            for left, right in zip(candles, candles[1:], strict=False)
        ):
            raise ValueError("DataFeed candles must not overlap")
        for candle in candles:
            assert_finalized(candle, boundary)
            if candle.symbol != config.symbol or candle.timeframe != config.timeframe:
                raise ValueError("DataFeed returned a candle outside the configured series")

    @staticmethod
    def _validate_series_sequence(
        candles: list[Candle],
        boundary: datetime,
        *,
        symbol: str,
        timeframe: str,
    ) -> None:
        if any(
            right.open_time <= left.open_time
            for left, right in zip(candles, candles[1:], strict=False)
        ):
            raise ValueError("DataFeed candles must have strictly increasing open_time")
        if any(
            right.open_time < left.close_time
            for left, right in zip(candles, candles[1:], strict=False)
        ):
            raise ValueError("DataFeed candles must not overlap")
        for candle in candles:
            assert_finalized(candle, boundary)
            if candle.symbol != symbol or candle.timeframe != timeframe:
                raise ValueError("DataFeed returned a candle outside the requested series")

    def _process(
        self,
        candle: Candle,
        boundary: datetime,
        current_position: Position | None,
    ) -> PersistedSignal | None:
        assert_finalized(candle, boundary)
        self._confirmed.append(candle)
        indicator_values = dict(self._series_values)
        self._advance_non_execution_series(candle.close_time)
        indicator_values.update(self._series_values)
        for spec in self._specs:
            if spec.timeframe != self._require_config().timeframe:
                continue
            key = series_key(spec.spec, spec.timeframe)
            if spec.needs_reference_series:
                reference_symbol = self._require_config().reference_symbol
                if reference_symbol is None:
                    raise ValueError("reference_symbol is required by a paired series")
                reference = {
                    item.close_time: item
                    for item in self._series_history(
                        self._require_config(),
                        reference_symbol,
                        spec.timeframe,
                        candle.close_time,
                    )
                }.get(candle.close_time)
                if reference is None or candle.close_time <= self._paired_last_close[key]:
                    continue
                value = cast(PairedSeriesState, self._states[key]).update(
                    candle,
                    reference,
                )
                self._paired_last_close[key] = candle.close_time
            else:
                value = cast(SeriesState, self._states[key]).update(candle)
            self._assert_finite_indicator(value, spec.identifier)
            indicator_values[key] = value
            self._series_values[key] = value

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
        self._reported_missing_until = max(
            candle.close_time,
            self._reported_missing_until or candle.close_time,
        )
        if signal is None:
            return None
        validate_strategy_result(self._require_strategy().get_metadata(), signal)
        if isinstance(signal, DecisionIntent):
            if signal.action is DecisionAction.HOLD:
                return None
            signal = self._materialize_decision(
                signal,
                candle,
                indicator_values,
            )
        if signal.timestamp > candle.close_time:
            raise ValueError("strategy signal cannot be later than the confirmed candle")
        persisted = self._persisted_signal(signal, candle, current_position)
        if self._sink.store(persisted) and self._queue is not None:
            self._queue.publish(persisted)
        return persisted

    def _advance_non_execution_series(self, boundary: datetime) -> None:
        config = self._require_config()
        for (symbol, timeframe), after in tuple(self._series_last_close.items()):
            fresh = sorted(
                self._feed.candles_after(
                    symbol,
                    timeframe,
                    after,
                    boundary,
                ),
                key=lambda candle: candle.open_time,
            )
            self._validate_series_sequence(
                fresh,
                boundary,
                symbol=symbol,
                timeframe=timeframe,
            )
            for source_candle in fresh:
                for spec in self._specs:
                    if spec.needs_reference_series or spec.timeframe != timeframe:
                        continue
                    key = series_key(spec.spec, timeframe)
                    value = cast(SeriesState, self._states[key]).update(source_candle)
                    self._assert_finite_indicator(value, spec.identifier)
                    self._series_values[key] = value
                self._series_last_close[(symbol, timeframe)] = source_candle.close_time

        reference_symbol = config.reference_symbol
        if reference_symbol is None:
            return
        for spec in self._specs:
            if not spec.needs_reference_series or spec.timeframe == config.timeframe:
                continue
            key = series_key(spec.spec, spec.timeframe)
            primary = self._series_history(
                config,
                config.symbol,
                spec.timeframe,
                boundary,
            )
            reference = self._series_history(
                config,
                reference_symbol,
                spec.timeframe,
                boundary,
            )
            pairs = [
                pair
                for pair in self._match_candles(primary, reference)
                if pair[0].close_time > self._paired_last_close[key]
            ]
            state = cast(PairedSeriesState, self._states[key])
            for primary_candle, reference_candle in pairs:
                value = state.update(primary_candle, reference_candle)
                self._assert_finite_indicator(value, spec.identifier)
                self._series_values[key] = value
                self._paired_last_close[key] = primary_candle.close_time

    @staticmethod
    def _match_candles(
        primary: list[Candle],
        reference: list[Candle],
    ) -> list[tuple[Candle, Candle]]:
        reference_by_close = {candle.close_time: candle for candle in reference}
        return [
            (candle, reference_by_close[candle.close_time])
            for candle in primary
            if candle.close_time in reference_by_close
        ]

    def _materialize_decision(
        self,
        decision: DecisionIntent,
        candle: Candle,
        indicators: Mapping[str, object],
    ) -> TradingSignal:
        config = self._require_config()
        if decision.action is DecisionAction.EXIT:
            return TradingSignal(
                symbol=decision.symbol,
                timestamp=decision.timestamp,
                confidence=decision.confidence,
                price=decision.reference_price,
                stop_loss=None,
                take_profit=None,
                market_type=config.market_type,
                leverage=1,
                reason=decision.reason,
                metadata={
                    **dict(decision.metadata),
                    "decision_action": decision.action.value,
                },
            )
        policy = self._money_management
        if not isinstance(policy, ManualMoneyManagement):
            raise ValueError("signal generation currently requires manual money management")
        # Read what the policy declared rather than a key written here, so the
        # lookup cannot drift from the declaration that produced the value.
        requirements = policy.required_indicators()
        if len(requirements) != 1 or requirements[0].timeframe != "strategy":
            raise ValueError("signal generation requires one strategy-timeframe policy input")
        key = series_key_of(
            requirements[0].name,
            requirements[0].params,
            config.timeframe,
        )
        volatility = indicators.get(key)
        if isinstance(volatility, bool) or not isinstance(volatility, float | int):
            raise ValueError(f"money management requires current {key}")
        plan = policy.plan_entry(
            decision,
            MarketSnapshot(
                reference_price=decision.reference_price,
                volatility=float(volatility),
                volatility_name=key,
                volatility_timestamp=candle.close_time,
            ),
            # Signal generation has no account or order authority. The manual
            # policy's protection and fixed leverage do not depend on these
            # placeholder sizing inputs, and requested quantity is not emitted.
            AccountRiskSnapshot(
                equity=1.0,
                available_cash=1.0,
                market_type=MarketType(config.market_type),
            ),
            RiskLimits(
                risk_per_trade=0.01,
                maintenance_margin_rate=0.004,
            ),
        )
        return TradingSignal(
            symbol=decision.symbol,
            timestamp=decision.timestamp,
            confidence=decision.confidence,
            price=decision.reference_price,
            stop_loss=plan.stop_loss,
            take_profit=plan.take_profit,
            market_type=config.market_type,
            leverage=plan.requested_leverage,
            reason=decision.reason,
            metadata={
                **dict(decision.metadata),
                "decision_action": decision.action.value,
                "money_management": {
                    "policy_id": policy.id,
                    "policy_version": policy.version,
                    "resolved_config": dict(policy.resolved_config()),
                    "volatility_name": key,
                    "volatility": float(volatility),
                    "volatility_timestamp": candle.close_time.isoformat(),
                },
            },
        )

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
            params=self._resolved_params,
            mode=config.mode,
            timeframe=config.timeframe,
            candle=candle,
            signal=signal,
            signal_type=signal_type,
            intent=intent,
            side=side,
        )

    def _report_series_gaps(
        self,
        candles: list[Candle],
        detected_at: datetime,
    ) -> tuple[DataGap, ...]:
        reports: list[DataGap] = []
        for left, right in zip(candles, candles[1:], strict=False):
            if right.open_time > left.close_time:
                reports.append(
                    self._record_gap(
                        symbol=left.symbol,
                        timeframe=left.timeframe,
                        previous_close=left.close_time,
                        next_open=right.open_time,
                        detected_at=detected_at,
                        duration=left.close_time - left.open_time,
                    )
                )
        return tuple(reports)

    def _report_poll_gaps(
        self,
        config: SignalGenerationConfig,
        last_close: datetime,
        fresh: list[Candle],
        detected_at: datetime,
    ) -> tuple[DataGap, ...]:
        reports: list[DataGap] = []
        duration = self._timeframe_duration(config.timeframe)
        if fresh:
            if fresh[0].open_time > last_close:
                reports.append(
                    self._record_gap(
                        symbol=config.symbol,
                        timeframe=config.timeframe,
                        previous_close=last_close,
                        next_open=fresh[0].open_time,
                        detected_at=detected_at,
                        duration=duration,
                    )
                )
            reports.extend(self._report_series_gaps(fresh, detected_at))
            return tuple(reports)

        missing_start = max(
            last_close,
            self._reported_missing_until or last_close,
        )
        complete_missing, _ = divmod(detected_at - missing_start, duration)
        if complete_missing > 0:
            report = self._record_gap(
                symbol=config.symbol,
                timeframe=config.timeframe,
                previous_close=missing_start,
                next_open=None,
                detected_at=detected_at,
                duration=duration,
                missing_candles=complete_missing,
            )
            self._reported_missing_until = missing_start + complete_missing * duration
            reports.append(report)
        return tuple(reports)

    def _record_gap(
        self,
        *,
        symbol: str,
        timeframe: str,
        previous_close: datetime,
        next_open: datetime | None,
        detected_at: datetime,
        duration: timedelta,
        missing_candles: int | None = None,
    ) -> DataGap:
        if missing_candles is None:
            assert next_open is not None
            quotient, remainder = divmod(next_open - previous_close, duration)
            missing_candles = quotient + int(remainder > timedelta(0))
        report = DataGap(
            symbol=symbol,
            timeframe=timeframe,
            previous_close=previous_close,
            next_open=next_open,
            detected_at=detected_at,
            missing_candles=missing_candles,
        )
        self._gap_reports.append(report)
        _LOGGER.warning(
            "detected %d missing finalized candle(s) for %s %s after %s through %s",
            report.missing_candles,
            symbol,
            timeframe,
            previous_close.isoformat(),
            (next_open or detected_at).isoformat(),
        )
        return report

    @staticmethod
    def _timeframe_duration(timeframe: str) -> timedelta:
        match = re.fullmatch(r"(?P<count>[1-9]\d*)(?P<unit>[mhd])", timeframe)
        if match is None:
            raise ValueError(f"unsupported timeframe: {timeframe!r}")
        units = {
            "m": timedelta(minutes=1),
            "h": timedelta(hours=1),
            "d": timedelta(days=1),
        }
        return int(match.group("count")) * units[match.group("unit")]

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
