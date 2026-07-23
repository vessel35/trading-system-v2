"""Verify completed-trade forensic and PnL invariants."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from core_lib.types import ExitReason, MarketType, OrderSide, Trade


def make_trade(
    *,
    net_pnl: Decimal = Decimal("17.5"),
    funding_cost: Decimal = Decimal("-0.5"),
    liquidation_penalty: Decimal = Decimal("0"),
    exit_reason: ExitReason = ExitReason.TAKE_PROFIT,
    liquidated: bool = False,
    r0: Decimal | None = Decimal("5"),
) -> Trade:
    entry_time = datetime(2026, 1, 1, tzinfo=UTC)
    return Trade(
        source_type="backtest",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        market_type=MarketType.FUTURES,
        entry_price=Decimal("100"),
        entry_quantity=Decimal("1"),
        entry_time=entry_time,
        exit_price=Decimal("120"),
        exit_quantity=Decimal("1"),
        exit_time=entry_time + timedelta(hours=1),
        exit_reason=exit_reason,
        gross_pnl=Decimal("20"),
        total_fee=Decimal("1"),
        slippage=Decimal("2"),
        funding_cost=funding_cost,
        liquidation_penalty=liquidation_penalty,
        net_pnl=net_pnl,
        return_pct=Decimal("17.5"),
        r0=r0,
        leverage=2,
        liquidated=liquidated,
        wallet_id=None,
        backtest_run_id="bt_20260101_000001",
        strategy_id="breakout-v1",
        strategy_name="Breakout",
        hold_duration_seconds=3600,
        signal_confidence=0.8,
        reason="target reached",
    )


def test_r0_is_recorded_and_may_be_null_without_an_initial_stop() -> None:
    assert make_trade().r0 == Decimal("5.00000000")
    assert make_trade(r0=None).r0 is None


def test_net_pnl_subtracts_all_four_cost_terms_and_allows_funding_income() -> None:
    trade = make_trade()
    assert trade.funding_cost == Decimal("-0.50000000")
    assert trade.net_pnl == Decimal("17.50000000")
    with pytest.raises(ValueError, match="net_pnl"):
        make_trade(net_pnl=Decimal("18"))


def test_liquidation_penalty_is_non_negative() -> None:
    with pytest.raises(ValueError, match="liquidation_penalty"):
        make_trade(liquidation_penalty=Decimal("-0.01"))


def test_liquidated_flag_pairs_with_liquidation_exit_reason() -> None:
    liquidated_trade = make_trade(
        net_pnl=Decimal("16.5"),
        liquidation_penalty=Decimal("1"),
        exit_reason=ExitReason.LIQUIDATION,
        liquidated=True,
    )
    assert liquidated_trade.liquidated is True
    with pytest.raises(ValueError, match="pair"):
        make_trade(exit_reason=ExitReason.LIQUIDATION, liquidated=False)
