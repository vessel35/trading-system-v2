"""Define strategy family, expectancy envelope, tail shape, and maturity profiles."""

from dataclasses import dataclass

_TAIL_SHAPES = {"right_fat", "symmetric", "left_fat"}
_RISK_ADJUSTED_PREFERENCES = {"sortino", "sharpe", "calmar"}
_ENVELOPE_STATUSES = {"provisional", "updating", "established"}


@dataclass(frozen=True, slots=True)
class StrategyProfile:
    """A strategy-owned declaration of its expected performance shape."""

    id: str
    family: str
    bar: str
    expected_win_rate: tuple[float, float]
    expected_payoff: tuple[float, float]
    tail_shape: str
    holding_horizon: str
    primary_metric: str
    risk_adjusted_pref: str
    profit_structure_to_preserve: str
    envelope_tolerance: float
    envelope_status: str

    def __post_init__(self) -> None:
        if not self.id or not self.family or not self.bar:
            raise ValueError("profile id, family, and bar must not be empty")
        self._validate_range("expected_win_rate", self.expected_win_rate, lower_bound=0.0)
        if self.expected_win_rate[1] > 1.0:
            raise ValueError("expected_win_rate upper bound cannot exceed 1")
        self._validate_range("expected_payoff", self.expected_payoff, lower_bound=0.0)
        if self.tail_shape not in _TAIL_SHAPES:
            raise ValueError(f"unsupported tail_shape: {self.tail_shape}")
        if self.risk_adjusted_pref not in _RISK_ADJUSTED_PREFERENCES:
            raise ValueError(f"unsupported risk_adjusted_pref: {self.risk_adjusted_pref}")
        if self.envelope_status not in _ENVELOPE_STATUSES:
            raise ValueError(f"unsupported envelope_status: {self.envelope_status}")
        if self.envelope_tolerance < 0.0:
            raise ValueError("envelope_tolerance must be non-negative")

    @staticmethod
    def _validate_range(
        name: str,
        value: tuple[float, float],
        *,
        lower_bound: float,
    ) -> None:
        if len(value) != 2:
            raise ValueError(f"{name} must contain exactly two bounds")
        lower, upper = value
        if lower < lower_bound or upper < lower:
            raise ValueError(f"invalid {name} range")
