"""Define the StrategyAdapter decision protocol."""

import math
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from core_lib.money_management import MoneyManagementBase
from core_lib.series import SeriesSpec, series_key, series_key_of
from core_lib.types import (
    Candle,
    DecisionAction,
    DecisionIntent,
    MarketType,
    Position,
    TradingSignal,
)

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


@dataclass(frozen=True, slots=True)
class DecisionInputs:
    """The six inputs the Engine hands a strategy, read once with their types checked."""

    candles: tuple[Candle, ...]
    candle: Candle
    symbol: str
    timeframe: str
    market_type: MarketType
    indicators: Mapping[str, object]


class StrategyBase(ABC):
    """Optional stateless convenience base that satisfies ``StrategyAdapter``.

    The five static helpers below are the code every strategy otherwise repeats: reading the
    six inputs with their types checked, reading one declared series by its execution key,
    narrowing a value to a number or to named outputs, and building a ``DecisionIntent`` the
    way the authoring contract (section 4.1) requires. None of them keeps state.
    """

    __slots__ = ()

    @staticmethod
    def read_inputs(market_data: Mapping[str, object]) -> DecisionInputs:
        """Read the six inputs the Engine passes, refusing a missing or mistyped one."""
        candles = market_data.get("candles")
        candle = market_data.get("candle")
        symbol = market_data.get("symbol")
        timeframe = market_data.get("timeframe")
        market_type = market_data.get("market_type")
        indicators = market_data.get("indicators")
        if not isinstance(candles, list | tuple) or not candles:
            raise TypeError("market_data.candles must be a non-empty sequence of Candle")
        if not all(isinstance(item, Candle) for item in candles):
            raise TypeError("market_data.candles must contain Candle values only")
        if not isinstance(candle, Candle):
            raise TypeError("market_data.candle must be Candle")
        if not isinstance(symbol, str) or not symbol:
            raise TypeError("market_data.symbol must be a non-empty string")
        if not isinstance(timeframe, str) or not timeframe:
            raise TypeError("market_data.timeframe must be a non-empty string")
        if isinstance(market_type, MarketType):
            resolved_market_type = market_type
        elif isinstance(market_type, str):
            try:
                resolved_market_type = MarketType(market_type)
            except ValueError as error:
                raise TypeError(
                    f"market_data.market_type is not a market type: {market_type!r}"
                ) from error
        else:
            raise TypeError("market_data.market_type must be a market type or its name")
        if not isinstance(indicators, Mapping):
            raise TypeError("market_data.indicators must be a mapping")
        return DecisionInputs(
            candles=tuple(candles),
            candle=candle,
            symbol=symbol,
            timeframe=timeframe,
            market_type=resolved_market_type,
            indicators=MappingProxyType({str(key): value for key, value in indicators.items()}),
        )

    @staticmethod
    def series(
        inputs: DecisionInputs,
        name: str,
        params: Mapping[str, object],
        timeframe: str | None = None,
    ) -> object:
        """Read one declared series at the deciding bar by the key the Engine used.

        A series declared on its own timeframe is read with that timeframe; ``None`` or
        ``"strategy"`` means the run's timeframe, as in the declaration.
        """
        resolved = inputs.timeframe if timeframe in (None, "strategy") else timeframe
        key = series_key_of(name, params, resolved)
        try:
            return inputs.indicators[key]
        except KeyError as error:
            raise KeyError(
                f"series {key!r} is not among the inputs; declare it in required_indicators"
            ) from error

    @staticmethod
    def number(value: object, name: str) -> float:
        """Narrow a single-output series value to a float, refusing bool and anything else."""
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise TypeError(f"{name} must be a number, got {type(value).__name__}")
        return float(value)

    @staticmethod
    def outputs(value: object, name: str) -> Mapping[str, float]:
        """Narrow a multi-output series value to named numbers."""
        if not isinstance(value, Mapping):
            raise TypeError(
                f"{name} must be a mapping of named outputs, got {type(value).__name__}"
            )
        narrowed: dict[str, float] = {}
        for key, item in value.items():
            if isinstance(item, bool) or not isinstance(item, int | float):
                raise TypeError(f"{name}[{key!r}] must be a number, got {type(item).__name__}")
            narrowed[str(key)] = float(item)
        return MappingProxyType(narrowed)

    @staticmethod
    def decide(
        candle: Candle,
        action: DecisionAction | str,
        reason: str,
        *,
        adaptee: str,
        confidence: float = 1.0,
        metadata: Mapping[str, object] | None = None,
    ) -> DecisionIntent:
        """Build the decision for ``candle`` the way contract section 4.1 requires.

        The symbol and the timestamp come from the deciding candle, the reference price is its
        close, and the metadata names the strategy under ``adaptee``.
        """
        return DecisionIntent(
            action=DecisionAction(action),
            symbol=candle.symbol,
            timestamp=candle.close_time,
            reference_price=float(candle.close),
            confidence=float(confidence),
            reason=reason,
            metadata={"adaptee": adaptee, **dict(metadata or {})},
        )

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
