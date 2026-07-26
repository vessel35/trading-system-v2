"""Inject conservative paper values while ``core_lib.costs`` owns formulas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from core_lib.costs import SlippageParams, effective_slippage_rate
from core_lib.ports import CostModel
from core_lib.types import Order
from core_lib.types.money import ZERO


class PaperCostModel(CostModel):
    """Provide deterministic paper fee, slippage, funding, and margin values."""

    def __init__(
        self,
        *,
        taker_fee_rate: Decimal = Decimal("0.0005"),
        entry_slippage_rate: Decimal = Decimal("0.0005"),
        exit_slippage_rate: Decimal = Decimal("0.0001"),
        funding_fallback_rate: Decimal = Decimal("0.0001"),
        maintenance_margin_rate: Decimal = Decimal("0.004"),
        gap_multiplier: Decimal = Decimal("2"),
    ) -> None:
        self._taker_fee_rate = self._non_negative(taker_fee_rate, "taker_fee_rate")
        self._entry_slippage_rate = self._non_negative(
            entry_slippage_rate,
            "entry_slippage_rate",
        )
        self._exit_slippage_rate = self._non_negative(
            exit_slippage_rate,
            "exit_slippage_rate",
        )
        self._funding_fallback_rate = self._non_negative(
            funding_fallback_rate,
            "funding_fallback_rate",
        )
        self._maintenance_margin_rate = self._non_negative(
            maintenance_margin_rate,
            "maintenance_margin_rate",
        )
        if not isinstance(gap_multiplier, Decimal):
            raise TypeError("gap_multiplier must be Decimal")
        if gap_multiplier < Decimal("1"):
            raise ValueError("gap_multiplier must be at least one")
        self._gap_multiplier = gap_multiplier

    @staticmethod
    def _non_negative(value: Decimal, name: str) -> Decimal:
        if not isinstance(value, Decimal):
            raise TypeError(f"{name} must be Decimal")
        if value < ZERO:
            raise ValueError(f"{name} must be non-negative")
        return value

    def fee(self, symbol: str, notional: Decimal) -> Decimal:
        """Return the injected taker fee rate."""
        if not symbol:
            raise ValueError("symbol must not be empty")
        if not isinstance(notional, Decimal):
            raise TypeError("notional must be Decimal")
        return self._taker_fee_rate

    def slippage(self, order: Order, context: dict[str, object]) -> Decimal:
        """Delegate the effective adverse-rate formula to ``core_lib.costs``."""
        fixed_rate = (
            self._exit_slippage_rate
            if order.reduce_only or order.close_position
            else self._entry_slippage_rate
        )
        return effective_slippage_rate(
            SlippageParams(
                fixed_rate=fixed_rate,
                gap_multiplier=self._gap_multiplier,
            ),
            order=order,
            context=context,
        )

    def funding_rate(self, at: datetime) -> Decimal:
        """Return the configured fallback only; no market connection exists."""
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("funding timestamp must be timezone-aware")
        return self._funding_fallback_rate

    def liq_params(self) -> dict[str, object]:
        """Return the shared liquidation formula's injected maintenance rate."""
        return {"maintenance_margin_rate": self._maintenance_margin_rate}
