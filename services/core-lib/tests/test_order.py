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
        filled_quantity=Decimal("0.25"),
        average_filled_price=Decimal("100"),
        status=OrderStatus.PARTIALLY_FILLED,
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
    assert order.status is OrderStatus.PARTIALLY_FILLED


def test_order_quantity_must_be_positive() -> None:
    with pytest.raises(ValueError, match="quantity"):
        make_order(quantity=Decimal("0"))


def test_reduce_only_and_close_position_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        make_order(reduce_only=True, close_position=True)


def test_order_rejects_float_at_the_decimal_boundary() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        make_order(quantity=cast(Decimal, 1.0))


def test_order_lifecycle_rules_remain_deferred_to_execution_milestone() -> None:
    assert not hasattr(Order, "VALID_TRANSITIONS")
    assert not hasattr(Order, "mark_as_filled")


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
