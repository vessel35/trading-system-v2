"""Canonical tests for shared runner observability."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from service_commons.observability import (
    RunnerLogFormatter,
    RunnerObservability,
    safe_exception_info,
)

SENSITIVE_VALUE = "postgresql://operator:fake-password@db.example/service"


class _Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def _secret_exception() -> Exception:
    try:
        raise ValueError(SENSITIVE_VALUE)
    except ValueError as exc:
        return exc


def test_log_formatter_renders_allowlist_and_redacts_exception_secrets() -> None:
    record = logging.LogRecord(
        "service.runner",
        logging.ERROR,
        __file__,
        1,
        "poll failed",
        (),
        safe_exception_info(_secret_exception()),
    )
    vars(record).update(
        {
            "event": "runner_poll_error",
            "service": "test-service",
            "count": 3,
            "api_key": SENSITIVE_VALUE,
            "database_url": SENSITIVE_VALUE,
        }
    )

    rendered = RunnerLogFormatter().format(record)

    assert "poll failed" in rendered
    assert 'event="runner_poll_error"' in rendered
    assert 'service="test-service"' in rendered
    assert "count=3" in rendered
    assert "details redacted" in rendered
    assert "api_key" not in rendered
    assert "database_url" not in rendered
    assert "fake-password" not in rendered
    assert SENSITIVE_VALUE not in rendered


def test_metrics_increment_for_every_runner_outcome() -> None:
    clock = _Clock(datetime(2026, 7, 27, tzinfo=UTC))
    observability = RunnerObservability(
        "test-service",
        counter_names=(
            "warmups",
            "poll_cycles",
            "poll_errors",
            "signals_generated",
            "signals_consumed_filled",
            "signals_consumed_rejected",
            "signals_consumed_skipped",
            "gap_rewarmups",
            "records_processed",
            "gaps_detected",
        ),
        stale_after_seconds=180,
        clock=clock,
    )

    observability.mark_running()
    observability.record_warmup()
    observability.record_poll()
    observability.record_poll_error()
    observability.record_signal_generated(2)
    observability.record_signal_consumed("filled")
    observability.record_signal_consumed("rejected", 2)
    observability.record_signal_consumed("skipped", 3)
    observability.record_gap_rewarmup()
    observability.record_processed(4, gaps_detected=2)

    snapshot = observability.metrics_snapshot()
    assert snapshot.counters == {
        "warmups": 1,
        "poll_cycles": 1,
        "poll_errors": 1,
        "signals_generated": 2,
        "signals_consumed_filled": 1,
        "signals_consumed_rejected": 2,
        "signals_consumed_skipped": 3,
        "gap_rewarmups": 1,
        "records_processed": 4,
        "gaps_detected": 2,
    }
    assert snapshot.last_poll_at == clock.now
    assert snapshot.last_progress_at == clock.now
    assert snapshot.failure_streaks == {"poll_errors": 1, "gap_rewarmups": 1}
    assert "fake-password" not in repr(snapshot)


def test_health_snapshot_detects_stalled_polling() -> None:
    clock = _Clock(datetime(2026, 7, 27, tzinfo=UTC))
    observability = RunnerObservability(
        "test-service",
        counter_names=("poll_cycles", "poll_errors"),
        stale_after_seconds=60,
        clock=clock,
    )
    observability.mark_running()

    clock.advance(61)
    snapshot = observability.health_snapshot()

    assert snapshot.running is True
    assert snapshot.stale is True
    assert snapshot.stale_reason == "poll_stalled"
    assert snapshot.healthy is False
    assert "fake-password" not in repr(snapshot)


def test_health_snapshot_detects_repeated_poll_failures() -> None:
    clock = _Clock(datetime(2026, 7, 27, tzinfo=UTC))
    observability = RunnerObservability(
        "test-service",
        counter_names=("poll_cycles", "poll_errors"),
        stale_after_seconds=600,
        failure_streak_threshold=2,
        clock=clock,
    )
    observability.mark_running()
    observability.record_poll_error()
    observability.record_poll_error()

    snapshot = observability.health_snapshot()

    assert snapshot.stale is True
    assert snapshot.stale_reason == "poll_errors"
    assert snapshot.metrics.failure_streaks == {"poll_errors": 2}
