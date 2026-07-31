"""Define required volatility indicators and the follow-up volatility catalog."""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isnan, sqrt

from core_lib.types import Candle

from .primitives import (
    NAN,
    EmaState,
    RmaState,
    RollingExtremeState,
    SmaState,
    StdevState,
    ema,
    hh,
    hl2,
    ll,
    rma,
    safe_divide,
    sma,
    stdev,
    tr,
)

BollingerValue = dict[str, float]
KeltnerValue = dict[str, float]
DonchianValue = dict[str, float]
SuperTrendValue = dict[str, float]
ChandelierValue = dict[str, float]

FOLLOW_UP_INDICATORS: tuple[str, ...] = ()

# §3.4 names two trend states and no numbers for them, so the two states are
# mapped onto the two signs of one output rather than onto invented labels: the
# output is a float like every other indicator value, and a strategy reads the
# sign. Nothing else in the standard depends on the magnitude.
SUPERTREND_UPTREND = 1.0
SUPERTREND_DOWNTREND = -1.0


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


def keltner_channel(
    candles: Sequence[Candle],
    period: int = 20,
    atr_period: int = 10,
    multiplier: float = 2.0,
) -> list[KeltnerValue]:
    """Compute the modern Keltner Channel, an EMA centre with ATR width (§3.2).

    §12 lists Keltner as an indicator whose implementations disagree, and §3.2
    states the disagreement itself: the original is `SMA(TP) ± SMA(H − L)` while
    the modern form is `EMA(C) ± mult·ATR`. The standard's own formula block is
    the modern one, so that is what this computes and the original branch is not
    implemented here.
    """
    if period <= 0 or atr_period <= 0:
        raise ValueError("periods must be positive")
    if multiplier <= 0.0:
        raise ValueError("multiplier must be positive")
    middles = ema([candle.close for candle in candles], period)
    ranges = atr(candles, atr_period)
    return [
        {"middle": NAN, "upper": NAN, "lower": NAN}
        if isnan(middle) or isnan(average_range)
        else {
            "middle": middle,
            "upper": middle + multiplier * average_range,
            "lower": middle - multiplier * average_range,
        }
        for middle, average_range in zip(middles, ranges, strict=True)
    ]


