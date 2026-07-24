"""Enforce aggregate risk limits by market, correlation group, and direction."""

from math import fsum, inf, isfinite, nextafter


def _within_limit(risks: list[float], limit: float) -> bool:
    if not isinstance(risks, list):
        raise TypeError("risks must be a list of float values")
    if not isinstance(limit, float):
        raise TypeError("limit must be float")
    if not isfinite(limit) or limit < 0.0:
        raise ValueError("limit must be finite and non-negative")
    for risk in risks:
        if not isinstance(risk, float):
            raise TypeError("every risk contribution must be float")
        if not isfinite(risk) or risk < 0.0:
            raise ValueError("risk contributions must be finite and non-negative")

    aggregate_risk = fsum(risks)
    return aggregate_risk <= nextafter(limit, inf)


def single_market(risks: list[float], limit: float) -> bool:
    """Return whether aggregate risk for one market is at or below its limit."""
    return _within_limit(risks, limit)


def correlation_group(risks: list[float], limit: float) -> bool:
    """Return whether aggregate risk for one correlation group is within limit."""
    return _within_limit(risks, limit)


def single_direction(risks: list[float], limit: float) -> bool:
    """Return whether aggregate risk in one directional book is within limit."""
    return _within_limit(risks, limit)
