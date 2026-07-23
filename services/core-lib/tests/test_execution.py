"""Verify deterministic matching, lifecycle consumption, books, and accounting."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from core_lib.costs import SlippageParams
from core_lib.execution import (
    PositionBook,
    assert_identity,
    can_transition,
    match,
    normalize_order,
    order_lifecycle,
    recompute,
    resolve_triggers,
    to_decimal,
)
from core_lib.types import (
    Candle,
    ExitReason,
    Fill,
    MarginType,
    MarketType,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSide,
)


class FakeCostModel:
    """Value-only M5 stand-in for the M6 CostModel port."""

    def __init__(
        self,
        *,
        fee_rate: Decimal = Decimal("0"),
        fixed_slippage: Decimal = Decimal("0"),
        gap_multiplier: Decimal = Decimal("1"),
        mmr: Decimal = Decimal("0.004"),
    ) -> None:
        self._fee_rate = fee_rate
        self._fixed_slippage = fixed_slippage
        self._gap_multiplier = gap_multiplier
        self._mmr = mmr

    def fee_rate(self, order: Order) -> Decimal:
        del order
        return self._fee_rate

    def slippage_params(
        self,
        order: Order | None,
        context: Mapping[str, object],
    ) -> SlippageParams:
        del order, context
        return SlippageParams(
            fixed_rate=self._fixed_slippage,
            gap_multiplier=self._gap_multiplier,
        )

    def liquidation_mmr(self, position: Position) -> Decimal:
        del position
        return self._mmr


def make_candle(
    hour: int,
    *,
    open_price: float = 100.0,
    high: float = 105.0,
    low: float = 95.0,
    close: float = 101.0,
) -> Candle:
    open_time = datetime(2026, 1, 1, hour, tzinfo=UTC)
    return Candle(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe="1h",
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=10.0,
        quote_volume=None,
        trade_count=None,
    )


def make_request(
    *,
    quantity: float = 1.0,
    price: float | None = None,
    stop_price: float | None = None,
    order_type: OrderType = OrderType.MARKET,
    side: OrderSide = OrderSide.BUY,
    position_side: PositionSide = PositionSide.LONG,
) -> OrderRequest:
    return OrderRequest(
        symbol="BTCUSDT",
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=price,
        stop_price=stop_price,
        market_type=MarketType.FUTURES,
        position_side=position_side,
        reduce_only=False,
        close_position=False,
        time_in_force="GTC",
    )


def make_position(
    *,
    side: PositionSide = PositionSide.LONG,
    liquidation_price: Decimal = Decimal("90.4"),
) -> Position:
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
        liquidation_price=liquidation_price,
        funding_fee_total=Decimal("0"),
    )


def make_fill(
    *,
    price: Decimal,
    quantity: Decimal,
    reduce_only: bool = False,
) -> Fill:
    return Fill(
        order_id=f"fill-{price}-{quantity}-{reduce_only}",
        symbol="BTCUSDT",
        side=OrderSide.SELL if reduce_only else OrderSide.BUY,
        position_side=PositionSide.LONG,
        reference_price=price,
        price=price,
        quantity=quantity,
        fee=Decimal("0"),
        slippage=Decimal("0"),
        liquidity="taker",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        reduce_only=reduce_only,
        exit_reason=ExitReason.SIGNAL_EXIT if reduce_only else None,
    )


def test_normalizer_is_the_only_float_to_decimal_cast_gateway() -> None:
    order = normalize_order(
        make_request(quantity=1.000000015, price=100.125, stop_price=95.25),
        order_id="normalized-order",
    )
    assert to_decimal(1.000000015) == Decimal("1.00000002")
    assert order.quantity == Decimal("1.00000002")
    assert order.price == Decimal("100.12500000")
    assert order.status is OrderStatus.NEW

    package_root = Path(__file__).parents[1] / "core_lib"
    cast_sites = [
        path.relative_to(package_root).as_posix()
        for package in ("execution", "costs", "sizing")
        for path in (package_root / package).glob("*.py")
        if "Decimal(str(" in path.read_text()
    ]
    assert cast_sites == ["execution/normalizer.py"]


def test_execution_lifecycle_consumes_the_order_owned_transition_table() -> None:
    assert can_transition(OrderStatus.NEW, OrderStatus.FILLED)
    assert not can_transition(OrderStatus.FILLED, OrderStatus.NEW)
    assert not hasattr(order_lifecycle, "VALID_TRANSITIONS")


def test_next_bar_open_gap_reanchors_stop_and_truncates_quantity() -> None:
    decision = make_candle(0, close=101.0)
    next_bar = make_candle(1, open_price=110.0, high=112.0, low=108.0, close=111.0)
    order = normalize_order(
        make_request(quantity=2.0, price=100.0, stop_price=90.0),
        order_id="gap-entry",
    )
    fill = match(
        order,
        decision,
        [decision, next_bar],
        FakeCostModel(),
        "next_bar",
        available_margin=Decimal("40"),
        leverage=5,
    )
    assert fill.reference_price == Decimal("110.00000000")
    assert fill.timestamp == next_bar.open_time + timedelta(milliseconds=1)
    assert fill.timestamp > decision.close_time
    assert fill.quantity == Decimal("1.81818182")
    assert fill.qty_truncated is True
    assert order.stop_price == Decimal("100.00000000")
    assert order.status is OrderStatus.FILLED


def test_fill_timing_immediate_uses_decision_close_and_unknown_values_fail() -> None:
    decision = make_candle(0, close=101.0)
    immediate_order = normalize_order(make_request(), order_id="immediate-entry")
    fill = match(
        immediate_order,
        decision,
        [],
        FakeCostModel(),
        "immediate",
    )
    assert fill.reference_price == Decimal("101.00000000")
    assert fill.timestamp == decision.close_time

    with pytest.raises(ValueError, match="fill_timing"):
        match(
            normalize_order(make_request(), order_id="invalid-timing"),
            decision,
            [],
            FakeCostModel(),
            "unknown",
        )


def test_simultaneous_stop_and_take_profit_resolves_to_stop_loss() -> None:
    candle = make_candle(1, open_price=100.0, high=106.0, low=94.0, close=101.0)
    fill = resolve_triggers(
        make_position(),
        [candle],
        FakeCostModel(),
        stop_price=Decimal("95"),
        take_profit_price=Decimal("105"),
        entry_time=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert fill is not None
    assert fill.exit_reason is ExitReason.STOP_LOSS
    assert fill.reference_price == Decimal("95.00000000")


def test_trigger_gap_uses_unfavorable_open_and_skips_the_fill_candle() -> None:
    fill_candle = make_candle(1, open_price=100.0, high=102.0, low=90.0, close=91.0)
    later_candle = make_candle(2, open_price=90.0, high=92.0, low=89.0, close=91.0)
    entry_time = fill_candle.open_time
    fill = resolve_triggers(
        make_position(liquidation_price=Decimal("80")),
        [fill_candle, later_candle],
        FakeCostModel(),
        stop_price=Decimal("95"),
        entry_time=entry_time,
    )
    assert fill is not None
    assert fill.timestamp == later_candle.close_time
    assert fill.reference_price == Decimal("90.00000000")
    assert fill.gap_filled is True


def test_position_book_owns_open_increase_reduce_close_and_accounting_identity() -> None:
    book = PositionBook()
    book.apply(
        make_fill(price=Decimal("100"), quantity=Decimal("2")),
        leverage=10,
        margin_type=MarginType.ISOLATED,
        liquidation_price=Decimal("90.4"),
    )
    book.apply(make_fill(price=Decimal("130"), quantity=Decimal("1")))
    position = book.get("BTCUSDT", PositionSide.LONG)
    assert position is not None
    assert position.quantity == Decimal("3.00000000")
    assert position.average_price == Decimal("110.00000000")
    assert position.margin == Decimal("33.00000000")
    position.update_price(Decimal("120"))
    equity = recompute(Decimal("1000"), position)
    assert equity == Decimal("1063.00000000")
    assert_identity(Decimal("1000"), Decimal("63"), equity)

    book.apply(
        make_fill(
            price=Decimal("120"),
            quantity=Decimal("3"),
            reduce_only=True,
        )
    )
    assert book.get("BTCUSDT", PositionSide.LONG) is None


def test_opening_a_position_requires_the_keyword_only_book_context() -> None:
    with pytest.raises(ValueError, match="leverage and margin_type"):
        PositionBook().apply(make_fill(price=Decimal("100"), quantity=Decimal("1")))
