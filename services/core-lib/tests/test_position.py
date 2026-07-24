"""Verify position accounting-basis invariants and updates."""

from decimal import Decimal

import pytest
from core_lib.types import MarginType, MarketType, Position, PositionSide


def make_position(
    *,
    total_cost: Decimal = Decimal("200"),
    average_price: Decimal = Decimal("100"),
    entry_price: Decimal = Decimal("100"),
    side: PositionSide = PositionSide.LONG,
) -> Position:
    return Position(
        wallet_id=None,
        symbol="BTCUSDT",
        quantity=Decimal("2"),
        average_price=average_price,
        total_cost=total_cost,
        current_price=Decimal("100"),
        unrealized_pnl=Decimal("0"),
        side=side,
        market_type=MarketType.FUTURES,
        leverage=10,
        margin_type=MarginType.ISOLATED,
        margin=Decimal("20"),
        entry_price=entry_price,
        mark_price=Decimal("100"),
        liquidation_price=Decimal("91"),
        funding_fee_total=Decimal("0"),
    )


def test_total_cost_tolerance_is_enforced_at_construction() -> None:
    assert make_position(total_cost=Decimal("200.01")).total_cost == Decimal("200.01000000")
    with pytest.raises(ValueError, match="total_cost"):
        make_position(total_cost=Decimal("200.01000001"))


def test_update_price_recalculates_unrealized_pnl() -> None:
    position = make_position(
        total_cost=Decimal("220"),
        average_price=Decimal("110"),
        entry_price=Decimal("100"),
    )
    position.update_price(Decimal("120"))
    assert position.mark_price == Decimal("120.00000000")
    assert position.unrealized_pnl == Decimal("40.00000000")


def test_short_unrealized_pnl_has_the_inverse_price_direction() -> None:
    position = make_position(side=PositionSide.SHORT)
    position.update_price(Decimal("90"))
    assert position.unrealized_pnl == Decimal("20.00000000")
    position.update_price(Decimal("110"))
    assert position.unrealized_pnl == Decimal("-20.00000000")


def test_add_quantity_updates_weighted_average_and_cost() -> None:
    position = make_position()
    position.add_quantity(Decimal("1"), Decimal("130"))
    assert position.quantity == Decimal("3.00000000")
    assert position.average_price == Decimal("110.00000000")
    assert position.total_cost == Decimal("330.00000000")


def test_reduce_quantity_returns_proportional_margin() -> None:
    position = make_position()
    released_margin = position.reduce_quantity(Decimal("0.5"))
    assert released_margin == Decimal("5.00000000")
    assert position.quantity == Decimal("1.50000000")
    assert position.total_cost == Decimal("150.00000000")
    assert position.margin == Decimal("15.00000000")
