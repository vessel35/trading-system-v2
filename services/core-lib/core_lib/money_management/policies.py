"""Implement manual compatibility and Turtle-derived money management."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Protocol, runtime_checkable

from core_lib.types import Candle, DecisionAction, DecisionIntent, MarketType

from .models import (
    AccountRiskSnapshot,
    MarketSnapshot,
    MoneyManagementError,
    MoneyManagementPlan,
    PolicyIndicatorRequirement,
    RiskLimits,
)


@runtime_checkable
class MoneyManagementPolicy(Protocol):
    """A stateless policy that turns an entry decision into a bounded plan."""

    id: ClassVar[str]
    version: ClassVar[str]

    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        """Return the policy-owned finalized market inputs."""
        ...

    def resolved_config(self) -> Mapping[str, object]:
        """Return the normalized, non-secret policy configuration."""
        ...

    def plan_entry(
        self,
        decision: DecisionIntent,
        market: MarketSnapshot,
        account: AccountRiskSnapshot,
        global_limits: RiskLimits,
    ) -> MoneyManagementPlan:
        """Return a proposed protection, quantity, and leverage plan."""
        ...


class MoneyManagementBase(ABC):
    """Optional stateless convenience base that satisfies ``MoneyManagementPolicy``.

    The protocol is structural, so it only checks that the three members exist.
    A policy whose ``plan_entry`` takes the wrong arguments still satisfies it and
    fails at run time instead. Inheriting here refuses the instance up front, and
    supplies the two calculations both shipped policies share so a new policy does
    not restate the global risk cap and get it wrong.
    """

    __slots__ = ()

    id: ClassVar[str]
    version: ClassVar[str]

    requires_signal_exit: ClassVar[bool] = False
    """Whether this policy leaves the exit to the strategy.

    A policy that never sets ``take_profit`` has no way out of a position on its
    own. Pairing it with a strategy that cannot emit an exit would open a trade
    with nothing to close it, so the composition is refused up front. Declaring it
    here keeps the check off the policy's name.
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


@dataclass(frozen=True, slots=True)
class ManualMoneyManagement(MoneyManagementBase):
    """Reproduce the legacy Vessel ATR stop, fixed target, and leverage."""

    leverage: int = 1
    reward_risk: float = 2.0
    atr_stop_multiple: float = 2.0

    id: ClassVar[str] = "manual"
    version: ClassVar[str] = "1.0.0"

    def __post_init__(self) -> None:
        if isinstance(self.leverage, bool) or not isinstance(self.leverage, int):
            raise TypeError("manual leverage must be an integer")
        if not 1 <= self.leverage <= 100:
            raise ValueError("manual leverage must be in [1, 100]")
        for name, value in (
            ("reward_risk", self.reward_risk),
            ("atr_stop_multiple", self.atr_stop_multiple),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, float | int)
                or not math.isfinite(float(value))
                or not 0.1 <= float(value) <= 10.0
            ):
                raise ValueError(f"manual {name} must be finite and in [0.1, 10]")

    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        return (
            PolicyIndicatorRequirement(
                name="ATR",
                params={"period": 14},
                timeframe="strategy",
                min_history=14,
            ),
        )

    def resolved_config(self) -> Mapping[str, object]:
        return {
            "mode": self.id,
            "leverage": self.leverage,
            "reward_risk": float(self.reward_risk),
            "atr_stop_multiple": float(self.atr_stop_multiple),
        }

    def plan_entry(
        self,
        decision: DecisionIntent,
        market: MarketSnapshot,
        account: AccountRiskSnapshot,
        global_limits: RiskLimits,
    ) -> MoneyManagementPlan:
        side = self.entry_side(decision)
        stop_distance = market.volatility * float(self.atr_stop_multiple)
        risk_budget, quantity = self.risk_inputs(market, account, global_limits, stop_distance)
        stop_loss = market.reference_price - side * stop_distance
        take_profit = market.reference_price + side * stop_distance * float(self.reward_risk)
        if stop_loss <= 0.0 or take_profit <= 0.0:
            raise MoneyManagementError("manual protection prices must remain positive")
        leverage = self.leverage if account.market_type is MarketType.FUTURES else 1
        if leverage > global_limits.max_leverage:
            raise MoneyManagementError("manual leverage exceeds the global maximum")
        return MoneyManagementPlan(
            stop_loss=stop_loss,
            take_profit=take_profit,
            requested_quantity=quantity,
            requested_leverage=leverage,
            initial_risk_amount=risk_budget,
            diagnostics={
                "policy_id": self.id,
                "policy_version": self.version,
                "volatility_name": market.volatility_name,
                "volatility": market.volatility,
                "volatility_timestamp": market.volatility_timestamp.isoformat(),
                "stop_distance": stop_distance,
                "risk_budget": risk_budget,
                "liquidation_safe": True,
            },
        )


