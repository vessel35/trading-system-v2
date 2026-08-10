"""Register candlestick pattern identities and their two execution entry points.

Patterns live in their own registry and never enter `DEFAULT_REGISTRY`. The
indicator standard's count of 89 systems is a separate document's tally and this
package does not move it.

`PatternSpec` is a separate type from `IndicatorSpec` on purpose. What the two
share is only what the backtest engine and signal-service actually read — the
seven members of `core_lib.series.SeriesSpec` — so both satisfy that protocol and
the executors merge them into one list without a second code path. What they do
not share is the indicator-only vocabulary: `pinned_impl` and `required_inputs`
stay in the indicator layer, because a pattern pins a different standard and
takes no external input beyond its candles.

TA-Lib specs declare `explicit_min_history` from the source lookback. The legacy
span/trend warm-up derivation was retired with the hand-written pattern rules.

Section numbers in this module are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

import builtins
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from core_lib.indicators.contracts import assert_finalized
from core_lib.series import PairedSeriesState, SeriesParam
from core_lib.types import Candle

from .outputs import assert_pattern_name

PatternValue = dict[str, float]
"""One bar's four §5.1 outputs, keyed by name."""

PatternSeries = Sequence[PatternValue]


@runtime_checkable
class PatternState(Protocol):
    """Structural contract for an incremental pattern implementation.

    Narrower than `core_lib.series.SeriesState` in one way — the value is always
    the four-key dictionary of §5.1, never a bare number — and wider in two:
    `min_history` and `current()` are here because core-lib's own tests use them
    to check warm-up boundaries and the parity of the two execution paths.
    Neither service calls `current()`.
    """

    min_history: int

    @property
    def warmed_up(self) -> bool:
        """Return whether enough confirmed candles have arrived to judge."""
        ...

    def seed(self, candles: Sequence[Candle]) -> None:
        """Reset and repopulate the state from warm-up candles."""
        ...

    def update(self, candle: Candle) -> PatternValue:
        """Advance by exactly one confirmed candle."""
        ...

    def current(self) -> PatternValue:
        """Return the latest four outputs, NaN-shaped while still warming up."""
        ...


@dataclass(frozen=True, slots=True)
class PatternSpec:
    """Immutable pattern identity and its two execution entry points."""

    name: str
    params: Mapping[str, SeriesParam]
    version: str
    """The edition of the pattern standard this identity was written against.

    It plays the same role as an indicator's version — run metadata records it so
    a stored result can be traced to the rules that produced it — but it points
    at `candlestick_pattern_calc_spec.md`, not the indicator standard.
    """

    _vectorized: Callable[[Sequence[Candle]], PatternSeries] = field(
        repr=False,
        compare=False,
    )
    _state_factory: Callable[[], PatternState] = field(repr=False, compare=False)
    explicit_min_history: int
    """Warm-up length declared directly from the source implementation.

    The TA-Lib registration path uses `lookback + 1`.
    """

    needs_reference_series: bool = False
    undefined_outputs: tuple[str, ...] = ()
    """Output keys the standard itself leaves undefined after warm-up.

    Empty for every pattern written so far, and §5.3 is why: once warm-up ends
    each of the four keys carries a finite number, and a degenerate bar reports
    not-matched rather than declining to answer. The field exists because the
    consumption contract has it, not because patterns need it today.
    """

    def __post_init__(self) -> None:
        assert_pattern_name(self.name)
        if not self.version:
            raise ValueError("pattern version must not be empty")
        if self.explicit_min_history <= 0:
            raise ValueError("explicit_min_history must be positive")
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))
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

    @property
    def min_history(self) -> int:
        """Return the first valid output's required candle count."""
        return self.explicit_min_history

    def compute_vectorized(self, candles: Sequence[Candle]) -> PatternSeries:
        """Compute the complete batch series."""
        return self._vectorized(candles)

    def make_state(self) -> PatternState:
        """Create a fresh incremental state with no shared execution data."""
        return self._state_factory()

    def make_paired_state(self) -> PairedSeriesState:
        """Reject a paired path because candlestick patterns consume one series."""
        raise TypeError("candlestick patterns do not accept a reference series")


RegistryKey = tuple[str, tuple[tuple[str, SeriesParam], ...]]


