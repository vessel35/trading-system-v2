"""Define shared order, position, market, margin, and exit enums."""

from enum import StrEnum


class OrderType(StrEnum):
    """Supported exchange order kinds."""

    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    TAKE_PROFIT_MARKET = "take_profit_market"
    TRAILING_STOP_MARKET = "trailing_stop_market"


class OrderSide(StrEnum):
    """Exchange order direction."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(StrEnum):
    """Order lifecycle state."""

    NEW = "new"
    PARTIALLY_FILLED = "partially_filled"
    PENDING_CANCEL = "pending_cancel"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"
    FAILED = "failed"

    def is_terminal(self) -> bool:
        """Return whether no further state transition is possible."""
        return self in {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.EXPIRED,
            OrderStatus.REJECTED,
            OrderStatus.FAILED,
        }

    def is_active(self) -> bool:
        """Return whether the order remains active."""
        return self in {
            OrderStatus.NEW,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.PENDING_CANCEL,
        }


class PositionSide(StrEnum):
    """Exchange position side or one-way mode."""

    LONG = "long"
    SHORT = "short"
    BOTH = "both"


class MarginType(StrEnum):
    """Position margin isolation mode."""

    CROSS = "cross"
    ISOLATED = "isolated"


class MarketType(StrEnum):
    """Trading market kind."""

    SPOT = "spot"
    FUTURES = "futures"


class ExitReason(StrEnum):
    """Reason a position was closed."""

    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"
    LIQUIDATION = "LIQUIDATION"
    SIGNAL_EXIT = "SIGNAL_EXIT"
    REVERSAL = "REVERSAL"
    DATA_GAP = "DATA_GAP"
    END_OF_DATA = "END_OF_DATA"
