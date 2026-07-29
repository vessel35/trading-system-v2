"""Define immutable inputs and outputs for common money-management policies."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Literal

from core_lib.types import MarketType


def _positive(value: float, *, name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, float)
        or not math.isfinite(value)
        or value <= 0.0
    ):
        raise ValueError(f"{name} must be a finite positive float")


@dataclass(frozen=True, slots=True)
class PolicyIndicatorRequirement:
    """One policy-owned value and the timeframe on which it is finalized."""

    name: str
    params: Mapping[str, object]
    timeframe: Literal["strategy", "1d"]
    min_history: int

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("indicator requirement name must not be empty")
        if self.min_history <= 0:
            raise ValueError("indicator requirement min_history must be positive")
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """The finalized market facts supplied by the runtime at decision time."""

    reference_price: float
    volatility: float
    volatility_name: str
    volatility_timestamp: datetime

    def __post_init__(self) -> None:
        _positive(self.reference_price, name="reference_price")
        _positive(self.volatility, name="volatility")
        if not self.volatility_name:
            raise ValueError("volatility_name must not be empty")
        if (
            self.volatility_timestamp.tzinfo is None
            or self.volatility_timestamp.utcoffset() is None
        ):
            raise ValueError("volatility_timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True)
class AccountRiskSnapshot:
    """The immutable account facts available to one policy calculation."""

    equity: float
    available_cash: float
    market_type: MarketType

    def __post_init__(self) -> None:
        _positive(self.equity, name="equity")
        _positive(self.available_cash, name="available_cash")
        object.__setattr__(self, "market_type", MarketType(self.market_type))


@dataclass(frozen=True, slots=True)
class RiskLimits:
    """Global hard limits that a policy may use but never increase."""

    risk_per_trade: float
    maintenance_margin_rate: float
    max_leverage: int = 100

    def __post_init__(self) -> None:
        if (
            isinstance(self.risk_per_trade, bool)
            or not isinstance(self.risk_per_trade, float)
            or not math.isfinite(self.risk_per_trade)
            or not 0.0 < self.risk_per_trade <= 0.01
        ):
            raise ValueError("risk_per_trade must be a finite float in (0, 0.01]")
        if (
            isinstance(self.maintenance_margin_rate, bool)
            or not isinstance(self.maintenance_margin_rate, float)
            or not math.isfinite(self.maintenance_margin_rate)
            or not 0.0 <= self.maintenance_margin_rate < 1.0
        ):
            raise ValueError("maintenance_margin_rate must be a finite float in [0, 1)")
        if (
            isinstance(self.max_leverage, bool)
            or not isinstance(self.max_leverage, int)
            or self.max_leverage <= 0
        ):
            raise ValueError("max_leverage must be a positive integer")


@dataclass(frozen=True, slots=True)
class MoneyManagementPlan:
    """The policy request that the risk and execution layers must still approve."""

    stop_loss: float
    take_profit: float | None
    requested_quantity: float
    requested_leverage: int
    initial_risk_amount: float
    diagnostics: Mapping[str, object]

    def __post_init__(self) -> None:
        _positive(self.stop_loss, name="stop_loss")
        if self.take_profit is not None:
            _positive(self.take_profit, name="take_profit")
        _positive(self.requested_quantity, name="requested_quantity")
        _positive(self.initial_risk_amount, name="initial_risk_amount")
        if (
            isinstance(self.requested_leverage, bool)
            or not isinstance(self.requested_leverage, int)
            or self.requested_leverage <= 0
        ):
            raise ValueError("requested_leverage must be a positive integer")
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))


class MoneyManagementError(ValueError):
    """A safe, deterministic rejection of a proposed money-management plan."""
