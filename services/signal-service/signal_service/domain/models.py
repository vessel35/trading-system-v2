"""Define values owned by the signal-service persistence boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from core_lib.types import Candle, PositionSide, SignalType, TradingSignal


class SignalMode(StrEnum):
    """Name the execution environment that produced an operational signal."""

    PAPER = "paper"
    LIVE = "live"


class SignalIntent(StrEnum):
    """Persist the action inferred by the driver from a decision-only signal."""

    ENTER = "enter"
    REVERSE = "reverse"
    EXIT = "exit"


@dataclass(frozen=True, slots=True)
class DataGap:
    """Report missing finalized candles without synthesizing replacements."""

    symbol: str
    timeframe: str
    previous_close: datetime
    next_open: datetime | None
    detected_at: datetime
    missing_candles: int

    def __post_init__(self) -> None:
        if not self.symbol or not self.timeframe:
            raise ValueError("gap series identity must not be empty")
        if self.missing_candles <= 0:
            raise ValueError("missing_candles must be positive")
        if self.next_open is not None and self.next_open <= self.previous_close:
            raise ValueError("gap next_open must be later than previous_close")


@dataclass(frozen=True, slots=True)
class PersistedSignal:
    """Join a core decision to driver-owned operational context."""

    strategy_id: str
    params: Mapping[str, object]
    mode: SignalMode
    timeframe: str
    candle: Candle
    signal: TradingSignal
    signal_type: SignalType
    intent: SignalIntent
    side: PositionSide | None

    def __post_init__(self) -> None:
        if not self.strategy_id:
            raise ValueError("strategy_id must not be empty")
        if not self.timeframe:
            raise ValueError("timeframe must not be empty")
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))
        if self.candle.timeframe != self.timeframe:
            raise ValueError("persisted timeframe must match the decision candle")
        if self.signal.symbol != self.candle.symbol:
            raise ValueError("signal symbol must match the decision candle")
        if self.signal.timestamp > self.candle.close_time:
            raise ValueError("signal cannot be later than the decision candle")
