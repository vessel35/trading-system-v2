"""Verify finite, boundary-aligned draining of paper-only wallet signals."""

from __future__ import annotations

import logging
from dataclasses import replace
from decimal import Decimal
from threading import Event

import pytest
from service_commons.observability import RunnerLogFormatter
from wallet_service.application import (
    RunnerHealthSnapshot,
    WalletPollingRunner,
    WalletService,
)
from wallet_service.core import RiskPolicy
from wallet_service.domain import (
    PaperIntent,
    PaperSignal,
    SignalConsumptionStatus,
    WalletExecution,
)
from wallet_service.infrastructure import PaperBroker, PaperCostModel
from wallet_service.main import run_paper_wallet

from tests.conftest import QueueDouble, RepositoryDouble, paper_signal

SENSITIVE_ERROR = "postgresql://operator:fake-password@db.example/wallet"


class _Clock:
    def __init__(
        self,
        now: float,
        stop_event: Event,
        queue: QueueDouble,
    ) -> None:
        self.now = now
        self._stop_event = stop_event
        self._queue = queue
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.now += delay
        if len(self.sleeps) == 2:
            self._queue.messages.append(
                paper_signal(
                    "signal-3",
                    decision_index=1,
                    intent=PaperIntent.EXIT,
                    side=None,
                    execution_open=110.0,
                    stop_loss=None,
                    take_profit=None,
                )
            )
        elif len(self.sleeps) == 3:
            self._stop_event.set()


class _SelectiveRepository(RepositoryDouble):
    def store(self, execution: WalletExecution) -> bool:
        if execution.signal_id == "signal-skipped":
            return False
        return super().store(execution)


class _PoisonQueue(QueueDouble):
    def receive(self) -> PaperSignal | None:
        raise ValueError(SENSITIVE_ERROR)


def test_main_drains_rejection_then_fill_and_repeats_until_stopped() -> None:
    rejected = replace(
        paper_signal("signal-1"),
        wallet_id="another-wallet",
    )
    queue = QueueDouble([rejected, paper_signal("signal-2")])
    repository = RepositoryDouble()
    service = _paper_service(queue, repository)
    stop_event = Event()
    clock = _Clock(15.0, stop_event, queue)

    run_paper_wallet(
        service,
        wall_clock=clock,
        sleep=clock.sleep,
        stop_event=stop_event,
    )

    assert queue.messages == []
    assert queue.close_calls == 1
    assert [entry[1:3] for entry in repository.consumptions] == [
        ("signal-1", SignalConsumptionStatus.REJECTED),
        ("signal-2", SignalConsumptionStatus.FILLED),
        ("signal-3", SignalConsumptionStatus.FILLED),
    ]
    assert len(repository.executions) == 2
    assert repository.executions[-1].position is None
    assert clock.sleeps == [47.0, 60.0, 60.0]
    assert logging.getLogger().level == logging.INFO
    assert all(
        isinstance(handler.formatter, RunnerLogFormatter)
        for handler in logging.getLogger().handlers
    )


def test_drain_once_checks_stop_without_touching_the_queue() -> None:
    queue = QueueDouble([paper_signal()])
    repository = RepositoryDouble()
    stop_event = Event()
    stop_event.set()
    runner = WalletPollingRunner(
        _paper_service(queue, repository),
        stop_event=stop_event,
    )

    assert runner.drain_once() == 0
    assert len(queue.messages) == 1
    assert repository.executions == []


