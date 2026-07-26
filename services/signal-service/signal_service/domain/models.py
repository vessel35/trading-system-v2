"""Define values owned by the signal-service persistence boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

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
class PersistedSignal:
    """Join a core decision to driver-owned operational context."""

    strategy_id: str
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
        if self.candle.timeframe != self.timeframe:
            raise ValueError("persisted timeframe must match the decision candle")
        if self.signal.symbol != self.candle.symbol:
            raise ValueError("signal symbol must match the decision candle")
        if self.signal.timestamp > self.candle.close_time:
            raise ValueError("signal cannot be later than the decision candle")
