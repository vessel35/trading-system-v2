"""Define the StrategyAdapter decision protocol."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from core_lib.types import Position, TradingSignal

from .config import ParameterSchema
from .profile import StrategyProfile


@dataclass(slots=True)
class StrategyMetadata:
    """The indicators, history, timeframes, and shape declared by an Adaptee."""

    required_indicators: list[dict[str, object]]
    min_history: int
    supported_timeframes: list[str]
    profile: StrategyProfile

    def __post_init__(self) -> None:
        if self.min_history <= 0:
            raise ValueError("min_history must be positive")
        if not self.supported_timeframes:
            raise ValueError("supported_timeframes must not be empty")
        self.required_indicators = [dict(item) for item in self.required_indicators]
        self.supported_timeframes = list(self.supported_timeframes)


@runtime_checkable
class StrategyAdapter(Protocol):
    """Stateless, decision-only strategy contract shared by every execution mode."""

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        """Return the Adaptee-owned execution requirements."""
        ...

    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        """Return the Adaptee-owned parameter declaration."""
        ...

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> TradingSignal | None:
        """Return a decision signal, or None for HOLD."""
        ...