class PatternRegistry:
    """Own registered pattern specs and batch calculation selection.

    It offers the same `resolve_specs` and `specs_from_descriptors` the two
    services already call on the indicator registry, because those two entry
    points are what the executors reach through. Everything else here exists to
    support them or to give the tests a batch oracle.

    One behaviour deliberately differs from `IndicatorRegistry`: an empty
    resolution is allowed. A run with no indicators at all is a mistake, but a
    strategy that asks for no patterns is ordinary, and refusing it would force
    every caller to special-case the common case.
    """

    def __init__(self) -> None:
        self._specs: dict[RegistryKey, PatternSpec] = {}

    @staticmethod
    def _key(name: str, params: Mapping[str, SeriesParam]) -> RegistryKey:
        return name, tuple(sorted(params.items()))

    def get(self, name: str, params: Mapping[str, SeriesParam]) -> PatternSpec:
        """Return the exact registered name-and-parameters spec."""
        try:
            return self._specs[self._key(name, params)]
        except KeyError as error:
            raise KeyError(f"pattern is not registered: {name} {dict(params)}") from error

    def register(self, spec: PatternSpec) -> None:
        """Register one immutable spec, rejecting collisions and warm-up drift."""
        key = self._key(spec.name, spec.params)
        if key in self._specs:
            raise ValueError(f"pattern already registered: {spec.identifier}")
        self._assert_warmup_agrees(spec)
        self._specs[key] = spec

    @staticmethod
    def _assert_warmup_agrees(spec: PatternSpec) -> None:
        """Reject a spec whose state disagrees with it about warm-up length.

        `PatternSpec.min_history` decides how much history a run fetches; the
        incremental state carries its own `min_history` and decides when it
        calls itself warmed up. The two are written in different places, so
        nothing but this check stops them from drifting apart, and a drift
        surfaces later as a first valid bar that is off by exactly the
        difference.

        Registration is the right moment because it is the last point where both
        numbers are visible and no run has fetched history yet. The indicator
        side enforces the same agreement, but only through a test that sweeps the
        registry; asserting here fails at construction instead of waiting for a
        suite to be run.
        """
        state_min_history = spec.make_state().min_history
        if state_min_history != spec.min_history:
            raise ValueError(
                f"{spec.identifier} declares min_history={spec.min_history} "
                f"but its state declares {state_min_history}"
            )

    def list(self) -> builtins.list[PatternSpec]:
        """Return all specs in deterministic identifier order."""
        return sorted(self._specs.values(), key=lambda spec: spec.identifier)

    def names(self) -> set[str]:
        """Return every registered pattern name.

        Decision G forbids a pattern and an indicator sharing a name, and the
        check that enforces it needs both name sets.
        """
        return {spec.name for spec in self._specs.values()}

    def _matching_specs(self, requested: str) -> builtins.list[PatternSpec]:
        matches = [
            spec
            for spec in self._specs.values()
            if spec.name == requested or spec.identifier == requested
        ]
        if not matches:
            raise KeyError(f"pattern is not registered: {requested}")
        return matches

    def _descriptor_spec(self, descriptor: Mapping[str, object]) -> PatternSpec:
        """Resolve one external name-and-parameters descriptor to its registry spec."""
        if set(descriptor) != {"name", "params"}:
            raise ValueError("pattern descriptor must contain exactly name and params")
        name = descriptor["name"]
        params = descriptor["params"]
        if not isinstance(name, str) or not isinstance(params, Mapping):
            raise TypeError("pattern descriptor name/params have invalid types")
        normalized_params = dict(params)
        if any(
            not isinstance(key, str) or not isinstance(value, bool | float | int | str)
            for key, value in normalized_params.items()
        ):
            raise TypeError("pattern params must use scalar registry values")
        matches = [
            spec
            for spec in self._specs.values()
            if spec.name.casefold() == name.casefold() and dict(spec.params) == normalized_params
        ]
        if len(matches) != 1:
            raise KeyError(f"pattern is not registered: {name} {normalized_params}")
        return matches[0]

    def specs_for(self, enabled_set: Collection[str]) -> builtins.list[PatternSpec]:
        """Return the deterministic, de-duplicated specs named by an enabled set."""
        selected: dict[str, PatternSpec] = {}
        for requested in enabled_set:
            for spec in self._matching_specs(requested):
                selected[spec.identifier] = spec
        return [selected[identifier] for identifier in sorted(selected)]

    def specs_from_descriptors(
        self,
        descriptors: Collection[Mapping[str, object]],
    ) -> builtins.list[PatternSpec]:
        """Resolve descriptors to deterministic, de-duplicated registry specs."""
        selected: dict[str, PatternSpec] = {}
        for descriptor in descriptors:
            spec = self._descriptor_spec(descriptor)
            selected[spec.identifier] = spec
        return [selected[identifier] for identifier in sorted(selected)]

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
            raise ValueError("pattern mode must be auto, explicit, or all")
        for requested in resolved:
            self._matching_specs(requested)
        return resolved

    def resolve_specs(
        self,
        mode: str,
        declared: Collection[Mapping[str, object]],
        explicit: Collection[Mapping[str, object]],
    ) -> builtins.list[PatternSpec]:
        """Resolve external descriptors and calculation mode through one registry path."""
        declared_ids = {spec.identifier for spec in self.specs_from_descriptors(declared)}
        explicit_ids = {spec.identifier for spec in self.specs_from_descriptors(explicit)}
        return self.specs_for(self.resolve_enabled(mode, declared_ids, explicit_ids))

    def compute_batch(
        self,
        candles: Sequence[Candle],
        enabled_set: set[str],
        *,
        decision_time: datetime | None = None,
    ) -> dict[str, PatternSeries]:
        """Compute a batch series after finalized-candle and history validation.

        The executors run patterns through incremental state so their look-ahead
        boundary stays structural. This path exists as the independent oracle
        those states are checked against.
        """
        effective_decision_time = decision_time
        if effective_decision_time is None and candles:
            effective_decision_time = candles[-1].close_time
        if effective_decision_time is not None:
            for candle in candles:
                assert_finalized(candle, effective_decision_time)

        result: dict[str, PatternSeries] = {}
        for spec in self.specs_for(enabled_set):
            if len(candles) < spec.min_history:
                raise ValueError(
                    f"{spec.identifier} requires {spec.min_history} candles, got {len(candles)}"
                )
            result[spec.identifier] = spec.compute_vectorized(candles)
        return result
