"""Define required momentum indicators and the follow-up momentum catalog."""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isnan

from core_lib.types import Candle

from .primitives import (
    NAN,
    EmaState,
    RmaState,
    RollingExtremeState,
    SmaState,
    ema,
    hh,
    hl2,
    ll,
    rma,
    safe_divide,
    sma,
    tp,
)

StochasticValue = dict[str, float]
MacdValue = dict[str, float]
PpoValue = dict[str, float]
SmiValue = dict[str, float]

FOLLOW_UP_INDICATORS = (
    "Stochastic RSI",
    "TRIX",
    "CMO",
    "Williams %R",
    "Ultimate Oscillator",
    "Fisher Transform",
    "Connors RSI",
    "QStick",
    "Chande Forecast Oscillator",
    "DeMarker",
    "DPO",
    "Schaff Trend Cycle",
    "Relative Vigor Index",
    "Laguerre RSI",
    "Pretty Good Oscillator",
    "KST",
    "Coppock Curve",
    "Special K",
)


def _rsi_value(average_gain: float, average_loss: float) -> float:
    if average_loss == 0.0:
        return 100.0
    if average_gain == 0.0:
        return 0.0
    relative_strength = average_gain / average_loss
    return 100.0 - 100.0 / (1.0 + relative_strength)


def rsi(candles: Sequence[Candle], period: int = 14) -> list[float]:
    """Compute Wilder RSI from close-price deltas."""
    if period <= 0:
        raise ValueError("period must be positive")
    gains = [NAN]
    losses = [NAN]
    for previous, current in zip(candles, candles[1:], strict=False):
        change = current.close - previous.close
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    average_gains = rma(gains, period)
    average_losses = rma(losses, period)
    result: list[float] = []
    for average_gain, average_loss in zip(average_gains, average_losses, strict=True):
        if isnan(average_gain) or isnan(average_loss):
            result.append(NAN)
        else:
            result.append(_rsi_value(average_gain, average_loss))
    return result


@dataclass(slots=True)
class RSIState:
    """O(1)-per-candle Wilder RSI state."""

    period: int = 14
    min_history: int = field(init=False)
    _previous_close: float | None = field(init=False, default=None)
    _gains: RmaState = field(init=False)
    _losses: RmaState = field(init=False)
    _value: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period + 1
        self._gains = RmaState(self.period)
        self._losses = RmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return self._value is not None

    def seed(self, candles: Sequence[Candle]) -> None:
        self._previous_close = None
        self._gains.reset()
        self._losses.reset()
        self._value = None
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        if self._previous_close is None:
            self._previous_close = candle.close
            return NAN

        change = candle.close - self._previous_close
        self._previous_close = candle.close
        average_gain = self._gains.update(max(change, 0.0))
        average_loss = self._losses.update(max(-change, 0.0))
        if not isnan(average_gain) and not isnan(average_loss):
            self._value = _rsi_value(average_gain, average_loss)
        return self.current()

    def current(self) -> float:
        return self._value if self._value is not None else NAN


def stochastic(
    candles: Sequence[Candle],
    period: int = 14,
    smooth_period: int = 3,
) -> list[StochasticValue]:
    """Compute fast Stochastic %K and its SMA-smoothed %D."""
    if period <= 0 or smooth_period <= 0:
        raise ValueError("periods must be positive")
    highest = hh([candle.high for candle in candles], period)
    lowest = ll([candle.low for candle in candles], period)
    percent_k: list[float] = []
    previous_k = 50.0
    for candle, high, low in zip(candles, highest, lowest, strict=True):
        if isnan(high) or isnan(low):
            percent_k.append(NAN)
            continue
        # §2.2 keeps the previous %K when the window is flat, starting at 50.
        current_k = safe_divide(
            100.0 * (candle.close - low),
            high - low,
            on_zero=previous_k,
        )
        percent_k.append(current_k)
        previous_k = current_k
    percent_d = sma(percent_k, smooth_period)
    return [
        {"percent_k": current_k, "percent_d": current_d}
        for current_k, current_d in zip(percent_k, percent_d, strict=True)
    ]


