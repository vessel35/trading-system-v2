"""Define standalone indicator systems and the follow-up systems catalog.

Two conventions are decided here rather than per indicator, because the indicators
in this module are the ones that need them and a second answer to either question
would make two of them disagree about what an index means.

**Which candle carries which value.** Several sections of the standard describe an
indicator by where it is drawn on a chart rather than by when it can be computed.
§6.1 shifts the three Alligator averages forward, §9.2 shifts the Ichimoku Senkou
spans forward and the Chikou span backward, and §6.2 marks a fractal on a candle
that only two later candles can confirm. A returned series here is indexed by the
chart position, and a value is published at index ``t`` only when candles up to and
including ``t`` determine it; where the chart position comes before the determining
candle, publication waits exactly as long as it must. Concretely the Senkou span at
index ``t`` is the midpoint computed at ``t - displacement``, which §9.2's own note
calls the past value that the current bar's cloud shows; the Alligator lines at
index ``t`` are the smoothed medians computed at ``t - shift``; and the fractal flags
at index ``t`` describe the candle at ``t - 2``, which is the most recent candle the
five-bar pattern can have settled. Nothing at index ``t`` reads a candle after ``t``.

The Chikou span is the one output this convention cannot publish. Its chart position
``t`` holds the close of ``t + displacement``, so it is unknown at ``t``; delaying it
by the same displacement leaves the close of ``t`` itself at index ``t``, which is
the candle's own close and carries nothing the caller does not already have. So the
Ichimoku value here has four keys rather than five, and a caller comparing the close
against the price ``displacement`` candles back reads the candles directly.

**How a state that is not a number is encoded.** §6.2, §9.4, §9.5, and §9.6 classify
rather than measure, and the registry carries floats. Each classification is mapped
onto the states its own section names and onto no others. Where a section names two
independent patterns (§6.2's up and down fractals, which one candle can satisfy at
once), each becomes its own key holding ``1.0`` or ``0.0``. Where a section names a
directional scale (§9.4's three colours, §9.5's two setup directions, §9.6's zones
either side of zero), the sign follows the price direction the section describes and
not the trade it suggests: §9.4's green rising impulse is positive and §9.5's buy
setup, which the section defines as nine consecutive falling closes, is negative.
"""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isnan

from core_lib.types import Candle

from .momentum import CCIState, MACDState, cci, macd
from .primitives import (
    NAN,
    EmaState,
    RmaState,
    RollingExtremeState,
    Series,
    ema,
    hh,
    hl2,
    ll,
    rma,
    safe_divide,
)

ElderRayValue = dict[str, float]
IchimokuValue = dict[str, float]
AlligatorValue = dict[str, float]
GatorValue = dict[str, float]
FractalValue = dict[str, float]
WoodiesValue = dict[str, float]

FOLLOW_UP_INDICATORS: tuple[str, ...] = ()


def elder_ray(candles: Sequence[Candle], period: int = 13) -> list[ElderRayValue]:
    """Measure how far each extreme sits from a smoothed close (§9.3)."""
    if period <= 0:
        raise ValueError("period must be positive")
    averages = ema([candle.close for candle in candles], period)
    return [
        {
            "bull_power": NAN if isnan(average) else candle.high - average,
            "bear_power": NAN if isnan(average) else candle.low - average,
        }
        for candle, average in zip(candles, averages, strict=True)
    ]


