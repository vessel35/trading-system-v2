"""Implement §3 of the candlestick pattern standard: the prior trend.

Forty-five of the sixty-one patterns require a prior trend and the pattern judges
it itself rather than asking a strategy for it. §3 fixes how: a ten-period
exponential average of the high-low midpoint, compared against the midpoint of
the pattern's *first* bar.

Two details in that sentence do the damage when missed. The average smooths the
midpoint, not the close. And the comparison happens on the first bar of the
pattern, which for a `k`-bar pattern is `k - 1` bars behind the bar being judged
— so a state holding only the current average cannot make the comparison at all.
That is why `PriorTrendState` keeps a short queue.

Section numbers in this module are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isnan

from core_lib.indicators.primitives import NAN, EmaState
from core_lib.indicators.primitives import ema as ema_primitive
from core_lib.types import Candle

from .primitives import range_mid

TREND_EMA_PERIOD = 10
"""§3.1, from Morris: "the exponential period of 10 days seemed to work as well as any"."""

UPTREND = 1.0
DOWNTREND = -1.0
NO_TREND = 0.0
"""§3.1: a first-day midpoint exactly on the average is neither up nor down.

Attaching the equality to one side would widen that direction with no source
behind it, so the standard drops it from both. A pattern requiring a trend does
not hold on such a bar.
"""


def trend_ema(candles: Sequence[Candle]) -> list[float]:
    """Return ``EMA(RangeMid, 10)`` over the whole series (§3.1, §3.2).

    This calls the indicator standard's own EMA, seeded with the simple average
    of the first ten values, so indexes 0 through 8 are NaN and index 9 carries
    the first value. §3.2 adopts that seeding rule rather than restating one.
    """
    return ema_primitive([range_mid(candle) for candle in candles], TREND_EMA_PERIOD)


def prior_trend(candles: Sequence[Candle], bar_count: int) -> list[float]:
    """Return the trend direction judged at each index for a ``bar_count``-bar pattern.

    The value at index `i` reads bar `f = i - (bar_count - 1)`, the pattern's
    first day, and answers `UPTREND`, `DOWNTREND`, `NO_TREND`, or NaN while the
    average at `f` does not exist yet. It is the batch counterpart of
    `PriorTrendState` and exists so the two paths can be checked against each
    other.
    """
    if bar_count <= 0:
        raise ValueError("bar_count must be positive")
    averages = trend_ema(candles)
    midpoints = [range_mid(candle) for candle in candles]
    result: list[float] = []
    for index in range(len(candles)):
        first_day = index - (bar_count - 1)
        if first_day < 0 or isnan(averages[first_day]):
            result.append(NAN)
            continue
        result.append(_direction(midpoints[first_day], averages[first_day]))
    return result


def _direction(midpoint: float, average: float) -> float:
    if midpoint > average:
        return UPTREND
    if midpoint < average:
        return DOWNTREND
    return NO_TREND


@dataclass(slots=True)
class PriorTrendState:
    """Judge the prior trend incrementally for a pattern spanning ``bar_count`` bars.

    The queue is what §3.3 asks for. The average is advanced once per confirmed
    candle and its value pushed onto a `deque` of length `bar_count`; the oldest
    entry is then the pattern's first day. Both the queue and the work per candle
    are bounded by `bar_count`, which a pattern's definition fixes and no
    registered parameter can grow.

    Nothing here is fed an unconfirmed bar: `update` advances a recursive average
    and the repository rule is that only closed candles reach it.
    """

    bar_count: int
    min_history: int = field(init=False)
    _average: EmaState = field(init=False, repr=False)
    _history: deque[tuple[float, float]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.bar_count <= 0:
            raise ValueError("bar_count must be positive")
        # §6's trend formula, restated: the first day needs a valid average, and
        # the first day sits `bar_count - 1` bars behind the judged bar.
        self.min_history = TREND_EMA_PERIOD + self.bar_count - 1
        self._average = EmaState(TREND_EMA_PERIOD)
        self._history = deque(maxlen=self.bar_count)

    def reset(self) -> None:
        """Drop the average and the first-day queue."""
        self._average.reset()
        self._history.clear()

    @property
    def warmed_up(self) -> bool:
        """Return whether the pattern's first day already carries an average."""
        return len(self._history) == self.bar_count and not isnan(self._history[0][1])

    def seed(self, candles: Sequence[Candle]) -> None:
        """Reset and replay warm-up candles one at a time."""
        self.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        """Advance one confirmed candle and return the trend direction it judges."""
        midpoint = range_mid(candle)
        self._history.append((midpoint, self._average.update(midpoint)))
        return self.current()

    def current(self) -> float:
        """Return the current trend direction, or NaN before warm-up ends."""
        if not self.warmed_up:
            return NAN
        midpoint, average = self._history[0]
        return _direction(midpoint, average)

    def first_day_average(self) -> float:
        """Return the average on the pattern's first day, or NaN before warm-up ends."""
        if not self.warmed_up:
            return NAN
        return self._history[0][1]

    def uptrend(self) -> bool:
        """Return whether the pattern's first day sits above its average."""
        return self.current() == UPTREND

    def downtrend(self) -> bool:
        """Return whether the pattern's first day sits below its average."""
        return self.current() == DOWNTREND
