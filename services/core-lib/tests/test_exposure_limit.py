"""Verify the three aggregate exposure limits and their Engine composition."""

from collections.abc import Callable

import pytest
from core_lib.sizing import exposure_limit
from core_lib.sizing.risk_money import one_r, size

LimitCheck = Callable[[list[float], float], bool]

LIMIT_CHECKS: tuple[LimitCheck, ...] = (
    exposure_limit.single_market,
    exposure_limit.correlation_group,
    exposure_limit.single_direction,
)


@pytest.mark.parametrize("check", LIMIT_CHECKS)
def test_each_limit_includes_the_exact_float_boundary(check: LimitCheck) -> None:
    assert check([0.1, 0.2], 0.3)


@pytest.mark.parametrize("check", LIMIT_CHECKS)
def test_each_limit_accepts_below_and_rejects_above(check: LimitCheck) -> None:
    assert check([0.05, 0.10], 0.20)
    assert not check([0.05, 0.16], 0.20)


def test_engine_can_compose_candidate_risk_across_all_three_limits() -> None:
    account_equity = 10_000.0
    candidate_quantity = size(0.01, account_equity, 100.0)
    candidate_risk_pct = (
        one_r(1_000.0, 900.0, candidate_quantity) / account_equity
    )
    checks = (
        exposure_limit.single_market([0.01, candidate_risk_pct], 0.02),
        exposure_limit.correlation_group([0.02, candidate_risk_pct], 0.03),
        exposure_limit.single_direction(
            [0.03, 0.02, candidate_risk_pct],
            0.06,
        ),
    )
    assert all(checks)
    assert not exposure_limit.single_direction(
        [0.03, 0.02, candidate_risk_pct],
        0.059,
    )


@pytest.mark.parametrize("check", LIMIT_CHECKS)
def test_limits_reject_negative_or_non_float_risk_inputs(check: LimitCheck) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        check([0.01, -0.001], 0.02)
    with pytest.raises(TypeError, match="float"):
        check([0.01, 1], 0.02)
