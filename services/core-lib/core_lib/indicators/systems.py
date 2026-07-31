"""Define standalone indicator systems and the follow-up systems catalog."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isnan

from core_lib.types import Candle

from .primitives import NAN, EmaState, ema

ElderRayValue = dict[str, float]

FOLLOW_UP_INDICATORS = (
    "Ichimoku Kinko Hyo",
    "Elder Impulse System",
    "TD Sequential",
    "Woodies CCI",
)


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
