"""Define discrete funding settlement formulas at boundary-candle open."""

from datetime import UTC, datetime
from decimal import Decimal

from core_lib.types import Position, PositionSide
from core_lib.types.money import quantize_amount


def settle(position: Position, rate: Decimal, price: Decimal) -> Decimal:
    """Return one full discrete funding cost at the caller-confirmed boundary."""
    if not isinstance(rate, Decimal) or not isinstance(price, Decimal):
        raise TypeError("funding rate and settlement price must be Decimal")
    if price <= 0:
        raise ValueError("settlement price must be positive")
    if position.side is PositionSide.BOTH:
        raise ValueError("funding direction is ambiguous for PositionSide.BOTH")
    direction = Decimal("1") if position.side is PositionSide.LONG else Decimal("-1")
    return quantize_amount(position.quantity * price * rate * direction)


def is_boundary(at: datetime) -> bool:
    """Return whether ``at`` is exactly a UTC 00:00, 08:00, or 16:00 boundary."""
    if at.tzinfo is None:
        raise ValueError("funding boundary timestamps must be timezone-aware")
    utc_at = at.astimezone(UTC)
    return (
        utc_at.hour in {0, 8, 16}
        and utc_at.minute == 0
        and utc_at.second == 0
        and utc_at.microsecond == 0
    )
