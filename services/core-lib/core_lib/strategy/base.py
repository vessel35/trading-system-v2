"""Define the StrategyAdapter decision protocol."""

import math
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from core_lib.money_management import MoneyManagementBase
from core_lib.series import SeriesSpec, series_key
from core_lib.types import DecisionIntent, Position, TradingSignal

from .config import ParameterSchema
from .profile import StrategyProfile


class StrategyDecisionContract(StrEnum):
    """Declare which decision value a strategy promises to return."""

    TRADING_SIGNAL = "TradingSignal"
    DECISION_INTENT = "DecisionIntent"


@dataclass(frozen=True, slots=True)
class MoneyManagementSupport:
    """Declare the policies and capabilities accepted by a strategy."""

    supported: tuple[str, ...] = ()
    default: str | None = None
    supports_external_stop: bool = False
    supports_external_take_profit: bool = False
    supports_signal_exit: bool = False
    supports_pyramiding: bool = False
    default_settings: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    """Policy settings the strategy's document fixed, keyed by the mode they belong to.

    A run submitted without a setting reads it from here before the policy's own
    default, so a document that says "1.5 times ATR" is run that way unless the
    user asks for something else. Only the structure is checked here: whether a
    name exists on the policy and whether a value is in range is decided where the
    policy is constructed, because this module does not know the policies.
    """

    def __post_init__(self) -> None:
        if len(set(self.supported)) != len(self.supported):
            raise ValueError("money-management modes must be unique")
        if self.default is not None and self.default not in self.supported:
            raise ValueError("default money-management mode must be supported")
        object.__setattr__(
            self,
            "default_settings",
            _frozen_default_settings(self.supported, self.default_settings),
        )

    def resolve_settings(self, submitted: Mapping[str, object]) -> dict[str, object]:
        """Fill what a submission left out from the settings declared for its mode.

        The submission wins, this declaration comes second, and the policy's own
        defaults come last (they are applied where the policy is constructed).
        Resolving an already resolved mapping changes nothing, so every boundary
        that builds a configuration may call this without checking who called first.
        A submission without a string ``mode`` is returned as it came; the policy
        factory is the one that refuses it.
        """
        mode = submitted.get("mode")
        if not isinstance(mode, str):
            return dict(submitted)
        declared = self.default_settings.get(mode, {})
        return {
            "mode": mode,
            **declared,
            **{name: value for name, value in submitted.items() if name != "mode"},
        }


def _frozen_default_settings(
    supported: tuple[str, ...],
    declared: Mapping[str, Mapping[str, object]],
) -> Mapping[str, Mapping[str, object]]:
    if not isinstance(declared, Mapping):
        raise TypeError("default_settings must map a supported mode to its settings")
    frozen: dict[str, Mapping[str, object]] = {}
    for mode, settings in declared.items():
        if mode not in supported:
            raise ValueError(f"default_settings names unsupported money-management mode {mode!r}")
        if not isinstance(settings, Mapping):
            raise TypeError(f"default_settings[{mode!r}] must be a mapping of setting values")
        values: dict[str, object] = {}
        for name, value in settings.items():
            if not isinstance(name, str) or not name:
                raise TypeError(f"default_settings[{mode!r}] has a setting name that is not text")
            if name == "mode":
                raise ValueError(f"default_settings[{mode!r}] may not set 'mode'")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"default_settings[{mode!r}][{name!r}] must be a finite number")
            if not isinstance(value, bool | int | float | str):
                raise TypeError(
                    f"default_settings[{mode!r}][{name!r}] must be a number, text, or boolean"
                )
            values[name] = value
        frozen[mode] = MappingProxyType(values)
    return MappingProxyType(frozen)


@dataclass(slots=True)
class StrategyMetadata:
    """The indicators, history, timeframes, and shape declared by an Adaptee."""

    required_indicators: list[dict[str, object]]
    min_history: int
    supported_timeframes: list[str]
    profile: StrategyProfile
    money_management: MoneyManagementSupport = field(default_factory=MoneyManagementSupport)
    decision_contract: StrategyDecisionContract = StrategyDecisionContract.TRADING_SIGNAL

    def __post_init__(self) -> None:
        if self.min_history <= 0:
            raise ValueError("min_history must be positive")
        if not self.supported_timeframes:
            raise ValueError("supported_timeframes must not be empty")
        self.decision_contract = StrategyDecisionContract(self.decision_contract)
        self.required_indicators = [dict(item) for item in self.required_indicators]
        self.supported_timeframes = list(self.supported_timeframes)


def validate_strategy_result(metadata: StrategyMetadata, result: object) -> None:
    """Reject values outside the transition contract before an executor uses them."""
    if not isinstance(result, (DecisionIntent, TradingSignal)):
        raise TypeError("strategy analyze() must return DecisionIntent, TradingSignal, or None")
    if metadata.decision_contract is StrategyDecisionContract.DECISION_INTENT and isinstance(
        result, TradingSignal
    ):
        raise TypeError("strategy declared DecisionIntent but returned TradingSignal")


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
        timeframe = market_data.get("timeframe")
        if not isinstance(timeframe, str):
            raise TypeError("market_data.timeframe must be a string")
        key = series_key(spec, timeframe)
        try:
            return values[key]
        except KeyError as error:
            raise KeyError(f"market_data has no value for declared series: {key}") from error


@dataclass(frozen=True, slots=True)
class StrategyRuntime:
    """Compose a decision strategy with an optional common money policy."""

    strategy: StrategyAdapter
    money_management: MoneyManagementBase | None
