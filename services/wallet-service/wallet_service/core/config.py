"""Validate the risk limits injected into the paper wallet driver."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    """Hold safety limits; calculation and aggregation remain in ``core_lib``."""

    allowed_symbols: frozenset[str]
    risk_per_trade: float = 0.01
    max_order_quantity: float = 1_000_000.0
    max_order_notional: float = 100_000_000.0
    single_market_limit: float = 0.01
    correlation_group_limit: float = 0.02
    single_direction_limit: float = 0.02
    kill_switch_engaged: bool = False

    def __post_init__(self) -> None:
        normalized_symbols = frozenset(symbol.strip().upper() for symbol in self.allowed_symbols)
        if not normalized_symbols or any(not symbol for symbol in normalized_symbols):
            raise ValueError("allowed_symbols must contain at least one non-empty symbol")
        object.__setattr__(self, "allowed_symbols", normalized_symbols)

        positive = {
            "risk_per_trade": self.risk_per_trade,
            "max_order_quantity": self.max_order_quantity,
            "max_order_notional": self.max_order_notional,
        }
        for name, value in positive.items():
            if not isinstance(value, float):
                raise TypeError(f"{name} must be float")
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if self.risk_per_trade > 0.01:
            raise ValueError("risk_per_trade must not exceed one percent")

        limits = {
            "single_market_limit": self.single_market_limit,
            "correlation_group_limit": self.correlation_group_limit,
            "single_direction_limit": self.single_direction_limit,
        }
        for name, value in limits.items():
            if not isinstance(value, float):
                raise TypeError(f"{name} must be float")
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
