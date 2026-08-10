"""Register indicator versions, implementations, and minimum history."""

from __future__ import annotations

import builtins
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from core_lib.types import Candle

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
    _state_factory: Callable[[], Any] = field(
        repr=False,
        compare=False,
    )
    needs_reference_series: bool = False
    undefined_outputs: tuple[str, ...] = ()
    """Output keys the standard itself leaves undefined for degenerate windows.

    Bollinger %B is the first case: §3.10 writes "분모 0 → 미정의" because a
    collapsed band has no relative position to report. An indicator must not
    invent a number where the standard declines to define one, so those keys may
    carry NaN after warm-up and every other key may not. Consumers read this list
    rather than guessing which NaN is legitimate.
    """

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("indicator name must not be empty")
        if self.min_history <= 0:
            raise ValueError("min_history must be positive")
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))
        object.__setattr__(self, "required_inputs", tuple(self.required_inputs))
        object.__setattr__(self, "undefined_outputs", tuple(self.undefined_outputs))
        if any(not isinstance(name, str) or not name for name in self.undefined_outputs):
            raise ValueError("undefined_outputs must name output keys")

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
        state = self._state_factory()
        if self.needs_reference_series or not isinstance(state, IndicatorState):
            raise TypeError(f"indicator {self.identifier} does not provide a single-series state")
        return state

    def make_paired_state(self) -> Any:
        """Create a fresh paired state from a reference-series declaration."""
        state = self._state_factory()
        if not self.needs_reference_series:
            raise TypeError(f"indicator {self.identifier} does not provide a paired-series state")
        return state


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

    def _descriptor_spec(self, descriptor: Mapping[str, object]) -> IndicatorSpec:
        """Resolve one external name-and-parameters descriptor to its registry spec."""
        if set(descriptor) != {"name", "params"}:
            raise ValueError("indicator descriptor must contain exactly name and params")
        name = descriptor["name"]
        params = descriptor["params"]
        if not isinstance(name, str) or not isinstance(params, Mapping):
            raise TypeError("indicator descriptor name/params have invalid types")
        normalized_params = dict(params)
        if any(
            not isinstance(key, str) or not isinstance(value, bool | float | int | str)
            for key, value in normalized_params.items()
        ):
            raise TypeError("indicator params must use scalar registry values")
        matches = [
            spec
            for spec in self._specs.values()
            if spec.name.casefold() == name.casefold() and dict(spec.params) == normalized_params
        ]
        if len(matches) != 1:
            raise KeyError(f"indicator is not registered: {name} {normalized_params}")
        return matches[0]

    def specs_for(
        self,
        enabled_set: Collection[str],
    ) -> builtins.list[IndicatorSpec]:
        """Return the deterministic, de-duplicated specs named by an enabled set."""
        selected: dict[str, IndicatorSpec] = {}
        for requested in enabled_set:
            for spec in self._matching_specs(requested):
                selected[spec.identifier] = spec
        return [selected[identifier] for identifier in sorted(selected)]

    def specs_from_descriptors(
        self,
        descriptors: Collection[Mapping[str, object]],
    ) -> builtins.list[IndicatorSpec]:
        """Resolve descriptors to deterministic, de-duplicated registry specs."""
        selected: dict[str, IndicatorSpec] = {}
        for descriptor in descriptors:
            spec = self._descriptor_spec(descriptor)
            selected[spec.identifier] = spec
        return [selected[identifier] for identifier in sorted(selected)]

    def compute_batch(
        self,
        candles: Sequence[Candle],
        enabled_set: set[str],
        *,
        decision_time: datetime | None = None,
        available_inputs: Collection[str] = (),
    ) -> dict[str, IndicatorSeries]:
        """Compute a batch/research series after finalized/history/input validation.

        The backtest engine deliberately uses incremental state updates so its
        look-ahead boundary stays structural. This batch path remains the
        independent parity oracle for those state implementations.
        """
        effective_decision_time = decision_time
        if effective_decision_time is None and candles:
            effective_decision_time = candles[-1].close_time
        if effective_decision_time is not None:
            for candle in candles:
                assert_finalized(candle, effective_decision_time)

        available = set(available_inputs)
        result: dict[str, IndicatorSeries] = {}
        for spec in self.specs_for(enabled_set):
            if not set(spec.required_inputs).issubset(available):
                continue
            if len(candles) < spec.min_history:
                raise ValueError(
                    f"{spec.identifier} requires {spec.min_history} candles, got {len(candles)}"
                )
            result[spec.identifier] = spec.compute_vectorized(candles)
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
            resolved = set(explicit)
        elif mode == "all":
            resolved = {spec.identifier for spec in self._specs.values()}
        else:
            raise ValueError("indicator mode must be auto, explicit, or all")
        for requested in resolved:
            self._matching_specs(requested)
        return resolved

    def resolve_specs(
        self,
        mode: str,
        declared: Collection[Mapping[str, object]],
        explicit: Collection[Mapping[str, object]],
    ) -> builtins.list[IndicatorSpec]:
        """Resolve external descriptors and calculation mode through one registry path."""
        declared_ids = {spec.identifier for spec in self.specs_from_descriptors(declared)}
        explicit_ids = {spec.identifier for spec in self.specs_from_descriptors(explicit)}
        enabled = self.resolve_enabled(mode, declared_ids, explicit_ids)
        specs = self.specs_for(enabled)
        if not specs:
            raise ValueError("an indicator selection must resolve at least one spec")
        return specs


def build_default_registry() -> IndicatorRegistry:
    """Build the registry by gathering every category's registration list.

    The lists live in `specs/`, one module per category, each spec pinned to the
    authority calculation standard. Gathering them here is what lets this function
    stay the same size while the catalog grows.
    """
    # The category modules are imported here rather than at module scope because each
    # of them needs `IndicatorSpec`, which this module defines. Importing them at the
    # top would ask for the class before this module has finished creating it.
    from .specs import all_specs

    registry = IndicatorRegistry()
    for spec in all_specs():
        registry.register(spec)
    return registry


DEFAULT_REGISTRY = build_default_registry()
