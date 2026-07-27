"""Verify the finite, boundary-aligned signal polling runner."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from threading import Event
from typing import cast

import pytest
from core_lib.types import MarketType
from signal_service.application import (
    RunnerHealthSnapshot,
    SignalCycleResult,
    SignalPollingRunner,
    SignalStateRecoveryRequired,
    seconds_until_next_poll,
)
from signal_service.application.observability import RunnerLogFormatter
from signal_service.core import SignalGenerationConfig
from signal_service.domain import PersistedSignal, SignalMode
from signal_service.main import run_signal_generator

SENSITIVE_ERROR = "postgresql://operator:fake-password@db.example/signals"


class _Clock:
    def __init__(self, now: float) -> None:
        self.now = now
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.now += delay


class _Generator:
    def __init__(self, stop_event: Event, *, stop_after_polls: int) -> None:
        self._stop_event = stop_event
        self._stop_after_polls = stop_after_polls
        self.starts: list[tuple[SignalGenerationConfig, datetime]] = []
        self.polls: list[datetime] = []
        self.rewarms: list[datetime] = []

    def start(
        self,
        config: SignalGenerationConfig,
        decision_time: datetime,
    ) -> object:
        self.starts.append((config, decision_time))
        return None

    def poll(self, decision_time: datetime) -> object:
        self.polls.append(decision_time)
        if len(self.polls) == self._stop_after_polls:
            self._stop_event.set()
        return None

    def rewarm(self, decision_time: datetime) -> object:
        self.rewarms.append(decision_time)
        return None


class _UnrecoverableGenerator(_Generator):
    def poll(self, decision_time: datetime) -> object:
        self.polls.append(decision_time)
        if len(self.polls) == 1:
            raise ValueError(SENSITIVE_ERROR)
        self._stop_event.set()
        return None


class _RecoveringGeneratedGenerator(_Generator):
    def _generated(self) -> SignalCycleResult:
        return SignalCycleResult(cast(PersistedSignal, object()))

    def start(
        self,
        config: SignalGenerationConfig,
        decision_time: datetime,
    ) -> object:
        super().start(config, decision_time)
        return self._generated()

    def poll(self, decision_time: datetime) -> object:
        self.polls.append(decision_time)
        raise SignalStateRecoveryRequired("sensitive detail must not be logged")

    def rewarm(self, decision_time: datetime) -> object:
        self.rewarms.append(decision_time)
        self._stop_event.set()
        return self._generated()


class _RepeatedGapGenerator(_Generator):
    def poll(self, decision_time: datetime) -> object:
        self.polls.append(decision_time)
        raise SignalStateRecoveryRequired("repeated gap")

    def rewarm(self, decision_time: datetime) -> object:
        self.rewarms.append(decision_time)
        return None


def _config() -> SignalGenerationConfig:
    return SignalGenerationConfig(
        strategy_id="vessel-reference",
        symbol="BTCUSDT",
        timeframe="1h",
        market_type=MarketType.FUTURES,
        mode=SignalMode.PAPER,
    )


def test_main_warms_once_then_polls_aligned_boundaries_for_finite_cycles() -> None:
    stop_event = Event()
    clock = _Clock(15.0)
    generator = _Generator(stop_event, stop_after_polls=2)

    run_signal_generator(
        generator,
        _config(),
        wall_clock=clock,
        sleep=clock.sleep,
        stop_event=stop_event,
    )

    assert generator.starts == [(_config(), datetime(1970, 1, 1, 0, 0, 15, tzinfo=UTC))]
    assert generator.polls == [
        datetime(1970, 1, 1, 0, 1, 2, tzinfo=UTC),
        datetime(1970, 1, 1, 0, 2, 2, tzinfo=UTC),
    ]
    assert clock.sleeps == [47.0, 60.0]
    assert generator.rewarms == []
    assert logging.getLogger().level == logging.INFO
    assert all(
        isinstance(handler.formatter, RunnerLogFormatter)
        for handler in logging.getLogger().handlers
    )


def test_stop_during_sleep_prevents_another_poll() -> None:
    stop_event = Event()
    clock = _Clock(59.5)
    generator = _Generator(stop_event, stop_after_polls=1)

    def stop_during_sleep(delay: float) -> None:
        clock.sleep(delay)
        stop_event.set()

    runner = SignalPollingRunner(
        generator,
        _config(),
        wall_clock=clock,
        sleep=stop_during_sleep,
        stop_event=stop_event,
    )
    runner.run()

    assert len(generator.starts) == 1
    assert generator.polls == []
    assert clock.sleeps == [2.5]
    assert runner.stopped is True


def test_unrelated_poll_error_does_not_trigger_indicator_rewarm(
    caplog: pytest.LogCaptureFixture,
) -> None:
    stop_event = Event()
    clock = _Clock(15.0)
    generator = _UnrecoverableGenerator(stop_event, stop_after_polls=2)
    runner = SignalPollingRunner(
        generator,
        _config(),
        wall_clock=clock,
        sleep=clock.sleep,
        stop_event=stop_event,
    )

    with caplog.at_level("ERROR"):
        runner.run()

    assert len(generator.polls) == 2
    assert generator.rewarms == []
    assert "signal_poll_failed" in caplog.text
    assert "signal_poll_rewarmed" not in caplog.text
    assert "fake-password" not in caplog.text
    assert runner.metrics_snapshot().counters["poll_cycles"] == 2
    assert runner.metrics_snapshot().counters["poll_errors"] == 1
    error_record = next(
        record for record in caplog.records if getattr(record, "event", None) == "runner_poll_error"
    )
    assert getattr(error_record, "service", None) == "signal"
    assert getattr(error_record, "symbol", None) == "BTCUSDT"
    assert getattr(error_record, "reason", None) == "poll_failed"
    assert getattr(error_record, "error_type", None) == "ValueError"
    assert error_record.exc_info is not None
    vars(error_record)["api_key"] = SENSITIVE_ERROR
    formatted = RunnerLogFormatter().format(error_record)
    assert "Traceback (most recent call last)" in formatted
    assert 'event="runner_poll_error"' in formatted
    assert 'service="signal"' in formatted
    assert "fake-password" not in formatted
    assert "fake-password" not in repr(runner.metrics_snapshot())
    assert "fake-password" not in repr(runner.health_snapshot())


def test_observability_counts_generation_gap_rewarm_and_structured_events(
    caplog: pytest.LogCaptureFixture,
) -> None:
    stop_event = Event()
    clock = _Clock(15.0)
    generator = _RecoveringGeneratedGenerator(stop_event, stop_after_polls=1)
    runner = SignalPollingRunner(
        generator,
        _config(),
        wall_clock=clock,
        sleep=clock.sleep,
        stop_event=stop_event,
    )

    with caplog.at_level(logging.INFO):
        runner.run()

    metrics = runner.metrics_snapshot()
    assert metrics.counters == {
        "warmups": 2,
        "poll_cycles": 1,
        "poll_errors": 0,
        "signals_generated": 2,
        "gap_rewarmups": 1,
    }
    assert metrics.last_poll_at == datetime(1970, 1, 1, 0, 1, 2, tzinfo=UTC)
    assert metrics.last_progress_at == datetime(1970, 1, 1, 0, 1, 2, tzinfo=UTC)
    events = {getattr(record, "event", None) for record in caplog.records}
    assert {
        "runner_warmup",
        "runner_poll_started",
        "signal_generated",
        "runner_gap_rewarmup",
        "runner_poll_completed",
        "runner_shutdown",
    } <= events
    rewarm_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "runner_gap_rewarmup"
    )
    assert getattr(rewarm_record, "service", None) == "signal"
    assert getattr(rewarm_record, "count", None) == 1
    assert getattr(rewarm_record, "outcome", None) == "completed"
    assert getattr(rewarm_record, "reason", None) == "state_recovery_required"
    formatted = RunnerLogFormatter().format(rewarm_record)
    assert 'event="runner_gap_rewarmup"' in formatted
    assert 'symbol="BTCUSDT"' in formatted
    assert 'outcome="completed"' in formatted


def test_normal_polling_without_signals_remains_healthy() -> None:
    stop_event = Event()
    clock = _Clock(15.0)
    generator = _Generator(stop_event, stop_after_polls=5)
    snapshots: list[RunnerHealthSnapshot] = []
    runner: SignalPollingRunner

    def inspect_while_running(delay: float) -> None:
        clock.sleep(delay)
        snapshots.append(runner.health_snapshot())

    runner = SignalPollingRunner(
        generator,
        _config(),
        wall_clock=clock,
        sleep=inspect_while_running,
        stop_event=stop_event,
    )
    runner.run()

    assert len(snapshots) == 5
    assert all(snapshot.running for snapshot in snapshots)
    assert all(snapshot.last_progress_at is None for snapshot in snapshots)
    assert all(snapshot.stale is False for snapshot in snapshots)
    assert all(snapshot.stale_reason is None for snapshot in snapshots)
    assert all(snapshot.healthy for snapshot in snapshots)
    assert runner.health_snapshot().running is False


def test_health_snapshot_detects_a_poll_that_stops_making_liveness_progress() -> None:
    stop_event = Event()
    clock = _Clock(15.0)
    snapshots: list[RunnerHealthSnapshot] = []
    runner: SignalPollingRunner

    class _StallingGenerator(_Generator):
        def poll(self, decision_time: datetime) -> object:
            self.polls.append(decision_time)
            clock.now += 181
            snapshots.append(runner.health_snapshot())
            stop_event.set()
            return None

    runner = SignalPollingRunner(
        _StallingGenerator(stop_event, stop_after_polls=1),
        _config(),
        wall_clock=clock,
        sleep=clock.sleep,
        stop_event=stop_event,
    )
    runner.run()

    assert len(snapshots) == 1
    assert snapshots[0].running is True
    assert snapshots[0].stale is True
    assert snapshots[0].stale_reason == "poll_stalled"
    assert snapshots[0].healthy is False


def test_health_snapshot_detects_repeated_gap_rewarmup_stall() -> None:
    stop_event = Event()
    clock = _Clock(15.0)
    snapshots: list[RunnerHealthSnapshot] = []
    runner: SignalPollingRunner
    generator = _RepeatedGapGenerator(stop_event, stop_after_polls=99)

    def inspect_after_three_rewarmups(delay: float) -> None:
        clock.sleep(delay)
        if len(clock.sleeps) == 4:
            snapshots.append(runner.health_snapshot())
            stop_event.set()

    runner = SignalPollingRunner(
        generator,
        _config(),
        wall_clock=clock,
        sleep=inspect_after_three_rewarmups,
        stop_event=stop_event,
    )
    runner.run()

    assert len(generator.rewarms) == 3
    assert len(snapshots) == 1
    assert snapshots[0].stale is True
    assert snapshots[0].stale_reason == "gap_rewarmups"
    assert snapshots[0].metrics.failure_streaks == {
        "poll_errors": 0,
        "gap_rewarmups": 3,
    }


@pytest.mark.parametrize(
    ("interval", "buffer", "message"),
    [
        (0, 0, "positive"),
        (60, -1, "within"),
        (60, 60, "within"),
    ],
)
def test_poll_alignment_rejects_invalid_configuration(
    interval: int,
    buffer: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        seconds_until_next_poll(
            0.0,
            poll_interval_seconds=interval,
            poll_buffer_seconds=buffer,
        )
