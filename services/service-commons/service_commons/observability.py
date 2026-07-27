"""In-process runner metrics, health snapshots, and safe structured logging."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from types import MappingProxyType, TracebackType

_CONSUMPTION_OUTCOMES = ("filled", "rejected", "skipped")
_DIAGNOSTIC_FIELDS = (
    "event",
    "service",
    "strategy_id",
    "symbol",
    "timeframe",
    "exchange",
    "count",
    "outcome",
    "reason",
    "error_type",
    "poll_interval_seconds",
)
_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class RunnerLogFormatter(logging.Formatter):
    """Render only allowlisted, non-sensitive structured diagnostics."""

    def __init__(self) -> None:
        super().__init__(_LOG_FORMAT)

    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        diagnostics = " ".join(
            f"{field}={json.dumps(getattr(record, field), default=str, ensure_ascii=True)}"
            for field in _DIAGNOSTIC_FIELDS
            if hasattr(record, field)
        )
        return rendered if not diagnostics else f"{rendered} {diagnostics}"


def configure_logging(level: int = logging.INFO) -> None:
    """Configure process-owned handlers to emit INFO and structured fields."""

    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    for handler in root.handlers:
        if handler.level > level:
            handler.setLevel(level)
        handler.setFormatter(RunnerLogFormatter())


def safe_exception_info(
    exc: Exception,
) -> tuple[type[BaseException], BaseException, TracebackType | None]:
    """Keep the original stack while replacing a potentially secret-bearing value."""

    redacted = RuntimeError(f"{type(exc).__name__}: details redacted")
    return RuntimeError, redacted, exc.__traceback__


@dataclass(frozen=True, slots=True)
class RunnerMetricsSnapshot:
    """A read-only point-in-time view of service-relevant runner counters."""

    counters: Mapping[str, int]
    last_poll_at: datetime | None
    last_successful_poll_at: datetime | None
    last_progress_at: datetime | None
    failure_streaks: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class RunnerHealthSnapshot:
    """Separate polling liveness from optional data progress."""

    service: str
    running: bool
    last_poll_at: datetime | None
    last_successful_poll_at: datetime | None
    last_progress_at: datetime | None
    stale: bool
    stale_reason: str | None
    healthy: bool
    stale_after_seconds: float
    failure_streak_threshold: int
    observed_at: datetime
    metrics: RunnerMetricsSnapshot


class RunnerObservability:
    """Maintain bounded, thread-safe counters and liveness state."""

    def __init__(
        self,
        service: str,
        *,
        counter_names: Iterable[str],
        stale_after_seconds: float,
        failure_streak_threshold: int = 3,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if not service:
            raise ValueError("service must not be empty")
        if stale_after_seconds <= 0:
            raise ValueError("stale threshold must be positive")
        if failure_streak_threshold <= 0:
            raise ValueError("failure streak threshold must be positive")
        names = tuple(counter_names)
        if not names or any(not name for name in names) or len(set(names)) != len(names):
            raise ValueError("counter names must be non-empty and unique")
        self._service = service
        self._stale_after_seconds = stale_after_seconds
        self._failure_streak_threshold = failure_streak_threshold
        self._clock = clock
        self._lock = RLock()
        self._running = False
        self._started_at: datetime | None = None
        self._last_poll_at: datetime | None = None
        self._last_successful_poll_at: datetime | None = None
        self._last_progress_at: datetime | None = None
        self._counters = dict.fromkeys(names, 0)
        streak_names = ("poll_errors", "gap_rewarmups")
        self._failure_streaks = {name: 0 for name in streak_names if name in self._counters}

    def mark_running(self) -> None:
        """Mark the runner active and begin a new liveness window."""

        with self._lock:
            self._running = True
            self._started_at = self._now()
            for name in self._failure_streaks:
                self._failure_streaks[name] = 0

    def mark_stopped(self) -> None:
        """Mark the runner inactive without discarding accumulated counters."""

        with self._lock:
            self._running = False

    def record_warmup(self) -> None:
        with self._lock:
            self._increment("warmups")

    def record_poll(self) -> None:
        with self._lock:
            self._increment("poll_cycles")
            self._last_poll_at = self._now()

    def record_poll_success(self, *, gap_rewarmed: bool = False) -> None:
        """Record a completed cycle and reset recovered failure streaks."""

        with self._lock:
            self._last_successful_poll_at = self._now()
            self._failure_streaks["poll_errors"] = 0
            if not gap_rewarmed:
                gap_streak = self._failure_streaks.get("gap_rewarmups")
                if gap_streak is not None:
                    self._failure_streaks["gap_rewarmups"] = 0

    def record_poll_error(self) -> None:
        with self._lock:
            self._increment("poll_errors")
            self._failure_streaks["poll_errors"] += 1

    def record_signal_generated(self, count: int = 1) -> None:
        self._require_non_negative(count, name="generated signal")
        if count == 0:
            return
        with self._lock:
            self._increment("signals_generated", count)
            self._last_progress_at = self._now()

    def record_signal_consumed(self, outcome: str, count: int = 1) -> None:
        if outcome not in _CONSUMPTION_OUTCOMES:
            raise ValueError(f"unsupported signal outcome: {outcome}")
        self._require_non_negative(count, name="consumed signal")
        if count == 0:
            return
        with self._lock:
            self._increment(f"signals_consumed_{outcome}", count)
            self._last_progress_at = self._now()

    def record_gap_rewarmup(self) -> None:
        with self._lock:
            self._increment("gap_rewarmups")
            self._failure_streaks["gap_rewarmups"] += 1

    def record_processed(self, count: int, *, gaps_detected: int = 0) -> None:
        self._require_non_negative(count, name="processed record")
        self._require_non_negative(gaps_detected, name="detected gap")
        with self._lock:
            self._increment("records_processed", count)
            self._increment("gaps_detected", gaps_detected)
            if count:
                self._last_progress_at = self._now()

    def metrics_snapshot(self) -> RunnerMetricsSnapshot:
        """Return detached counter values safe for concurrent readers."""

        with self._lock:
            return self._metrics_unlocked()

    def health_snapshot(self) -> RunnerHealthSnapshot:
        """Return liveness and failure-streak health independently of data progress."""

        with self._lock:
            observed_at = self._now()
            stale_reason = self._stale_reason_unlocked(observed_at)
            metrics = self._metrics_unlocked()
            return RunnerHealthSnapshot(
                service=self._service,
                running=self._running,
                last_poll_at=self._last_poll_at,
                last_successful_poll_at=self._last_successful_poll_at,
                last_progress_at=self._last_progress_at,
                stale=stale_reason is not None,
                stale_reason=stale_reason,
                healthy=self._running and stale_reason is None,
                stale_after_seconds=self._stale_after_seconds,
                failure_streak_threshold=self._failure_streak_threshold,
                observed_at=observed_at,
                metrics=metrics,
            )

    def _metrics_unlocked(self) -> RunnerMetricsSnapshot:
        return RunnerMetricsSnapshot(
            counters=MappingProxyType(dict(self._counters)),
            last_poll_at=self._last_poll_at,
            last_successful_poll_at=self._last_successful_poll_at,
            last_progress_at=self._last_progress_at,
            failure_streaks=MappingProxyType(dict(self._failure_streaks)),
        )

    def _stale_reason_unlocked(self, observed_at: datetime) -> str | None:
        if not self._running:
            return None
        reference = self._started_at
        if self._last_poll_at is not None and (reference is None or self._last_poll_at > reference):
            reference = self._last_poll_at
        if (
            reference is not None
            and (observed_at - reference).total_seconds() > self._stale_after_seconds
        ):
            return "poll_stalled"
        if self._failure_streaks["poll_errors"] >= self._failure_streak_threshold:
            return "poll_errors"
        if self._failure_streaks.get("gap_rewarmups", 0) >= self._failure_streak_threshold:
            return "gap_rewarmups"
        return None

    def _increment(self, name: str, count: int = 1) -> None:
        try:
            self._counters[name] += count
        except KeyError as exc:
            raise RuntimeError(f"counter is not configured for {self._service}: {name}") from exc

    @staticmethod
    def _require_non_negative(count: int, *, name: str) -> None:
        if count < 0:
            raise ValueError(f"{name} count must not be negative")

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observability clock must return a timezone-aware datetime")
        return value.astimezone(UTC)
