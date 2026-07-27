"""Continuously poll finalized-candle boundaries for new trading signals."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Event
from typing import Protocol

from signal_service.core import SignalGenerationConfig

from .observability import (
    RunnerHealthSnapshot,
    RunnerMetricsSnapshot,
    RunnerObservability,
)
from .service import SignalCycleResult, SignalStateRecoveryRequired

_LOGGER = logging.getLogger(__name__)


class SignalGenerator(Protocol):
    """The warmed signal-generation operations used by the runner."""

    def start(
        self,
        config: SignalGenerationConfig,
        decision_time: datetime,
    ) -> object:
        """Warm indicator state and judge the latest finalized candle."""

    def poll(self, decision_time: datetime) -> object:
        """Judge the next finalized candle, if one is available."""

    def rewarm(self, decision_time: datetime) -> object:
        """Re-seed indicator state at the latest finalized candle."""


def seconds_until_next_poll(
    now: float,
    *,
    poll_interval_seconds: int = 60,
    poll_buffer_seconds: int = 2,
) -> float:
    """Align polling to a wall-clock period boundary plus a close buffer."""

    if poll_interval_seconds <= 0:
        raise ValueError("poll interval must be positive")
    if not 0 <= poll_buffer_seconds < poll_interval_seconds:
        raise ValueError("poll buffer must be within the polling interval")
    seconds_into_period = now % poll_interval_seconds
    if seconds_into_period < poll_buffer_seconds:
        return poll_buffer_seconds - seconds_into_period
    return poll_interval_seconds - seconds_into_period + poll_buffer_seconds


class SignalPollingRunner:
    """Warm once, then poll continuously at confirmed-candle boundaries."""

    def __init__(
        self,
        generator: SignalGenerator,
        config: SignalGenerationConfig,
        *,
        poll_interval_seconds: int = 60,
        poll_buffer_seconds: int = 2,
        wall_clock: Callable[[], float] = time.time,
        sleep: Callable[[float], object] | None = None,
        stop_event: Event | None = None,
        stale_after_seconds: float | None = None,
    ) -> None:
        seconds_until_next_poll(
            0.0,
            poll_interval_seconds=poll_interval_seconds,
            poll_buffer_seconds=poll_buffer_seconds,
        )
        self._generator = generator
        self._config = config
        self._poll_interval_seconds = poll_interval_seconds
        self._poll_buffer_seconds = poll_buffer_seconds
        self._wall_clock = wall_clock
        self._stop_event = Event() if stop_event is None else stop_event
        self._sleep = self._stop_event.wait if sleep is None else sleep
        self._observability = RunnerObservability(
            "signal",
            stale_after_seconds=(
                poll_interval_seconds * 3.0 if stale_after_seconds is None else stale_after_seconds
            ),
            clock=self._decision_time,
        )

    @property
    def stopped(self) -> bool:
        """Return whether shutdown has been requested."""

        return self._stop_event.is_set()

    def stop(self) -> None:
        """Wake the runner and request a cooperative shutdown."""

        self._stop_event.set()

    def metrics_snapshot(self) -> RunnerMetricsSnapshot:
        """Return the current in-process signal-runner counters."""

        return self._observability.metrics_snapshot()

    def health_snapshot(self) -> RunnerHealthSnapshot:
        """Return liveness and signal-generation progress for health checks."""

        return self._observability.health_snapshot()

    def run(self) -> None:
        """Warm once and poll until the injected stop event is set."""

        if self._stop_event.is_set():
            return
        self._observability.mark_running()
        try:
            warmup_result = self._generator.start(self._config, self._decision_time())
            self._observability.record_warmup()
            _LOGGER.info(
                "signal_runner_started",
                extra=self._event_fields(
                    "runner_warmup",
                    count=1,
                    poll_interval_seconds=self._poll_interval_seconds,
                ),
            )
            self._record_generated(warmup_result)
            while not self._stop_event.is_set():
                delay = seconds_until_next_poll(
                    self._wall_clock(),
                    poll_interval_seconds=self._poll_interval_seconds,
                    poll_buffer_seconds=self._poll_buffer_seconds,
                )
                self._sleep(delay)
                if self._stop_event.is_set():
                    break
                decision_time = self._decision_time()
                self._observability.record_poll()
                _LOGGER.info(
                    "signal_poll_started",
                    extra=self._event_fields("runner_poll_started", count=0),
                )
                try:
                    result = self._generator.poll(decision_time)
                except SignalStateRecoveryRequired:
                    self._observability.record_gap_rewarmup()
                    try:
                        result = self._generator.rewarm(decision_time)
                    except Exception as exc:
                        self._observability.record_poll_error()
                        _LOGGER.error(
                            "signal_rewarm_failed",
                            extra=self._event_fields(
                                "runner_poll_error",
                                count=1,
                                outcome="error",
                                reason="gap_rewarmup_failed",
                                error_type=type(exc).__name__,
                            ),
                        )
                    else:
                        self._observability.record_warmup()
                        generated = self._record_generated(result)
                        _LOGGER.warning(
                            "signal_poll_rewarmed",
                            extra=self._event_fields(
                                "runner_gap_rewarmup",
                                count=1,
                                outcome="completed",
                                reason="state_recovery_required",
                            ),
                        )
                        self._log_poll_completed(generated)
                except Exception as exc:
                    self._observability.record_poll_error()
                    _LOGGER.error(
                        "signal_poll_failed",
                        extra=self._event_fields(
                            "runner_poll_error",
                            count=1,
                            outcome="error",
                            reason="poll_failed",
                            error_type=type(exc).__name__,
                        ),
                    )
                else:
                    self._log_poll_completed(self._record_generated(result))
        finally:
            self._observability.mark_stopped()
            _LOGGER.info(
                "signal_runner_stopped",
                extra=self._event_fields(
                    "runner_shutdown",
                    count=0,
                    outcome="stopped",
                    reason="stop_requested",
                ),
            )

    def _decision_time(self) -> datetime:
        return datetime.fromtimestamp(self._wall_clock(), tz=UTC)

    def _record_generated(self, result: object) -> int:
        if not isinstance(result, SignalCycleResult) or result.signal is None:
            return 0
        self._observability.record_signal_generated()
        _LOGGER.info(
            "signal_generated",
            extra=self._event_fields(
                "signal_generated",
                count=1,
                outcome="generated",
            ),
        )
        return 1

    def _log_poll_completed(self, generated: int) -> None:
        _LOGGER.info(
            "signal_poll_completed",
            extra=self._event_fields(
                "runner_poll_completed",
                count=generated,
                outcome="completed",
            ),
        )

    def _event_fields(self, event: str, **fields: object) -> dict[str, object]:
        return {
            "event": event,
            "service": "signal",
            "strategy_id": self._config.strategy_id,
            "symbol": self._config.symbol,
            "timeframe": self._config.timeframe,
            **fields,
        }
