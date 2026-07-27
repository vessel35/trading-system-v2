"""Expose the signal generation use case and its output ports."""

from .ports import SignalDataFeed, SignalQueue, SignalSink
from .runner import SignalGenerator, SignalPollingRunner, seconds_until_next_poll
from .service import SignalCycleResult, SignalGenerationService

__all__ = [
    "SignalCycleResult",
    "SignalDataFeed",
    "SignalGenerator",
    "SignalGenerationService",
    "SignalPollingRunner",
    "SignalQueue",
    "SignalSink",
    "seconds_until_next_poll",
]
