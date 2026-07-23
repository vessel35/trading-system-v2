"""Register indicator versions, implementations, and minimum history."""

import builtins
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from core_lib.types import Candle

from . import momentum, trend, volatility, volume
from .contracts import assert_finalized

IndicatorParam = bool | float | int | str
IndicatorValue = float | dict[str, float]
IndicatorSeries = Sequence[IndicatorValue]


@runtime_checkable
class IndicatorState(Protocol):
    """Structural contract for an incremental indicator implementation."""

    min_history: int

    @property
    def warmed_up(self) -> bool:
        """Return whether the state has enough candles for a valid value."""
        ...

    def seed(self, candles: Sequence[Candle]) -> None:
        """Reset and populate state from warm-up candles."""
        ...

    def update(self, candle: Candle) -> IndicatorValue:
        """Advance by one finalized candle."""
        ...

    def current(self) -> IndicatorValue:
        """Return the latest value or NaN-shaped warm-up value."""
        ...


@dataclass(frozen=True, slots=True)
class IndicatorSpec:
    """Immutable calculation identity and its two execution entry points."""

    name: str
    params: Mapping[str, IndicatorParam]
    version: str
    pinned_impl: str
    min_history: int
    category: str
    required_inputs: tuple[str, ...]
    _vectorized: Callable[[Sequence[Candle]], IndicatorSeries] = field(
        repr=False,
        compare=False,
    )
    _state_factory: Callable[[], IndicatorState] = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("indicator name must not be empty")
        if self.min_history <= 0:
            raise ValueError("min_history must be positive")
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))
        object.__setattr__(self, "required_inputs", tuple(self.required_inputs))

    @property
    def identifier(self) -> str:
        """Return a stable name-plus-parameters registry identifier."""
        if not self.params:
            return self.name
        rendered = ",".join(f"{key}={value!r}" for key, value in sorted(self.params.items()))
        return f"{self.name}({rendered})"

    def compute_vectorized(self, candles: Sequence[Candle]) -> IndicatorSeries:
        """Compute the complete batch series."""
        return self._vectorized(candles)

    def make_state(self) -> IndicatorState:
        """Create a fresh incremental state with no shared execution data."""
        return self._state_factory()


RegistryKey = tuple[str, tuple[tuple[str, IndicatorParam], ...]]


class IndicatorRegistry:
    """Own registered indicator specs and batch calculation selection."""

    def __init__(self) -> None:
        self._specs: dict[RegistryKey, IndicatorSpec] = {}

    @staticmethod
    def _key(name: str, params: Mapping[str, IndicatorParam]) -> RegistryKey:
        return name, tuple(sorted(params.items()))

    def get(self, name: str, params: Mapping[str, IndicatorParam]) -> IndicatorSpec:
        """Return the exact registered name-and-parameters spec."""
        try:
            return self._specs[self._key(name, params)]
        except KeyError as error:
            raise KeyError(f"indicator is not registered: {name} {dict(params)}") from error

    def register(self, spec: IndicatorSpec) -> None:
        """Register one immutable spec, rejecting an identity collision."""
        key = self._key(spec.name, spec.params)
        if key in self._specs:
            raise ValueError(f"indicator already registered: {spec.identifier}")
        self._specs[key] = spec

    def list(self) -> list[IndicatorSpec]:
        """Return all specs in deterministic identifier order."""
        return sorted(self._specs.values(), key=lambda spec: spec.identifier)

    def _matching_specs(self, requested: str) -> builtins.list[IndicatorSpec]:
        matches = [
            spec
            for spec in self._specs.values()
            if spec.name == requested or spec.identifier == requested
        ]
        if not matches:
            raise KeyError(f"indicator is not registered: {requested}")
        return matches

    def compute_batch(
        self,
        candles: Sequence[Candle],
        enabled_set: set[str],
        *,
        decision_time: datetime | None = None,
        available_inputs: Collection[str] = (),
    ) -> dict[str, IndicatorSeries]:
        """Compute enabled specs after finalized/history/input validation."""
        effective_decision_time = decision_time
        if effective_decision_time is None and candles:
            effective_decision_time = candles[-1].close_time
        if effective_decision_time is not None:
            for candle in candles:
                assert_finalized(candle, effective_decision_time)

        selected: dict[str, IndicatorSpec] = {}
        for requested in enabled_set:
            for spec in self._matching_specs(requested):
                selected[spec.identifier] = spec

        available = set(available_inputs)
        result: dict[str, IndicatorSeries] = {}
        for identifier, spec in sorted(selected.items()):
            if not set(spec.required_inputs).issubset(available):
                continue
            if len(candles) < spec.min_history:
                raise ValueError(
                    f"{identifier} requires {spec.min_history} candles, got {len(candles)}"
                )
            result[identifier] = spec.compute_vectorized(candles)
        return result

    def resolve_enabled(
        self,
        mode: str,
        declared: Collection[str],
        explicit: Collection[str],
    ) -> set[str]:
        """Resolve auto, explicit, or all calculation selection."""
        if mode == "auto":
            resolved = set(declared)
        elif mode == "explicit":
            resolved = set(declared) | set(explicit)
        elif mode == "all":
            resolved = {spec.identifier for spec in self._specs.values()}
        else:
            raise ValueError("indicator mode must be auto, explicit, or all")
        for requested in resolved:
            self._matching_specs(requested)
        return resolved


