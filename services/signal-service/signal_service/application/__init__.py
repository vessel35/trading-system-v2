"""Expose the signal generation use case and its output ports."""

from .observability import RunnerHealthSnapshot, RunnerMetricsSnapshot
from .ports import SignalDataFeed, SignalQueue, SignalSink
from .runner import SignalGenerator, SignalPollingRunner, seconds_until_next_poll
from .service import (
    SignalCycleResult,
    SignalGenerationService,
    SignalStateRecoveryRequired,
)

__all__ = [
    "SignalCycleResult",
    "SignalDataFeed",
    "SignalGenerator",
    "SignalGenerationService",
    "SignalPollingRunner",
    "SignalQueue",
    "SignalSink",
    "SignalStateRecoveryRequired",
    "RunnerHealthSnapshot",
    "RunnerMetricsSnapshot",
    "seconds_until_next_poll",
]
