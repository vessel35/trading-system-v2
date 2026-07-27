"""Continuously drain ready paper signals at aligned polling boundaries."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from threading import Event

from .service import WalletService

_LOGGER = logging.getLogger(__name__)


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

    @property
    def stopped(self) -> bool:
        """Return whether shutdown has been requested."""

        return self._stop_event.is_set()

    def stop(self) -> None:
        """Wake the runner and request a cooperative shutdown."""

        self._stop_event.set()

    def drain_once(self) -> int:
        """Process ready messages until the queue reports that it is empty."""

        consumed = 0
        while not self._stop_event.is_set():
            self._service.run_once()
            if not self._service.last_run_received:
                break
            consumed += 1
        return consumed

    def run(self) -> None:
        """Poll and drain until the injected stop event is set."""

        _LOGGER.info("paper_wallet_runner_started")
        while not self._stop_event.is_set():
            try:
                consumed = self.drain_once()
                if consumed:
                    _LOGGER.info("paper_wallet_queue_drained messages=%d", consumed)
            except Exception:
                _LOGGER.exception("paper_wallet_poll_failed")
            if self._stop_event.is_set():
                break
            delay = seconds_until_next_poll(
                self._wall_clock(),
                poll_interval_seconds=self._poll_interval_seconds,
                poll_buffer_seconds=self._poll_buffer_seconds,
            )
            self._sleep(delay)
        _LOGGER.info("paper_wallet_runner_stopped")
