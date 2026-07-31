"""Define trend-strength indicators and the follow-up strength catalog."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isnan

from core_lib.types import Candle

from .primitives import NAN, RmaState, rma, safe_divide, tr

DmiValue = dict[str, float]
AroonValue = dict[str, float]

FOLLOW_UP_INDICATORS = (
    "Vortex",
    "Choppiness Index",
    "QQE",
    "Random Walk Index",
)


def _directional_movement(previous: Candle, current: Candle) -> tuple[float, float]:
    """Return the (+DM, -DM) pair for one candle transition (§5.1)."""
    up_move = current.high - previous.high
    down_move = previous.low - current.low
    plus = up_move if up_move > down_move and up_move > 0.0 else 0.0
    minus = down_move if down_move > up_move and down_move > 0.0 else 0.0
    return plus, minus


def _directional_index(plus: float, minus: float) -> float:
    """Return DX from the two directional indicators; §5.1 sets a zero sum to 0."""
    return 100.0 * safe_divide(abs(plus - minus), plus + minus, on_zero=0.0)


def dmi(candles: Sequence[Candle], period: int = 14) -> list[DmiValue]:
    """Compute Wilder's directional system: +DI, -DI, ADX and ADXR (§5.1)."""
    if period <= 0:
        raise ValueError("period must be positive")
    plus_moves = [NAN]
    minus_moves = [NAN]
    for previous, current in zip(candles, candles[1:], strict=False):
        plus, minus = _directional_movement(previous, current)
        plus_moves.append(plus)
        minus_moves.append(minus)
    # The directional moves do not exist for the first candle, so the range series
    # starts with them rather than with the standard's first-bar True Range.
    ranges = [NAN, *tr(candles)[1:]]
    smoothed_range = rma(ranges, period)
    smoothed_plus = rma(plus_moves, period)
    smoothed_minus = rma(minus_moves, period)

    directional: list[float] = []
    plus_indicators: list[float] = []
    minus_indicators: list[float] = []
    for span, plus, minus in zip(smoothed_range, smoothed_plus, smoothed_minus, strict=True):
        if isnan(span) or isnan(plus) or isnan(minus):
            plus_indicators.append(NAN)
            minus_indicators.append(NAN)
            directional.append(NAN)
            continue
        # A window with no range at all leaves both indicators undefined by
        # division; zero keeps them finite and says no direction was measured.
        plus_indicator = 100.0 * safe_divide(plus, span, on_zero=0.0)
        minus_indicator = 100.0 * safe_divide(minus, span, on_zero=0.0)
        plus_indicators.append(plus_indicator)
        minus_indicators.append(minus_indicator)
        directional.append(_directional_index(plus_indicator, minus_indicator))
    average = rma(directional, period)
    result: list[DmiValue] = []
    for index, (plus, minus, adx) in enumerate(
        zip(plus_indicators, minus_indicators, average, strict=True)
    ):
        earlier = average[index - period] if index >= period else NAN
        result.append(
            {
                "plus_di": plus,
                "minus_di": minus,
                "adx": adx,
                "adxr": NAN if isnan(adx) or isnan(earlier) else (adx + earlier) / 2.0,
            }
        )
    return result


