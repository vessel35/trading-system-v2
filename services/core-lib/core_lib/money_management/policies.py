"""Define the common money-management contract and finalized Turtle N series."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import ClassVar

from core_lib.types import Candle, DecisionAction, DecisionIntent

from .models import (
    AccountRiskSnapshot,
    MarketSnapshot,
    MoneyManagementError,
    MoneyManagementPlan,
    PolicyIndicatorRequirement,
    RiskLimits,
)


class MoneyManagementBase(ABC):
    """The stateless base contract for every money-management policy."""

    __slots__ = ()

    id: ClassVar[str]
    version: ClassVar[str]

    requires_signal_exit: ClassVar[bool] = False
    """Declare that a policy setting ``take_profit`` does not need a signal exit.

    A policy that leaves the exit to the strategy overrides this to true.
    """

    protection_and_leverage_ignore_account_state: ClassVar[bool] = False
    """Declare account-independent protection prices and requested leverage.

    Signal generation may use this capability when it has no real account
    snapshot and does not emit the policy's requested quantity or risk amount.
    """

    @abstractmethod
    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        """Return the policy-owned finalized market inputs."""

    @abstractmethod
    def resolved_config(self) -> Mapping[str, object]:
        """Return the normalized, non-secret policy configuration."""

    @abstractmethod
    def plan_entry(
        self,
        decision: DecisionIntent,
        market: MarketSnapshot,
        account: AccountRiskSnapshot,
        global_limits: RiskLimits,
    ) -> MoneyManagementPlan:
        """Return a proposed protection, quantity, and leverage plan."""

    @staticmethod
    def entry_side(decision: DecisionIntent) -> int:
        """Return 1 for a long entry and -1 for a short, refusing anything else."""
        if decision.action is DecisionAction.ENTER_LONG:
            return 1
        if decision.action is DecisionAction.ENTER_SHORT:
            return -1
        raise MoneyManagementError("money management accepts entry decisions only")

    @staticmethod
    def risk_inputs(
        market: MarketSnapshot,
        account: AccountRiskSnapshot,
        limits: RiskLimits,
        stop_distance: float,
    ) -> tuple[float, float]:
        """Return the globally capped risk budget and the quantity it buys.

        The budget comes from ``RiskLimits`` alone. A policy that recomputed it
        from its own configuration could exceed the per-trade cap, so the one
        derivation lives here rather than in each policy.
        """
        if stop_distance <= 0.0 or not math.isfinite(stop_distance):
            raise MoneyManagementError("stop distance must be finite and positive")
        risk_budget = account.equity * limits.risk_per_trade
        quantity = risk_budget / stop_distance
        if not math.isfinite(quantity) or quantity <= 0.0:
            raise MoneyManagementError("requested quantity must be finite and positive")
        if market.reference_price * quantity <= 0.0:
            raise MoneyManagementError("requested notional must be positive")
        return risk_budget, quantity


def turtle_n_series(
    candles: Sequence[Candle],
    *,
    period: int = 20,
) -> tuple[tuple[datetime, float], ...]:
    """Return Wilder-smoothed N values keyed by finalized candle close time."""
    if isinstance(period, bool) or not isinstance(period, int) or period < 2:
        raise ValueError("period must be an integer of at least 2")
    ordered = list(candles)
    if any(
        right.open_time <= left.open_time for left, right in zip(ordered, ordered[1:], strict=False)
    ):
        raise ValueError("turtle N candles must be strictly increasing")
    true_ranges: list[float] = []
    previous_close: float | None = None
    for candle in ordered:
        prices = (candle.high, candle.low, candle.close)
        if any(not math.isfinite(value) or value <= 0.0 for value in prices):
            raise ValueError("turtle N candles must contain finite positive prices")
        current = candle.high - candle.low
        if previous_close is not None:
            current = max(
                current,
                abs(candle.high - previous_close),
                abs(candle.low - previous_close),
            )
        true_ranges.append(current)
        previous_close = candle.close
    if len(true_ranges) < period:
        return ()
    current_n = sum(true_ranges[:period]) / period
    series = [(ordered[period - 1].close_time, current_n)]
    for index in range(period, len(ordered)):
        current_n = ((period - 1) * current_n + true_ranges[index]) / period
        series.append((ordered[index].close_time, current_n))
    return tuple(series)
