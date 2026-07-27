"""Continuously drain ready paper signals at aligned polling boundaries."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Event

from service_commons.observability import (
    RunnerHealthSnapshot,
    RunnerMetricsSnapshot,
    RunnerObservability,
    safe_exception_info,
)
from service_commons.polling import seconds_until_next_poll

from .service import WalletService

_LOGGER = logging.getLogger(__name__)


class WalletPollingRunner:
    """Drain every ready paper signal, then wait for the next aligned poll."""

    def __init__(
        self,
        service: WalletService,
        *,
        poll_interval_seconds: int = 60,
        poll_buffer_seconds: int = 2,
        wall_clock: Callable[[], float] = time.time,
        sleep: Callable[[float], object] | None = None,
        stop_event: Event | None = None,
        stale_after_seconds: float | None = None,
        failure_streak_threshold: int = 3,
    ) -> None:
        seconds_until_next_poll(
            0.0,
            poll_interval_seconds=poll_interval_seconds,
            poll_buffer_seconds=poll_buffer_seconds,
        )
        self._service = service
        self._poll_interval_seconds = poll_interval_seconds
        self._poll_buffer_seconds = poll_buffer_seconds
        self._wall_clock = wall_clock
        self._stop_event = Event() if stop_event is None else stop_event
        self._sleep = self._stop_event.wait if sleep is None else sleep
        self._observability = RunnerObservability(
            "wallet",
            counter_names=(
                "poll_cycles",
                "poll_errors",
                "signals_consumed_filled",
                "signals_consumed_rejected",
                "signals_consumed_skipped",
            ),
            stale_after_seconds=(
                poll_interval_seconds * 3.0 if stale_after_seconds is None else stale_after_seconds
            ),
            failure_streak_threshold=failure_streak_threshold,
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
        """Return the current in-process wallet-runner counters."""

        return self._observability.metrics_snapshot()

    def health_snapshot(self) -> RunnerHealthSnapshot:
        """Return liveness and signal-consumption progress for health checks."""

        return self._observability.health_snapshot()

    def drain_once(self) -> int:
        """Process ready messages until the queue reports that it is empty."""

        consumed = 0
        while not self._stop_event.is_set():
            self._service.run_once()
            if not self._service.last_run_received:
                break
            consumed += 1
            outcome = self._service.last_run_outcome
            if outcome is not None:
                self._observability.record_signal_consumed(outcome.value)
                _LOGGER.info(
                    "paper_wallet_signal_consumed",
                    extra=self._event_fields(
                        "signal_consumed",
                        count=1,
                        outcome=outcome.value,
                        reason=self._service.last_run_reason or "terminal_outcome",
                        symbol=self._service.last_run_symbol or "unknown",
                    ),
                )
        return consumed

    def run(self) -> None:
        """Poll and drain until the injected stop event is set."""

        self._observability.mark_running()
        _LOGGER.info(
            "paper_wallet_runner_started",
            extra=self._event_fields(
                "runner_started",
                count=0,
                poll_interval_seconds=self._poll_interval_seconds,
            ),
        )
        try:
            while not self._stop_event.is_set():
                self._observability.record_poll()
                _LOGGER.info(
                    "paper_wallet_poll_started",
                    extra=self._event_fields("runner_poll_started", count=0),
                )
                try:
                    consumed = self.drain_once()
                except Exception as exc:
                    self._observability.record_poll_error()
                    _LOGGER.error(
                        "paper_wallet_poll_failed",
                        extra=self._event_fields(
                            "runner_poll_error",
                            count=1,
                            outcome="error",
                            reason="poll_failed",
                            error_type=type(exc).__name__,
                            symbol=self._service.last_run_symbol or "unknown",
                        ),
                        exc_info=safe_exception_info(exc),
                    )
                else:
                    self._observability.record_poll_success()
                    _LOGGER.info(
                        "paper_wallet_queue_drained",
                        extra=self._event_fields(
                            "runner_poll_completed",
                            count=consumed,
                            outcome="completed",
                        ),
                    )
                if self._stop_event.is_set():
                    break
                delay = seconds_until_next_poll(
                    self._wall_clock(),
                    poll_interval_seconds=self._poll_interval_seconds,
                    poll_buffer_seconds=self._poll_buffer_seconds,
                )
                self._sleep(delay)
        finally:
            self._observability.mark_stopped()
            _LOGGER.info(
                "paper_wallet_runner_stopped",
                extra=self._event_fields(
                    "runner_shutdown",
                    count=0,
                    outcome="stopped",
                    reason="stop_requested",
                ),
            )

    def _decision_time(self) -> datetime:
        return datetime.fromtimestamp(self._wall_clock(), tz=UTC)

    @staticmethod
    def _event_fields(event: str, **fields: object) -> dict[str, object]:
        return {
            "event": event,
            "service": "wallet",
            "symbol": "unknown",
            **fields,
        }
