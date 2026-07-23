"""Verify standardized metrics, integrity, gates, profiles, and decisions."""

import math
import statistics
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from core_lib.eval import (
    GateResult,
    MetricSet,
    annualize,
    check_envelope,
    check_integrity,
    compute,
    decide,
    is_pass,
    judge,
    risk_of_ruin,
    universal,
)
from core_lib.strategy import StrategyProfile
from core_lib.types import ExitReason, MarketType, OrderSide, Trade


def make_trade(r_multiple: float, index: int) -> Trade:
    """Build a net trade whose initial risk is exactly 100 quote units."""
    opened = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=index)
    net_pnl = Decimal(str(r_multiple * 100))
    return Trade(
        source_type="backtest",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        market_type=MarketType.FUTURES,
        entry_price=Decimal("100"),
        entry_quantity=Decimal("1"),
        entry_time=opened,
        exit_price=Decimal("101"),
        exit_quantity=Decimal("1"),
        exit_time=opened + timedelta(hours=1),
        exit_reason=ExitReason.SIGNAL_EXIT,
        gross_pnl=net_pnl,
        total_fee=Decimal("0"),
        slippage=Decimal("0"),
        funding_cost=Decimal("0"),
        liquidation_penalty=Decimal("0"),
        net_pnl=net_pnl,
        return_pct=Decimal("0"),
        r0=Decimal("100"),
        leverage=1,
        liquidated=False,
        wallet_id=None,
        backtest_run_id="BT-TEST",
        strategy_id="fake",
        strategy_name="Fake",
        hold_duration_seconds=3600,
        signal_confidence=1.0,
        reason="test",
    )


def make_profile(*, status: str = "provisional") -> StrategyProfile:
    return StrategyProfile(
        id="profile",
        family="breakout",
        bar="1d",
        expected_win_rate=(0.4, 0.7),
        expected_payoff=(1.0, 3.0),
        tail_shape="right_fat",
        holding_horizon="multi_day",
        primary_metric="calmar",
        risk_adjusted_pref="sortino",
        profit_structure_to_preserve="large winners",
        envelope_tolerance=0.05,
        envelope_status=status,
    )


def passing_metrics(**overrides: float | int) -> MetricSet:
    values: dict[str, float | int] = {
        "pf": 1.5,
        "sortino": 1.5,
        "calmar_or_mar": 1.0,
        "sqn": 2.0,
        "mdd": -0.20,
        "ror": 0.0009,
        "sharpe": 0.5,
        "win_rate": 0.5,
        "payoff": 2.0,
        "expectancy_r": 0.2,
        "ulcer": 10.0,
        "kelly": 0.25,
        "trade_count": 30,
    }
    values.update(overrides)
    return MetricSet(**values)  # type: ignore[arg-type]


def test_metrics_resample_daily_and_use_whole_n_sortino_denominator() -> None:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    equity = {
        start: 100.0,
        start + timedelta(hours=12): 103.0,
        start + timedelta(days=1): 110.0,
        start + timedelta(days=2): 104.5,
        start + timedelta(days=3): 104.5,
    }
    trades = [make_trade(2.0 if index % 2 == 0 else -1.0, index) for index in range(30)]
    metrics = compute(trades, equity)

    daily_returns = [110.0 / 103.0 - 1.0, -0.05, 0.0]
    expected_downside = math.sqrt(sum(min(0.0, value) ** 2 for value in daily_returns) / 3)
    expected_sortino = (
        math.sqrt(365) * statistics.fmean(daily_returns) / expected_downside
    )
    expected_sharpe = (
        math.sqrt(365)
        * statistics.fmean(daily_returns)
        / statistics.stdev(daily_returns)
    )
    assert metrics.sortino == pytest.approx(expected_sortino)
    assert metrics.sharpe == pytest.approx(expected_sharpe)
    assert annualize(equity) == pytest.approx(expected_sharpe)
    assert metrics.mdd == pytest.approx(-0.05)
    assert metrics.ulcer == pytest.approx(math.sqrt(10.0))
    assert metrics.pf == 2.0
    assert metrics.trade_count == 30


