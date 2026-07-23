"""Simulate deterministic fills through the shared Decimal normalizer."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from core_lib.execution import match, normalize_order
from core_lib.ports import Broker, CostModel
from core_lib.types import Candle, Fill, Order, OrderRequest


@dataclass(frozen=True, slots=True)
class _ExecutionContext:
    decision_candle: Candle
    history: tuple[Candle, ...]
    fill_timing: str
    risk_budget: Decimal | None
    available_margin: Decimal | None
    leverage: int


class BacktestBroker(Broker):
    """Normalize and match one atomic order against configured simulation data."""

    def __init__(self, cost_model: CostModel) -> None:
        self._cost_model = cost_model
        self._open: list[Order] = []
        self._execution: _ExecutionContext | None = None
        self._next_order_sequence = 1

    def configure_execution(
        self,
        decision_candle: Candle,
        history: list[Candle],
        *,
        fill_timing: str = "next_bar",
        risk_budget: Decimal | None = None,
        available_margin: Decimal | None = None,
        leverage: int = 1,
    ) -> None:
        """Bind the current candle-loop context consumed by subsequent submits."""
        if fill_timing != "next_bar":
            raise ValueError("BacktestBroker supports next_bar fill_timing only")
        if decision_candle not in history:
            raise ValueError("history must contain the decision candle")
        self._execution = _ExecutionContext(
            decision_candle=decision_candle,
            history=tuple(history),
            fill_timing=fill_timing,
            risk_budget=risk_budget,
            available_margin=available_margin,
            leverage=leverage,
        )

    def submit(self, request: OrderRequest) -> Fill:
        """Normalize one float request, then delegate its fill to the matcher."""
        if self._execution is None:
            raise RuntimeError("configure_execution must be called before submit")
        order_id = f"bt-order-{self._next_order_sequence:08d}"
        self._next_order_sequence += 1
        order = normalize_order(request, order_id=order_id)
        self._open.append(order)
        try:
            fill = match(
                order,
                self._execution.decision_candle,
                list(self._execution.history),
                self._cost_model,
                self._execution.fill_timing,
                risk_budget=self._execution.risk_budget,
                available_margin=self._execution.available_margin,
                leverage=self._execution.leverage,
            )
        except Exception:
            if order.status.is_terminal():
                self._open.remove(order)
            raise
        self._open.remove(order)
        return fill

    def open_orders(self) -> list[Order]:
        """Return a stable snapshot of all still-active normalized orders."""
        return list(self._open)

    def cancel(self, order_id: str) -> None:
        """Cancel one matching active order through the Order-owned state machine."""
        for order in self._open:
            if order.id == order_id:
                order.mark_as_cancelled()
                self._open.remove(order)
                return
        raise KeyError(order_id)
