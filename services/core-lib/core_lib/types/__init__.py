"""Define shared domain value types and money precision."""

from .candle import Candle
from .enums import (
    ExitReason,
    MarginType,
    MarketType,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
)
from .fill import Fill
from .money import (
    ONE_HUNDRED,
    Q_AMOUNT,
    Q_FEE_RATE,
    Q_PERCENT,
    Q_PRICE,
    Q_RATIO,
    ZERO,
    quantize_amount,
    quantize_fee_rate,
    quantize_percent,
    quantize_price,
    quantize_ratio,
)
from .order import Order, OrderRequest
from .position import Position
from .signal import SignalType, TradingSignal
from .trade import Trade

__all__ = [
    "ONE_HUNDRED",
    "Q_AMOUNT",
    "Q_FEE_RATE",
    "Q_PERCENT",
    "Q_PRICE",
    "Q_RATIO",
    "ZERO",
    "Candle",
    "ExitReason",
    "Fill",
    "MarginType",
    "MarketType",
    "Order",
    "OrderRequest",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "Position",
    "PositionSide",
    "SignalType",
    "Trade",
    "TradingSignal",
    "quantize_amount",
    "quantize_fee_rate",
    "quantize_percent",
    "quantize_price",
    "quantize_ratio",
]
