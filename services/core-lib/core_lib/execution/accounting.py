"""Enforce equity accounting identities and single cost deduction."""

from decimal import Decimal

from core_lib.types import MarketType, Position
from core_lib.types.money import quantize_amount


def position_value(position: Position | None) -> Decimal:
    """Return the position term used by the cash + position equity identity."""
    if position is None:
        return quantize_amount(Decimal("0"))
    if position.market_type is MarketType.FUTURES:
        return quantize_amount(position.margin + position.unrealized_pnl)
    return quantize_amount(position.quantity * position.current_price)


def recompute(cash: Decimal, position: Position | None) -> Decimal:
    """Return equity as normalized cash plus the current position term."""
    if not isinstance(cash, Decimal):
        raise TypeError("cash must be Decimal")
    return quantize_amount(cash + position_value(position))


def assert_identity(
    cash: Decimal,
    current_position_value: Decimal,
    equity: Decimal,
) -> None:
    """Raise when the normalized cash + position = equity identity is broken."""
    values = (cash, current_position_value, equity)
    if any(not isinstance(value, Decimal) for value in values):
        raise TypeError("accounting identity values must be Decimal")
    expected = quantize_amount(cash + current_position_value)
    if quantize_amount(equity) != expected:
        raise ValueError("accounting identity violated: cash + position != equity")