def build_default_registry() -> IndicatorRegistry:
    """Build the first-strategy coverage registry pinned to the authority spec."""
    registry = IndicatorRegistry()
    for period in (9, 21, 55, 200):
        registry.register(
            IndicatorSpec(
                name="EMA",
                params={"period": period},
                version="1.0.0",
                pinned_impl="technical_indicators_calc_spec.md §0.3 (SMA seed, recursive)",
                min_history=period,
                category="trend",
                required_inputs=(),
                _vectorized=partial(trend.ema, period=period),
                _state_factory=partial(trend.EMAState, period=period),
            )
        )
    registry.register(
        IndicatorSpec(
            name="RSI",
            params={"period": 14},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §2.1 + §0.5 (Wilder RMA)",
            min_history=15,
            category="momentum",
            required_inputs=(),
            _vectorized=partial(momentum.rsi, period=14),
            _state_factory=partial(momentum.RSIState, period=14),
        )
    )
    registry.register(
        IndicatorSpec(
            name="Stochastic",
            params={"period": 14, "smooth_period": 3},
            version="1.0.0",
            pinned_impl=(
                "technical_indicators_calc_spec.md §2.2 "
                "(fast %K/%D; flat range keeps previous, initially 50)"
            ),
            min_history=16,
            category="momentum",
            required_inputs=(),
            _vectorized=partial(momentum.stochastic, period=14, smooth_period=3),
            _state_factory=partial(momentum.StochasticState, period=14, smooth_period=3),
        )
    )
    registry.register(
        IndicatorSpec(
            name="ATR",
            params={"period": 14},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §3.1 + §0.6 + §0.5",
            min_history=14,
            category="volatility",
            required_inputs=(),
            _vectorized=partial(volatility.atr, period=14),
            _state_factory=partial(volatility.ATRState, period=14),
        )
    )
    registry.register(
        IndicatorSpec(
            name="Bollinger Bands",
            params={"period": 20, "multiplier": 2.0},
            version="1.0.1",
            pinned_impl=(
                "technical_indicators_calc_spec.md §3.10 + §0.7 "
                "(population stdev, rolling Welford moments)"
            ),
            min_history=20,
            category="volatility",
            required_inputs=(),
            _vectorized=partial(
                volatility.bollinger_bands,
                period=20,
                multiplier=2.0,
            ),
            _state_factory=partial(
                volatility.BollingerBandsState,
                period=20,
                multiplier=2.0,
            ),
        )
    )
    registry.register(
        IndicatorSpec(
            name="Volume SMA",
            params={"period": 20},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §0.2 (volume input)",
            min_history=20,
            category="volume",
            required_inputs=(),
            _vectorized=partial(volume.volume_sma, period=20),
            _state_factory=partial(volume.VolumeSMAState, period=20),
        )
    )
    return registry


DEFAULT_REGISTRY = build_default_registry()
