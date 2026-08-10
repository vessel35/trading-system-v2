"""Define the execution contract that indicators and candlestick patterns share.

Two kinds of time series now run through the same executors: the technical
indicators of `core_lib.indicators` and the candlestick patterns of
`core_lib.patterns`. The two carry different calculation identities and must not
share a spec type, but the backtest engine and signal-service read them through
exactly one set of members. That set is what this module states.

The members were not guessed. `docs/candlestick-patterns/analysis-2-corelib-structure.md`
counted every spec attribute the two consumers touch: the backtest engine reads
seven (`identifier`, `name`, `params`, `version`, `min_history`,
`undefined_outputs`, `make_state()`) and signal-service reads five of those same
seven, so their union is the seven below. The state side is smaller: the two
services call `seed()`, `update()`, and read `warmed_up`, and nothing else.

Two members that look like they belong here deliberately do not.
`compute_vectorized()` on the spec and `current()` on the state are called by
core-lib's own tests and by `IndicatorRegistry.compute_batch`, never by either
service. They belong to the verification contract — the batch path exists as an
independent oracle for the incremental path — and putting them here would claim
a consumer requirement that does not exist.

Nothing implements these protocols by inheritance. `IndicatorSpec` already
satisfies `SeriesSpec` as written, which is the point: extracting the protocol
had to leave the indicator layer untouched.
"""

from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from core_lib.types import Candle

SeriesParam = bool | float | int | str
"""A registry parameter value. Scalars only, so an identity renders and compares."""

SeriesValue = float | dict[str, float]
"""One bar's output: a single number, or named outputs for a multi-output series."""


@runtime_checkable
class SeriesState(Protocol):
    """What the two services use from an incremental state, and nothing more."""

    @property
    def warmed_up(self) -> bool:
        """Return whether enough confirmed candles have arrived for a valid value."""
        ...

    def seed(self, candles: Sequence[Candle]) -> None:
        """Reset and repopulate the state from warm-up candles."""
        ...

    def update(self, candle: Candle) -> SeriesValue:
        """Advance by exactly one confirmed candle and return this bar's value."""
        ...


@runtime_checkable
class PairedSeriesState(Protocol):
    """Incremental state for a calculation over matched primary/reference bars."""

    @property
    def warmed_up(self) -> bool:
        """Return whether enough matched confirmed candle pairs have arrived."""
        ...

    def seed(
        self,
        candles: Sequence[Candle],
        reference_candles: Sequence[Candle],
    ) -> None:
        """Reset from equal-length candles already matched by close time."""
        ...

    def update(self, candle: Candle, reference_candle: Candle) -> SeriesValue:
        """Advance by one newly confirmed, close-time-matched candle pair."""
        ...


@runtime_checkable
class SeriesSpec(Protocol):
    """What the two services read from a spec, and nothing more.

    Every member is read-only here. A spec is an immutable calculation identity,
    and declaring the members as properties keeps a frozen dataclass — which is
    what both spec types are — a valid implementation.
    """

    @property
    def identifier(self) -> str:
        """Return the stable name-plus-parameters identity used as a result key."""
        ...

    @property
    def name(self) -> str:
        """Return the registered name without parameters."""
        ...

    @property
    def params(self) -> Mapping[str, SeriesParam]:
        """Return the parameter values this identity pins."""
        ...

    @property
    def version(self) -> str:
        """Return the calculation version recorded in run metadata."""
        ...

    @property
    def min_history(self) -> int:
        """Return the confirmed candles needed before the first valid value."""
        ...

    @property
    def undefined_outputs(self) -> tuple[str, ...]:
        """Return the output keys a standard leaves undefined after warm-up."""
        ...

    @property
    def needs_reference_series(self) -> bool:
        """Return whether this calculation consumes a matched reference series."""
        ...

    def make_state(self) -> SeriesState:
        """Create a fresh single-series state sharing no execution data."""
        ...

    def make_paired_state(self) -> PairedSeriesState:
        """Create a fresh paired-series state sharing no execution data."""
        ...
