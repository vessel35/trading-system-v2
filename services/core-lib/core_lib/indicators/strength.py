"""Define trend-strength indicators and the follow-up strength catalog."""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isnan, log10, sqrt

from core_lib.types import Candle

from .primitives import (
    NAN,
    RmaState,
    RollingExtremeState,
    SmaState,
    hh,
    ll,
    rma,
    safe_divide,
    sma,
    tr,
)
from .volatility import ATRState, atr

DmiValue = dict[str, float]
AroonValue = dict[str, float]
VortexValue = dict[str, float]
RandomWalkValue = dict[str, float]

# QQE is the only §5 indicator left unregistered: §5.5 states the trailing band
# logic only by reference to the original code, so its constants are not here to
# transcribe.
FOLLOW_UP_INDICATORS: tuple[str, ...] = ("QQE",)


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


def _true_range(candle: Candle, previous_close: float | None) -> float:
    """Return one candle's True Range (§0.6), with the first-candle fallback."""
    if previous_close is None:
        return candle.high - candle.low
    return max(
        candle.high - candle.low,
        abs(candle.high - previous_close),
        abs(candle.low - previous_close),
    )


def _vortex_value(upward: float, downward: float, span: float) -> VortexValue:
    """Divide §5.2's two rotational sums by the summed range over one window."""

    # A window with no True Range at all recorded no rotation to divide, and §5.2
    # names no substitute. Zero keeps both lines finite and says nothing was
    # measured, which is the reading §5.1's directional indicators already take
    # for the same collapsed window.
    return {
        "vi_plus": safe_divide(upward, span, on_zero=0.0),
        "vi_minus": safe_divide(downward, span, on_zero=0.0),
    }


def vortex(candles: Sequence[Candle], period: int = 14) -> list[VortexValue]:
    """Measure §5.2's two rotational movements against the range they spanned."""

    if period <= 0:
        raise ValueError("period must be positive")
    true_ranges = tr(candles)
    upward: list[float] = []
    downward: list[float] = []
    ranges: list[float] = []
    for index, candle in enumerate(candles):
        if index == 0:
            # Both rotational movements reach back to the previous candle, so the
            # first candle contributes neither of them and its True Range leaves
            # the window with them, exactly as §5.1's system treats its own first
            # candle here.
            upward.append(NAN)
            downward.append(NAN)
            ranges.append(NAN)
            continue
        previous = candles[index - 1]
        upward.append(abs(candle.high - previous.low))
        downward.append(abs(candle.low - previous.high))
        ranges.append(true_ranges[index])
    # §5.2's three sums share one window, so their averages stand in for them:
    # dividing every sum by the same length leaves both ratios unchanged.
    return [
        {"vi_plus": NAN, "vi_minus": NAN}
        if isnan(plus) or isnan(minus) or isnan(span)
        else _vortex_value(plus, minus, span)
        for plus, minus, span in zip(
            sma(upward, period),
            sma(downward, period),
            sma(ranges, period),
            strict=True,
        )
    ]


@dataclass(slots=True)
class VortexState:
    """O(1)-per-candle Vortex state over three rolling averages."""

    period: int = 14
    min_history: int = field(init=False)
    _previous: Candle | None = field(init=False, default=None)
    _upward: SmaState = field(init=False)
    _downward: SmaState = field(init=False)
    _ranges: SmaState = field(init=False)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        # The first candle contributes no rotational movement, so a full window
        # closes one candle after the period itself.
        self.min_history = self.period + 1
        self._upward = SmaState(self.period)
        self._downward = SmaState(self.period)
        self._ranges = SmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return self._ranges.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._previous = None
        for state in (self._upward, self._downward, self._ranges):
            state.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> VortexValue:
        if self._previous is None:
            plus = self._upward.update(NAN)
            minus = self._downward.update(NAN)
            span = self._ranges.update(NAN)
        else:
            plus = self._upward.update(abs(candle.high - self._previous.low))
            minus = self._downward.update(abs(candle.low - self._previous.high))
            span = self._ranges.update(_true_range(candle, self._previous.close))
        self._previous = candle
        if isnan(plus) or isnan(minus) or isnan(span):
            return {"vi_plus": NAN, "vi_minus": NAN}
        return _vortex_value(plus, minus, span)

    def current(self) -> VortexValue:
        plus = self._upward.current()
        minus = self._downward.current()
        span = self._ranges.current()
        if isnan(plus) or isnan(minus) or isnan(span):
            return {"vi_plus": NAN, "vi_minus": NAN}
        return _vortex_value(plus, minus, span)


def _choppiness_value(average_range: float, span: float, period: int) -> float:
    """Turn §5.4's summed True Range and window span into the index.

    §5.4 names no substitute for a window whose high equals its low, and the
    engine accepts no non-finite scalar once warm-up is over. The ratio the
    logarithm reads saturates at the window length, which is where the index
    reads 100, and a market that did not move at all is the extreme this index
    calls choppy rather than trending, so that is the value a collapsed window
    takes here.

    The logarithm needs no guard of its own. Consecutive True Ranges cover the
    path the window's span measures end to end, so the summed range is never
    smaller than the span: a positive span implies a positive sum, and the two
    reach zero only together, which is the case the substitute above answers.
    """

    # The rolling average over the window times its length is the sum §5.4 writes.
    ratio = safe_divide(average_range * period, span, on_zero=float(period))
    return 100.0 * log10(ratio) / log10(period)


