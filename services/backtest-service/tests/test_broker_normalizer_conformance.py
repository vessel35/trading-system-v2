"""Prove the simulated Broker cannot bypass the one Decimal gateway."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from backtest_service.adapters import broker as broker_module
from backtest_service.adapters.broker import BacktestBroker
from backtest_service.adapters.cost_model import BacktestCostModel
from core_lib.execution import normalize_order as shared_normalize_order
from core_lib.ports import Broker
from core_lib.types import (
    Candle,
    MarketType,
    Order,
    OrderRequest,
    OrderSide,
    OrderType,
    PositionSide,
)


def _candle(hour: int, *, open_price: float, close_price: float) -> Candle:
    open_time = datetime(2026, 1, 1, hour, tzinfo=UTC)
    return Candle(
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="1h",
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open=open_price,
        high=max(open_price, close_price) + 1.0,
        low=min(open_price, close_price) - 1.0,
        close=close_price,
        volume=10.0,
        quote_volume=None,
        trade_count=None,
    )


def _request(
    *,
    quantity: float = 1.234567891,
    order_type: OrderType = OrderType.MARKET,
    price: float | None = None,
) -> OrderRequest:
    return OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=order_type,
        quantity=quantity,
        price=price,
        stop_price=None,
        market_type=MarketType.FUTURES,
        position_side=PositionSide.LONG,
        reduce_only=False,
        close_position=False,
        time_in_force="GTC",
    )


def _zero_cost_model() -> BacktestCostModel:
    return BacktestCostModel(
        {
            "futures_taker_fee_rate": Decimal("0"),
            "futures_entry_slippage_rate": Decimal("0"),
        }
    )


def test_broker_submit_calls_shared_normalizer_before_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Observe the shared gateway call and its quantized Order at the boundary."""
    normalized: list[Order] = []

    def observe_normalizer(
        request: OrderRequest,
        *,
        order_id: str | None = None,
        client_order_id: UUID | None = None,
        wallet_id: str | None = None,
        signal_id: str | None = None,
    ) -> Order:
        order = shared_normalize_order(
            request,
            order_id=order_id,
            client_order_id=client_order_id,
            wallet_id=wallet_id,
            signal_id=signal_id,
        )
        normalized.append(order)
        return order

    monkeypatch.setattr(broker_module, "normalize_order", observe_normalizer)
    decision = _candle(0, open_price=100.0, close_price=101.0)
    next_bar = _candle(1, open_price=102.0, close_price=103.0)
    broker = BacktestBroker(_zero_cost_model())
    assert isinstance(broker, Broker)
    broker.configure_execution(decision, [decision, next_bar])

    fill = broker.submit(_request())

    assert len(normalized) == 1
    assert normalized[0].quantity == Decimal("1.23456789")
    assert fill.quantity == Decimal("1.23456789")
    assert fill.reference_price == Decimal("102.00000000")
    assert fill.timestamp == next_bar.open_time + timedelta(milliseconds=1)
    assert broker.open_orders() == []


def test_broker_source_has_no_private_decimal_cast() -> None:
    """Fail if the adapter grows a second float-to-Decimal conversion site."""
    source_path = Path(broker_module.__file__)
    source = source_path.read_text()
    assert "normalize_order(" in source
    assert "Decimal(str(" not in source


def test_untriggered_order_remains_open_and_can_be_cancelled() -> None:
    """Keep a normalized untriggered order active until cancellation."""
    decision = _candle(0, open_price=100.0, close_price=101.0)
    next_bar = _candle(1, open_price=102.0, close_price=103.0)
    broker = BacktestBroker(_zero_cost_model())
    broker.configure_execution(decision, [decision, next_bar])
    with pytest.raises(ValueError, match="did not trigger"):
        broker.submit(_request(order_type=OrderType.LIMIT, price=90.0))

    open_orders = broker.open_orders()
    assert len(open_orders) == 1
    broker.cancel(open_orders[0].id)
    assert broker.open_orders() == []


def test_broker_requires_explicit_candle_loop_context() -> None:
    """Reject a submit that has no deterministic decision/next-bar context."""
    broker = BacktestBroker(_zero_cost_model())
    with pytest.raises(RuntimeError, match="configure_execution"):
        broker.submit(_request())
