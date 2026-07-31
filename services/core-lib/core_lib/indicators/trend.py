"""Define required trend indicators and the follow-up trend catalog."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isnan

from core_lib.types import Candle

from .primitives import NAN, EmaState
from .primitives import ema as ema_primitive

FOLLOW_UP_INDICATORS = (
    "TEMA",
    "T3",
    "HMA",
    "ZLEMA",
    "ALMA",
    "KAMA",
    "VIDYA",
    "McGinley Dynamic",
    "Guppy GMMA",
)


def ema(candles: Sequence[Candle], period: int) -> list[float]:
    """Compute close-price EMA using the §0.3 SMA seed."""
    return ema_primitive([candle.close for candle in candles], period)


@dataclass(slots=True)
class EMAState:
    """O(1)-per-candle incremental EMA state over close prices.

    The recursion itself lives in the primitive layer so this class only decides
    which price feeds it. Every indicator that smooths something reuses the same
    implementation rather than restating the seed-and-alpha rule.
    """

    period: int
    min_history: int = field(init=False)
    _average: EmaState = field(init=False)

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
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        return self._average.update(candle.close)

    def current(self) -> float:
        return self._average.current()


def dema(candles: Sequence[Candle], period: int) -> list[float]:
    """Compute the double EMA, ``2 * EMA1 - EMA2`` (§1.1)."""
    closes = [candle.close for candle in candles]
    first = ema_primitive(closes, period)
    second = ema_primitive(first, period)
    return [
        NAN if isnan(one) or isnan(two) else 2.0 * one - two
        for one, two in zip(first, second, strict=True)
    ]


@dataclass(slots=True)
class DEMAState:
    """O(1)-per-candle double EMA state.

    The second EMA smooths the first one's output, so it only starts once the
    first has a value. Feeding the warm-up NaN through keeps the incremental
    path aligned with the vectorized one, which sees the same NaN prefix.
    """

    period: int
    min_history: int = field(init=False)
    _first: EmaState = field(init=False)
    _second: EmaState = field(init=False)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        # The first average needs `period` closes; the second needs `period`
        # values of the first, and they start arriving on that same candle.
        self.min_history = 2 * self.period - 1
        self._first = EmaState(self.period)
        self._second = EmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return self._second.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._first.reset()
        self._second.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        first = self._first.update(candle.close)
        second = self._second.update(first)
        return NAN if isnan(first) or isnan(second) else 2.0 * first - second

    def current(self) -> float:
        first = self._first.current()
        second = self._second.current()
        return NAN if isnan(first) or isnan(second) else 2.0 * first - second
