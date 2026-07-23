"""Define evaluation thresholds in one shared implementation."""

import math
from collections.abc import Mapping
from dataclasses import dataclass

from .metrics import MetricSet


@dataclass(frozen=True, slots=True)
class GateResult:
    """A Hard Gate A/B result and its stable catalog verdict."""

    passed: bool
    stage: str
    failed: list[str]
    verdict: str


def universal() -> dict[str, float]:
    """Return the single standard set of universal thresholds."""
    return {
        "pf_min": 1.3,
        "sortino_min": 1.0,
        "calmar_or_mar_min": 0.8,
        "sqn_min": 1.6,
        "mdd_max": 0.30,
        "ror_max_exclusive": 0.001,
        "expectancy_r_min_exclusive": 0.0,
        "trade_count_min": 30.0,
    }


def _below(value: float, limit: float) -> bool:
    return math.isnan(value) or value < limit


def is_pass(
    metric_set: MetricSet,
    values: Mapping[str, float] | None = None,
) -> GateResult:
    """Apply universal net, survival, and sample-size gates."""
    limits = universal() if values is None else values
    failed: list[str] = []
    minimum_trades = int(limits["trade_count_min"])
    if metric_set.trade_count < minimum_trades:
        failed.append(
            f"trade_count: insufficient sample "
            f"({metric_set.trade_count} < {minimum_trades})"
        )
    if _below(metric_set.pf, limits["pf_min"]):
        failed.append("pf")
    if _below(metric_set.sortino, limits["sortino_min"]):
        failed.append("sortino")
    if _below(metric_set.calmar_or_mar, limits["calmar_or_mar_min"]):
        failed.append("calmar_or_mar")
    if _below(metric_set.sqn, limits["sqn_min"]):
        failed.append("sqn")
    if math.isnan(metric_set.mdd) or abs(metric_set.mdd) > limits["mdd_max"]:
        failed.append("mdd")
    if (
        math.isnan(metric_set.ror)
        or metric_set.ror >= limits["ror_max_exclusive"]
    ):
        failed.append("ror")
    if (
        math.isnan(metric_set.expectancy_r)
        or metric_set.expectancy_r
        <= limits["expectancy_r_min_exclusive"]
    ):
        failed.append("expectancy_r")
    return GateResult(
        passed=not failed,
        stage="A",
        failed=failed,
        verdict="pass" if not failed else "not_promotable",
    )