def choppiness_index(candles: Sequence[Candle], period: int = 14) -> list[float]:
    """Compare §5.4's summed True Range with the span the window covered."""

    if period < 2:
        raise ValueError("period must be at least 2")
    averages = sma(tr(candles), period)
    highest = hh([candle.high for candle in candles], period)
    lowest = ll([candle.low for candle in candles], period)
    return [
        NAN
        if isnan(average) or isnan(high) or isnan(low)
        else _choppiness_value(average, high - low, period)
        for average, high, low in zip(averages, highest, lowest, strict=True)
    ]


@dataclass(slots=True)
class ChoppinessIndexState:
    """O(1)-per-candle Choppiness state over one average and two extremes."""

    period: int = 14
    min_history: int = field(init=False)
    _previous_close: float | None = field(init=False, default=None)
    _ranges: SmaState = field(init=False)
    _highest: RollingExtremeState = field(init=False)
    _lowest: RollingExtremeState = field(init=False)

    def __post_init__(self) -> None:
        if self.period < 2:
            raise ValueError("period must be at least 2")
        # §0.6 gives the first candle its own True Range, so nothing is dropped
        # here and the window closes on the period itself.
        self.min_history = self.period
        self._ranges = SmaState(self.period)
        self._highest = RollingExtremeState(self.period, highest=True)
        self._lowest = RollingExtremeState(self.period, highest=False)

    @property
    def warmed_up(self) -> bool:
        return self._ranges.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._previous_close = None
        self._ranges.reset()
        self._highest.reset()
        self._lowest.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        average = self._ranges.update(_true_range(candle, self._previous_close))
        self._previous_close = candle.close
        high = self._highest.update(candle.high)
        low = self._lowest.update(candle.low)
        if isnan(average) or isnan(high) or isnan(low):
            return NAN
        return _choppiness_value(average, high - low, self.period)

    def current(self) -> float:
        average = self._ranges.current()
        high = self._highest.current()
        low = self._lowest.current()
        if isnan(average) or isnan(high) or isnan(low):
            return NAN
        return _choppiness_value(average, high - low, self.period)


def _random_walk_value(
    candle: Candle,
    earlier: Candle,
    average_range: float,
    root: float,
) -> RandomWalkValue:
    """Scale §5.6's two displacements by what a random walk would have covered."""

    # A window with no average range gives no yardstick to divide by, and §5.6
    # names no substitute. Zero says the displacement measured nothing rather
    # than reporting an unbounded one.
    scale = average_range * root
    return {
        "high": safe_divide(candle.high - earlier.low, scale, on_zero=0.0),
        "low": safe_divide(earlier.high - candle.low, scale, on_zero=0.0),
    }


def random_walk_index(candles: Sequence[Candle], period: int = 14) -> list[RandomWalkValue]:
    """Compare §5.6's displacement over `period` candles with a random walk's.

    The yardstick is the registered ATR of §3.1, taken from the volatility
    module rather than smoothed again here, because §5.6 names that indicator as
    the quantity it divides by.
    """

    if period <= 0:
        raise ValueError("period must be positive")
    averages = atr(candles, period)
    root = sqrt(period)
    result: list[RandomWalkValue] = []
    for index, candle in enumerate(candles):
        if index < period or isnan(averages[index]):
            result.append({"high": NAN, "low": NAN})
            continue
        result.append(_random_walk_value(candle, candles[index - period], averages[index], root))
    return result


@dataclass(slots=True)
class RandomWalkIndexState:
    """O(1)-per-candle Random Walk Index state over the registered ATR."""

    period: int = 14
    min_history: int = field(init=False)
    _root: float = field(init=False)
    _average: ATRState = field(init=False)
    _window: deque[Candle] = field(init=False)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        # ATR closes on the period itself, and the displacement also needs the
        # candle from `period` candles back, which arrives one candle later.
        self.min_history = self.period + 1
        self._root = sqrt(self.period)
        self._average = ATRState(self.period)
        self._window = deque(maxlen=self.period + 1)

    @property
    def warmed_up(self) -> bool:
        return len(self._window) == self.period + 1 and self._average.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._average.seed(())
        self._window.clear()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> RandomWalkValue:
        average = self._average.update(candle)
        self._window.append(candle)
        if not self.warmed_up or isnan(average):
            return {"high": NAN, "low": NAN}
        return _random_walk_value(candle, self._window[0], average, self._root)

    def current(self) -> RandomWalkValue:
        average = self._average.current()
        if not self.warmed_up or isnan(average):
            return {"high": NAN, "low": NAN}
        return _random_walk_value(self._window[-1], self._window[0], average, self._root)
