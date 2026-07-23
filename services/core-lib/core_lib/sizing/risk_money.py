"""Define universal stop-distance risk-money sizing."""

MAX_RISK_PER_TRADE = 0.01


def size(risk_per_trade: float, equity: float, stop_distance: float) -> float:
    """Return ``risk_per_trade × equity / stop_distance`` with the 1% cap."""
    values = (risk_per_trade, equity, stop_distance)
    if any(not isinstance(value, float) for value in values):
        raise TypeError("risk sizing inputs must be float")
    if not 0.0 < risk_per_trade <= MAX_RISK_PER_TRADE:
        raise ValueError("risk_per_trade must be in (0, 0.01]")
    if equity <= 0.0 or stop_distance <= 0.0:
        raise ValueError("equity and stop_distance must be positive")
    return risk_per_trade * equity / stop_distance


def one_r(entry: float, stop: float, quantity: float) -> float:
    """Return initial risk ``abs(entry - stop) × quantity``."""
    if any(not isinstance(value, float) for value in (entry, stop, quantity)):
        raise TypeError("1R inputs must be float")
    if entry <= 0.0 or stop <= 0.0 or quantity <= 0.0:
        raise ValueError("entry, stop, and quantity must be positive")
    return abs(entry - stop) * quantity


def equity(cash: float, used_margin: float, unrealized: float) -> float:
    """Return the signal-time equity snapshot."""
    if any(not isinstance(value, float) for value in (cash, used_margin, unrealized)):
        raise TypeError("equity inputs must be float")
    if cash < 0.0 or used_margin < 0.0:
        raise ValueError("cash and used_margin must be non-negative")
    return cash + used_margin + unrealized