@dataclass(slots=True)
class StochasticState:
    """O(1)-per-candle fast Stochastic state."""

    period: int = 14
    smooth_period: int = 3
    min_history: int = field(init=False)
    _highest: RollingExtremeState = field(init=False)
    _lowest: RollingExtremeState = field(init=False)
    _smoothed: SmaState = field(init=False)
    _previous_k: float = field(init=False, default=50.0)
    _value: StochasticValue = field(
        init=False,
        default_factory=lambda: {"percent_k": NAN, "percent_d": NAN},
    )

    def __post_init__(self) -> None:
        if self.period <= 0 or self.smooth_period <= 0:
            raise ValueError("periods must be positive")
        self.min_history = self.period + self.smooth_period - 1
        self._highest = RollingExtremeState(self.period, highest=True)
        self._lowest = RollingExtremeState(self.period, highest=False)
        self._smoothed = SmaState(self.smooth_period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["percent_d"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._highest.reset()
        self._lowest.reset()
        self._smoothed.reset()
        self._previous_k = 50.0
        self._value = {"percent_k": NAN, "percent_d": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> StochasticValue:
        highest = self._highest.update(candle.high)
        lowest = self._lowest.update(candle.low)
        if isnan(highest) or isnan(lowest):
            self._value = {"percent_k": NAN, "percent_d": NAN}
            return self.current()

        # §2.2 keeps the previous %K when the window is flat, starting at 50.
        current_k = safe_divide(
            100.0 * (candle.close - lowest),
            highest - lowest,
            on_zero=self._previous_k,
        )
        self._previous_k = current_k
        current_d = self._smoothed.update(current_k)
        self._value = {"percent_k": current_k, "percent_d": current_d}
        return self.current()

    def current(self) -> StochasticValue:
        return dict(self._value)


def macd(
    candles: Sequence[Candle],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> list[MacdValue]:
    """Compute MACD, its signal line, and the histogram (§2.4)."""
    if fast_period <= 0 or slow_period <= 0 or signal_period <= 0:
        raise ValueError("periods must be positive")
    if fast_period >= slow_period:
        raise ValueError("fast_period must be shorter than slow_period")
    closes = [candle.close for candle in candles]
    fast = ema(closes, fast_period)
    slow = ema(closes, slow_period)
    line = [
        NAN if isnan(quick) or isnan(slow_value) else quick - slow_value
        for quick, slow_value in zip(fast, slow, strict=True)
    ]
    signal = ema(line, signal_period)
    return [
        {
            "macd": macd_value,
            "signal": signal_value,
            "histogram": NAN
            if isnan(macd_value) or isnan(signal_value)
            else macd_value - signal_value,
        }
        for macd_value, signal_value in zip(line, signal, strict=True)
    ]


@dataclass(slots=True)
class MACDState:
    """O(1)-per-candle MACD state over two close EMAs and a signal EMA."""

    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    min_history: int = field(init=False)
    _fast: EmaState = field(init=False)
    _slow: EmaState = field(init=False)
    _signal: EmaState = field(init=False)
    _value: MacdValue = field(
        init=False,
        default_factory=lambda: {"macd": NAN, "signal": NAN, "histogram": NAN},
    )

    def __post_init__(self) -> None:
        if self.fast_period <= 0 or self.slow_period <= 0 or self.signal_period <= 0:
            raise ValueError("periods must be positive")
        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be shorter than slow_period")
        # The MACD line starts with the slow average; the signal then needs its
        # own period of MACD values, the first of which lands on that candle.
        self.min_history = self.slow_period + self.signal_period - 1
        self._fast = EmaState(self.fast_period)
        self._slow = EmaState(self.slow_period)
        self._signal = EmaState(self.signal_period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["signal"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._fast.reset()
        self._slow.reset()
        self._signal.reset()
        self._value = {"macd": NAN, "signal": NAN, "histogram": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> MacdValue:
        fast = self._fast.update(candle.close)
        slow = self._slow.update(candle.close)
        line = NAN if isnan(fast) or isnan(slow) else fast - slow
        signal = self._signal.update(line)
        self._value = {
            "macd": line,
            "signal": signal,
            "histogram": NAN if isnan(line) or isnan(signal) else line - signal,
        }
        return self.current()

    def current(self) -> MacdValue:
        return dict(self._value)


def tsi(candles: Sequence[Candle], long_period: int = 25, short_period: int = 13) -> list[float]:
    """Compute the True Strength Index from doubly smoothed momentum (§2.7)."""
    if long_period <= 0 or short_period <= 0:
        raise ValueError("periods must be positive")
    changes = [NAN]
    for previous, current in zip(candles, candles[1:], strict=False):
        changes.append(current.close - previous.close)
    magnitudes = [NAN if isnan(change) else abs(change) for change in changes]
    smoothed = ema(ema(changes, long_period), short_period)
    absolute = ema(ema(magnitudes, long_period), short_period)
    return [
        NAN
        if isnan(numerator) or isnan(denominator)
        # A zero denominator means no movement at all in the window, and a
        # motionless market has no strength in either direction. §2.7 does not
        # name a substitute, so this repository chooses zero as that reading.
        else 100.0 * safe_divide(numerator, denominator, on_zero=0.0)
        for numerator, denominator in zip(smoothed, absolute, strict=True)
    ]


@dataclass(slots=True)
class TSIState:
    """O(1)-per-candle True Strength Index state over four chained EMAs."""

    long_period: int = 25
    short_period: int = 13
    min_history: int = field(init=False)
    _previous_close: float | None = field(init=False, default=None)
    _change_long: EmaState = field(init=False)
    _change_short: EmaState = field(init=False)
    _magnitude_long: EmaState = field(init=False)
    _magnitude_short: EmaState = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if self.long_period <= 0 or self.short_period <= 0:
            raise ValueError("periods must be positive")
        # One candle produces no change, the long average then needs its period,
        # and the short average needs its own period of long-average values.
        self.min_history = 1 + self.long_period + self.short_period - 1
        self._change_long = EmaState(self.long_period)
        self._change_short = EmaState(self.short_period)
        self._magnitude_long = EmaState(self.long_period)
        self._magnitude_short = EmaState(self.short_period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._previous_close = None
        self._change_long.reset()
        self._change_short.reset()
        self._magnitude_long.reset()
        self._magnitude_short.reset()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        change = NAN if self._previous_close is None else candle.close - self._previous_close
        self._previous_close = candle.close
        magnitude = NAN if isnan(change) else abs(change)
        smoothed = self._change_short.update(self._change_long.update(change))
        absolute = self._magnitude_short.update(self._magnitude_long.update(magnitude))
        self._value = (
            NAN
            if isnan(smoothed) or isnan(absolute)
            else 100.0 * safe_divide(smoothed, absolute, on_zero=0.0)
        )
        return self.current()

    def current(self) -> float:
        return self._value


def cci(candles: Sequence[Candle], period: int = 20) -> list[float]:
    """Compute the Commodity Channel Index from typical price (§2.10)."""
    if period <= 0:
        raise ValueError("period must be positive")
    typical = tp(candles)
    averages = sma(typical, period)
    result: list[float] = []
    for index, average in enumerate(averages):
        if isnan(average):
            result.append(NAN)
            continue
        window = typical[index - period + 1 : index + 1]
        mean_deviation = sum(abs(value - average) for value in window) / period
        # A window whose typical prices are all identical has no deviation to
        # scale by, and the price sits exactly on its own mean. §2.10 does not
        # name a substitute, so this repository reads that as zero.
        result.append(safe_divide(typical[index] - average, 0.015 * mean_deviation, on_zero=0.0))
    return result


@dataclass(slots=True)
class CCIState:
    """O(period)-per-candle CCI state; mean absolute deviation needs the window."""

    period: int = 20
    min_history: int = field(init=False)
    _typical: deque[float] = field(init=False, default_factory=deque)
    _average: SmaState = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period
        self._typical = deque(maxlen=self.period)
        self._average = SmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._typical.clear()
        self._average.reset()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        typical = (candle.high + candle.low + candle.close) / 3.0
        self._typical.append(typical)
        average = self._average.update(typical)
        if isnan(average):
            self._value = NAN
            return self.current()
        mean_deviation = sum(abs(value - average) for value in self._typical) / self.period
        self._value = safe_divide(typical - average, 0.015 * mean_deviation, on_zero=0.0)
        return self.current()

    def current(self) -> float:
        return self._value


def awesome_oscillator(
    candles: Sequence[Candle],
    fast_period: int = 5,
    slow_period: int = 34,
) -> list[float]:
    """Compute the Awesome Oscillator over median price (§2.12)."""
    if fast_period <= 0 or slow_period <= 0:
        raise ValueError("periods must be positive")
    if fast_period >= slow_period:
        raise ValueError("fast_period must be shorter than slow_period")
    median = hl2(candles)
    fast = sma(median, fast_period)
    slow = sma(median, slow_period)
    return [
        NAN if isnan(quick) or isnan(slow_value) else quick - slow_value
        for quick, slow_value in zip(fast, slow, strict=True)
    ]


@dataclass(slots=True)
class AwesomeOscillatorState:
    """O(1)-per-candle Awesome Oscillator state over two median-price averages."""

    fast_period: int = 5
    slow_period: int = 34
    min_history: int = field(init=False)
    _fast: SmaState = field(init=False)
    _slow: SmaState = field(init=False)

    def __post_init__(self) -> None:
        if self.fast_period <= 0 or self.slow_period <= 0:
            raise ValueError("periods must be positive")
        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be shorter than slow_period")
        self.min_history = self.slow_period
        self._fast = SmaState(self.fast_period)
        self._slow = SmaState(self.slow_period)

    @property
    def warmed_up(self) -> bool:
        return self._slow.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._fast.reset()
        self._slow.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        median = (candle.high + candle.low) / 2.0
        fast = self._fast.update(median)
        slow = self._slow.update(median)
        return NAN if isnan(fast) or isnan(slow) else fast - slow

    def current(self) -> float:
        fast = self._fast.current()
        slow = self._slow.current()
        return NAN if isnan(fast) or isnan(slow) else fast - slow


def ppo(
    candles: Sequence[Candle],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> list[PpoValue]:
    """Compute the percentage price oscillator, MACD scaled by the slow EMA (§2.5)."""
    if fast_period <= 0 or slow_period <= 0 or signal_period <= 0:
        raise ValueError("periods must be positive")
    if fast_period >= slow_period:
        raise ValueError("fast_period must be shorter than slow_period")
    closes = [candle.close for candle in candles]
    fast = ema(closes, fast_period)
    slow = ema(closes, slow_period)
    line = [
        NAN
        if isnan(quick) or isnan(base)
        # A zero slow average would need a zero price, which the candle contract
        # already rejects; the substitute exists so the helper stays total.
        else 100.0 * safe_divide(quick - base, base, on_zero=0.0)
        for quick, base in zip(fast, slow, strict=True)
    ]
    signal = ema(line, signal_period)
    return [
        {
            "ppo": ppo_value,
            "signal": signal_value,
            "histogram": NAN
            if isnan(ppo_value) or isnan(signal_value)
            else ppo_value - signal_value,
        }
        for ppo_value, signal_value in zip(line, signal, strict=True)
    ]


@dataclass(slots=True)
class PPOState:
    """O(1)-per-candle percentage price oscillator state."""

    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    min_history: int = field(init=False)
    _fast: EmaState = field(init=False)
    _slow: EmaState = field(init=False)
    _signal: EmaState = field(init=False)
    _value: PpoValue = field(
        init=False,
        default_factory=lambda: {"ppo": NAN, "signal": NAN, "histogram": NAN},
    )

    def __post_init__(self) -> None:
        if self.fast_period <= 0 or self.slow_period <= 0 or self.signal_period <= 0:
            raise ValueError("periods must be positive")
        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be shorter than slow_period")
        self.min_history = self.slow_period + self.signal_period - 1
        self._fast = EmaState(self.fast_period)
        self._slow = EmaState(self.slow_period)
        self._signal = EmaState(self.signal_period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["signal"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._fast.reset()
        self._slow.reset()
        self._signal.reset()
        self._value = {"ppo": NAN, "signal": NAN, "histogram": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> PpoValue:
        fast = self._fast.update(candle.close)
        slow = self._slow.update(candle.close)
        line = (
            NAN
            if isnan(fast) or isnan(slow)
            else 100.0 * safe_divide(fast - slow, slow, on_zero=0.0)
        )
        signal = self._signal.update(line)
        self._value = {
            "ppo": line,
            "signal": signal,
            "histogram": NAN if isnan(line) or isnan(signal) else line - signal,
        }
        return self.current()

    def current(self) -> PpoValue:
        return dict(self._value)


def accelerator_oscillator(
    candles: Sequence[Candle],
    fast_period: int = 5,
    slow_period: int = 34,
    smooth_period: int = 5,
) -> list[float]:
    """Compute the Accelerator Oscillator, ``AO - SMA(AO, 5)`` (§2.13)."""
    if smooth_period <= 0:
        raise ValueError("smooth_period must be positive")
    oscillator = awesome_oscillator(candles, fast_period, slow_period)
    smoothed = sma(oscillator, smooth_period)
    return [
        NAN if isnan(value) or isnan(average) else value - average
        for value, average in zip(oscillator, smoothed, strict=True)
    ]


@dataclass(slots=True)
class AcceleratorOscillatorState:
    """O(1)-per-candle Accelerator Oscillator state over the Awesome Oscillator."""

    fast_period: int = 5
    slow_period: int = 34
    smooth_period: int = 5
    min_history: int = field(init=False)
    _oscillator: AwesomeOscillatorState = field(init=False)
    _smoothed: SmaState = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if self.smooth_period <= 0:
            raise ValueError("smooth_period must be positive")
        self._oscillator = AwesomeOscillatorState(
            fast_period=self.fast_period,
            slow_period=self.slow_period,
        )
        self._smoothed = SmaState(self.smooth_period)
        self.min_history = self._oscillator.min_history + self.smooth_period - 1

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._oscillator.seed(())
        self._smoothed.reset()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        oscillator = self._oscillator.update(candle)
        average = self._smoothed.update(oscillator)
        self._value = NAN if isnan(oscillator) or isnan(average) else oscillator - average
        return self.current()

    def current(self) -> float:
        return self._value


def smi(
    candles: Sequence[Candle],
    period: int = 13,
    long_period: int = 25,
    short_period: int = 13,
    signal_period: int = 3,
) -> list[SmiValue]:
    """Compute the Stochastic Momentum Index and its signal (§2.27).

    The standard lists more than one parameter set and asks that the adopted one
    be stated. This repository takes Blau's original 13/25/13 with a 3-period
    signal, which also matches the double smoothing already used for TSI.
    """
    if min(period, long_period, short_period, signal_period) <= 0:
        raise ValueError("periods must be positive")
    highest = hh([candle.high for candle in candles], period)
    lowest = ll([candle.low for candle in candles], period)
    distances: list[float] = []
    ranges: list[float] = []
    for candle, high, low in zip(candles, highest, lowest, strict=True):
        if isnan(high) or isnan(low):
            distances.append(NAN)
            ranges.append(NAN)
            continue
        distances.append(candle.close - (high + low) / 2.0)
        ranges.append((high - low) / 2.0)
    smoothed = ema(ema(distances, long_period), short_period)
    smoothed_range = ema(ema(ranges, long_period), short_period)
    line = [
        NAN
        if isnan(numerator) or isnan(denominator)
        # §2.27 states the degenerate rule for this one: "분모 0 → 0".
        else 100.0 * safe_divide(numerator, denominator, on_zero=0.0)
        for numerator, denominator in zip(smoothed, smoothed_range, strict=True)
    ]
    signal = ema(line, signal_period)
    return [
        {"smi": smi_value, "signal": signal_value}
        for smi_value, signal_value in zip(line, signal, strict=True)
    ]


@dataclass(slots=True)
class SMIState:
    """O(1)-per-candle Stochastic Momentum Index state."""

    period: int = 13
    long_period: int = 25
    short_period: int = 13
    signal_period: int = 3
    min_history: int = field(init=False)
    _highest: RollingExtremeState = field(init=False)
    _lowest: RollingExtremeState = field(init=False)
    _distance_long: EmaState = field(init=False)
    _distance_short: EmaState = field(init=False)
    _range_long: EmaState = field(init=False)
    _range_short: EmaState = field(init=False)
    _signal: EmaState = field(init=False)
    _value: SmiValue = field(init=False, default_factory=lambda: {"smi": NAN, "signal": NAN})

    def __post_init__(self) -> None:
        if min(self.period, self.long_period, self.short_period, self.signal_period) <= 0:
            raise ValueError("periods must be positive")
        self.min_history = (
            self.period + self.long_period + self.short_period + self.signal_period - 3
        )
        self._highest = RollingExtremeState(self.period, highest=True)
        self._lowest = RollingExtremeState(self.period, highest=False)
        self._distance_long = EmaState(self.long_period)
        self._distance_short = EmaState(self.short_period)
        self._range_long = EmaState(self.long_period)
        self._range_short = EmaState(self.short_period)
        self._signal = EmaState(self.signal_period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["signal"])

    def seed(self, candles: Sequence[Candle]) -> None:
        for state in (
            self._highest,
            self._lowest,
            self._distance_long,
            self._distance_short,
            self._range_long,
            self._range_short,
            self._signal,
        ):
            state.reset()
        self._value = {"smi": NAN, "signal": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> SmiValue:
        highest = self._highest.update(candle.high)
        lowest = self._lowest.update(candle.low)
        if isnan(highest) or isnan(lowest):
            distance = NAN
            price_range = NAN
        else:
            distance = candle.close - (highest + lowest) / 2.0
            price_range = (highest - lowest) / 2.0
        smoothed = self._distance_short.update(self._distance_long.update(distance))
        smoothed_range = self._range_short.update(self._range_long.update(price_range))
        line = (
            NAN
            if isnan(smoothed) or isnan(smoothed_range)
            else 100.0 * safe_divide(smoothed, smoothed_range, on_zero=0.0)
        )
        self._value = {"smi": line, "signal": self._signal.update(line)}
        return self.current()

    def current(self) -> SmiValue:
        return dict(self._value)
