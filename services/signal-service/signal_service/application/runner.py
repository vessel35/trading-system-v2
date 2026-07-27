"""Continuously poll finalized-candle boundaries for new trading signals."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Event
from typing import Protocol

from signal_service.core import SignalGenerationConfig

from .service import SignalStateRecoveryRequired

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

    @property
    def stopped(self) -> bool:
        """Return whether shutdown has been requested."""

        return self._stop_event.is_set()

    def stop(self) -> None:
        """Wake the runner and request a cooperative shutdown."""

        self._stop_event.set()

    def run(self) -> None:
        """Warm once and poll until the injected stop event is set."""

        if self._stop_event.is_set():
            return
        self._generator.start(self._config, self._decision_time())
        _LOGGER.info(
            "signal_runner_started strategy_id=%s symbol=%s timeframe=%s",
            self._config.strategy_id,
            self._config.symbol,
            self._config.timeframe,
        )
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
            try:
                self._generator.poll(decision_time)
            except SignalStateRecoveryRequired as exc:
                try:
                    self._generator.rewarm(decision_time)
                except Exception:
                    _LOGGER.exception(
                        "signal_rewarm_failed strategy_id=%s symbol=%s timeframe=%s",
                        self._config.strategy_id,
                        self._config.symbol,
                        self._config.timeframe,
                    )
                else:
                    _LOGGER.warning(
                        "signal_poll_rewarmed strategy_id=%s symbol=%s timeframe=%s reason=%s",
                        self._config.strategy_id,
                        self._config.symbol,
                        self._config.timeframe,
                        exc,
                    )
            except Exception:
                _LOGGER.exception(
                    "signal_poll_failed strategy_id=%s symbol=%s timeframe=%s",
                    self._config.strategy_id,
                    self._config.symbol,
                    self._config.timeframe,
                )
        _LOGGER.info(
            "signal_runner_stopped strategy_id=%s symbol=%s timeframe=%s",
            self._config.strategy_id,
            self._config.symbol,
            self._config.timeframe,
        )

    def _decision_time(self) -> datetime:
        return datetime.fromtimestamp(self._wall_clock(), tz=UTC)
