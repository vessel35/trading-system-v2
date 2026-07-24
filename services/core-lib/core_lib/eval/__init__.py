"""Define shared performance formulas and three-stage evaluation."""

from .decision import DecisionResult, decide
from .hard_gate import judge
from .integrity import IntegrityResult
from .integrity import check as check_integrity
from .metrics import MetricSet, annualize, compute, risk_of_ruin
from .profile import EnvelopeResult, check_envelope
from .thresholds import GateResult, is_pass, overfit, universal

__all__ = [
    "DecisionResult",
    "EnvelopeResult",
    "GateResult",
    "IntegrityResult",
    "MetricSet",
    "annualize",
    "check_envelope",
    "check_integrity",
    "compute",
    "decide",
    "is_pass",
    "judge",
    "overfit",
    "risk_of_ruin",
    "universal",
]
