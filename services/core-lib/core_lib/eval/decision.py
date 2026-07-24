"""Define preregistered primary-metric decision routing."""

from collections.abc import Mapping
from dataclasses import dataclass

from .thresholds import GateResult


@dataclass(frozen=True, slots=True)
class DecisionResult:
    """A preregistration-based final route and human-readable rationale."""

    route: str
    rationale: str


def _number(prereg: Mapping[str, object], key: str) -> float:
    value = prereg.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"prereg.{key} must be numeric")
    return float(value)


def decide(
    gate_result: GateResult,
    prereg: Mapping[str, object],
) -> DecisionResult:
    """Route a passed gate against preregistered success and failure criteria."""
    if not gate_result.passed:
        raise ValueError("Decision requires a passed Hard Gate")
    primary_metric = prereg.get("primary_metric")
    if not isinstance(primary_metric, str) or not primary_metric:
        raise ValueError("prereg.primary_metric must be a non-empty string")
    observed = _number(prereg, "observed_value")
    success_threshold = _number(prereg, "success_threshold")
    failure_threshold = _number(prereg, "failure_threshold")
    higher_is_better = prereg.get("higher_is_better", True)
    edge_distinguishable = prereg.get("edge_distinguishable")
    if not isinstance(higher_is_better, bool):
        raise TypeError("prereg.higher_is_better must be bool")
    if not isinstance(edge_distinguishable, bool):
        raise TypeError("prereg.edge_distinguishable must be bool")

    success = observed >= success_threshold if higher_is_better else observed <= success_threshold
    failed = observed <= failure_threshold if higher_is_better else observed >= failure_threshold
    if success:
        route = "promote"
        reason = "met the preregistered success threshold"
    elif failed and not edge_distinguishable:
        route = "abandon"
        reason = "met the failure threshold and the edge is not distinguishable"
    elif failed:
        route = "retest"
        reason = "met the failure threshold but the edge remains distinguishable"
    else:
        route = "partial_keep"
        reason = "fell between preregistered success and failure thresholds"
    return DecisionResult(route=route, rationale=f"{primary_metric}: {reason}")
