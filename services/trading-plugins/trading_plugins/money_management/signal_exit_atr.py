"""Provide the deployed ATR-stop-only policy that leaves every exit to the strategy."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from core_lib.indicators import DEFAULT_REGISTRY
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
class SignalExitAtrMoneyManagement(MoneyManagementBase):
    """Place an ATR-multiple stop, no target, and let the strategy's EXIT close the trade.

    This is the minimal policy the authoring contract shows in section 5.3.1, deployed as a
    file. It declares ``requires_signal_exit`` because it never produces a take-profit, so a
    strategy that cannot emit EXIT must not be paired with it.
    """

    atr_period: int = 14
    atr_stop_multiple: float = 2.5
    leverage_cap: int = 5

    id: ClassVar[str] = "signal-exit-atr"
    version: ClassVar[str] = "1.0.0"
    requires_signal_exit: ClassVar[bool] = True

    def __post_init__(self) -> None:
        if isinstance(self.atr_period, bool) or not isinstance(self.atr_period, int):
            raise TypeError("atr_period must be an integer")
        if not 2 <= self.atr_period <= 200:
            raise ValueError("atr_period must be an integer in [2, 200]")
        multiple = self.atr_stop_multiple
        if (
            isinstance(multiple, bool)
            or not isinstance(multiple, float | int)
            or not math.isfinite(float(multiple))
            or not 0.1 <= float(multiple) <= 10.0
        ):
            raise ValueError("atr_stop_multiple must be finite and in [0.1, 10]")
        if isinstance(self.leverage_cap, bool) or not isinstance(self.leverage_cap, int):
            raise TypeError("leverage_cap must be an integer")
        if not 1 <= self.leverage_cap <= 100:
            raise ValueError("leverage_cap must be an integer in [1, 100]")
        # The requirement below is resolved against the indicator registry when the run
        # starts. Refusing an unregistered period here keeps a configuration the run
        # would only reject at series resolution from being accepted at submission.
        try:
            DEFAULT_REGISTRY.get("ATR", {"period": self.atr_period})
        except KeyError as error:
            raise ValueError(
                f"atr_period {self.atr_period} is not a registered ATR combination"
            ) from error

    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        return (
            PolicyIndicatorRequirement(
                name="ATR",
                params={"period": self.atr_period},
                timeframe="strategy",
                min_history=self.atr_period,
            ),
        )

    def resolved_config(self) -> Mapping[str, object]:
        return {
            "mode": self.id,
            "atr_period": self.atr_period,
            "atr_stop_multiple": float(self.atr_stop_multiple),
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
        stop_distance = market.volatility * float(self.atr_stop_multiple)
        risk_budget, quantity = self.risk_inputs(market, account, global_limits, stop_distance)

        stop_loss = market.reference_price - side * stop_distance
        if stop_loss <= 0.0:
            raise MoneyManagementError("stop price must remain positive")

        notional = market.reference_price * quantity
        if account.market_type is MarketType.SPOT:
            leverage = 1
            if notional > account.available_cash:
                raise MoneyManagementError("spot plan exceeds available cash")
        else:
            needed = max(1, math.ceil(notional / account.available_cash))
            if needed > min(self.leverage_cap, global_limits.max_leverage):
                raise MoneyManagementError("plan requires leverage above the cap")
            leverage = needed

        # A stop placed beyond the liquidation price is never honoured: the position is
        # liquidated first (contract section 4.1). Refuse the plan rather than record a
        # stop the run cannot keep.
        liquidation_price = _liquidation_price(
            market.reference_price, leverage, global_limits.maintenance_margin_rate, side
        )
        liquidation_safe = (
            liquidation_price < stop_loss if side > 0 else liquidation_price > stop_loss
        )
        if not liquidation_safe:
            raise MoneyManagementError("liquidation would occur before the stop")

        return MoneyManagementPlan(
            stop_loss=stop_loss,
            take_profit=None,
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
                "requested_notional": notional,
                "liquidation_price": liquidation_price,
                "liquidation_safe": liquidation_safe,
            },
        )


def _liquidation_price(price: float, leverage: int, mmr: float, side: int) -> float:
    """Return the isolated-margin liquidation price for an entry at ``price``."""
    if side > 0:
        return price * (1.0 - 1.0 / leverage + mmr)
    return price * (1.0 + 1.0 / leverage - mmr)
