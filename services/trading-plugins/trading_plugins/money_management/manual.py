"""Provide the deployed manual compatibility money-management policy."""

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
class ManualMoneyManagement(MoneyManagementBase):
    """Reproduce the legacy Vessel ATR stop, fixed target, and leverage."""

    leverage: int = 1
    reward_risk: float = 2.0
    atr_stop_multiple: float = 2.0

    id: ClassVar[str] = "manual"
    version: ClassVar[str] = "1.0.0"
    protection_and_leverage_ignore_account_state: ClassVar[bool] = True

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
