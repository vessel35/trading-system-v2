"""Verify explicit fill facts and their provenance flags."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from core_lib.types import Fill, OrderSide, PositionSide


def make_fill(*, order_id: str = "order-1", liquidity: str = "taker") -> Fill:
    return Fill(
        order_id=order_id,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        position_side=PositionSide.LONG,
        reference_price=Decimal("100"),
        price=Decimal("100.123456785"),
        quantity=Decimal("0.5"),
        fee=Decimal("0.01"),
        slippage=Decimal("0.06172839"),
        liquidity=liquidity,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        reduce_only=False,
        exit_reason=None,
    )


def test_fill_is_explicit_and_flags_default_to_false() -> None:
    fill = make_fill()
    assert fill.reference_price == Decimal("100.00000000")
    assert fill.price == Decimal("100.12345678")
    assert fill.gap_filled is False
    assert fill.qty_truncated is False


def test_fill_order_id_is_never_empty() -> None:
    with pytest.raises(ValueError, match="order_id"):
        make_fill(order_id="")


def test_fill_liquidity_is_maker_or_taker() -> None:
    with pytest.raises(ValueError, match="liquidity"):
        make_fill(liquidity="unknown")
