"""Define fixed-basis-point, spread, and impact slippage formulas."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from core_lib.ports import CostModel
from core_lib.types import Order, OrderSide
from core_lib.types.money import ZERO, quantize_amount


@dataclass(frozen=True, slots=True)
class SlippageParams:
    """CostModel-owned values consumed by the shared slippage formula."""

    spread_rate: Decimal = ZERO
    impact_coefficient: Decimal = ZERO
    liquidity: Decimal | None = None
    fixed_rate: Decimal | None = None
    gap_multiplier: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        values = (
            self.spread_rate,
            self.impact_coefficient,
            self.gap_multiplier,
        )
        if any(not isinstance(value, Decimal) for value in values):
            raise TypeError("slippage parameters must be Decimal")
        if self.fixed_rate is not None and not isinstance(self.fixed_rate, Decimal):
            raise TypeError("fixed_rate must be Decimal or None")
        if self.liquidity is not None and not isinstance(self.liquidity, Decimal):
            raise TypeError("liquidity must be Decimal or None")
        if self.spread_rate < ZERO or self.impact_coefficient < ZERO:
            raise ValueError("spread and impact parameters must be non-negative")
        if self.fixed_rate is not None and self.fixed_rate < ZERO:
            raise ValueError("fixed_rate must be non-negative")
        if self.liquidity is not None and self.liquidity <= ZERO:
            raise ValueError("liquidity must be positive")
        if self.gap_multiplier < Decimal("1"):
            raise ValueError("gap_multiplier must be at least one")


def effective_rate(
    params: SlippageParams,
    *,
    order: Order,
    context: Mapping[str, object] | None = None,
) -> Decimal:
    """Calculate the effective adverse rate from injected values."""
    effective_context = {} if context is None else context

    if params.fixed_rate is not None:
        rate = params.fixed_rate
    else:
        impact = ZERO
        if params.liquidity is not None:
            impact = params.impact_coefficient * order.quantity / params.liquidity
        rate = params.spread_rate / Decimal("2") + impact
    if effective_context.get("gap_filled") is True:
        rate *= params.gap_multiplier
    return rate


def apply(
    notional: Decimal,
    side: OrderSide,
    cost_model: CostModel,
    *,
    order: Order,
    context: dict[str, object] | None = None,
) -> Decimal:
    """Return signed adverse slippage from an injected standard CostModel."""
    if not isinstance(notional, Decimal):
        raise TypeError("notional must be Decimal")
    if notional < ZERO:
        raise ValueError("notional must be non-negative")
    normalized_side = OrderSide(side)
    effective_context = {} if context is None else context
    rate = cost_model.slippage(order, effective_context)
    if not isinstance(rate, Decimal):
        raise TypeError("slippage rate must be Decimal")
    if rate < ZERO:
        raise ValueError("slippage rate must be non-negative")

    magnitude = quantize_amount(notional * rate)
    return magnitude if normalized_side is OrderSide.BUY else -magnitude
