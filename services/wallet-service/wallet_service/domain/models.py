"""Define paper signal envelopes and persisted execution facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from core_lib.types import Candle, Fill, Position, PositionSide, TradingSignal


class PaperIntent(StrEnum):
    """Name the wallet action already derived by signal-service."""

    ENTER = "enter"
    REVERSE = "reverse"
    EXIT = "exit"


class RiskRejected(RuntimeError):
    """Report a deliberate safety rejection before any fill or persistence."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class PaperSignal:
    """Carry one finalized decision and its explicit next paper candle."""

    wallet_id: str
    signal_id: str
    decision_candle: Candle
    execution_candle: Candle
    signal: TradingSignal
    intent: PaperIntent
    side: PositionSide | None
    mode: str = "paper"

    def __post_init__(self) -> None:
        if not self.wallet_id or not self.signal_id:
            raise ValueError("wallet_id and signal_id must not be empty")
        if self.mode != "paper":
            raise ValueError("wallet-service accepts paper signals only")
        object.__setattr__(self, "intent", PaperIntent(self.intent))
        if self.side is not None:
            object.__setattr__(self, "side", PositionSide(self.side))
        if self.intent in {PaperIntent.ENTER, PaperIntent.REVERSE} and self.side is None:
            raise ValueError("entry and reversal signals require a directional side")
        if self.intent is PaperIntent.EXIT and self.side is not None:
            raise ValueError("exit signals must not propose a new side")
        if self.signal.symbol != self.decision_candle.symbol:
            raise ValueError("signal symbol must match the decision candle")
        if self.execution_candle.symbol != self.decision_candle.symbol:
            raise ValueError("decision and execution candles must share a symbol")
        if self.execution_candle.timeframe != self.decision_candle.timeframe:
            raise ValueError("decision and execution candles must share a timeframe")
        if self.execution_candle.open_time != self.decision_candle.close_time:
            raise ValueError("paper execution requires the contiguous next candle")
        self._require_aware(self.signal.timestamp, "feature_ts")
        self._require_aware(self.decision_time, "decision_ts")
        self._require_aware(self.execution_candle.open_time, "execution candle open_time")
        if self.signal.timestamp > self.decision_time:
            raise ValueError("feature_ts must not be later than decision_ts")

    @property
    def feature_time(self) -> datetime:
        """Return the strategy evidence time."""
        return self.signal.timestamp

    @property
    def decision_time(self) -> datetime:
        """Return the finalized decision boundary."""
        return self.decision_candle.close_time

    @staticmethod
    def _require_aware(value: datetime, name: str) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class AccountingSnapshot:
    """Persist the shared accounting identity after an atomic signal."""

    occurred_at: datetime
    cash_balance: Decimal
    position_value: Decimal
    total_equity: Decimal
    fee_total: Decimal
    slippage_total: Decimal

    def __post_init__(self) -> None:
        values = (
            self.cash_balance,
            self.position_value,
            self.total_equity,
            self.fee_total,
            self.slippage_total,
        )
        if any(not isinstance(value, Decimal) for value in values):
            raise TypeError("accounting values must be Decimal")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("accounting timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True)
class WalletExecution:
    """Bundle the transaction that wallet_db commits or rolls back as one unit."""

    wallet_id: str
    signal_id: str
    symbol: str
    fills: tuple[Fill, ...]
    position: Position | None
    accounting: AccountingSnapshot

    def __post_init__(self) -> None:
        if not self.wallet_id or not self.signal_id or not self.symbol:
            raise ValueError("execution identity must not be empty")
        if not self.fills:
            raise ValueError("an execution transaction requires at least one fill")
        if any(fill.symbol != self.symbol for fill in self.fills):
            raise ValueError("all fills must match the execution symbol")