def test_observability_counts_every_consumption_outcome_and_structured_events(
    caplog: pytest.LogCaptureFixture,
) -> None:
    rejected = replace(
        paper_signal("signal-rejected"),
        wallet_id="another-wallet",
    )
    queue = QueueDouble(
        [
            rejected,
            paper_signal("signal-filled"),
            paper_signal(
                "signal-skipped",
                decision_index=1,
                intent=PaperIntent.EXIT,
                side=None,
                execution_open=110.0,
                stop_loss=None,
                take_profit=None,
            ),
        ]
    )
    repository = _SelectiveRepository()
    service = _paper_service(queue, repository)
    stop_event = Event()
    now = 15.0
    snapshots: list[RunnerHealthSnapshot] = []
    runner: WalletPollingRunner

    def wall_clock() -> float:
        return now

    def stop_after_first_cycle(delay: float) -> None:
        nonlocal now
        now += delay
        snapshots.append(runner.health_snapshot())
        stop_event.set()

    runner = WalletPollingRunner(
        service,
        wall_clock=wall_clock,
        sleep=stop_after_first_cycle,
        stop_event=stop_event,
    )

    with caplog.at_level(logging.INFO):
        runner.run()

    metrics = runner.metrics_snapshot()
    assert metrics.counters == {
        "poll_cycles": 1,
        "poll_errors": 0,
        "signals_consumed_filled": 1,
        "signals_consumed_rejected": 1,
        "signals_consumed_skipped": 1,
    }
    assert metrics.last_progress_at is not None
    assert len(snapshots) == 1
    assert snapshots[0].last_progress_at is not None
    assert snapshots[0].stale is False
    assert snapshots[0].stale_reason is None
    assert snapshots[0].healthy is True
    records = [
        record for record in caplog.records if getattr(record, "event", None) == "signal_consumed"
    ]
    assert {getattr(record, "outcome", None) for record in records} == {
        "filled",
        "rejected",
        "skipped",
    }
    assert all(getattr(record, "service", None) == "wallet" for record in records)
    assert all(getattr(record, "symbol", None) == "BTCUSDT" for record in records)
    assert all(getattr(record, "count", None) == 1 for record in records)
    formatted = RunnerLogFormatter().format(records[0])
    assert 'event="signal_consumed"' in formatted
    assert 'service="wallet"' in formatted
    assert 'symbol="BTCUSDT"' in formatted
    events = {getattr(record, "event", None) for record in caplog.records}
    assert {
        "runner_started",
        "runner_poll_started",
        "runner_poll_completed",
        "signal_consumed",
        "runner_shutdown",
    } <= events


def test_poison_poll_error_is_secret_safe_and_staleness_is_visible(
    caplog: pytest.LogCaptureFixture,
) -> None:
    queue = _PoisonQueue()
    repository = RepositoryDouble()
    service = _paper_service(queue, repository)
    stop_event = Event()
    now = 15.0
    sleep_calls = 0
    snapshots: list[RunnerHealthSnapshot] = []
    runner: WalletPollingRunner

    def wall_clock() -> float:
        return now

    def inspect_after_error(delay: float) -> None:
        nonlocal now, sleep_calls
        now += delay
        sleep_calls += 1
        if sleep_calls == 3:
            snapshots.append(runner.health_snapshot())
            stop_event.set()

    runner = WalletPollingRunner(
        service,
        wall_clock=wall_clock,
        sleep=inspect_after_error,
        stop_event=stop_event,
        stale_after_seconds=600,
    )

    with caplog.at_level(logging.ERROR):
        runner.run()

    metrics = runner.metrics_snapshot()
    assert metrics.counters == {
        "poll_cycles": 3,
        "poll_errors": 3,
        "signals_consumed_filled": 0,
        "signals_consumed_rejected": 0,
        "signals_consumed_skipped": 0,
    }
    assert metrics.last_progress_at is None
    assert len(snapshots) == 1
    assert snapshots[0].running is True
    assert snapshots[0].stale is True
    assert snapshots[0].stale_reason == "poll_errors"
    assert snapshots[0].healthy is False
    assert snapshots[0].metrics.failure_streaks == {"poll_errors": 3}
    error_record = next(
        record for record in caplog.records if getattr(record, "event", None) == "runner_poll_error"
    )
    assert getattr(error_record, "service", None) == "wallet"
    assert getattr(error_record, "error_type", None) == "ValueError"
    assert getattr(error_record, "reason", None) == "poll_failed"
    assert error_record.exc_info is not None
    formatted = RunnerLogFormatter().format(error_record)
    assert "Traceback (most recent call last)" in formatted
    assert 'event="runner_poll_error"' in formatted
    assert 'service="wallet"' in formatted
    assert "fake-password" not in formatted
    assert "fake-password" not in caplog.text
    assert "fake-password" not in repr(metrics)
    assert "fake-password" not in repr(runner.health_snapshot())


def _paper_service(
    queue: QueueDouble,
    repository: RepositoryDouble,
) -> WalletService:
    return WalletService(
        "wallet-1",
        queue,
        PaperBroker(PaperCostModel()),
        repository,
        RiskPolicy(frozenset({"BTCUSDT"})),
        initial_cash=Decimal("1000"),
    )
