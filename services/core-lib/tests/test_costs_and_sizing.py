"""Verify net-cost formulas and survival sizing boundaries."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from core_lib.costs import (
    SlippageParams,
    apply_slippage,
    calculate_fee,
    effective_slippage_rate,
    funding_boundaries_between,
    is_funding_boundary,
    is_liquidation_triggered,
    liquidation_price,
    settle_funding,
)
from core_lib.execution import normalize_order
from core_lib.ports import CostModel
from core_lib.sizing import (
    cap_kelly,
    equity,
    f_star,
    non_compliant,
    one_r,
    pyramid_step,
    size,
    unit_limit,
    unit_size,
    wallet_pct_size,
)
from core_lib.types import (
    MarginType,
    MarketType,
    Order,
    OrderRequest,
    OrderSide,
    OrderType,
    Position,
    PositionSide,
)


class FixedSlippageModel(CostModel):
    """Return deterministic values while leaving the formula in core_lib.costs."""

    def __init__(self, params: SlippageParams) -> None:
        self.params = params

    def fee(self, symbol: str, notional: Decimal) -> Decimal:
        del symbol, notional
        return Decimal("0")

    def slippage(
        self,
        order: Order,
        context: dict[str, object],
    ) -> Decimal:
        return effective_slippage_rate(self.params, order=order, context=context)

    def funding_rate(self, at: datetime) -> Decimal:
        del at
        return Decimal("0")

    def liq_params(self) -> dict[str, object]:
        return {"maintenance_margin_rate": Decimal("0.004")}


def make_position(side: PositionSide = PositionSide.LONG) -> Position:
    return Position(
        wallet_id=None,
        symbol="BTCUSDT",
        quantity=Decimal("2"),
        average_price=Decimal("100"),
        total_cost=Decimal("200"),
        current_price=Decimal("100"),
        unrealized_pnl=Decimal("0"),
        side=side,
        market_type=MarketType.FUTURES,
        leverage=10,
        margin_type=MarginType.ISOLATED,
        margin=Decimal("20"),
        entry_price=Decimal("100"),
        mark_price=Decimal("100"),
        liquidation_price=(Decimal("90.4") if side is PositionSide.LONG else Decimal("109.6")),
        funding_fee_total=Decimal("0"),
    )


def test_fee_and_signed_slippage_costs_are_deterministic() -> None:
    assert calculate_fee(Decimal("1000"), Decimal("0.0005")) == Decimal("0.50000000")
    order = normalize_order(
        OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10.0,
            price=None,
            stop_price=None,
            market_type=MarketType.FUTURES,
            position_side=PositionSide.LONG,
            reduce_only=False,
            close_position=False,
            time_in_force="GTC",
        )
    )
    model = FixedSlippageModel(SlippageParams(fixed_rate=Decimal("0.001")))
    assert apply_slippage(Decimal("1000"), OrderSide.BUY, model, order=order) == Decimal(
        "1.00000000"
    )
    assert apply_slippage(Decimal("1000"), OrderSide.SELL, model, order=order) == Decimal(
        "-1.00000000"
    )
    stress_model = FixedSlippageModel(
        SlippageParams(
            spread_rate=Decimal("0.002"),
            impact_coefficient=Decimal("0.1"),
            liquidity=Decimal("1000"),
        )
    )
    assert apply_slippage(
        Decimal("1000"),
        OrderSide.BUY,
        stress_model,
        order=order,
    ) == Decimal("2.00000000")


def test_funding_is_discrete_at_utc_boundaries_and_directional() -> None:
    assert is_funding_boundary(datetime(2026, 1, 1, 8, tzinfo=UTC))
    assert not is_funding_boundary(datetime(2026, 1, 1, 8, 1, tzinfo=UTC))
    rate = Decimal("0.00008750")
    assert settle_funding(make_position(), rate, Decimal("100")) == Decimal("0.01750000")
    assert settle_funding(
        make_position(PositionSide.SHORT),
        rate,
        Decimal("100"),
    ) == Decimal("-0.01750000")


def test_funding_boundaries_cover_coarse_intervals_without_double_charging() -> None:
    start = datetime(2026, 1, 1, 7, tzinfo=UTC)
    assert funding_boundaries_between(
        start,
        datetime(2026, 1, 2, 16, tzinfo=UTC),
    ) == (
        datetime(2026, 1, 1, 8, tzinfo=UTC),
        datetime(2026, 1, 1, 16, tzinfo=UTC),
        datetime(2026, 1, 2, 0, tzinfo=UTC),
        datetime(2026, 1, 2, 8, tzinfo=UTC),
        datetime(2026, 1, 2, 16, tzinfo=UTC),
    )
    assert (
        funding_boundaries_between(
            datetime(2026, 1, 1, 8, tzinfo=UTC),
            datetime(2026, 1, 1, 8, tzinfo=UTC),
        )
        == ()
    )


def test_liquidation_price_and_trigger_are_conservative_by_side() -> None:
    long_price = liquidation_price(
        Decimal("100"),
        10,
        Decimal("0.004"),
        side=PositionSide.LONG,
    )
    short_price = liquidation_price(
        Decimal("100"),
        10,
        Decimal("0.004"),
        side=PositionSide.SHORT,
    )
    assert long_price == Decimal("90.40000000")
    assert short_price == Decimal("109.60000000")
    assert is_liquidation_triggered(make_position(), Decimal("90.4"))
    assert is_liquidation_triggered(
        make_position(PositionSide.SHORT),
        Decimal("109.6"),
    )


def test_risk_money_enforces_one_percent_and_one_r_identity() -> None:
    quantity = size(0.01, 10_000.0, 100.0)
    assert quantity == 1.0
    assert one_r(1_000.0, 900.0, quantity) == 100.0
    assert equity(9_000.0, 1_000.0, -100.0) == 9_900.0
    with pytest.raises(ValueError, match="0.01"):
        size(0.0100001, 10_000.0, 100.0)


def test_optional_sizing_paths_expose_their_framework_boundaries() -> None:
    assert unit_size(0.01, 10_000.0, 100.0) == 1.0
    assert unit_limit == 4
    assert pyramid_step() == 0.5
    assert non_compliant is True
    assert wallet_pct_size(1_000.0) == 200.0
    assert f_star(0.5, 2.0) == 0.25
    assert cap_kelly(0.25, 0.5) == 0.125
    with pytest.raises(ValueError, match="0.5"):
        cap_kelly(0.25, 1.0)
