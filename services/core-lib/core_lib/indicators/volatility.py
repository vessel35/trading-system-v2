"""Define required volatility indicators and the follow-up volatility catalog."""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isnan

from core_lib.types import Candle

from .primitives import NAN, _RollingPopulationStdev, rma, sma, stdev, tr

BollingerValue = dict[str, float]

FOLLOW_UP_INDICATORS = (
    "Keltner Channel",
    "SuperTrend",
    "Chandelier Exit",
    "Ulcer Index",
    "Relative Volatility Index",
    "Chaikin Volatility",
    "Mass Index",
)


def atr(candles: Sequence[Candle], period: int = 14) -> list[float]:
    """Compute Wilder ATR from True Range."""
    return rma(tr(candles), period)


@dataclass(slots=True)
class ATRState:
    """O(1)-per-candle Wilder ATR state."""

    period: int = 14
    min_history: int = field(init=False)
    _previous_close: float | None = field(init=False, default=None)
    _count: int = field(init=False, default=0)
    _seed_sum: float = field(init=False, default=0.0)
    _value: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period

    @property
    def warmed_up(self) -> bool:
        return self._value is not None

    def seed(self, candles: Sequence[Candle]) -> None:
        self._previous_close = None
        self._count = 0
        self._seed_sum = 0.0
        self._value = None
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        if self._previous_close is None:
            true_range = candle.high - candle.low
        else:
            true_range = max(
                candle.high - candle.low,
                abs(candle.high - self._previous_close),
                abs(candle.low - self._previous_close),
            )
        self._previous_close = candle.close
        if self._value is None:
            self._count += 1
            self._seed_sum += true_range
            if self._count == self.period:
                self._value = self._seed_sum / self.period
        else:
            self._value += (true_range - self._value) / self.period
        return self.current()

    def current(self) -> float:
        return self._value if self._value is not None else NAN


def bollinger_bands(
    candles: Sequence[Candle],
    period: int = 20,
    multiplier: float = 2.0,
) -> list[BollingerValue]:
    """Compute Bollinger middle/upper/lower bands, %B, and BandWidth."""
    if multiplier <= 0.0:
        raise ValueError("multiplier must be positive")
    closes = [candle.close for candle in candles]
    middles = sma(closes, period)
    deviations = stdev(closes, period)
    result: list[BollingerValue] = []
    for close, middle, deviation in zip(closes, middles, deviations, strict=True):
        if isnan(middle) or isnan(deviation):
            result.append(
                {
                    "middle": NAN,
                    "upper": NAN,
                    "lower": NAN,
                    "percent_b": NAN,
                    "bandwidth": NAN,
                }
            )
            continue
        upper = middle + multiplier * deviation
        lower = middle - multiplier * deviation
        width = upper - lower
        result.append(
            {
                "middle": middle,
                "upper": upper,
                "lower": lower,
                "percent_b": (close - lower) / width if width != 0.0 else NAN,
                "bandwidth": width / middle if middle != 0.0 else NAN,
            }
        )
    return result


@dataclass(slots=True)
class BollingerBandsState:
    """O(1)-per-candle Bollinger Bands state."""

    period: int = 20
    multiplier: float = 2.0
    min_history: int = field(init=False)
    _window: deque[float] = field(init=False, default_factory=deque)
    _total: float = field(init=False, default=0.0)
    _deviation: _RollingPopulationStdev = field(init=False)
    _value: BollingerValue = field(
        init=False,
        default_factory=lambda: {
            "middle": NAN,
            "upper": NAN,
            "lower": NAN,
            "percent_b": NAN,
            "bandwidth": NAN,
        },
    )

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        if self.multiplier <= 0.0:
            raise ValueError("multiplier must be positive")
        self.min_history = self.period
        self._deviation = _RollingPopulationStdev(self.period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["middle"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._window.clear()
        self._total = 0.0
        self._deviation.reset()
        self._value = {
            "middle": NAN,
            "upper": NAN,
            "lower": NAN,
            "percent_b": NAN,
            "bandwidth": NAN,
        }
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> BollingerValue:
        close = candle.close
        self._window.append(close)
        self._total += close
        deviation = self._deviation.update(close)
        if len(self._window) > self.period:
            removed = self._window.popleft()
            self._total -= removed
        if len(self._window) < self.period:
            return self.current()

        middle = self._total / self.period
        upper = middle + self.multiplier * deviation
        lower = middle - self.multiplier * deviation
        width = upper - lower
        self._value = {
            "middle": middle,
            "upper": upper,
            "lower": lower,
            "percent_b": (close - lower) / width if width != 0.0 else NAN,
            "bandwidth": width / middle if middle != 0.0 else NAN,
        }
        return self.current()

    def current(self) -> BollingerValue:
        return dict(self._value)