@dataclass(frozen=True, slots=True)
class TurtleMoneyManagement(MoneyManagementBase):
    """Apply Turtle-derived daily N sizing under the platform 1% risk cap."""

    n_period: int = 20
    n_timeframe: str = "1d"
    stop_n_multiple: float = 2.0
    leverage_cap: int = 10

    id: ClassVar[str] = "turtle"
    version: ClassVar[str] = "1.0.0"
    requires_signal_exit: ClassVar[bool] = True

    def __post_init__(self) -> None:
        if (
            isinstance(self.n_period, bool)
            or not isinstance(self.n_period, int)
            or not 2 <= self.n_period <= 200
        ):
            raise ValueError("turtle n_period must be an integer in [2, 200]")
        if self.n_timeframe != "1d":
            raise ValueError("turtle n_timeframe must be '1d'")
        if (
            isinstance(self.stop_n_multiple, bool)
            or not isinstance(self.stop_n_multiple, float | int)
            or not math.isfinite(float(self.stop_n_multiple))
            or not 0.1 <= float(self.stop_n_multiple) <= 10.0
        ):
            raise ValueError("turtle stop_n_multiple must be finite and in [0.1, 10]")
        if (
            isinstance(self.leverage_cap, bool)
            or not isinstance(self.leverage_cap, int)
            or not 1 <= self.leverage_cap <= 100
        ):
            raise ValueError("turtle leverage_cap must be an integer in [1, 100]")

    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        return (
            PolicyIndicatorRequirement(
                name="TURTLE_N",
                params={"period": self.n_period},
                timeframe="1d",
                min_history=self.n_period,
            ),
        )

    def resolved_config(self) -> Mapping[str, object]:
        return {
            "mode": self.id,
            "n_period": self.n_period,
            "n_timeframe": self.n_timeframe,
            "stop_n_multiple": float(self.stop_n_multiple),
            "leverage_cap": self.leverage_cap,
        }

    def plan_entry(
        self,
        decision: DecisionIntent,
        market: MarketSnapshot,
        account: AccountRiskSnapshot,
        global_limits: RiskLimits,
    ) -> MoneyManagementPlan:
        side = self.entry_side(decision)
        stop_distance = market.volatility * float(self.stop_n_multiple)
        risk_budget, quantity = self.risk_inputs(market, account, global_limits, stop_distance)
        stop_loss = market.reference_price - side * stop_distance
        if stop_loss <= 0.0:
            raise MoneyManagementError("turtle stop price must remain positive")
        notional = market.reference_price * quantity
        requested_leverage = max(1, math.ceil(notional / account.available_cash))
        leverage_limit = min(self.leverage_cap, global_limits.max_leverage)
        if account.market_type is MarketType.SPOT:
            if requested_leverage > 1:
                raise MoneyManagementError("turtle spot plan exceeds available cash")
            requested_leverage = 1
        elif requested_leverage > leverage_limit:
            raise MoneyManagementError("turtle plan requires leverage above the configured cap")
        liquidation_price = _liquidation_price(
            market.reference_price,
            requested_leverage,
            global_limits.maintenance_margin_rate,
            side,
        )
        liquidation_safe = (
            liquidation_price < stop_loss if side > 0 else liquidation_price > stop_loss
        )
        if not liquidation_safe:
            raise MoneyManagementError("liquidation would occur before the turtle stop")
        return MoneyManagementPlan(
            stop_loss=stop_loss,
            take_profit=None,
            requested_quantity=quantity,
            requested_leverage=requested_leverage,
            initial_risk_amount=risk_budget,
            diagnostics={
                "policy_id": self.id,
                "policy_version": self.version,
                "volatility_name": market.volatility_name,
                "volatility": market.volatility,
                "volatility_timestamp": market.volatility_timestamp.isoformat(),
                "stop_distance": stop_distance,
                "risk_budget": risk_budget,
                "requested_notional": notional,
                "liquidation_price": liquidation_price,
                "liquidation_safe": liquidation_safe,
            },
        )


def _liquidation_price(price: float, leverage: int, mmr: float, side: int) -> float:
    if side > 0:
        return price * (1.0 - 1.0 / leverage + mmr)
    return price * (1.0 + 1.0 / leverage - mmr)


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
