"""Define accounting, timing, cost, determinism, and evidence integrity checks."""

from collections.abc import Mapping
from dataclasses import dataclass

REQUIRED_CHECKS = (
    "accounting_identity",
    "timestamp_order",
    "cost_once",
    "net_of_cost",
    "deterministic",
    "evidence_complete",
)
TRAILING_PARITY_CHECK = "trailing_parity"


@dataclass(frozen=True, slots=True)
class IntegrityResult:
    """The evidence checks that must pass before evaluation continues."""

    passed: bool
    failed_checks: list[str]


def check(evidence: Mapping[str, bool]) -> IntegrityResult:
    """Check the six mandatory evidence facts and optional trailing parity."""
    failed = [name for name in REQUIRED_CHECKS if evidence.get(name) is not True]
    if (
        TRAILING_PARITY_CHECK in evidence
        and evidence[TRAILING_PARITY_CHECK] is not True
    ):
        failed.append(TRAILING_PARITY_CHECK)
    return IntegrityResult(passed=not failed, failed_checks=failed)
