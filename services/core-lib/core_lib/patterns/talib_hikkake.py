"""TA-Lib source ports for the stateful Hikkake ``CDL`` patterns.

``CDLHIKKAKE`` and ``CDLHIKKAKEMOD`` are the only TA-Lib candlestick functions
in this migration that carry a previous pattern forward while looking for a
confirmation. They therefore use a small stateful port instead of the stateless
``TalibPatternPort`` used by the other fifty-nine direct ports.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from core_lib.types import Candle

from .registry import PatternSeries, PatternValue
from .talib_candles import CandleAverageState, CandleSettingType, candle_settings_lookback
from .talib_raw import (
    TalibRawPatternSpec,
    _outputs_from_talib_integer,
    _undetermined_outputs,
    validate_talib_raw_integer_series,
)

_HIKKAKE_LOOKBACK = 5
_HIKKAKEMOD_LOOKBACK = candle_settings_lookback(
    (CandleSettingType.NEAR,),
    minimum=1,
    extra_bars=5,
)
_CONFIRMATION_BARS = 3
_MATCH_MAGNITUDE = 100

HikkakeJudge = Callable[[Sequence[Candle], int, float | None], int]


@dataclass(slots=True)
class TalibHikkakeState:
    """Incrementally replay TA-Lib's Hikkake state machine."""

    name: str
    lookback: int
    transition_start: int
    judge: HikkakeJudge
    uses_near_average: bool = False
    min_history: int = field(init=False)
    _seen: int = field(init=False, default=0, repr=False)
    _candles: list[Candle] = field(init=False, repr=False)
    _near_average: CandleAverageState | None = field(init=False, default=None, repr=False)
    _pattern_idx: int = field(init=False, default=0, repr=False)
    _pattern_result: int = field(init=False, default=0, repr=False)
    _current_integer: int | None = field(init=False, default=None, repr=False)
    _current: PatternValue = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.transition_start < 0:
            raise ValueError("transition_start must not be negative")
        if self.transition_start > self.lookback:
            raise ValueError("transition_start must not be greater than lookback")
        self.min_history = self.lookback + 1
        self._candles = []
        if self.uses_near_average:
            self._near_average = CandleAverageState(CandleSettingType.NEAR, target_offset=2)
        self._current = _undetermined_outputs(self.name)

    @property
    def warmed_up(self) -> bool:
        """Return whether this state has reached TA-Lib's first output index."""
        return self._seen >= self.min_history

    def reset(self) -> None:
        """Clear all carried Hikkake and candle-average state."""
        self._seen = 0
        self._candles.clear()
        if self._near_average is not None:
            self._near_average.reset()
        self._pattern_idx = 0
        self._pattern_result = 0
        self._current_integer = None
        self._current = _undetermined_outputs(self.name)

    def seed(self, candles: Sequence[Candle]) -> None:
        """Reset and replay prior candles, including warm-up state transitions."""
        self.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> PatternValue:
        """Advance by one confirmed candle and return the four-key output."""
        integer = self.update_integer(candle)
        self._current = (
            _undetermined_outputs(self.name)
            if integer is None
            else _outputs_from_talib_integer(self.name, integer)
        )
        return self._current

    def update_integer(self, candle: Candle) -> int | None:
        """Advance by one candle and return the raw integer, or ``None`` during warm-up."""
        index = self._seen
        self._seen += 1
        self._candles.append(candle)
        near_average = self._near_average.update(candle) if self._near_average is not None else None

        integer = 0
        if index >= self.transition_start:
            integer = self._advance(index, near_average)

        self._current_integer = integer if index >= self.lookback else None
        return self._current_integer

    def current(self) -> PatternValue:
        """Return the latest four-key output, NaN-shaped while still warming up."""
        return self._current

    def current_integer(self) -> int | None:
        """Return the latest raw integer, or ``None`` while still warming up."""
        return self._current_integer

    def _advance(self, index: int, near_average: float | None) -> int:
        new_result = self.judge(self._candles, index, near_average)
        if new_result != 0:
            self._pattern_result = new_result
            self._pattern_idx = index
            return self._pattern_result

        current = self._candles[index]
        if index <= self._pattern_idx + _CONFIRMATION_BARS and (
            self._pattern_result > 0
            and current.close > self._candles[self._pattern_idx - 1].high
            or self._pattern_result < 0
            and current.close < self._candles[self._pattern_idx - 1].low
        ):
            self._pattern_idx = 0
            return self._pattern_result + _MATCH_MAGNITUDE * (1 if self._pattern_result > 0 else -1)
        return 0


