"""Define Decimal orders and pre-normalization float order requests."""

from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar
from uuid import UUID

from .enums import MarketType, OrderSide, OrderStatus, OrderType, PositionSide
from .money import ZERO, quantize_amount, quantize_price


@dataclass(slots=True)
class Order:
    """An order identity and its current lifecycle facts."""

    VALID_TRANSITIONS: ClassVar[dict[OrderStatus, frozenset[OrderStatus]]] = {
        OrderStatus.NEW: frozenset(
            {
                OrderStatus.PARTIALLY_FILLED,
                OrderStatus.FILLED,
                OrderStatus.PENDING_CANCEL,
                OrderStatus.CANCELLED,
                OrderStatus.REJECTED,
                OrderStatus.EXPIRED,
                OrderStatus.FAILED,
            }
        ),
        OrderStatus.PARTIALLY_FILLED: frozenset(
            {
                OrderStatus.PARTIALLY_FILLED,
                OrderStatus.FILLED,
                OrderStatus.PENDING_CANCEL,
                OrderStatus.CANCELLED,
                OrderStatus.FAILED,
            }
        ),
        OrderStatus.PENDING_CANCEL: frozenset(
            {
                OrderStatus.CANCELLED,
                OrderStatus.FILLED,
                OrderStatus.FAILED,
            }
        ),
        OrderStatus.FILLED: frozenset(),
        OrderStatus.CANCELLED: frozenset(),
        OrderStatus.EXPIRED: frozenset(),
        OrderStatus.REJECTED: frozenset(),
        OrderStatus.FAILED: frozenset(),
    }

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
        self._validate_fill_status()

    def _validate_fill_status(self) -> None:
        if self.filled_quantity == ZERO:
            if self.average_filled_price is not None:
                raise ValueError(
                    "average_filled_price must be None when filled_quantity is zero"
                )
        elif self.average_filled_price is None or self.average_filled_price <= ZERO:
            raise ValueError(
                "average_filled_price must be positive when filled_quantity is positive"
            )

        if self.status is OrderStatus.PARTIALLY_FILLED and not (
            ZERO < self.filled_quantity < self.quantity
        ):
            raise ValueError(
                "PARTIALLY_FILLED requires 0 < filled_quantity < quantity"
            )
        if self.status is OrderStatus.FILLED and self.filled_quantity != self.quantity:
            raise ValueError("FILLED requires filled_quantity to equal quantity")
        if self.status is not OrderStatus.FILLED and self.filled_quantity == self.quantity:
            raise ValueError("only FILLED may have the full quantity filled")
        if self.status in {
            OrderStatus.NEW,
            OrderStatus.EXPIRED,
            OrderStatus.REJECTED,
        } and self.filled_quantity != ZERO:
            raise ValueError(f"{self.status.value} orders cannot have filled quantity")

    def _transition_to(self, new_status: OrderStatus) -> None:
        normalized_status = OrderStatus(new_status)
        if normalized_status not in self.VALID_TRANSITIONS[self.status]:
            raise ValueError(
                f"invalid order status transition: {self.status.value} -> "
                f"{normalized_status.value}"
            )
        self.status = normalized_status

    def mark_as_filled(
        self,
        filled_quantity: Decimal,
        average_price: Decimal,
    ) -> None:
        """Record a cumulative full fill through the owned state machine."""
        normalized_quantity = quantize_amount(filled_quantity)
        normalized_price = quantize_price(average_price)
        if normalized_quantity != self.quantity:
            raise ValueError("filled quantity must equal order quantity")
        if normalized_quantity < self.filled_quantity:
            raise ValueError("filled quantity cannot decrease")
        if normalized_price <= ZERO:
            raise ValueError("average fill price must be positive")
        self._transition_to(OrderStatus.FILLED)
        self.filled_quantity = normalized_quantity
        self.average_filled_price = normalized_price
        self._validate_fill_status()

    def mark_as_partially_filled(
        self,
        filled_quantity: Decimal,
        average_price: Decimal,
    ) -> None:
        """Record a cumulative partial fill through the owned state machine."""
        normalized_quantity = quantize_amount(filled_quantity)
        normalized_price = quantize_price(average_price)
        if not ZERO < normalized_quantity < self.quantity:
            raise ValueError("partial fill must be between zero and order quantity")
        if normalized_quantity < self.filled_quantity:
            raise ValueError("filled quantity cannot decrease")
        if normalized_price <= ZERO:
            raise ValueError("average fill price must be positive")
        self._transition_to(OrderStatus.PARTIALLY_FILLED)
        self.filled_quantity = normalized_quantity
        self.average_filled_price = normalized_price
        self._validate_fill_status()

    def mark_as_cancelled(self) -> None:
        """Cancel an unfilled or partially filled order through the state machine."""
        self._transition_to(OrderStatus.CANCELLED)
        self._validate_fill_status()

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
