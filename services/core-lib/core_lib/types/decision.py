"""Define strategy-owned decisions without execution or money-management fields."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

__all__ = ["DecisionAction", "DecisionIntent"]


class DecisionAction(StrEnum):
    """The explicit entry/exit action selected by a strategy."""

    ENTER_LONG = "ENTER_LONG"
    ENTER_SHORT = "ENTER_SHORT"
    EXIT = "EXIT"
    HOLD = "HOLD"


@dataclass(frozen=True, slots=True)
class DecisionIntent:
    """A deterministic strategy decision that contains no sizing or leverage."""

    action: DecisionAction
    symbol: str
    timestamp: datetime
    reference_price: float
    confidence: float
    reason: str
    metadata: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", DecisionAction(self.action))
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        if (
            isinstance(self.reference_price, bool)
            or not isinstance(self.reference_price, float)
            or not math.isfinite(self.reference_price)
            or self.reference_price <= 0.0
        ):
            raise ValueError("reference_price must be a finite positive float")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, float)
            or not math.isfinite(self.confidence)
            or not 0.0 <= self.confidence <= 1.0
        ):
            raise ValueError("confidence must be a finite float between 0 and 1")
        if not self.reason.strip():
            raise ValueError("reason must not be empty")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
