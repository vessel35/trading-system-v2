"""Define conservative isolated liquidation prices and triggers."""

from decimal import Decimal

from core_lib.types import Position, PositionSide
from core_lib.types.money import ZERO, quantize_price


def price(
    entry: Decimal,
    leverage: int,
    mmr: Decimal,
    *,
    side: PositionSide,
) -> Decimal:
    """Return the conservative isolated liquidation price for one side."""
    if not isinstance(entry, Decimal) or not isinstance(mmr, Decimal):
        raise TypeError("entry and mmr must be Decimal")
    if entry <= ZERO:
        raise ValueError("entry must be positive")
    if isinstance(leverage, bool) or not isinstance(leverage, int):
        raise TypeError("leverage must be int")
    if leverage <= 0:
        raise ValueError("leverage must be positive")
    if not ZERO <= mmr < Decimal("1"):
        raise ValueError("mmr must be between zero and one")
    normalized_side = PositionSide(side)
    leverage_term = Decimal("1") / Decimal(leverage)
    if normalized_side is PositionSide.LONG:
        result = entry * (Decimal("1") - leverage_term + mmr)
    elif normalized_side is PositionSide.SHORT:
        result = entry * (Decimal("1") + leverage_term - mmr)
    else:
        raise ValueError("liquidation direction is ambiguous for PositionSide.BOTH")
    return quantize_price(result)


def is_triggered(position: Position, market_price: Decimal) -> bool:
    """Compare one adverse last-price extreme with the stored liquidation price."""
    if not isinstance(market_price, Decimal):
        raise TypeError("market_price must be Decimal")
    if position.side is PositionSide.LONG:
        return market_price <= position.liquidation_price
    if position.side is PositionSide.SHORT:
        return market_price >= position.liquidation_price
    raise ValueError("liquidation direction is ambiguous for PositionSide.BOTH")
