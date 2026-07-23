"""Define maker and taker fee formulas."""

from decimal import Decimal

from core_lib.types.money import ZERO, quantize_amount


def calc(notional: Decimal, rate: Decimal) -> Decimal:
    """Return ``notional × rate`` as a non-negative normalized cost."""
    if not isinstance(notional, Decimal) or not isinstance(rate, Decimal):
        raise TypeError("fee inputs must be Decimal")
    if notional < ZERO:
        raise ValueError("notional must be non-negative")
    if rate < ZERO:
        raise ValueError("fee rate must be non-negative")
    return quantize_amount(notional * rate)
