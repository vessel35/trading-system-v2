"""Define Decimal precision constants and half-even quantizers."""

from decimal import ROUND_HALF_EVEN, Decimal

ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")

Q_PRICE = Decimal("0.00000001")
Q_AMOUNT = Decimal("0.00000001")
Q_PERCENT = Decimal("0.01")
Q_RATIO = Decimal("0.0001")
Q_FEE_RATE = Decimal("0.0001")


def _quantize(value: Decimal, quantum: Decimal) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError("money values must be Decimal")
    return value.quantize(quantum, rounding=ROUND_HALF_EVEN)


def quantize_price(value: Decimal) -> Decimal:
    """Round a price to eight decimal places using bankers' rounding."""
    return _quantize(value, Q_PRICE)


def quantize_amount(value: Decimal) -> Decimal:
    """Round an amount to eight decimal places using bankers' rounding."""
    return _quantize(value, Q_AMOUNT)


def quantize_percent(value: Decimal) -> Decimal:
    """Round a percentage to two decimal places using bankers' rounding."""
    return _quantize(value, Q_PERCENT)


def quantize_ratio(value: Decimal) -> Decimal:
    """Round a ratio to four decimal places using bankers' rounding."""
    return _quantize(value, Q_RATIO)


def quantize_fee_rate(value: Decimal) -> Decimal:
    """Round a fee rate to four decimal places using bankers' rounding."""
    return _quantize(value, Q_FEE_RATE)
