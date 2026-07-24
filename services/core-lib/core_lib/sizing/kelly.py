"""Define capped half-Kelly and quarter-Kelly sizing."""


def f_star(p: float, payoff_ratio: float) -> float:
    """Return full Kelly ``p - (1-p)/B`` without silently applying a cap."""
    if not isinstance(p, float) or not isinstance(payoff_ratio, float):
        raise TypeError("Kelly inputs must be float")
    if not 0.0 <= p <= 1.0:
        raise ValueError("win probability must be between zero and one")
    if payoff_ratio <= 0.0:
        raise ValueError("payoff ratio must be positive")
    return p - (1.0 - p) / payoff_ratio


def cap(full_kelly: float, fraction: float) -> float:
    """Return a non-negative Half-or-less fractional Kelly allocation."""
    if not isinstance(full_kelly, float) or not isinstance(fraction, float):
        raise TypeError("Kelly cap inputs must be float")
    if not 0.0 < fraction <= 0.5:
        raise ValueError("fraction must be in (0, 0.5]")
    return max(0.0, full_kelly) * fraction