def test_sqn_uses_r_multiples_caps_n_at_100_and_rejects_short_samples() -> None:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    equity = {
        start + timedelta(days=index): 100.0 + index
        for index in range(121)
    }
    r_multiples = [2.0] * 90 + [-1.0] * 30
    metrics = compute(
        [make_trade(value, index) for index, value in enumerate(r_multiples)],
        equity,
    )
    expected_sqn = (
        math.sqrt(100)
        * statistics.fmean(r_multiples)
        / statistics.stdev(r_multiples)
    )
    assert metrics.sqn == pytest.approx(expected_sqn)

    short_metrics = compute(
        [make_trade(1.0, index) for index in range(29)],
        dict(list(equity.items())[:30]),
    )
    assert math.isnan(short_metrics.sqn)


def test_risk_of_ruin_is_fixed_seed_monte_carlo_not_closed_form() -> None:
    sample = [2.0, -1.0, 0.5, -0.25]
    first = risk_of_ruin(sample, iterations=500)
    second = risk_of_ruin(sample, iterations=500)
    assert first == second
    assert risk_of_ruin([-100.0], iterations=25) == 1.0


def test_thresholds_enforce_exact_boundaries_and_direct_trade_count_gate() -> None:
    assert is_pass(passing_metrics()).passed
    at_boundaries = passing_metrics(
        pf=1.3,
        sortino=1.0,
        calmar_or_mar=0.8,
        sqn=1.6,
        mdd=-0.30,
        ror=0.000999,
        expectancy_r=0.000001,
    )
    assert is_pass(at_boundaries).passed
    insufficient = is_pass(passing_metrics(trade_count=29))
    assert not insufficient.passed
    assert insufficient.failed[0] == "trade_count: insufficient sample (29 < 30)"
    assert not is_pass(passing_metrics(ror=0.001)).passed
    assert universal()["trade_count_min"] == 30.0


def test_profile_drift_warns_until_established_then_hard_gate_rejects() -> None:
    drifted = passing_metrics(win_rate=0.2, payoff=0.5)
    provisional = check_envelope(make_profile(), drifted)
    assert provisional.status == "warning"
    assert provisional.deviated == ["win_rate", "payoff"]

    established_profile = make_profile(status="established")
    established = check_envelope(established_profile, drifted)
    assert established.status == "reject"
    gate = judge(drifted, universal(), established_profile)
    assert gate == GateResult(
        passed=False,
        stage="B",
        failed=["win_rate", "payoff"],
        verdict="established_regression",
    )


def test_integrity_mapping_contract_requires_six_checks_and_optional_parity() -> None:
    evidence = {
        "accounting_identity": True,
        "timestamp_order": True,
        "cost_once": True,
        "net_of_cost": True,
        "deterministic": True,
        "evidence_complete": True,
    }
    assert check_integrity(evidence).passed
    evidence["timestamp_order"] = False
    assert check_integrity(evidence).failed_checks == ["timestamp_order"]
    evidence["timestamp_order"] = True
    evidence["trailing_parity"] = False
    assert check_integrity(evidence).failed_checks == ["trailing_parity"]


@pytest.mark.parametrize(
    ("observed", "edge_distinguishable", "expected"),
    [
        (1.5, True, "promote"),
        (1.2, True, "partial_keep"),
        (0.7, True, "retest"),
        (0.7, False, "abandon"),
    ],
)
def test_decision_routes_only_passed_gates_against_preregistered_values(
    observed: float,
    edge_distinguishable: bool,
    expected: str,
) -> None:
    result = decide(
        GateResult(True, "B", [], "pass"),
        {
            "primary_metric": "calmar",
            "observed_value": observed,
            "success_threshold": 1.3,
            "failure_threshold": 0.8,
            "edge_distinguishable": edge_distinguishable,
        },
    )
    assert result.route == expected

    with pytest.raises(ValueError, match="passed Hard Gate"):
        decide(
            GateResult(False, "A", ["pf"], "not_promotable"),
            {
                "primary_metric": "pf",
                "observed_value": 1.0,
                "success_threshold": 1.3,
                "failure_threshold": 1.0,
                "edge_distinguishable": True,
            },
        )