@dataclass(slots=True)
class KeltnerChannelState:
    """O(1)-per-candle Keltner Channel state over one EMA and one ATR."""

    period: int = 20
    atr_period: int = 10
    multiplier: float = 2.0
    min_history: int = field(init=False)
    _middle: EmaState = field(init=False)
    _range: "ATRState" = field(init=False)
    _value: KeltnerValue = field(
        init=False,
        default_factory=lambda: {"middle": NAN, "upper": NAN, "lower": NAN},
    )

    def __post_init__(self) -> None:
        if self.period <= 0 or self.atr_period <= 0:
            raise ValueError("periods must be positive")
        if self.multiplier <= 0.0:
            raise ValueError("multiplier must be positive")
        # The centre and the width warm up on their own schedules, and a band
        # exists only once both do.
        self.min_history = max(self.period, self.atr_period)
        self._middle = EmaState(self.period)
        self._range = ATRState(self.atr_period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["middle"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._middle.reset()
        self._range.seed(())
        self._value = {"middle": NAN, "upper": NAN, "lower": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> KeltnerValue:
        middle = self._middle.update(candle.close)
        average_range = self._range.update(candle)
        self._value = (
            {"middle": NAN, "upper": NAN, "lower": NAN}
            if isnan(middle) or isnan(average_range)
            else {
                "middle": middle,
                "upper": middle + self.multiplier * average_range,
                "lower": middle - self.multiplier * average_range,
            }
        )
        return self.current()

    def current(self) -> KeltnerValue:
        return dict(self._value)


def donchian_channel(candles: Sequence[Candle], period: int = 20) -> list[DonchianValue]:
    """Compute the Donchian Channel from the rolling extremes (§3.3).

    §0.8 defines `HH(n)_t` as the maximum over `H_t` down to `H_{t-n+1}`, so the
    current candle belongs to its own window and the upper band touches the high
    on a new extreme. A breakout rule that has to compare price against the
    channel as it stood before this candle takes the previous value of this
    series; that shift is the strategy's decision and is deliberately not built
    into the indicator.
    """
    if period <= 0:
        raise ValueError("period must be positive")
    highest = hh([candle.high for candle in candles], period)
    lowest = ll([candle.low for candle in candles], period)
    return [
        {"upper": NAN, "lower": NAN, "middle": NAN}
        if isnan(upper) or isnan(lower)
        else {"upper": upper, "lower": lower, "middle": (upper + lower) / 2.0}
        for upper, lower in zip(highest, lowest, strict=True)
    ]


@dataclass(slots=True)
class DonchianChannelState:
    """O(1)-per-candle Donchian Channel state over two rolling extremes."""

    period: int = 20
    min_history: int = field(init=False)
    _highest: RollingExtremeState = field(init=False)
    _lowest: RollingExtremeState = field(init=False)
    _value: DonchianValue = field(
        init=False,
        default_factory=lambda: {"upper": NAN, "lower": NAN, "middle": NAN},
    )

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period
        self._highest = RollingExtremeState(self.period, highest=True)
        self._lowest = RollingExtremeState(self.period, highest=False)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["upper"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._highest.reset()
        self._lowest.reset()
        self._value = {"upper": NAN, "lower": NAN, "middle": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> DonchianValue:
        upper = self._highest.update(candle.high)
        lower = self._lowest.update(candle.low)
        self._value = (
            {"upper": NAN, "lower": NAN, "middle": NAN}
            if isnan(upper) or isnan(lower)
            else {"upper": upper, "lower": lower, "middle": (upper + lower) / 2.0}
        )
        return self.current()

    def current(self) -> DonchianValue:
        return dict(self._value)


@dataclass(slots=True)
class _SuperTrendTracker:
    """Carry the locked bands and the trend state between candles (§3.4).

    The two final bands are recursive: each candle either takes the freshly
    computed band or inherits the previous one, and the trend state carries
    forward until price crosses a band. Both execution paths drive this same
    object, so the batch series cannot drift from the incremental one.
    """

    multiplier: float
    _final_upper: float = field(init=False, default=NAN)
    _final_lower: float = field(init=False, default=NAN)
    _direction: float = field(init=False, default=NAN)
    _previous_close: float = field(init=False, default=NAN)

    def reset(self) -> None:
        """Return to the pre-first-candle state."""
        self._final_upper = NAN
        self._final_lower = NAN
        self._direction = NAN
        self._previous_close = NAN

    def update(self, candle: Candle, median: float, average_range: float) -> SuperTrendValue:
        """Advance one candle and return its bands, trend state, and line."""
        if isnan(average_range):
            return self.current()

        basic_upper = median + self.multiplier * average_range
        basic_lower = median - self.multiplier * average_range
        if isnan(self._final_upper):
            # The first candle with a defined ATR has no previous band to
            # inherit, so the lock rule has only its other branch available.
            final_upper = basic_upper
            final_lower = basic_lower
        else:
            final_upper = (
                basic_upper
                if basic_upper < self._final_upper or self._previous_close > self._final_upper
                else self._final_upper
            )
            final_lower = (
                basic_lower
                if basic_lower > self._final_lower or self._previous_close < self._final_lower
                else self._final_lower
            )

        if self._direction == SUPERTREND_UPTREND:
            direction = SUPERTREND_DOWNTREND if candle.close < final_lower else SUPERTREND_UPTREND
        else:
            # A downtrend flips upward on a close above the upper band. The very
            # first candle takes the same branch: there is no earlier state to
            # carry, and the standard's only rule for entering an uptrend is that
            # close above the upper band.
            direction = SUPERTREND_UPTREND if candle.close > final_upper else SUPERTREND_DOWNTREND

        self._final_upper = final_upper
        self._final_lower = final_lower
        self._direction = direction
        self._previous_close = candle.close
        return self.current()

    def current(self) -> SuperTrendValue:
        """Return the latest bands, trend state, and line, or a NaN warm-up value."""
        if isnan(self._direction):
            return {"supertrend": NAN, "direction": NAN, "upper": NAN, "lower": NAN}
        line = self._final_lower if self._direction == SUPERTREND_UPTREND else self._final_upper
        return {
            "supertrend": line,
            "direction": self._direction,
            "upper": self._final_upper,
            "lower": self._final_lower,
        }


def supertrend(
    candles: Sequence[Candle],
    period: int = 10,
    multiplier: float = 3.0,
) -> list[SuperTrendValue]:
    """Compute the SuperTrend bands, trend state, and line (§3.4)."""
    if period <= 0:
        raise ValueError("period must be positive")
    if multiplier <= 0.0:
        raise ValueError("multiplier must be positive")
    medians = hl2(candles)
    ranges = atr(candles, period)
    tracker = _SuperTrendTracker(multiplier=multiplier)
    tracker.reset()
    return [
        tracker.update(candle, median, average_range)
        for candle, median, average_range in zip(candles, medians, ranges, strict=True)
    ]


@dataclass(slots=True)
class SuperTrendState:
    """O(1)-per-candle SuperTrend state over one ATR and the locked bands."""

    period: int = 10
    multiplier: float = 3.0
    min_history: int = field(init=False)
    _range: "ATRState" = field(init=False)
    _tracker: _SuperTrendTracker = field(init=False)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        if self.multiplier <= 0.0:
            raise ValueError("multiplier must be positive")
        self.min_history = self.period
        self._range = ATRState(self.period)
        self._tracker = _SuperTrendTracker(multiplier=self.multiplier)
        self._tracker.reset()

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._tracker.current()["direction"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._range.seed(())
        self._tracker.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> SuperTrendValue:
        average_range = self._range.update(candle)
        # `hl2` is the standard's median price and already exists as a primitive,
        # so the one-candle call reuses it rather than restating `(H + L) / 2`.
        return self._tracker.update(candle, hl2((candle,))[0], average_range)

    def current(self) -> SuperTrendValue:
        return self._tracker.current()


def chandelier_exit(
    candles: Sequence[Candle],
    period: int = 22,
    multiplier: float = 3.0,
) -> list[ChandelierValue]:
    """Compute the long and short Chandelier stops (§3.5)."""
    if period <= 0:
        raise ValueError("period must be positive")
    if multiplier <= 0.0:
        raise ValueError("multiplier must be positive")
    highest = hh([candle.high for candle in candles], period)
    lowest = ll([candle.low for candle in candles], period)
    ranges = atr(candles, period)
    return [
        {"long": NAN, "short": NAN}
        if isnan(upper) or isnan(lower) or isnan(average_range)
        else {
            "long": upper - multiplier * average_range,
            "short": lower + multiplier * average_range,
        }
        for upper, lower, average_range in zip(highest, lowest, ranges, strict=True)
    ]


@dataclass(slots=True)
class ChandelierExitState:
    """O(1)-per-candle Chandelier Exit state over two extremes and one ATR."""

    period: int = 22
    multiplier: float = 3.0
    min_history: int = field(init=False)
    _highest: RollingExtremeState = field(init=False)
    _lowest: RollingExtremeState = field(init=False)
    _range: "ATRState" = field(init=False)
    _value: ChandelierValue = field(
        init=False,
        default_factory=lambda: {"long": NAN, "short": NAN},
    )

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        if self.multiplier <= 0.0:
            raise ValueError("multiplier must be positive")
        self.min_history = self.period
        self._highest = RollingExtremeState(self.period, highest=True)
        self._lowest = RollingExtremeState(self.period, highest=False)
        self._range = ATRState(self.period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["long"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._highest.reset()
        self._lowest.reset()
        self._range.seed(())
        self._value = {"long": NAN, "short": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> ChandelierValue:
        upper = self._highest.update(candle.high)
        lower = self._lowest.update(candle.low)
        average_range = self._range.update(candle)
        self._value = (
            {"long": NAN, "short": NAN}
            if isnan(upper) or isnan(lower) or isnan(average_range)
            else {
                "long": upper - self.multiplier * average_range,
                "short": lower + self.multiplier * average_range,
            }
        )
        return self.current()

    def current(self) -> ChandelierValue:
        return dict(self._value)


def _squared_drawdown(close: float, highest_close: float) -> float:
    """Return the squared percentage drawdown from the window's highest close (§3.6)."""
    if isnan(highest_close):
        return NAN
    # A zero highest close would need a zero price, which the candle contract
    # already rejects; the substitute exists so the helper stays total.
    drawdown = 100.0 * safe_divide(close - highest_close, highest_close, on_zero=0.0)
    return drawdown * drawdown


def _root_of_mean_square(mean: float) -> float:
    """Take the square root of a mean that is non-negative by definition.

    §3.6 averages squared drawdowns, so the true mean can never be negative and
    the root is always defined. The shared rolling mean carries a sum forward by
    adding and subtracting terms, so a window that returns to all zeros after a
    large drawdown has passed through leaves a residual near 1e-13 whose sign is
    not fixed. A negative residual would make `sqrt` raise instead of returning
    the zero the definition calls for, which would stop a backtest on an ordinary
    price series. Clamping here is the same guard the population standard
    deviation already applies to its own accumulated moment.
    """
    return sqrt(max(0.0, mean))


def ulcer_index(candles: Sequence[Candle], period: int = 14) -> list[float]:
    """Compute the root mean square of percentage drawdowns (§3.6)."""
    if period <= 0:
        raise ValueError("period must be positive")
    closes = [candle.close for candle in candles]
    maxima = hh(closes, period)
    squared = [
        _squared_drawdown(close, highest_close)
        for close, highest_close in zip(closes, maxima, strict=True)
    ]
    # §3.6 divides the sum of squares by `n`, which is what the shared rolling
    # mean already computes; only the square root is left to this indicator.
    return [NAN if isnan(mean) else _root_of_mean_square(mean) for mean in sma(squared, period)]


@dataclass(slots=True)
class UlcerIndexState:
    """O(1)-per-candle Ulcer Index state over one rolling maximum and one mean."""

    period: int = 14
    min_history: int = field(init=False)
    _highest: RollingExtremeState = field(init=False)
    _mean: SmaState = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        # The drawdown series itself needs a full window before its first value,
        # and the mean of squares needs a full window of those.
        self.min_history = 2 * self.period - 1
        self._highest = RollingExtremeState(self.period, highest=True)
        self._mean = SmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._highest.reset()
        self._mean.reset()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        highest_close = self._highest.update(candle.close)
        mean = self._mean.update(_squared_drawdown(candle.close, highest_close))
        self._value = NAN if isnan(mean) else _root_of_mean_square(mean)
        return self._value

    def current(self) -> float:
        return self._value


def _directional_deviations(
    close: float,
    previous_close: float | None,
    deviation: float,
) -> tuple[float, float]:
    """Split one deviation into its rising and falling halves (§3.7)."""
    if previous_close is None or isnan(deviation):
        return NAN, NAN
    change = close - previous_close
    return (
        deviation if change > 0.0 else 0.0,
        deviation if change < 0.0 else 0.0,
    )


def _relative_volatility(rising: float, falling: float) -> float:
    """Return the rising share of smoothed volatility on a 0-100 scale (§3.7)."""
    if isnan(rising) or isnan(falling):
        return NAN
    # Neither section §3.7 nor §0.11 names a substitute for a zero denominator,
    # which happens only when a window has no volatility at all in either
    # direction. The indicator is a bounded 0-100 oscillator, and a market that
    # leans neither way sits at the midpoint, so the share is one half. This is
    # the convention this repository already applies to Stochastic on a
    # collapsed range (§2.2), which is the same shape of degenerate window.
    return 100.0 * safe_divide(rising, rising + falling, on_zero=0.5)


def relative_volatility_index(
    candles: Sequence[Candle],
    period: int = 14,
    deviation_period: int = 10,
) -> list[float]:
    """Compute Dorsey's RSI-shaped index over standard deviation (§3.7).

    This is Donald Dorsey's Relative Volatility Index, not John Ehlers' Relative
    Vigor Index of §2.21; the standard notes that the two share an abbreviation
    and nothing else.
    """
    if period <= 0 or deviation_period <= 0:
        raise ValueError("periods must be positive")
    closes = [candle.close for candle in candles]
    deviations = stdev(closes, deviation_period)
    rising: list[float] = []
    falling: list[float] = []
    previous_close: float | None = None
    for close, deviation in zip(closes, deviations, strict=True):
        up, down = _directional_deviations(close, previous_close, deviation)
        rising.append(up)
        falling.append(down)
        previous_close = close
    return [
        _relative_volatility(up, down)
        for up, down in zip(rma(rising, period), rma(falling, period), strict=True)
    ]


@dataclass(slots=True)
class RelativeVolatilityIndexState:
    """O(1)-per-candle Dorsey Relative Volatility Index state."""

    period: int = 14
    deviation_period: int = 10
    min_history: int = field(init=False)
    _deviation: StdevState = field(init=False)
    _rising: RmaState = field(init=False)
    _falling: RmaState = field(init=False)
    _previous_close: float | None = field(init=False, default=None)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if self.period <= 0 or self.deviation_period <= 0:
            raise ValueError("periods must be positive")
        # The deviation series starts after its own window, and Wilder smoothing
        # then needs a full seed of those values.
        self.min_history = self.deviation_period + self.period - 1
        self._deviation = StdevState(self.deviation_period)
        self._rising = RmaState(self.period)
        self._falling = RmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._deviation.reset()
        self._rising.reset()
        self._falling.reset()
        self._previous_close = None
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        deviation = self._deviation.update(candle.close)
        up, down = _directional_deviations(candle.close, self._previous_close, deviation)
        self._previous_close = candle.close
        self._value = _relative_volatility(self._rising.update(up), self._falling.update(down))
        return self._value

    def current(self) -> float:
        return self._value


def _volatility_change(current: float, previous: float) -> float:
    """Return the percentage change between two smoothed ranges (§3.8)."""
    if isnan(current) or isnan(previous):
        return NAN
    # §3.8 names no substitute for a zero base, which happens only when the
    # average range was itself zero. This is a rate of change, and a move from no
    # volatility to no volatility is no change, so the substitute is zero. The
    # shared `RocState` cannot express this: §0.10 leaves the generic zero base
    # undefined and it returns NaN there, which a scalar output may not carry
    # past warm-up.
    return 100.0 * safe_divide(current - previous, previous, on_zero=0.0)


def chaikin_volatility(candles: Sequence[Candle], period: int = 10) -> list[float]:
    """Compute the rate of change of the smoothed high-low range (§3.8)."""
    if period <= 0:
        raise ValueError("period must be positive")
    averages = ema([candle.high - candle.low for candle in candles], period)
    result: list[float] = [NAN] * min(period, len(averages))
    for index in range(period, len(averages)):
        result.append(_volatility_change(averages[index], averages[index - period]))
    return result


@dataclass(slots=True)
class ChaikinVolatilityState:
    """O(1)-per-candle Chaikin Volatility state over one smoothed range."""

    period: int = 10
    min_history: int = field(init=False)
    _average: EmaState = field(init=False)
    _history: deque[float] = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        # The smoothed range needs its own window, and the change then looks back
        # a further `period` bars.
        self.min_history = 2 * self.period
        self._average = EmaState(self.period)
        self._history = deque(maxlen=self.period + 1)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._average.reset()
        self._history.clear()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        self._history.append(self._average.update(candle.high - candle.low))
        self._value = (
            NAN
            if len(self._history) <= self.period
            else _volatility_change(self._history[-1], self._history[0])
        )
        return self._value

    def current(self) -> float:
        return self._value


def _range_ratio(first: float, second: float) -> float:
    """Return one bar's ratio of the two range smoothings (§3.9)."""
    if isnan(first) or isnan(second):
        return NAN
    # §3.9 names no substitute for a zero denominator, which happens only when
    # every range in the window was zero. Numerator and denominator are then the
    # same quantity, so their ratio is one and the sum over the window is the
    # window length, which is where the standard's own reversal thresholds of
    # 27 and 26.5 sit relative to.
    return safe_divide(first, second, on_zero=1.0)


def mass_index(
    candles: Sequence[Candle],
    period: int = 9,
    sum_period: int = 25,
) -> list[float]:
    """Compute the sum of the double-smoothed range ratio (§3.9)."""
    if period <= 0 or sum_period <= 0:
        raise ValueError("periods must be positive")
    first = ema([candle.high - candle.low for candle in candles], period)
    second = ema(first, period)
    ratios = [_range_ratio(single, double) for single, double in zip(first, second, strict=True)]
    # §3.9 sums the ratio over the window; the shared rolling mean is that sum
    # divided by the window length, so multiplying it back is what reuses the
    # primitive instead of restating the sliding window here.
    return [NAN if isnan(mean) else mean * sum_period for mean in sma(ratios, sum_period)]


@dataclass(slots=True)
class MassIndexState:
    """O(1)-per-candle Mass Index state over two range smoothings and one sum."""

    period: int = 9
    sum_period: int = 25
    min_history: int = field(init=False)
    _first: EmaState = field(init=False)
    _second: EmaState = field(init=False)
    _sum: SmaState = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if self.period <= 0 or self.sum_period <= 0:
            raise ValueError("periods must be positive")
        # Each smoothing needs its own window in turn, and the sum then needs a
        # full window of ratios.
        self.min_history = 2 * self.period - 1 + self.sum_period - 1
        self._first = EmaState(self.period)
        self._second = EmaState(self.period)
        self._sum = SmaState(self.sum_period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._first.reset()
        self._second.reset()
        self._sum.reset()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        single = self._first.update(candle.high - candle.low)
        double = self._second.update(single)
        mean = self._sum.update(_range_ratio(single, double))
        self._value = NAN if isnan(mean) else mean * self.sum_period
        return self._value

    def current(self) -> float:
        return self._value
