"""Define Decimal orders and pre-normalization float order requests."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from .enums import MarketType, OrderSide, OrderStatus, OrderType, PositionSide
from .money import ZERO, quantize_amount, quantize_price


@dataclass(slots=True)
class Order:
    """An order identity and its current lifecycle facts."""

    id: str
    wallet_id: str | None
    signal_id: str | None
    order_type: OrderType
    side: OrderSide
    symbol: str
    quantity: Decimal
    price: Decimal | None
    filled_quantity: Decimal
    average_filled_price: Decimal | None
    status: OrderStatus
    fee: Decimal
    client_order_id: UUID
    market_type: MarketType
    position_side: PositionSide
    reduce_only: bool
    close_position: bool
    stop_price: Decimal | None
    time_in_force: str

    def __post_init__(self) -> None:
        self.order_type = OrderType(self.order_type)
        self.side = OrderSide(self.side)
        self.status = OrderStatus(self.status)
        self.market_type = MarketType(self.market_type)
        self.position_side = PositionSide(self.position_side)

        self.quantity = quantize_amount(self.quantity)
        self.filled_quantity = quantize_amount(self.filled_quantity)
        self.fee = quantize_amount(self.fee)
        if self.price is not None:
            self.price = quantize_price(self.price)
        if self.average_filled_price is not None:
            self.average_filled_price = quantize_price(self.average_filled_price)
        if self.stop_price is not None:
            self.stop_price = quantize_price(self.stop_price)

        if self.quantity <= ZERO:
            raise ValueError("quantity must be positive")
        if self.filled_quantity < ZERO:
            raise ValueError("filled_quantity must be non-negative")
        if self.filled_quantity > self.quantity:
            raise ValueError("filled_quantity cannot exceed quantity")
        if self.fee < ZERO:
            raise ValueError("fee must be non-negative")
        if self.reduce_only and self.close_position:
            raise ValueError("reduce_only and close_position are mutually exclusive")

    def remaining_quantity(self) -> Decimal:
        """Return the normalized quantity that has not filled."""
        return quantize_amount(self.quantity - self.filled_quantity)


@dataclass(slots=True)
class OrderRequest:
    """A float-valued order intent before Broker normalization."""

    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float | None
    stop_price: float | None
    market_type: MarketType
    position_side: PositionSide
    reduce_only: bool
    close_position: bool
    time_in_force: str

    def __post_init__(self) -> None:
        self.side = OrderSide(self.side)
        self.order_type = OrderType(self.order_type)
        self.market_type = MarketType(self.market_type)
        self.position_side = PositionSide(self.position_side)
        if not isinstance(self.quantity, float):
            raise TypeError("quantity must be float before normalization")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        for name, value in (("price", self.price), ("stop_price", self.stop_price)):
            if value is not None:
                if not isinstance(value, float):
                    raise TypeError(f"{name} must be float or None before normalization")
                if value <= 0:
                    raise ValueError(f"{name} must be positive")
        if self.reduce_only and self.close_position:
            raise ValueError("reduce_only and close_position are mutually exclusive")
