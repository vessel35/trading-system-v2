"""Verify the finite, boundary-aligned signal polling runner."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Event

import pytest
from core_lib.types import MarketType
from signal_service.application import SignalPollingRunner, seconds_until_next_poll
from signal_service.core import SignalGenerationConfig
from signal_service.domain import SignalMode
from signal_service.main import run_signal_generator


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
