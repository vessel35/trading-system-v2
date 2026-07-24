"""Define strategy-independent hard evaluation gates."""

from collections.abc import Mapping

from .metrics import MetricSet
from .profile import StrategyProfileShape, check_envelope
from .thresholds import GateResult, is_pass


def judge(
    metric_set: MetricSet,
    thresholds: Mapping[str, float],
    profile: StrategyProfileShape,
) -> GateResult:
    """Apply universal Gate A followed by the strategy-shape Gate B."""
    universal_result = is_pass(metric_set, thresholds)
    if not universal_result.passed:
        return universal_result
    envelope = check_envelope(profile, metric_set)
    if envelope.status == "reject":
        return GateResult(
            passed=False,
            stage="B",
            failed=envelope.deviated,
            verdict="established_regression",
        )
    return GateResult(passed=True, stage="B", failed=[], verdict="pass")