@dataclass(slots=True)
class DMIState:
    """O(1)-per-candle directional system state over four Wilder averages."""

    period: int = 14
    min_history: int = field(init=False)
    _previous: Candle | None = field(init=False, default=None)
    _range: RmaState = field(init=False)
    _plus: RmaState = field(init=False)
    _minus: RmaState = field(init=False)
    _average: RmaState = field(init=False)
    _history: list[float] = field(init=False, default_factory=list)
    _value: DmiValue = field(
        init=False,
        default_factory=lambda: {
            "plus_di": NAN,
            "minus_di": NAN,
            "adx": NAN,
            "adxr": NAN,
        },
    )

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        # The first candle produces no move, so the smoothed moves become valid
        # on candle `period`, the average of the directional index on candle
        # `2 * period`, and ADXR one more period after that.
        self.min_history = 3 * self.period
        self._range = RmaState(self.period)
        self._plus = RmaState(self.period)
        self._minus = RmaState(self.period)
        self._average = RmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["adxr"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._previous = None
        for state in (self._range, self._plus, self._minus, self._average):
            state.reset()
        self._history = []
        self._value = {"plus_di": NAN, "minus_di": NAN, "adx": NAN, "adxr": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> DmiValue:
        if self._previous is None:
            self._previous = candle
            span = NAN
            plus_move = NAN
            minus_move = NAN
        else:
            span = max(
                candle.high - candle.low,
                abs(candle.high - self._previous.close),
                abs(candle.low - self._previous.close),
            )
            plus_move, minus_move = _directional_movement(self._previous, candle)
            self._previous = candle

        smoothed_range = self._range.update(span)
        smoothed_plus = self._plus.update(plus_move)
        smoothed_minus = self._minus.update(minus_move)
        if isnan(smoothed_range) or isnan(smoothed_plus) or isnan(smoothed_minus):
            plus_indicator = NAN
            minus_indicator = NAN
            directional = NAN
        else:
            plus_indicator = 100.0 * safe_divide(smoothed_plus, smoothed_range, on_zero=0.0)
            minus_indicator = 100.0 * safe_divide(smoothed_minus, smoothed_range, on_zero=0.0)
            directional = _directional_index(plus_indicator, minus_indicator)
        adx = self._average.update(directional)
        self._history.append(adx)
        earlier = self._history[-1 - self.period] if len(self._history) > self.period else NAN
        self._value = {
            "plus_di": plus_indicator,
            "minus_di": minus_indicator,
            "adx": adx,
            "adxr": NAN if isnan(adx) or isnan(earlier) else (adx + earlier) / 2.0,
        }
        return self.current()

    def current(self) -> DmiValue:
        return dict(self._value)


def aroon(candles: Sequence[Candle], period: int = 25) -> list[AroonValue]:
    """Measure how recently the window's extremes occurred (§5.3)."""
    if period <= 0:
        raise ValueError("period must be positive")
    result: list[AroonValue] = []
    for index in range(len(candles)):
        if index < period:
            result.append({"up": NAN, "down": NAN, "oscillator": NAN})
            continue
        window = candles[index - period : index + 1]
        highs = [candle.high for candle in window]
        lows = [candle.low for candle in window]
        since_high = len(highs) - 1 - highs.index(max(highs))
        since_low = len(lows) - 1 - lows.index(min(lows))
        up = 100.0 * (period - since_high) / period
        down = 100.0 * (period - since_low) / period
        result.append({"up": up, "down": down, "oscillator": up - down})
    return result


@dataclass(slots=True)
class AroonState:
    """O(period)-per-candle Aroon state; the age of an extreme needs its window."""

    period: int = 25
    min_history: int = field(init=False)
    _highs: list[float] = field(init=False, default_factory=list)
    _lows: list[float] = field(init=False, default_factory=list)
    _value: AroonValue = field(
        init=False,
        default_factory=lambda: {"up": NAN, "down": NAN, "oscillator": NAN},
    )

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        # The window holds the current candle plus `period` earlier ones, so the
        # age of an extreme can reach `period` itself.
        self.min_history = self.period + 1

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["up"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._highs = []
        self._lows = []
        self._value = {"up": NAN, "down": NAN, "oscillator": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> AroonValue:
        self._highs.append(candle.high)
        self._lows.append(candle.low)
        if len(self._highs) > self.period + 1:
            self._highs.pop(0)
            self._lows.pop(0)
        if len(self._highs) < self.period + 1:
            self._value = {"up": NAN, "down": NAN, "oscillator": NAN}
            return self.current()
        since_high = len(self._highs) - 1 - self._highs.index(max(self._highs))
        since_low = len(self._lows) - 1 - self._lows.index(min(self._lows))
        up = 100.0 * (self.period - since_high) / self.period
        down = 100.0 * (self.period - since_low) / self.period
        self._value = {"up": up, "down": down, "oscillator": up - down}
        return self.current()

    def current(self) -> AroonValue:
        return dict(self._value)
