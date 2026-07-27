"""In-process runner metrics and health snapshots."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from types import MappingProxyType

_CONSUMPTION_OUTCOMES = ("filled", "rejected", "skipped")


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class RunnerMetricsSnapshot:
    """A read-only point-in-time view of in-process runner counters."""

    warmups: int
    poll_cycles: int
    poll_errors: int
    signals_generated: int
    signals_consumed: Mapping[str, int]
    gap_rewarmups: int
    records_processed: int
    gaps_detected: int
    last_poll_at: datetime | None
    last_progress_at: datetime | None


@dataclass(frozen=True, slots=True)
class RunnerHealthSnapshot:
    """Expose runner liveness and signal-processing progress without transport."""

    service: str
    running: bool
    last_poll_at: datetime | None
    last_progress_at: datetime | None
    stale: bool
    healthy: bool
    stale_after_seconds: float
    observed_at: datetime
    metrics: RunnerMetricsSnapshot


class RunnerObservability:
    """Maintain bounded, thread-safe counters and progress timestamps."""

    def __init__(
        self,
        service: str,
        *,
        stale_after_seconds: float,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if not service:
            raise ValueError("service must not be empty")
        if stale_after_seconds <= 0:
            raise ValueError("stale threshold must be positive")
        self._service = service
        self._stale_after_seconds = stale_after_seconds
        self._clock = clock
        self._lock = RLock()
        self._running = False
        self._started_at: datetime | None = None
        self._last_poll_at: datetime | None = None
        self._last_progress_at: datetime | None = None
        self._warmups = 0
        self._poll_cycles = 0
        self._poll_errors = 0
        self._signals_generated = 0
        self._signals_consumed = {outcome: 0 for outcome in _CONSUMPTION_OUTCOMES}
        self._gap_rewarmups = 0
        self._records_processed = 0
        self._gaps_detected = 0

    def mark_running(self) -> None:
        """Mark the runner active and begin a new staleness window."""

        with self._lock:
            self._running = True
            self._started_at = self._now()

    def mark_stopped(self) -> None:
        """Mark the runner inactive without discarding accumulated counters."""

        with self._lock:
            self._running = False

    def record_warmup(self) -> None:
        with self._lock:
            self._warmups += 1

    def record_poll(self) -> None:
        with self._lock:
            self._poll_cycles += 1
            self._last_poll_at = self._now()

    def record_poll_error(self) -> None:
        with self._lock:
            self._poll_errors += 1

    def record_signal_generated(self, count: int = 1) -> None:
        if count < 0:
            raise ValueError("generated signal count must not be negative")
        if count == 0:
            return
        with self._lock:
            self._signals_generated += count
            self._last_progress_at = self._now()

    def record_signal_consumed(self, outcome: str, count: int = 1) -> None:
        if outcome not in self._signals_consumed:
            raise ValueError(f"unsupported signal outcome: {outcome}")
        if count < 0:
            raise ValueError("consumed signal count must not be negative")
        if count == 0:
            return
        with self._lock:
            self._signals_consumed[outcome] += count
            self._last_progress_at = self._now()

    def record_gap_rewarmup(self) -> None:
        with self._lock:
            self._gap_rewarmups += 1

    def record_processed(self, count: int, *, gaps_detected: int = 0) -> None:
        if count < 0 or gaps_detected < 0:
            raise ValueError("processed and gap counts must not be negative")
        with self._lock:
            self._records_processed += count
            self._gaps_detected += gaps_detected
            if count:
                self._last_progress_at = self._now()

    def metrics_snapshot(self) -> RunnerMetricsSnapshot:
        """Return detached counter values safe for concurrent readers."""

        with self._lock:
            return self._metrics_unlocked()

    def health_snapshot(self) -> RunnerHealthSnapshot:
        """Return liveness, progress, and staleness at the current clock time."""

        with self._lock:
            observed_at = self._now()
            reference = self._started_at
            if self._last_progress_at is not None and (
                reference is None or self._last_progress_at > reference
            ):
                reference = self._last_progress_at
            stale = (
                self._running
                and reference is not None
                and (observed_at - reference).total_seconds() > self._stale_after_seconds
            )
            metrics = self._metrics_unlocked()
            return RunnerHealthSnapshot(
                service=self._service,
                running=self._running,
                last_poll_at=self._last_poll_at,
                last_progress_at=self._last_progress_at,
                stale=stale,
                healthy=self._running and not stale,
                stale_after_seconds=self._stale_after_seconds,
                observed_at=observed_at,
                metrics=metrics,
            )

    def _metrics_unlocked(self) -> RunnerMetricsSnapshot:
        return RunnerMetricsSnapshot(
            warmups=self._warmups,
            poll_cycles=self._poll_cycles,
            poll_errors=self._poll_errors,
            signals_generated=self._signals_generated,
            signals_consumed=MappingProxyType(dict(self._signals_consumed)),
            gap_rewarmups=self._gap_rewarmups,
            records_processed=self._records_processed,
            gaps_detected=self._gaps_detected,
            last_poll_at=self._last_poll_at,
            last_progress_at=self._last_progress_at,
        )

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observability clock must return a timezone-aware datetime")
        return value.astimezone(UTC)
