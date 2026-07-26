"""Simulate next-candle fills through the shared normalizer and matcher."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

import core_lib.execution as execution
from core_lib.ports import Broker, CostModel
from core_lib.types import Candle, Fill, Order, OrderRequest
from core_lib.types.money import quantize_amount


@dataclass(frozen=True, slots=True)
class _PaperContext:
    decision_candle: Candle
    execution_candle: Candle
    wallet_id: str
    signal_id: str
    equity: Decimal
    available_margin: Decimal
    leverage: int
    risk_fraction: float | None


class PaperBroker(Broker):
    """The only Broker adapter in wallet-service; it performs simulation only."""

    def __init__(self, cost_model: CostModel) -> None:
        self._cost_model = cost_model
        self._context: _PaperContext | None = None
        self._open: list[Order] = []

    @property
    def cost_model(self) -> CostModel:
        """Expose the injected values needed by shared liquidation calculation."""
        return self._cost_model

    def configure_execution(
        self,
        decision_candle: Candle,
        execution_candle: Candle,
        *,
        wallet_id: str,
        signal_id: str,
        equity: Decimal,
        available_margin: Decimal,
        leverage: int,
        risk_fraction: float | None,
    ) -> None:
        """Bind one contiguous, next-candle paper execution."""
        if execution_candle.open_time != decision_candle.close_time:
            raise ValueError("PaperBroker requires the contiguous next candle")
        if execution_candle.symbol != decision_candle.symbol:
            raise ValueError("paper execution candles must share a symbol")
        if execution_candle.timeframe != decision_candle.timeframe:
            raise ValueError("paper execution candles must share a timeframe")
        if not isinstance(equity, Decimal) or not isinstance(available_margin, Decimal):
            raise TypeError("paper account values must already be Decimal")
        if equity <= 0 or available_margin < 0:
            raise ValueError("paper equity must be positive and available margin non-negative")
        if isinstance(leverage, bool) or not isinstance(leverage, int) or leverage <= 0:
            raise ValueError("leverage must be a positive int")
        if risk_fraction is not None and not isinstance(risk_fraction, float):
            raise TypeError("risk_fraction must remain float until Broker.submit")
        if risk_fraction is not None and not 0.0 < risk_fraction <= 0.01:
            raise ValueError("risk_fraction must be in (0, 0.01]")
        self._context = _PaperContext(
            decision_candle=decision_candle,
            execution_candle=execution_candle,
            wallet_id=wallet_id,
            signal_id=signal_id,
            equity=equity,
            available_margin=available_margin,
            leverage=leverage,
            risk_fraction=risk_fraction,
        )

    def submit(self, request: OrderRequest) -> Fill:
        """Normalize float intent once, then simulate it with the shared matcher."""
        context = self._context
        if context is None:
            raise RuntimeError("configure_execution must be called before submit")
        self._context = None
        if request.symbol != context.decision_candle.symbol:
            raise ValueError("paper order symbol must match the configured candle")
        order_key = "|".join(
            (
                context.wallet_id,
                context.signal_id,
                str(request.reduce_only),
                str(request.close_position),
            )
        )
        order_id = f"paper-{uuid5(NAMESPACE_URL, order_key)}"
        order = execution.normalize_order(
            request,
            order_id=order_id,
            wallet_id=context.wallet_id,
            signal_id=context.signal_id,
        )
        risk_budget = (
            None
            if context.risk_fraction is None
            else quantize_amount(context.equity * execution.to_decimal(context.risk_fraction))
        )
        self._open.append(order)
        try:
            fill = execution.match(
                order,
                context.decision_candle,
                [context.decision_candle, context.execution_candle],
                self._cost_model,
                "next_bar",
                risk_budget=risk_budget,
                available_margin=(
                    None
                    if request.reduce_only or request.close_position
                    else context.available_margin
                ),
                leverage=context.leverage,
            )
        except Exception:
            if order in self._open:
                self._open.remove(order)
            raise
        self._open.remove(order)
        return fill

    def open_orders(self) -> list[Order]:
        """Return a snapshot of normalized paper orders not yet filled."""
        return list(self._open)

    def cancel(self, order_id: str) -> None:
        """Cancel a normalized paper order through the shared Order state machine."""
        for order in self._open:
            if order.id == order_id:
                order.mark_as_cancelled()
                self._open.remove(order)
                return
        raise KeyError(order_id)
