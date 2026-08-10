"""Provide the deployed Turtle-derived money-management policy."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from core_lib.money_management import (
    AccountRiskSnapshot,
    MarketSnapshot,
    MoneyManagementBase,
    MoneyManagementError,
    MoneyManagementPlan,
    PolicyIndicatorRequirement,
    RiskLimits,
)
from core_lib.types import DecisionIntent, MarketType


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
