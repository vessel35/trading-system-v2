"""Expose the signal generation use case and its output ports."""

from service_commons.observability import RunnerHealthSnapshot, RunnerMetricsSnapshot
from service_commons.polling import seconds_until_next_poll

from .ports import SignalDataFeed, SignalQueue, SignalSink
from .runner import SignalGenerator, SignalPollingRunner
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
