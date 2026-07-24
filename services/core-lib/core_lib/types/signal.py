"""Define decision-only trading signals and persistence-only signal types."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .enums import MarketType

__all__ = ["SignalType", "TradingSignal"]


class SignalType(StrEnum):
    """Persistence-only signal direction."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(slots=True)
class TradingSignal:
    """A strategy decision containing evidence and proposed protection levels."""

    symbol: str
    timestamp: datetime
    confidence: float
    price: float
    stop_loss: float | None
    take_profit: float | None
    market_type: MarketType
    leverage: int | None
    reason: str
    metadata: dict[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.confidence, float):
            raise TypeError("confidence must be float")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not isinstance(self.price, float):
            raise TypeError("price must be float")
        if self.price <= 0:
            raise ValueError("price must be positive")
        for name, value in (
            ("stop_loss", self.stop_loss),
            ("take_profit", self.take_profit),
        ):
            if value is not None:
                if not isinstance(value, float):
                    raise TypeError(f"{name} must be float or None")
                if value <= 0:
                    raise ValueError(f"{name} must be positive")
        if self.leverage is not None:
            if isinstance(self.leverage, bool) or not isinstance(self.leverage, int):
                raise TypeError("leverage must be int or None")
            if self.leverage <= 0:
                raise ValueError("leverage must be positive")
        self.market_type = MarketType(self.market_type)
