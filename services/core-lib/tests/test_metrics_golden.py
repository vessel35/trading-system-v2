"""Reproduce the maintained metric standard's golden example with production formulas.

The maintained reference is mirrored at docs/fullspec/50_metrics_reference.md.
"""

import math
import statistics
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from core_lib.eval import metrics
from core_lib.types import ZERO, ExitReason, MarketType, OrderSide, Trade

PNL = (200, -100, 150, -50, 300, -120, 80, 250, -70, 180)
MONTHLY_RETURNS = (
    0.03,
    -0.02,
    0.015,
    0.04,
    -0.01,
    0.025,
    -0.035,
    0.02,
    0.01,
    -0.015,
    0.03,
    0.02,
)


def _golden_trade(net_pnl: int) -> Trade:
    amount = Decimal(net_pnl)
    return Trade(
        source_type="backtest",
        symbol="BTC/USDT:USDT",
        side=OrderSide.BUY,
        market_type=MarketType.FUTURES,
        entry_price=Decimal("100"),
        entry_quantity=Decimal("1"),
        entry_time=datetime(2025, 1, 1, tzinfo=UTC),
        exit_price=Decimal("101"),
        exit_quantity=Decimal("1"),
        exit_time=datetime(2025, 1, 2, tzinfo=UTC),
        exit_reason=ExitReason.TAKE_PROFIT,
        gross_pnl=amount,
        total_fee=ZERO,
        slippage=ZERO,
        funding_cost=ZERO,
        liquidation_penalty=ZERO,
        net_pnl=amount,
        return_pct=ZERO,
        r0=Decimal("100"),
        leverage=1,
        liquidated=False,
        wallet_id=None,
        backtest_run_id=None,
        strategy_id="golden",
        strategy_name="golden",
        hold_duration_seconds=86_400,
        signal_confidence=1.0,
        reason="golden",
    )


def _golden_equity() -> list[tuple[datetime, float]]:
    timestamps = [datetime(2025, 1, 1, tzinfo=UTC)] + [
        datetime(2025 + (month // 12), (month % 12) + 1, 1, tzinfo=UTC) for month in range(1, 13)
    ]
    values = [100_000.0]
    running = values[0]
    for monthly_return in MONTHLY_RETURNS:
        running *= 1.0 + monthly_return
        values.append(running)
    return list(zip(timestamps, values, strict=True))


def test_non_annualized_metrics_reproduce_the_maintained_golden_values() -> None:
    trades = [_golden_trade(value) for value in PNL]
    equity = _golden_equity()

    result = metrics.compute(trades, equity)

    assert result.pf == pytest.approx(3.4118, abs=5e-5)
    assert result.mdd == pytest.approx(-0.035, abs=1e-12)
    assert result.calmar_or_mar == pytest.approx(3.2102, abs=5e-5)
    assert result.payoff == pytest.approx(2.2745, abs=5e-5)
    assert result.kelly == pytest.approx(0.4241, abs=5e-5)
    assert result.ulcer == pytest.approx(1.3771, abs=5e-5)
    assert result.win_rate == pytest.approx(0.60)
    # The reference's expectancy 82.0 is monetary; production stores R with r0=100.
    assert result.expectancy_r == pytest.approx(0.82)


def test_annualization_identity_and_small_sample_sqn_match_the_standard() -> None:
    trades = [_golden_trade(value) for value in PNL]
    equity = _golden_equity()
    result = metrics.compute(trades, equity)
    returns = list(MONTHLY_RETURNS)

    sharpe_ratio = statistics.fmean(returns) / statistics.stdev(returns)
    reference_sharpe = math.sqrt(12) * sharpe_ratio
    production_sharpe = reference_sharpe * math.sqrt(365 / 12)
    assert reference_sharpe == pytest.approx(1.3494, abs=1e-4)
    assert metrics.annualize(equity) == pytest.approx(production_sharpe)
    assert result.sharpe == pytest.approx(production_sharpe)

    downside = math.sqrt(sum(min(0.0, value) ** 2 for value in returns) / len(returns))
    sortino_ratio = statistics.fmean(returns) / downside
    reference_sortino = math.sqrt(12) * sortino_ratio
    production_sortino = reference_sortino * math.sqrt(365 / 12)
    assert reference_sortino == pytest.approx(2.4910, abs=1e-4)
    assert result.sortino == pytest.approx(production_sortino)

    # The maintained N=10 worked example is below production's N>=30 SQN gate.
    assert math.isnan(result.sqn)
    # RoR is intentionally excluded: production uses fixed-seed Monte Carlo, not (q/p)^B.
