"""Define optional Turtle N-unit sizing and pyramiding limits."""

from typing import Final

from .risk_money import size

unit_limit: Final = 4


def unit_size(risk_per_trade: float, equity: float, n: float) -> float:
    """Return one volatility-normalized Turtle unit."""
    return size(risk_per_trade, equity, n)


def pyramid_step() -> float:
    """Return the fixed 0.5N pyramiding distance multiplier."""
    return 0.5
