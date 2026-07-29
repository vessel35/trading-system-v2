"""Run the shared finalized-candle indicator and Adaptee call contract."""

from __future__ import annotations

import logging
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from core_lib.indicators import (
    DEFAULT_REGISTRY,
    IndicatorRegistry,
    IndicatorSpec,
    IndicatorState,
    assert_finalized,
)
from core_lib.money_management import (
    AccountRiskSnapshot,
    ManualMoneyManagement,
    MarketSnapshot,
    MoneyManagementPolicy,
    RiskLimits,
)
from core_lib.strategy import AdapterManager, StrategyAdapter, StrategyConfig
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
        queue: SignalQueue | None = None,
    ) -> None:
        self._feed = feed
        self._manager = manager
        self._sink = sink
        self._indicators = indicators
        self._queue = queue
        self._config: SignalGenerationConfig | None = None
        self._strategy: StrategyAdapter | None = None
        self._money_management: MoneyManagementPolicy | None = None
        self._specs: list[IndicatorSpec] = []
        self._states: dict[str, IndicatorState] = {}
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
        runtime = self._manager.create_runtime(
            config.strategy_id,
            {"strategy_id": config.strategy_id, "params": dict(config.params)},
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
                }
                for requirement in runtime.money_management.required_indicators()
                if requirement.timeframe == "strategy"
            ]
        )
        specs = self._indicators.resolve_specs(
            "auto",
            [*metadata.required_indicators, *policy_indicators],
            (),
        )
        required_warmup = max(
            metadata.min_history,
            max(spec.min_history for spec in specs),
        )
        resolved = StrategyConfig.resolve(
            strategy.get_parameter_schema(),
            {"strategy_id": config.strategy_id, "params": dict(config.params)},
        )
        serialized_params = StrategyConfig.serialize(resolved)["params"]
        if not isinstance(serialized_params, dict):
            raise TypeError("core_lib resolved strategy params must serialize to a dict")
        history = self._confirmed_history(config, boundary)
        if len(history) < required_warmup + 1:
            raise ValueError(
                "insufficient finalized history: "
                f"requires {required_warmup + 1}, got {len(history)}"
            )

        self._config = config
        self._strategy = strategy
        self._money_management = runtime.money_management
        self._specs = specs
        self._states = {spec.identifier: spec.make_state() for spec in specs}
        self._resolved_params = dict(serialized_params)
        decision_window = history[-(required_warmup + 1) :]
        gaps = self._report_series_gaps(decision_window, boundary)
        self._confirmed = decision_window[:-1]
        for state in self._states.values():
            state.seed(self._confirmed)
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
        self._reported_missing_until = max(
            candle.close_time,
            self._reported_missing_until or candle.close_time,
        )
        if signal is None:
            return None
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
        atr = indicators.get("atr:period=14")
        if isinstance(atr, bool) or not isinstance(atr, float | int):
            raise ValueError("manual money management requires current ATR(14)")
        plan = policy.plan_entry(
            decision,
            MarketSnapshot(
                reference_price=decision.reference_price,
                volatility=float(atr),
                volatility_name="ATR(14)",
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
                    "volatility": float(atr),
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
