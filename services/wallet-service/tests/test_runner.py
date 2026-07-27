"""Verify finite, boundary-aligned draining of paper-only wallet signals."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from threading import Event

from wallet_service.application import WalletPollingRunner, WalletService
from wallet_service.core import RiskPolicy
from wallet_service.domain import PaperIntent, SignalConsumptionStatus
from wallet_service.infrastructure import PaperBroker, PaperCostModel
from wallet_service.main import run_paper_wallet

from tests.conftest import QueueDouble, RepositoryDouble, paper_signal


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
