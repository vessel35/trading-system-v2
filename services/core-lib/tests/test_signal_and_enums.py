"""Verify decision-only signals and shared enum semantics."""

from dataclasses import fields
from datetime import UTC, datetime

import pytest
from core_lib.types import (
    MarketType,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
    SignalType,
    TradingSignal,
)


def make_signal(confidence: float = 0.75) -> TradingSignal:
    return TradingSignal(
        symbol="BTCUSDT",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        confidence=confidence,
        price=100.0,
        stop_loss=90.0,
        take_profit=120.0,
        market_type=MarketType.FUTURES,
        leverage=2,
        reason="breakout",
        metadata={"lookback": 20},
    )


def test_trading_signal_has_no_direction_or_quantity_field() -> None:
    field_names = {field.name for field in fields(TradingSignal)}
    assert field_names.isdisjoint({"signal_type", "direction", "side", "quantity"})
    assert make_signal().stop_loss == 90.0


def test_signal_confidence_is_bounded_by_zero_and_one() -> None:
    with pytest.raises(ValueError, match="confidence"):
        make_signal(-0.01)
    with pytest.raises(ValueError, match="confidence"):
        make_signal(1.01)


def test_signal_type_remains_a_persistence_only_enum() -> None:
    assert [member.value for member in SignalType] == ["BUY", "SELL", "HOLD"]


def test_adopted_wallet_enums_preserve_their_existing_values() -> None:
    assert OrderType.STOP_MARKET.value == "stop_market"
    assert OrderSide.BUY.value == "buy"
    assert OrderStatus.PARTIALLY_FILLED.value == "partially_filled"
    assert PositionSide.BOTH.value == "both"
    assert MarketType.FUTURES.value == "futures"


def test_order_status_sets_are_exhaustive_and_disjoint() -> None:
    active = {status for status in OrderStatus if status.is_active()}
    terminal = {status for status in OrderStatus if status.is_terminal()}
    assert active == {
        OrderStatus.NEW,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.PENDING_CANCEL,
    }
    assert terminal == {
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.EXPIRED,
        OrderStatus.REJECTED,
        OrderStatus.FAILED,
    }
    assert active.isdisjoint(terminal)
