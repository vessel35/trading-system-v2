"""Define required volatility indicators and the follow-up volatility catalog."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isnan

from core_lib.types import Candle

from .primitives import NAN, RmaState, SmaState, StdevState, rma, sma, stdev, tr

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
    """O(1)-per-candle Wilder ATR state over True Range.

    True Range needs the previous close, so that one step stays here; the
    Wilder smoothing on top of it comes from the shared primitive.
    """

    period: int = 14
    min_history: int = field(init=False)
    _previous_close: float | None = field(init=False, default=None)
    _average: RmaState = field(init=False)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period
        self._average = RmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return self._average.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._previous_close = None
        self._average.reset()
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
        return self._average.update(true_range)

    def current(self) -> float:
        return self._average.current()


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
    _middle: SmaState = field(init=False)
    _deviation: StdevState = field(init=False)
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
        self._middle = SmaState(self.period)
        self._deviation = StdevState(self.period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["middle"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._middle.reset()
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
        middle = self._middle.update(close)
        deviation = self._deviation.update(close)
        if isnan(middle) or isnan(deviation):
            return self.current()

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
