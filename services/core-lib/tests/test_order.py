"""Verify order type boundaries without implementing M5 lifecycle rules."""

from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
from core_lib.types import (
    MarketType,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
)


def make_order(
    *,
    quantity: Decimal = Decimal("1"),
    filled_quantity: Decimal = Decimal("0.25"),
    average_filled_price: Decimal | None = Decimal("100"),
    status: OrderStatus = OrderStatus.PARTIALLY_FILLED,
    reduce_only: bool = False,
    close_position: bool = False,
) -> Order:
    return Order(
        id="order-1",
        wallet_id=None,
        signal_id=None,
        order_type=OrderType.MARKET,
        side=OrderSide.BUY,
        symbol="BTCUSDT",
        quantity=quantity,
        price=None,
        filled_quantity=filled_quantity,
        average_filled_price=average_filled_price,
        status=status,
        fee=Decimal("0.01"),
        client_order_id=UUID("12345678-1234-5678-1234-567812345678"),
        market_type=MarketType.FUTURES,
        position_side=PositionSide.LONG,
        reduce_only=reduce_only,
        close_position=close_position,
        stop_price=None,
        time_in_force="GTC",
    )


def test_order_normalizes_enums_and_decimal_precision() -> None:
    order = make_order(quantity=Decimal("1.123456785"))
    assert order.quantity == Decimal("1.12345678")
    assert order.remaining_quantity() == Decimal("0.87345678")
    assert order.status.value == OrderStatus.PARTIALLY_FILLED.value


def test_order_quantity_must_be_positive() -> None:
    with pytest.raises(ValueError, match="quantity"):
        make_order(quantity=Decimal("0"))


def test_reduce_only_and_close_position_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        make_order(reduce_only=True, close_position=True)


def test_order_rejects_float_at_the_decimal_boundary() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        make_order(quantity=cast(Decimal, 1.0))


def test_order_owns_and_enforces_its_lifecycle_state_machine() -> None:
    order = make_order(
        filled_quantity=Decimal("0"),
        average_filled_price=None,
        status=OrderStatus.NEW,
    )
    assert OrderStatus.PARTIALLY_FILLED in Order.VALID_TRANSITIONS[OrderStatus.NEW]
    order.mark_as_partially_filled(Decimal("0.4"), Decimal("101"))
    assert order.status is OrderStatus.PARTIALLY_FILLED
    assert order.remaining_quantity() == Decimal("0.60000000")
    order.mark_as_filled(Decimal("1"), Decimal("102"))
    assert order.status.value == OrderStatus.FILLED.value
    with pytest.raises(ValueError, match="invalid order status transition"):
        order.mark_as_cancelled()


def test_order_cancel_accepts_unfilled_or_partial_but_no_terminal_exit() -> None:
    order = make_order()
    order.mark_as_cancelled()
    assert order.status is OrderStatus.CANCELLED
    assert order.filled_quantity == Decimal("0.25000000")
    with pytest.raises(ValueError, match="invalid order status transition"):
        order.mark_as_filled(Decimal("1"), Decimal("100"))


def test_order_status_and_filled_quantity_must_be_consistent() -> None:
    with pytest.raises(ValueError, match="PARTIALLY_FILLED"):
        make_order(
            filled_quantity=Decimal("0"),
            average_filled_price=None,
            status=OrderStatus.PARTIALLY_FILLED,
        )
    with pytest.raises(ValueError, match="FILLED"):
        make_order(
            filled_quantity=Decimal("0.5"),
            average_filled_price=Decimal("100"),
            status=OrderStatus.FILLED,
        )
    with pytest.raises(ValueError, match="average_filled_price"):
        make_order(
            filled_quantity=Decimal("0"),
            average_filled_price=Decimal("100"),
            status=OrderStatus.NEW,
        )


def test_order_request_is_float_before_normalization() -> None:
    request = OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1.5,
        price=100.0,
        stop_price=None,
        market_type=MarketType.FUTURES,
        position_side=PositionSide.LONG,
        reduce_only=False,
        close_position=False,
        time_in_force="GTC",
    )
    assert isinstance(request.quantity, float)

    with pytest.raises(TypeError, match="float"):
        OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=cast(float, Decimal("1.5")),
            price=100.0,
            stop_price=None,
            market_type=MarketType.FUTURES,
            position_side=PositionSide.LONG,
            reduce_only=False,
            close_position=False,
            time_in_force="GTC",
        )
