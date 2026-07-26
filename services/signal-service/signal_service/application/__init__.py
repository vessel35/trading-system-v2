"""Expose the signal generation use case and its output ports."""

from .ports import SignalDataFeed, SignalQueue, SignalSink
from .service import SignalCycleResult, SignalGenerationService

__all__ = [
    "SignalCycleResult",
    "SignalDataFeed",
    "SignalGenerationService",
    "SignalQueue",
    "SignalSink",
]
