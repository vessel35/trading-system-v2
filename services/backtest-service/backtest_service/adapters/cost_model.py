"""Provide conservative injected values while shared modules own cost formulas."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType

from core_lib.costs import SlippageParams, effective_slippage_rate
from core_lib.ports import CostModel
from core_lib.types import MarketType, Order
from core_lib.types.money import ZERO

_DEFAULTS = {
    "futures_maker_fee_rate": Decimal("0.0002"),
    "futures_taker_fee_rate": Decimal("0.0005"),
    "spot_taker_fee_rate": Decimal("0.0005"),
    "maintenance_margin_rate": Decimal("0.004"),
    "funding_fallback_rate": Decimal("0.0001"),
    "futures_entry_slippage_rate": Decimal("0.0005"),
    "spot_entry_slippage_rate": Decimal("0.001"),
    "exit_slippage_rate": Decimal("0.0001"),
    "spread_rate": ZERO,
    "impact_coefficient": ZERO,
    "gap_multiplier": Decimal("2"),
    "position_size_pct": Decimal("0.20"),
}
_STANDARD_SLIPPAGE_KEYS = frozenset({"spread_rate", "impact_coefficient", "liquidity"})


class BacktestCostModel(CostModel):
    """Inject conservative values and delegate every formula to core_lib.costs."""

    def __init__(
        self,
        params: Mapping[str, Decimal] | None = None,
        *,
        market_type: MarketType = MarketType.FUTURES,
    ) -> None:
        overrides = {} if params is None else dict(params)
        unknown = set(overrides) - (set(_DEFAULTS) | {"liquidity"})
        if unknown:
            raise ValueError(f"unknown cost parameter(s): {sorted(unknown)}")
        for name, value in overrides.items():
            if not isinstance(value, Decimal):
                raise TypeError(f"{name} must be Decimal")
        values = {**_DEFAULTS, **overrides}
        self._validate(values)
        self._params = MappingProxyType(values)
        self._market_type = MarketType(market_type)
        self._use_standard_slippage = bool(set(overrides) & _STANDARD_SLIPPAGE_KEYS)

    @staticmethod
    def _validate(params: Mapping[str, Decimal]) -> None:
        for name, value in params.items():
            if name == "liquidity":
                if value <= ZERO:
                    raise ValueError("liquidity must be positive")
            elif name == "gap_multiplier":
                if value < Decimal("1"):
                    raise ValueError("gap_multiplier must be at least one")
            elif value < ZERO:
                raise ValueError(f"{name} must be non-negative")
        position_size_pct = params["position_size_pct"]
        if position_size_pct <= ZERO or position_size_pct > Decimal("1"):
            raise ValueError("position_size_pct must be in (0, 1]")

    @property
    def params(self) -> Mapping[str, Decimal]:
        """Expose the immutable run-specific injected value set."""
        return self._params

    @property
    def position_size_pct(self) -> Decimal:
        """Return the compatibility pct-sizing default carried by the run."""
        return self._params["position_size_pct"]

    def fee(self, symbol: str, notional: Decimal) -> Decimal:
        """Return the conservative taker fee rate for this backtest."""
        if not symbol:
            raise ValueError("symbol must not be empty")
        if not isinstance(notional, Decimal):
            raise TypeError("notional must be Decimal")
        if self._market_type is MarketType.SPOT:
            return self._params["spot_taker_fee_rate"]
        return self._params["futures_taker_fee_rate"]

    def slippage(self, order: Order, context: dict[str, object]) -> Decimal:
        """Supply values to the one shared effective-rate formula."""
        fixed_rate: Decimal | None
        if self._use_standard_slippage:
            fixed_rate = None
        elif order.reduce_only or order.close_position:
            fixed_rate = self._params["exit_slippage_rate"]
        elif order.market_type is MarketType.SPOT:
            fixed_rate = self._params["spot_entry_slippage_rate"]
        else:
            fixed_rate = self._params["futures_entry_slippage_rate"]
        params = SlippageParams(
            spread_rate=self._params["spread_rate"],
            impact_coefficient=self._params["impact_coefficient"],
            liquidity=self._params.get("liquidity"),
            fixed_rate=fixed_rate,
            gap_multiplier=self._params["gap_multiplier"],
        )
        return effective_slippage_rate(params, order=order, context=context)

    def funding_rate(self, at: datetime) -> Decimal:
        """Return only the configured fallback rate, never measured history."""
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("funding timestamp must be timezone-aware")
        return self._params["funding_fallback_rate"]

    def liq_params(self) -> dict[str, object]:
        """Return the values consumed by the shared liquidation formula."""
        return {
            "maintenance_margin_rate": self._params["maintenance_margin_rate"],
        }
