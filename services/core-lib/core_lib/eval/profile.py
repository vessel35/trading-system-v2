"""Define profile-envelope warning and established-regression rules."""

import math
from dataclasses import dataclass
from typing import Protocol

from .metrics import MetricSet


class StrategyProfileShape(Protocol):
    """The StrategyProfile attributes consumed by the leaf eval component."""

    @property
    def expected_win_rate(self) -> tuple[float, float]:
        """Return the declared win-rate range."""
        ...

    @property
    def expected_payoff(self) -> tuple[float, float]:
        """Return the declared payoff range."""
        ...

    @property
    def envelope_tolerance(self) -> float:
        """Return the absolute envelope tolerance."""
        ...

    @property
    def envelope_status(self) -> str:
        """Return provisional, updating, or established maturity."""
        ...


@dataclass(frozen=True, slots=True)
class EnvelopeResult:
    """The realized strategy-shape comparison result."""

    status: str
    deviated: list[str]


def _outside(value: float, expected: tuple[float, float], tolerance: float) -> bool:
    return (
        math.isnan(value)
        or value < expected[0] - tolerance
        or value > expected[1] + tolerance
    )


def check_envelope(
    profile: StrategyProfileShape,
    metric_set: MetricSet,
) -> EnvelopeResult:
    """Warn on shape drift, rejecting only established-strategy regression."""
    deviated: list[str] = []
    if _outside(
        metric_set.win_rate,
        profile.expected_win_rate,
        profile.envelope_tolerance,
    ):
        deviated.append("win_rate")
    if _outside(
        metric_set.payoff,
        profile.expected_payoff,
        profile.envelope_tolerance,
    ):
        deviated.append("payoff")
    if not deviated:
        status = "in_range"
    elif profile.envelope_status == "established":
        status = "reject"
    else:
        status = "warning"
    return EnvelopeResult(status=status, deviated=deviated)