@dataclass(slots=True)
class ElderRayState:
    """O(1)-per-candle Elder Ray state over one smoothed close."""

    period: int = 13
    min_history: int = field(init=False)
    _average: EmaState = field(init=False)
    _value: ElderRayValue = field(
        init=False,
        default_factory=lambda: {"bull_power": NAN, "bear_power": NAN},
    )

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period
        self._average = EmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return self._average.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._average.reset()
        self._value = {"bull_power": NAN, "bear_power": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> ElderRayValue:
        average = self._average.update(candle.close)
        self._value = {
            "bull_power": NAN if isnan(average) else candle.high - average,
            "bear_power": NAN if isnan(average) else candle.low - average,
        }
        return self.current()

    def current(self) -> ElderRayValue:
        return dict(self._value)


@dataclass(slots=True)
class _SarTracker:
    """Carry the stop-and-reverse state between candles (§9.1).

    Wilder's rule set is sequential by nature: the stop moves toward the extreme
    point, accelerates when a new extreme appears, is held off the last two bars'
    range, and flips when price crosses it. Both execution paths drive this same
    object so the vectorized series cannot drift from the incremental one.
    """

    step: float
    maximum: float
    _rising: bool = field(init=False, default=True)
    _stop: float = field(init=False, default=NAN)
    _extreme: float = field(init=False, default=NAN)
    _acceleration: float = field(init=False, default=0.0)
    _previous: Candle | None = field(init=False, default=None)
    _before_previous: Candle | None = field(init=False, default=None)

    def reset(self) -> None:
        """Return to the pre-first-candle state."""
        self._rising = True
        self._stop = NAN
        self._extreme = NAN
        self._acceleration = self.step
        self._previous = None
        self._before_previous = None

    def update(self, candle: Candle) -> float:
        """Advance one candle and return the stop for it, or NaN on the first."""
        if self._previous is None:
            self._previous = candle
            self._acceleration = self.step
            return NAN

        if isnan(self._stop):
            # Wilder starts from an assumed direction; taking it from the first
            # transition avoids inventing one.
            self._rising = candle.close >= self._previous.close
            self._stop = self._previous.low if self._rising else self._previous.high
            self._extreme = self._previous.high if self._rising else self._previous.low
            self._acceleration = self.step

        stop = self._stop + self._acceleration * (self._extreme - self._stop)
        recent = [self._previous]
        if self._before_previous is not None:
            recent.append(self._before_previous)
        if self._rising:
            stop = min(stop, *(bar.low for bar in recent))
        else:
            stop = max(stop, *(bar.high for bar in recent))

        reversed_now = candle.low < stop if self._rising else candle.high > stop
        if reversed_now:
            stop = self._extreme
            self._rising = not self._rising
            self._extreme = candle.high if self._rising else candle.low
            self._acceleration = self.step
        elif (self._rising and candle.high > self._extreme) or (
            not self._rising and candle.low < self._extreme
        ):
            self._extreme = candle.high if self._rising else candle.low
            self._acceleration = min(self._acceleration + self.step, self.maximum)

        self._stop = stop
        self._before_previous = self._previous
        self._previous = candle
        return stop


def parabolic_sar(
    candles: Sequence[Candle],
    step: float = 0.02,
    maximum: float = 0.2,
) -> list[float]:
    """Compute Wilder's stop and reverse (§9.1)."""
    if step <= 0.0 or maximum <= 0.0:
        raise ValueError("step and maximum must be positive")
    if step > maximum:
        raise ValueError("step must not exceed maximum")
    tracker = _SarTracker(step=step, maximum=maximum)
    tracker.reset()
    return [tracker.update(candle) for candle in candles]


@dataclass(slots=True)
class ParabolicSARState:
    """O(1)-per-candle Parabolic SAR state."""

    step: float = 0.02
    maximum: float = 0.2
    min_history: int = field(init=False, default=2)
    _tracker: _SarTracker = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if self.step <= 0.0 or self.maximum <= 0.0:
            raise ValueError("step and maximum must be positive")
        if self.step > self.maximum:
            raise ValueError("step must not exceed maximum")
        self._tracker = _SarTracker(step=self.step, maximum=self.maximum)
        self._tracker.reset()

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._tracker.reset()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        self._value = self._tracker.update(candle)
        return self._value

    def current(self) -> float:
        return self._value


def _halfway(first: float, second: float) -> float:
    """Return the point midway between two values, NaN where either is."""
    if isnan(first) or isnan(second):
        return NAN
    return (first + second) / 2.0


def _midpoint(first: Sequence[float], second: Sequence[float]) -> Series:
    """Return the midway series of two aligned series."""
    return [_halfway(left, right) for left, right in zip(first, second, strict=True)]


def _publish_after(values: Sequence[float], delay: int) -> Series:
    """Return the same values republished ``delay`` candles later.

    The result keeps the input's length, so the candles before the first published
    value carry NaN exactly as a warm-up does. This is the batch counterpart of
    ``_DelayLine`` and the two must stay identical value for value.
    """

    if delay < 0:
        raise ValueError("delay must not be negative")
    if delay == 0:
        return list(values)
    return ([NAN] * delay + list(values))[: len(values)]


@dataclass(slots=True)
class _DelayLine:
    """Hold each value until the candle that is allowed to publish it."""

    delay: int
    _queue: deque[float] = field(init=False)

    def __post_init__(self) -> None:
        if self.delay < 0:
            raise ValueError("delay must not be negative")
        self._queue = deque(maxlen=self.delay + 1)

    def reset(self) -> None:
        """Drop every held value."""
        self._queue.clear()

    def update(self, value: float) -> float:
        """Accept one value and return the one this candle may publish."""
        self._queue.append(value)
        return self.current()

    def current(self) -> float:
        """Return the held value that has come due, or NaN while none has."""
        if len(self._queue) <= self.delay:
            return NAN
        return self._queue[0]


_EMPTY_ICHIMOKU: IchimokuValue = {
    "tenkan": NAN,
    "kijun": NAN,
    "senkou_a": NAN,
    "senkou_b": NAN,
}


def _validate_ichimoku(
    conversion_period: int,
    base_period: int,
    span_b_period: int,
    displacement: int,
) -> None:
    if min(conversion_period, base_period, span_b_period) <= 0:
        raise ValueError("periods must be positive")
    if displacement < 0:
        raise ValueError("displacement must not be negative")


def ichimoku_min_history(
    conversion_period: int = 9,
    base_period: int = 26,
    span_b_period: int = 52,
    displacement: int = 26,
) -> int:
    """Return the candles needed before all four published lines exist."""
    _validate_ichimoku(conversion_period, base_period, span_b_period, displacement)
    return max(
        conversion_period,
        base_period,
        base_period + displacement,
        span_b_period + displacement,
    )


def ichimoku(
    candles: Sequence[Candle],
    conversion_period: int = 9,
    base_period: int = 26,
    span_b_period: int = 52,
    displacement: int = 26,
) -> list[IchimokuValue]:
    """Compute the four publishable Ichimoku lines (§9.2).

    The Chikou span is absent for the reason this module's docstring states: the
    convention cannot publish it without either reading a future close or repeating
    the candle's own close.
    """

    _validate_ichimoku(conversion_period, base_period, span_b_period, displacement)
    highs = [candle.high for candle in candles]
    lows = [candle.low for candle in candles]
    conversion = _midpoint(hh(highs, conversion_period), ll(lows, conversion_period))
    base = _midpoint(hh(highs, base_period), ll(lows, base_period))
    leading_a = _publish_after(_midpoint(conversion, base), displacement)
    leading_b = _publish_after(
        _midpoint(hh(highs, span_b_period), ll(lows, span_b_period)),
        displacement,
    )
    return [
        {"tenkan": tenkan, "kijun": kijun, "senkou_a": span_a, "senkou_b": span_b}
        for tenkan, kijun, span_a, span_b in zip(
            conversion, base, leading_a, leading_b, strict=True
        )
    ]


@dataclass(slots=True)
class IchimokuState:
    """O(1)-per-candle Ichimoku state over three high/low windows and two delays."""

    conversion_period: int = 9
    base_period: int = 26
    span_b_period: int = 52
    displacement: int = 26
    min_history: int = field(init=False)
    _conversion_high: RollingExtremeState = field(init=False)
    _conversion_low: RollingExtremeState = field(init=False)
    _base_high: RollingExtremeState = field(init=False)
    _base_low: RollingExtremeState = field(init=False)
    _span_high: RollingExtremeState = field(init=False)
    _span_low: RollingExtremeState = field(init=False)
    _leading_a: _DelayLine = field(init=False)
    _leading_b: _DelayLine = field(init=False)
    _value: IchimokuValue = field(init=False, default_factory=lambda: dict(_EMPTY_ICHIMOKU))

    def __post_init__(self) -> None:
        _validate_ichimoku(
            self.conversion_period,
            self.base_period,
            self.span_b_period,
            self.displacement,
        )
        self.min_history = ichimoku_min_history(
            self.conversion_period,
            self.base_period,
            self.span_b_period,
            self.displacement,
        )
        self._conversion_high = RollingExtremeState(self.conversion_period, highest=True)
        self._conversion_low = RollingExtremeState(self.conversion_period, highest=False)
        self._base_high = RollingExtremeState(self.base_period, highest=True)
        self._base_low = RollingExtremeState(self.base_period, highest=False)
        self._span_high = RollingExtremeState(self.span_b_period, highest=True)
        self._span_low = RollingExtremeState(self.span_b_period, highest=False)
        self._leading_a = _DelayLine(self.displacement)
        self._leading_b = _DelayLine(self.displacement)

    @property
    def warmed_up(self) -> bool:
        return not any(isnan(value) for value in self._value.values())

    def seed(self, candles: Sequence[Candle]) -> None:
        for window in (
            self._conversion_high,
            self._conversion_low,
            self._base_high,
            self._base_low,
            self._span_high,
            self._span_low,
        ):
            window.reset()
        self._leading_a.reset()
        self._leading_b.reset()
        self._value = dict(_EMPTY_ICHIMOKU)
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> IchimokuValue:
        conversion = _halfway(
            self._conversion_high.update(candle.high),
            self._conversion_low.update(candle.low),
        )
        base = _halfway(
            self._base_high.update(candle.high),
            self._base_low.update(candle.low),
        )
        span_source = _halfway(
            self._span_high.update(candle.high),
            self._span_low.update(candle.low),
        )
        self._value = {
            "tenkan": conversion,
            "kijun": base,
            "senkou_a": self._leading_a.update(_halfway(conversion, base)),
            "senkou_b": self._leading_b.update(span_source),
        }
        return self.current()

    def current(self) -> IchimokuValue:
        return dict(self._value)


_EMPTY_ALLIGATOR: AlligatorValue = {"jaw": NAN, "teeth": NAN, "lips": NAN}


def _validate_alligator(
    jaw_period: int,
    jaw_shift: int,
    teeth_period: int,
    teeth_shift: int,
    lips_period: int,
    lips_shift: int,
) -> None:
    if min(jaw_period, teeth_period, lips_period) <= 0:
        raise ValueError("periods must be positive")
    if min(jaw_shift, teeth_shift, lips_shift) < 0:
        raise ValueError("shifts must not be negative")


def alligator_min_history(
    jaw_period: int = 13,
    jaw_shift: int = 8,
    teeth_period: int = 8,
    teeth_shift: int = 5,
    lips_period: int = 5,
    lips_shift: int = 3,
) -> int:
    """Return the candles needed before all three published lines exist."""
    _validate_alligator(jaw_period, jaw_shift, teeth_period, teeth_shift, lips_period, lips_shift)
    return max(jaw_period + jaw_shift, teeth_period + teeth_shift, lips_period + lips_shift)


def alligator(
    candles: Sequence[Candle],
    jaw_period: int = 13,
    jaw_shift: int = 8,
    teeth_period: int = 8,
    teeth_shift: int = 5,
    lips_period: int = 5,
    lips_shift: int = 3,
) -> list[AlligatorValue]:
    """Compute the three Wilder-smoothed median lines of §6.1.

    §6.1 writes the smoothing as SMMA, which §0.5 states is the same recursion as
    Wilder's RMA, so the shared primitive computes all three and no smoothing is
    written again here.
    """

    _validate_alligator(jaw_period, jaw_shift, teeth_period, teeth_shift, lips_period, lips_shift)
    median = hl2(candles)
    jaw = _publish_after(rma(median, jaw_period), jaw_shift)
    teeth = _publish_after(rma(median, teeth_period), teeth_shift)
    lips = _publish_after(rma(median, lips_period), lips_shift)
    return [
        {"jaw": jaw_value, "teeth": teeth_value, "lips": lips_value}
        for jaw_value, teeth_value, lips_value in zip(jaw, teeth, lips, strict=True)
    ]


@dataclass(slots=True)
class AlligatorState:
    """O(1)-per-candle Alligator state over three smoothings and three delays."""

    jaw_period: int = 13
    jaw_shift: int = 8
    teeth_period: int = 8
    teeth_shift: int = 5
    lips_period: int = 5
    lips_shift: int = 3
    min_history: int = field(init=False)
    _jaw: RmaState = field(init=False)
    _teeth: RmaState = field(init=False)
    _lips: RmaState = field(init=False)
    _jaw_delay: _DelayLine = field(init=False)
    _teeth_delay: _DelayLine = field(init=False)
    _lips_delay: _DelayLine = field(init=False)
    _value: AlligatorValue = field(init=False, default_factory=lambda: dict(_EMPTY_ALLIGATOR))

    def __post_init__(self) -> None:
        _validate_alligator(
            self.jaw_period,
            self.jaw_shift,
            self.teeth_period,
            self.teeth_shift,
            self.lips_period,
            self.lips_shift,
        )
        self.min_history = alligator_min_history(
            self.jaw_period,
            self.jaw_shift,
            self.teeth_period,
            self.teeth_shift,
            self.lips_period,
            self.lips_shift,
        )
        self._jaw = RmaState(self.jaw_period)
        self._teeth = RmaState(self.teeth_period)
        self._lips = RmaState(self.lips_period)
        self._jaw_delay = _DelayLine(self.jaw_shift)
        self._teeth_delay = _DelayLine(self.teeth_shift)
        self._lips_delay = _DelayLine(self.lips_shift)

    @property
    def warmed_up(self) -> bool:
        return not any(isnan(value) for value in self._value.values())

    def seed(self, candles: Sequence[Candle]) -> None:
        for smoothing in (self._jaw, self._teeth, self._lips):
            smoothing.reset()
        for line in (self._jaw_delay, self._teeth_delay, self._lips_delay):
            line.reset()
        self._value = dict(_EMPTY_ALLIGATOR)
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> AlligatorValue:
        median = (candle.high + candle.low) / 2.0
        self._value = {
            "jaw": self._jaw_delay.update(self._jaw.update(median)),
            "teeth": self._teeth_delay.update(self._teeth.update(median)),
            "lips": self._lips_delay.update(self._lips.update(median)),
        }
        return self.current()

    def current(self) -> AlligatorValue:
        return dict(self._value)


_EMPTY_GATOR: GatorValue = {"upper": NAN, "lower": NAN}


def _gator_from(lines: AlligatorValue) -> GatorValue:
    """Turn one set of Alligator lines into §6.3's two histogram bars."""
    jaw = lines["jaw"]
    teeth = lines["teeth"]
    lips = lines["lips"]
    return {
        "upper": NAN if isnan(jaw) or isnan(teeth) else abs(jaw - teeth),
        "lower": NAN if isnan(teeth) or isnan(lips) else -abs(teeth - lips),
    }


def gator_oscillator(
    candles: Sequence[Candle],
    jaw_period: int = 13,
    jaw_shift: int = 8,
    teeth_period: int = 8,
    teeth_shift: int = 5,
    lips_period: int = 5,
    lips_shift: int = 3,
) -> list[GatorValue]:
    """Compute §6.3's histogram from the §6.1 lines this module already builds."""
    return [
        _gator_from(lines)
        for lines in alligator(
            candles,
            jaw_period=jaw_period,
            jaw_shift=jaw_shift,
            teeth_period=teeth_period,
            teeth_shift=teeth_shift,
            lips_period=lips_period,
            lips_shift=lips_shift,
        )
    ]


@dataclass(slots=True)
class GatorOscillatorState:
    """O(1)-per-candle Gator state driven by one Alligator state."""

    jaw_period: int = 13
    jaw_shift: int = 8
    teeth_period: int = 8
    teeth_shift: int = 5
    lips_period: int = 5
    lips_shift: int = 3
    min_history: int = field(init=False)
    _lines: AlligatorState = field(init=False)
    _value: GatorValue = field(init=False, default_factory=lambda: dict(_EMPTY_GATOR))

    def __post_init__(self) -> None:
        self._lines = AlligatorState(
            jaw_period=self.jaw_period,
            jaw_shift=self.jaw_shift,
            teeth_period=self.teeth_period,
            teeth_shift=self.teeth_shift,
            lips_period=self.lips_period,
            lips_shift=self.lips_shift,
        )
        self.min_history = self._lines.min_history

    @property
    def warmed_up(self) -> bool:
        return not any(isnan(value) for value in self._value.values())

    def seed(self, candles: Sequence[Candle]) -> None:
        self._lines.seed(())
        self._value = dict(_EMPTY_GATOR)
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> GatorValue:
        self._value = _gator_from(self._lines.update(candle))
        return self.current()

    def current(self) -> GatorValue:
        return dict(self._value)


_EMPTY_FRACTAL: FractalValue = {"up": NAN, "down": NAN}


def _fractal_wing(period: int) -> int:
    """Return how many candles sit each side of the pattern's centre."""
    if period < 3 or period % 2 == 0:
        raise ValueError("period must be an odd count of at least three candles")
    return period // 2


def _fractal_flags(window: Sequence[Candle], wing: int) -> FractalValue:
    """Apply §6.2's two patterns to one complete window."""
    centre = window[wing]
    neighbours = [*window[:wing], *window[wing + 1 :]]
    return {
        "up": 1.0 if all(centre.high > other.high for other in neighbours) else 0.0,
        "down": 1.0 if all(centre.low < other.low for other in neighbours) else 0.0,
    }


def fractals(candles: Sequence[Candle], period: int = 5) -> list[FractalValue]:
    """Report whether the candle ``period // 2`` bars back was a fractal (§6.2).

    §6.2 marks the pattern on the middle candle, which the two candles after it
    settle. The flags at index ``t`` therefore describe the candle at ``t - 2``,
    which is what §6.2 calls a delayed signal rather than a look-ahead.
    """

    wing = _fractal_wing(period)
    result: list[FractalValue] = []
    for index in range(len(candles)):
        if index + 1 < period:
            result.append(dict(_EMPTY_FRACTAL))
            continue
        result.append(_fractal_flags(candles[index - period + 1 : index + 1], wing))
    return result


@dataclass(slots=True)
class FractalsState:
    """O(period)-per-candle fractal state; the pattern needs the whole window."""

    period: int = 5
    min_history: int = field(init=False)
    _wing: int = field(init=False)
    _window: deque[Candle] = field(init=False, default_factory=deque)
    _value: FractalValue = field(init=False, default_factory=lambda: dict(_EMPTY_FRACTAL))

    def __post_init__(self) -> None:
        self._wing = _fractal_wing(self.period)
        self.min_history = self.period
        self._window = deque(maxlen=self.period)

    @property
    def warmed_up(self) -> bool:
        return not any(isnan(value) for value in self._value.values())

    def seed(self, candles: Sequence[Candle]) -> None:
        self._window.clear()
        self._value = dict(_EMPTY_FRACTAL)
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> FractalValue:
        self._window.append(candle)
        if len(self._window) < self.period:
            self._value = dict(_EMPTY_FRACTAL)
        else:
            self._value = _fractal_flags(list(self._window), self._wing)
        return self.current()

    def current(self) -> FractalValue:
        return dict(self._value)


def _facilitation(candle: Candle) -> float:
    """Divide one candle's range by its volume (§6.4).

    §6.4 is the whole formula and names no substitute for a zero denominator.
    §0.11 lists zero among the answers implementations give, and a candle that
    traded nothing has no range its volume could have made, so this repository
    reads it as zero — the same reading §2.10's CCI already takes here for a
    window with no deviation to scale by.
    """

    return safe_divide(candle.high - candle.low, candle.volume, on_zero=0.0)


def market_facilitation_index(candles: Sequence[Candle]) -> list[float]:
    """Compute Bill Williams' range-per-volume measure (§6.4)."""
    return [_facilitation(candle) for candle in candles]


@dataclass(slots=True)
class MarketFacilitationIndexState:
    """O(1)-per-candle state; §6.4 reads one candle and keeps nothing."""

    min_history: int = field(init=False, default=1)
    _value: float = field(init=False, default=NAN)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        self._value = _facilitation(candle)
        return self._value

    def current(self) -> float:
        return self._value


IMPULSE_BULLISH = 1.0
IMPULSE_BEARISH = -1.0
IMPULSE_NEUTRAL = 0.0


def _impulse(
    average: float,
    previous_average: float,
    histogram: float,
    previous_histogram: float,
) -> float:
    """Map §9.4's three colours onto a rising/neutral/falling scale."""
    if isnan(average) or isnan(previous_average):
        return NAN
    if isnan(histogram) or isnan(previous_histogram):
        return NAN
    if average > previous_average and histogram > previous_histogram:
        return IMPULSE_BULLISH
    if average < previous_average and histogram < previous_histogram:
        return IMPULSE_BEARISH
    return IMPULSE_NEUTRAL


def elder_impulse_min_history(
    ema_period: int = 13,
    slow_period: int = 26,
    signal_period: int = 9,
) -> int:
    """Return the candles needed before both parts have a previous value."""
    if min(ema_period, slow_period, signal_period) <= 0:
        raise ValueError("periods must be positive")
    return max(ema_period + 1, slow_period + signal_period)


def elder_impulse(
    candles: Sequence[Candle],
    ema_period: int = 13,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> list[float]:
    """Combine the slope of §0.3's EMA with the slope of §2.4's histogram (§9.4).

    Both parts are the registered indicators' own output rather than a second
    calculation: the average comes from the shared EMA primitive and the histogram
    from the MACD this repository already implements for §2.4.
    """

    if ema_period <= 0:
        raise ValueError("period must be positive")
    averages = ema([candle.close for candle in candles], ema_period)
    histogram = [
        value["histogram"] for value in macd(candles, fast_period, slow_period, signal_period)
    ]
    result: Series = [NAN] * min(1, len(candles))
    for index in range(1, len(candles)):
        result.append(
            _impulse(
                averages[index],
                averages[index - 1],
                histogram[index],
                histogram[index - 1],
            )
        )
    return result


@dataclass(slots=True)
class ElderImpulseState:
    """O(1)-per-candle state over one EMA and one MACD histogram."""

    ema_period: int = 13
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    min_history: int = field(init=False)
    _average: EmaState = field(init=False)
    _macd: MACDState = field(init=False)
    _previous_average: float = field(init=False, default=NAN)
    _previous_histogram: float = field(init=False, default=NAN)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if self.ema_period <= 0:
            raise ValueError("period must be positive")
        self.min_history = elder_impulse_min_history(
            self.ema_period,
            self.slow_period,
            self.signal_period,
        )
        self._average = EmaState(self.ema_period)
        self._macd = MACDState(
            fast_period=self.fast_period,
            slow_period=self.slow_period,
            signal_period=self.signal_period,
        )

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._average.reset()
        self._macd.seed(())
        self._previous_average = NAN
        self._previous_histogram = NAN
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        average = self._average.update(candle.close)
        histogram = self._macd.update(candle)["histogram"]
        self._value = _impulse(
            average,
            self._previous_average,
            histogram,
            self._previous_histogram,
        )
        self._previous_average = average
        self._previous_histogram = histogram
        return self._value

    def current(self) -> float:
        return self._value


def _extend_setup(count: float, close: float, earlier: float) -> float:
    """Advance §9.5's consecutive setup count by one candle.

    §9.5 defines a buy setup as consecutive closes below the close ``lookback``
    candles earlier and a sell setup as consecutive closes above it, so the sign
    follows that price direction. A candle that breaks the run restarts the count
    in its own direction, and a close equal to the earlier one satisfies neither
    direction and ends the run.
    """

    if close < earlier:
        return count - 1.0 if count < 0.0 else -1.0
    if close > earlier:
        return count + 1.0 if count > 0.0 else 1.0
    return 0.0


def td_sequential(candles: Sequence[Candle], lookback: int = 4) -> list[float]:
    """Count §9.5's setup, signed by the direction that section names.

    Only the setup is implemented. §9.5 states the countdown's length and its
    ``C_t`` against ``C_{t-2}`` comparison but then defers the rules that cancel
    and restart it to DeMark's original work, and inventing those rules here would
    put a made-up condition where the standard declines to state one.

    The count is the plain number of consecutive candles satisfying §9.5's
    condition; the section completes a setup at nine, and nothing here caps or
    restarts the run at that point because §9.5 states no rule for either.
    """

    if lookback <= 0:
        raise ValueError("lookback must be positive")
    result: Series = [NAN] * min(lookback, len(candles))
    count = 0.0
    for index in range(lookback, len(candles)):
        count = _extend_setup(count, candles[index].close, candles[index - lookback].close)
        result.append(count)
    return result


@dataclass(slots=True)
class TDSequentialState:
    """O(1)-per-candle setup count over a fixed close lookback."""

    lookback: int = 4
    min_history: int = field(init=False)
    _closes: deque[float] = field(init=False, default_factory=deque)
    _count: float = field(init=False, default=0.0)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if self.lookback <= 0:
            raise ValueError("lookback must be positive")
        self.min_history = self.lookback + 1
        self._closes = deque(maxlen=self.lookback + 1)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._closes.clear()
        self._count = 0.0
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        self._closes.append(candle.close)
        if len(self._closes) <= self.lookback:
            self._value = NAN
            return self._value
        self._count = _extend_setup(self._count, candle.close, self._closes[0])
        self._value = self._count
        return self._value

    def current(self) -> float:
        return self._value


_EMPTY_WOODIES: WoodiesValue = {"cci": NAN, "turbo": NAN, "zone": NAN}


WOODIES_INNER_ZONE = 100.0
WOODIES_OUTER_ZONE = 200.0


def woodies_zone(value: float) -> float:
    """Number the bands §9.6's zone lines cut the oscillator into.

    §9.6 draws the lines at plus and minus 100 and plus and minus 200 and defines
    nothing between them, so the five bands are numbered outward from zero. A value
    sitting exactly on a line belongs to the inner band, which keeps the two
    directions symmetric.
    """

    if isnan(value):
        return NAN
    if value > WOODIES_OUTER_ZONE:
        return 2.0
    if value > WOODIES_INNER_ZONE:
        return 1.0
    if value < -WOODIES_OUTER_ZONE:
        return -2.0
    if value < -WOODIES_INNER_ZONE:
        return -1.0
    return 0.0


def woodies_cci(
    candles: Sequence[Candle],
    period: int = 14,
    turbo_period: int = 6,
) -> list[WoodiesValue]:
    """Show §9.6's two CCI lengths together with the zone the slower one sits in.

    Both values come from the §2.10 implementation this repository already has, at
    the two lengths §9.6 names. The section's zero-line patterns are named there
    (ZLR, TLB, GB100) but not defined, so they are not implemented; the zone lines
    are the only judgement §9.6 states in full.
    """

    if turbo_period <= 0:
        raise ValueError("period must be positive")
    main = cci(candles, period)
    turbo = cci(candles, turbo_period)
    return [
        {"cci": value, "turbo": quick, "zone": woodies_zone(value)}
        for value, quick in zip(main, turbo, strict=True)
    ]


@dataclass(slots=True)
class WoodiesCCIState:
    """O(period)-per-candle state over the two CCI lengths §9.6 names."""

    period: int = 14
    turbo_period: int = 6
    min_history: int = field(init=False)
    _main: CCIState = field(init=False)
    _turbo: CCIState = field(init=False)
    _value: WoodiesValue = field(init=False, default_factory=lambda: dict(_EMPTY_WOODIES))

    def __post_init__(self) -> None:
        if min(self.period, self.turbo_period) <= 0:
            raise ValueError("periods must be positive")
        self.min_history = max(self.period, self.turbo_period)
        self._main = CCIState(period=self.period)
        self._turbo = CCIState(period=self.turbo_period)

    @property
    def warmed_up(self) -> bool:
        return not any(isnan(value) for value in self._value.values())

    def seed(self, candles: Sequence[Candle]) -> None:
        self._main.seed(())
        self._turbo.seed(())
        self._value = dict(_EMPTY_WOODIES)
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> WoodiesValue:
        value = self._main.update(candle)
        self._value = {
            "cci": value,
            "turbo": self._turbo.update(candle),
            "zone": woodies_zone(value),
        }
        return self.current()

    def current(self) -> WoodiesValue:
        return dict(self._value)
