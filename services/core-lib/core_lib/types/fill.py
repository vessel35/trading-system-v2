"""Define explicit fill facts."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .enums import ExitReason, OrderSide, PositionSide
from .money import ZERO, quantize_amount, quantize_price


@dataclass(slots=True)
class Fill:
    """A single explicit execution fact consumed by positions and accounting."""

    order_id: str
    symbol: str
    side: OrderSide
    position_side: PositionSide
    reference_price: Decimal
    price: Decimal
    quantity: Decimal
    fee: Decimal
    slippage: Decimal
    liquidity: str
    timestamp: datetime
    reduce_only: bool
    exit_reason: ExitReason | None
    gap_filled: bool = False
    qty_truncated: bool = False

    def __post_init__(self) -> None:
        self.side = OrderSide(self.side)
        self.position_side = PositionSide(self.position_side)
        if self.exit_reason is not None:
            self.exit_reason = ExitReason(self.exit_reason)

        self.reference_price = quantize_price(self.reference_price)
        self.price = quantize_price(self.price)
        self.quantity = quantize_amount(self.quantity)
        self.fee = quantize_amount(self.fee)
        self.slippage = quantize_amount(self.slippage)

        if not self.order_id:
            raise ValueError("order_id must not be empty")
        if self.reference_price <= ZERO or self.price <= ZERO:
            raise ValueError("fill prices must be positive")
        if self.quantity <= ZERO:
            raise ValueError("fill quantity must be positive")
        if self.fee < ZERO or self.slippage < ZERO:
            raise ValueError("fee and slippage must be non-negative")
        if self.liquidity not in {"maker", "taker"}:
            raise ValueError("liquidity must be 'maker' or 'taker'")
