"""Define positions, weighted averages, and stored liquidation prices."""

from dataclasses import dataclass
from decimal import Decimal

from .enums import MarginType, MarketType, PositionSide
from .money import ZERO, quantize_amount, quantize_price

_TOTAL_COST_TOLERANCE = Decimal("0.01")


@dataclass(slots=True)
class Position:
    """A Decimal position record and its accounting basis."""

    wallet_id: str | None
    symbol: str
    quantity: Decimal
    average_price: Decimal
    total_cost: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    side: PositionSide
    market_type: MarketType
    leverage: int
    margin_type: MarginType
    margin: Decimal
    entry_price: Decimal
    mark_price: Decimal
    liquidation_price: Decimal
    funding_fee_total: Decimal

    def __post_init__(self) -> None:
        self.side = PositionSide(self.side)
        self.market_type = MarketType(self.market_type)
        self.margin_type = MarginType(self.margin_type)
        self._quantize_fields()
        if self.quantity < ZERO:
            raise ValueError("quantity must be non-negative")
        if isinstance(self.leverage, bool) or not isinstance(self.leverage, int):
            raise TypeError("leverage must be int")
        if self.leverage <= 0:
            raise ValueError("leverage must be positive")
        self._validate_total_cost()

    def _quantize_fields(self) -> None:
        self.quantity = quantize_amount(self.quantity)
        self.average_price = quantize_price(self.average_price)
        self.total_cost = quantize_amount(self.total_cost)
        self.current_price = quantize_price(self.current_price)
        self.unrealized_pnl = quantize_amount(self.unrealized_pnl)
        self.margin = quantize_amount(self.margin)
        self.entry_price = quantize_price(self.entry_price)
        self.mark_price = quantize_price(self.mark_price)
        self.liquidation_price = quantize_price(self.liquidation_price)
        self.funding_fee_total = quantize_amount(self.funding_fee_total)

    def _validate_total_cost(self) -> None:
        expected = self.quantity * self.average_price
        if abs(self.total_cost - expected) > _TOTAL_COST_TOLERANCE:
            raise ValueError("total_cost must equal quantity * average_price within 0.01")

    def update_price(self, price: Decimal) -> None:
        """Update the mark price and recalculate unrealized PnL."""
        normalized_price = quantize_price(price)
        if normalized_price <= ZERO:
            raise ValueError("mark price must be positive")
        self.current_price = normalized_price
        self.mark_price = normalized_price
        if self.market_type is MarketType.FUTURES:
            price_delta = normalized_price - self.entry_price
            if self.side is PositionSide.SHORT:
                price_delta = -price_delta
            self.unrealized_pnl = quantize_amount(price_delta * self.quantity)
        else:
            current_value = self.quantity * normalized_price
            self.unrealized_pnl = quantize_amount(current_value - self.total_cost)
        self._validate_total_cost()

    def add_quantity(self, quantity: Decimal, price: Decimal) -> None:
        """Increase the position and update its weighted average entry price."""
        normalized_quantity = quantize_amount(quantity)
        normalized_price = quantize_price(price)
        if normalized_quantity <= ZERO:
            raise ValueError("added quantity must be positive")
        if normalized_price <= ZERO:
            raise ValueError("entry price must be positive")

        new_quantity = quantize_amount(self.quantity + normalized_quantity)
        new_total_cost = quantize_amount(self.total_cost + normalized_quantity * normalized_price)
        self.quantity = new_quantity
        self.total_cost = new_total_cost
        self.average_price = quantize_price(new_total_cost / new_quantity)
        self.entry_price = self.average_price
        self._validate_total_cost()

    def reduce_quantity(self, quantity: Decimal) -> Decimal:
        """Reduce a position and return the proportional released margin."""
        normalized_quantity = quantize_amount(quantity)
        if normalized_quantity <= ZERO:
            raise ValueError("reduced quantity must be positive")
        if normalized_quantity > self.quantity:
            raise ValueError("cannot reduce more than the position quantity")

        old_quantity = self.quantity
        released_margin = quantize_amount(self.margin * normalized_quantity / old_quantity)
        self.quantity = quantize_amount(old_quantity - normalized_quantity)
        self.total_cost = quantize_amount(self.quantity * self.average_price)
        self.margin = quantize_amount(self.margin - released_margin)
        if self.quantity == ZERO:
            self.average_price = quantize_price(ZERO)
            self.entry_price = quantize_price(ZERO)
            self.current_price = quantize_price(ZERO)
            self.mark_price = quantize_price(ZERO)
            self.unrealized_pnl = quantize_amount(ZERO)
            self.liquidation_price = quantize_price(ZERO)
        self._validate_total_cost()
        return released_margin
