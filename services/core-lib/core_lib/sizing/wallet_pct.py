"""Define compatibility percentage sizing with noncompliance marking."""

from typing import Final

non_compliant: Final = True


def size(available_balance: float, position_size_pct: float = 0.20) -> float:
    """Return allocated notional for the explicitly non-compliant pct path."""
    if not isinstance(available_balance, float) or not isinstance(
        position_size_pct,
        float,
    ):
        raise TypeError("wallet pct inputs must be float")
    if available_balance < 0.0:
        raise ValueError("available_balance must be non-negative")
    if not 0.0 <= position_size_pct <= 1.0:
        raise ValueError("position_size_pct must be between zero and one")
    return available_balance * position_size_pct