@dataclass(frozen=True, slots=True)
class TalibStatefulPatternPort(TalibRawPatternSpec):
    """One unregistered TA-Lib raw integer pattern with candle-to-candle state."""

    _state_factory: Callable[[], TalibHikkakeState]

    def make_state(self) -> TalibHikkakeState:
        """Create a fresh incremental state."""
        return self._state_factory()

    def compute_integers(self, candles: Sequence[Candle]) -> list[int]:
        """Return TA-Lib integer outputs aligned to input candle indexes."""
        state = self.make_state()
        values = [state.update_integer(candle) or 0 for candle in candles]
        validate_talib_raw_integer_series(self, values, candle_count=len(candles))
        return values

    def compute_vectorized(self, candles: Sequence[Candle]) -> PatternSeries:
        """Return the repository four-key pattern outputs aligned to candles."""
        integers = self.compute_integers(candles)
        values: list[PatternValue] = []
        for index, integer in enumerate(integers):
            if index < self.lookback:
                values.append(_undetermined_outputs(self.name))
            else:
                values.append(_outputs_from_talib_integer(self.name, integer))
        return values


def _hikkake(candles: Sequence[Candle], index: int, near_average: float | None) -> int:
    del near_average
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    if (
        second.high < first.high
        and second.low > first.low
        and (
            third.high < second.high
            and third.low < second.low
            or third.high > second.high
            and third.low > second.low
        )
    ):
        return _MATCH_MAGNITUDE * (1 if third.high < second.high else -1)
    return 0


def _hikkake_modified(
    candles: Sequence[Candle],
    index: int,
    near_average: float | None,
) -> int:
    if near_average is None:
        raise ValueError("Near average is unavailable for CDLHIKKAKEMOD")

    first = candles[index - 3]
    second = candles[index - 2]
    third = candles[index - 1]
    fourth = candles[index]
    if (
        second.high < first.high
        and second.low > first.low
        and third.high < second.high
        and third.low > second.low
        and (
            fourth.high < third.high
            and fourth.low < third.low
            and second.close <= second.low + near_average
            or fourth.high > third.high
            and fourth.low > third.low
            and second.close >= second.high - near_average
        )
    ):
        return _MATCH_MAGNITUDE * (1 if fourth.high < third.high else -1)
    return 0


TALIB_HIKKAKE_PATTERNS: tuple[TalibStatefulPatternPort, ...] = (
    TalibStatefulPatternPort(
        "pat_hikkake",
        "CDLHIKKAKE",
        _HIKKAKE_LOOKBACK,
        lambda: TalibHikkakeState(
            "pat_hikkake",
            _HIKKAKE_LOOKBACK,
            _HIKKAKE_LOOKBACK - _CONFIRMATION_BARS,
            _hikkake,
        ),
    ),
    TalibStatefulPatternPort(
        "pat_hikkake_modified",
        "CDLHIKKAKEMOD",
        _HIKKAKEMOD_LOOKBACK,
        lambda: TalibHikkakeState(
            "pat_hikkake_modified",
            _HIKKAKEMOD_LOOKBACK,
            _HIKKAKEMOD_LOOKBACK - _CONFIRMATION_BARS,
            _hikkake_modified,
            uses_near_average=True,
        ),
    ),
)

TALIB_HIKKAKE_BY_NAME: Mapping[str, TalibStatefulPatternPort] = {
    pattern.name: pattern for pattern in TALIB_HIKKAKE_PATTERNS
}
TALIB_HIKKAKE_BY_FUNCTION: Mapping[str, TalibStatefulPatternPort] = {
    pattern.talib_function: pattern for pattern in TALIB_HIKKAKE_PATTERNS
}


def compute_talib_hikkake_patterns(candles: Sequence[Candle]) -> dict[str, PatternSeries]:
    """Compute the two stateful TA-Lib Hikkake patterns."""
    return {pattern.name: pattern.compute_vectorized(candles) for pattern in TALIB_HIKKAKE_PATTERNS}


__all__ = [
    "TALIB_HIKKAKE_BY_FUNCTION",
    "TALIB_HIKKAKE_BY_NAME",
    "TALIB_HIKKAKE_PATTERNS",
    "TalibHikkakeState",
    "TalibStatefulPatternPort",
    "compute_talib_hikkake_patterns",
]
