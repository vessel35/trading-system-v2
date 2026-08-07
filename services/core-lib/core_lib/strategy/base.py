"""Define the StrategyAdapter decision protocol."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from core_lib.money_management import MoneyManagementPolicy
from core_lib.series import SeriesSpec
from core_lib.series_resolution import series_key
from core_lib.types import DecisionIntent, Position, TradingSignal

from .config import ParameterSchema
from .profile import StrategyProfile


@dataclass(frozen=True, slots=True)
class MoneyManagementSupport:
    """Declare the policies and capabilities accepted by a strategy."""

    supported: tuple[str, ...] = ()
    default: str | None = None
    supports_external_stop: bool = False
    supports_external_take_profit: bool = False
    supports_signal_exit: bool = False
    supports_pyramiding: bool = False

    def __post_init__(self) -> None:
        if len(set(self.supported)) != len(self.supported):
            raise ValueError("money-management modes must be unique")
        if self.default is not None and self.default not in self.supported:
            raise ValueError("default money-management mode must be supported")


@dataclass(slots=True)
class StrategyMetadata:
    """The indicators, history, timeframes, and shape declared by an Adaptee."""

    required_indicators: list[dict[str, object]]
    min_history: int
    supported_timeframes: list[str]
    profile: StrategyProfile
    money_management: MoneyManagementSupport = field(default_factory=MoneyManagementSupport)

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
    ) -> DecisionIntent | TradingSignal | None:
        """Return a decision signal, or None for HOLD."""
        ...


class StrategyBase(ABC):
    """Optional stateless convenience base that satisfies ``StrategyAdapter``."""

    __slots__ = ()

    @classmethod
    @abstractmethod
    def get_metadata(cls) -> StrategyMetadata:
        """Return the strategy-owned execution requirements."""

    @classmethod
    @abstractmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        """Return the strategy-owned parameter declaration."""

    @abstractmethod
    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> DecisionIntent | None:
        """Return a decision signal, or None for HOLD."""

    @staticmethod
    def series_value(
        market_data: Mapping[str, object],
        spec: SeriesSpec,
    ) -> object:
        """Read one precomputed series value by its shared execution key."""
        values = market_data.get("indicators")
        if not isinstance(values, Mapping):
            raise TypeError("market_data.indicators must be a mapping")
        key = series_key(spec)
        try:
            return values[key]
        except KeyError as error:
            raise KeyError(f"market_data has no value for declared series: {key}") from error


@dataclass(frozen=True, slots=True)
class StrategyRuntime:
    """Compose a decision strategy with an optional common money policy."""

    strategy: StrategyAdapter
    money_management: MoneyManagementPolicy | None
