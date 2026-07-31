"""Define required momentum indicators and the follow-up momentum catalog."""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isnan, log
from typing import ClassVar

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
    roc,
    safe_divide,
    sma,
    tp,
    wma,
)

StochasticValue = dict[str, float]
MacdValue = dict[str, float]
PpoValue = dict[str, float]
SmiValue = dict[str, float]
StochRsiValue = dict[str, float]
KstValue = dict[str, float]
FisherValue = dict[str, float]

FOLLOW_UP_INDICATORS = (
    "Connors RSI",
    "QStick",
    "Chande Forecast Oscillator",
    "DeMarker",
    "DPO",
    "Schaff Trend Cycle",
    "Relative Vigor Index",
    "Laguerre RSI",
    "Pretty Good Oscillator",
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


def stochastic_rsi(
    candles: Sequence[Candle],
    rsi_period: int = 14,
    stochastic_period: int = 14,
    smooth_k: int = 3,
    smooth_d: int = 3,
) -> list[StochRsiValue]:
    """Normalize RSI through a stochastic window and smooth it twice (§2.3)."""
    if min(rsi_period, stochastic_period, smooth_k, smooth_d) <= 0:
        raise ValueError("periods must be positive")
    strength = rsi(candles, rsi_period)
    highest = hh(strength, stochastic_period)
    lowest = ll(strength, stochastic_period)
    raw: list[float] = []
    for value, high, low in zip(strength, highest, lowest, strict=True):
        if isnan(value) or isnan(high) or isnan(low):
            raw.append(NAN)
            continue
        # A flat RSI window has no position to report inside itself; the midpoint
        # is the neutral reading and keeps the value finite. §2.3 is silent here.
        raw.append(100.0 * safe_divide(value - low, high - low, on_zero=0.5))
    percent_k = sma(raw, smooth_k)
    percent_d = sma(percent_k, smooth_d)
    return [
        {"percent_k": k_value, "percent_d": d_value}
        for k_value, d_value in zip(percent_k, percent_d, strict=True)
    ]


@dataclass(slots=True)
class StochasticRSIState:
    """O(1)-per-candle Stochastic RSI state over an RSI state and two averages."""

    rsi_period: int = 14
    stochastic_period: int = 14
    smooth_k: int = 3
    smooth_d: int = 3
    min_history: int = field(init=False)
    _rsi: RSIState = field(init=False)
    _highest: RollingExtremeState = field(init=False)
    _lowest: RollingExtremeState = field(init=False)
    _smooth_k: SmaState = field(init=False)
    _smooth_d: SmaState = field(init=False)
    _value: StochRsiValue = field(
        init=False,
        default_factory=lambda: {"percent_k": NAN, "percent_d": NAN},
    )

    def __post_init__(self) -> None:
        if min(self.rsi_period, self.stochastic_period, self.smooth_k, self.smooth_d) <= 0:
            raise ValueError("periods must be positive")
        self._rsi = RSIState(period=self.rsi_period)
        self._highest = RollingExtremeState(self.stochastic_period, highest=True)
        self._lowest = RollingExtremeState(self.stochastic_period, highest=False)
        self._smooth_k = SmaState(self.smooth_k)
        self._smooth_d = SmaState(self.smooth_d)
        self.min_history = (
            self._rsi.min_history + self.stochastic_period + self.smooth_k + self.smooth_d - 3
        )

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["percent_d"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._rsi.seed(())
        for state in (self._highest, self._lowest, self._smooth_k, self._smooth_d):
            state.reset()
        self._value = {"percent_k": NAN, "percent_d": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> StochRsiValue:
        strength = self._rsi.update(candle)
        high = self._highest.update(strength)
        low = self._lowest.update(strength)
        if isnan(strength) or isnan(high) or isnan(low):
            raw = NAN
        else:
            raw = 100.0 * safe_divide(strength - low, high - low, on_zero=0.5)
        percent_k = self._smooth_k.update(raw)
        percent_d = self._smooth_d.update(percent_k)
        self._value = {"percent_k": percent_k, "percent_d": percent_d}
        return self.current()

    def current(self) -> StochRsiValue:
        return dict(self._value)


def trix(candles: Sequence[Candle], period: int = 15) -> list[float]:
    """Compute the percentage rate of change of a triple EMA (§2.6)."""
    if period <= 0:
        raise ValueError("period must be positive")
    closes = [candle.close for candle in candles]
    third = ema(ema(ema(closes, period), period), period)
    result = [NAN]
    for previous, current in zip(third, third[1:], strict=False):
        if isnan(previous) or isnan(current):
            result.append(NAN)
        else:
            # §2.6 notes TA-Lib scales by 100 and some implementations by 10000;
            # this repository takes the TA-Lib scale the section names first.
            result.append(100.0 * safe_divide(current - previous, previous, on_zero=0.0))
    return result


@dataclass(slots=True)
class TRIXState:
    """O(1)-per-candle TRIX state over three chained EMAs."""

    period: int = 15
    min_history: int = field(init=False)
    _first: EmaState = field(init=False)
    _second: EmaState = field(init=False)
    _third: EmaState = field(init=False)
    _previous: float = field(init=False, default=NAN)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        # Three chained averages, then one more candle to have something to
        # compare the third against.
        self.min_history = 3 * self.period - 1
        self._first = EmaState(self.period)
        self._second = EmaState(self.period)
        self._third = EmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._first.reset()
        self._second.reset()
        self._third.reset()
        self._previous = NAN
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        third = self._third.update(self._second.update(self._first.update(candle.close)))
        if isnan(third) or isnan(self._previous):
            self._value = NAN
        else:
            self._value = 100.0 * safe_divide(third - self._previous, self._previous, on_zero=0.0)
        self._previous = third
        return self.current()

    def current(self) -> float:
        return self._value


def cmo(candles: Sequence[Candle], period: int = 14) -> list[float]:
    """Compute the Chande Momentum Oscillator from unsmoothed sums (§2.8)."""
    if period <= 0:
        raise ValueError("period must be positive")
    gains = [NAN]
    losses = [NAN]
    for previous, current in zip(candles, candles[1:], strict=False):
        change = current.close - previous.close
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    up_sums = sma(gains, period)
    down_sums = sma(losses, period)
    result: list[float] = []
    for up_value, down_value in zip(up_sums, down_sums, strict=True):
        if isnan(up_value) or isnan(down_value):
            result.append(NAN)
            continue
        # A window without any movement has no momentum to report; §2.8 gives no
        # substitute, so zero is the reading taken here.
        result.append(
            100.0 * safe_divide(up_value - down_value, up_value + down_value, on_zero=0.0)
        )
    return result


@dataclass(slots=True)
class CMOState:
    """O(1)-per-candle Chande Momentum Oscillator state over two rolling sums."""

    period: int = 14
    min_history: int = field(init=False)
    _previous_close: float | None = field(init=False, default=None)
    _gains: SmaState = field(init=False)
    _losses: SmaState = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period + 1
        self._gains = SmaState(self.period)
        self._losses = SmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._previous_close = None
        self._gains.reset()
        self._losses.reset()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        if self._previous_close is None:
            self._previous_close = candle.close
            self._gains.update(NAN)
            self._losses.update(NAN)
            self._value = NAN
            return self.current()
        change = candle.close - self._previous_close
        self._previous_close = candle.close
        up_value = self._gains.update(max(change, 0.0))
        down_value = self._losses.update(max(-change, 0.0))
        if isnan(up_value) or isnan(down_value):
            self._value = NAN
        else:
            self._value = 100.0 * safe_divide(
                up_value - down_value, up_value + down_value, on_zero=0.0
            )
        return self.current()

    def current(self) -> float:
        return self._value


def williams_r(candles: Sequence[Candle], period: int = 14) -> list[float]:
    """Compute Williams %R, the stochastic read from the high side (§2.9)."""
    if period <= 0:
        raise ValueError("period must be positive")
    highest = hh([candle.high for candle in candles], period)
    lowest = ll([candle.low for candle in candles], period)
    result: list[float] = []
    for candle, high, low in zip(candles, highest, lowest, strict=True):
        if isnan(high) or isnan(low):
            result.append(NAN)
            continue
        # A flat window puts price at both extremes at once; -50 is the midpoint
        # of the -100..0 range this indicator lives in. §2.9 is silent.
        result.append(-100.0 * safe_divide(high - candle.close, high - low, on_zero=0.5))
    return result


@dataclass(slots=True)
class WilliamsRState:
    """O(1)-per-candle Williams %R state over two rolling extremes."""

    period: int = 14
    min_history: int = field(init=False)
    _highest: RollingExtremeState = field(init=False)
    _lowest: RollingExtremeState = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period
        self._highest = RollingExtremeState(self.period, highest=True)
        self._lowest = RollingExtremeState(self.period, highest=False)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._highest.reset()
        self._lowest.reset()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        high = self._highest.update(candle.high)
        low = self._lowest.update(candle.low)
        if isnan(high) or isnan(low):
            self._value = NAN
        else:
            self._value = -100.0 * safe_divide(high - candle.close, high - low, on_zero=0.5)
        return self.current()

    def current(self) -> float:
        return self._value


def ultimate_oscillator(
    candles: Sequence[Candle],
    short_period: int = 7,
    medium_period: int = 14,
    long_period: int = 28,
) -> list[float]:
    """Weigh buying pressure over three windows into one oscillator (§2.11)."""
    periods = (short_period, medium_period, long_period)
    if min(periods) <= 0:
        raise ValueError("periods must be positive")
    pressures: list[float] = [NAN]
    ranges: list[float] = [NAN]
    for previous, current in zip(candles, candles[1:], strict=False):
        true_low = min(current.low, previous.close)
        pressures.append(current.close - true_low)
        ranges.append(max(current.high, previous.close) - true_low)
    averages = []
    for period in periods:
        pressure_sums = sma(pressures, period)
        range_sums = sma(ranges, period)
        averages.append(
            [
                NAN
                if isnan(pressure) or isnan(span)
                # A window with no true range at all cannot be weighed; the
                # midpoint keeps the weighted average finite. §2.11 is silent.
                else safe_divide(pressure, span, on_zero=0.5)
                for pressure, span in zip(pressure_sums, range_sums, strict=True)
            ]
        )
    weights = (4.0, 2.0, 1.0)
    total_weight = sum(weights)
    return [
        NAN
        if any(isnan(value) for value in values)
        else 100.0
        * sum(weight * value for weight, value in zip(weights, values, strict=True))
        / total_weight
        for values in zip(*averages, strict=True)
    ]


@dataclass(slots=True)
class UltimateOscillatorState:
    """O(1)-per-candle Ultimate Oscillator state over three window pairs."""

    short_period: int = 7
    medium_period: int = 14
    long_period: int = 28
    min_history: int = field(init=False)
    _previous_close: float | None = field(init=False, default=None)
    _pressures: list[SmaState] = field(init=False, default_factory=list)
    _ranges: list[SmaState] = field(init=False, default_factory=list)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        periods = (self.short_period, self.medium_period, self.long_period)
        if min(periods) <= 0:
            raise ValueError("periods must be positive")
        self.min_history = max(periods) + 1
        self._pressures = [SmaState(period) for period in periods]
        self._ranges = [SmaState(period) for period in periods]

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._previous_close = None
        for state in (*self._pressures, *self._ranges):
            state.reset()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        if self._previous_close is None:
            self._previous_close = candle.close
            pressure = NAN
            span = NAN
        else:
            true_low = min(candle.low, self._previous_close)
            pressure = candle.close - true_low
            span = max(candle.high, self._previous_close) - true_low
            self._previous_close = candle.close
        averages = []
        for pressure_state, range_state in zip(self._pressures, self._ranges, strict=True):
            pressure_sum = pressure_state.update(pressure)
            range_sum = range_state.update(span)
            averages.append(
                NAN
                if isnan(pressure_sum) or isnan(range_sum)
                else safe_divide(pressure_sum, range_sum, on_zero=0.5)
            )
        weights = (4.0, 2.0, 1.0)
        if any(isnan(value) for value in averages):
            self._value = NAN
        else:
            self._value = (
                100.0
                * sum(weight * value for weight, value in zip(weights, averages, strict=True))
                / sum(weights)
            )
        return self.current()

    def current(self) -> float:
        return self._value


_FISHER_CLAMP = 0.999


def _fisher_step(
    median: float,
    high: float,
    low: float,
    previous_x: float,
    previous_fisher: float,
) -> tuple[float, float]:
    """Advance one Fisher Transform step, returning the new x and value."""
    raw = 2.0 * safe_divide(median - low, high - low, on_zero=0.5) - 1.0
    current_x = 0.33 * raw + 0.67 * previous_x
    current_x = max(-_FISHER_CLAMP, min(_FISHER_CLAMP, current_x))
    value = 0.5 * log((1.0 + current_x) / (1.0 - current_x)) + 0.5 * previous_fisher
    return current_x, value


def fisher_transform(candles: Sequence[Candle], period: int = 9) -> list[FisherValue]:
    """Normalize median price and apply the inverse hyperbolic transform (§2.14)."""
    if period <= 0:
        raise ValueError("period must be positive")
    median = hl2(candles)
    highest = hh(median, period)
    lowest = ll(median, period)
    result: list[FisherValue] = []
    current_x = 0.0
    previous_fisher = 0.0
    for value, high, low in zip(median, highest, lowest, strict=True):
        if isnan(high) or isnan(low):
            result.append({"fisher": NAN, "signal": NAN})
            continue
        signal = previous_fisher if result and not isnan(result[-1]["fisher"]) else NAN
        current_x, previous_fisher = _fisher_step(value, high, low, current_x, previous_fisher)
        result.append({"fisher": previous_fisher, "signal": signal})
    return result


@dataclass(slots=True)
class FisherTransformState:
    """O(1)-per-candle Fisher Transform state over median-price extremes."""

    period: int = 9
    min_history: int = field(init=False)
    _median_high: RollingExtremeState = field(init=False)
    _median_low: RollingExtremeState = field(init=False)
    _x: float = field(init=False, default=0.0)
    _fisher: float = field(init=False, default=0.0)
    _value: FisherValue = field(
        init=False,
        default_factory=lambda: {"fisher": NAN, "signal": NAN},
    )

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        # One candle produces the first value; the signal is that value delayed,
        # so a second candle is needed before both outputs exist.
        self.min_history = self.period + 1
        self._median_high = RollingExtremeState(self.period, highest=True)
        self._median_low = RollingExtremeState(self.period, highest=False)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["signal"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._median_high.reset()
        self._median_low.reset()
        self._x = 0.0
        self._fisher = 0.0
        self._value = {"fisher": NAN, "signal": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> FisherValue:
        median = (candle.high + candle.low) / 2.0
        high = self._median_high.update(median)
        low = self._median_low.update(median)
        if isnan(high) or isnan(low):
            self._value = {"fisher": NAN, "signal": NAN}
            return self.current()
        signal = self._fisher if not isnan(self._value["fisher"]) else NAN
        self._x, self._fisher = _fisher_step(median, high, low, self._x, self._fisher)
        self._value = {"fisher": self._fisher, "signal": signal}
        return self.current()

    def current(self) -> FisherValue:
        return dict(self._value)


def kst(candles: Sequence[Candle]) -> list[KstValue]:
    """Sum four smoothed rates of change with rising weights (§2.24)."""
    closes = [candle.close for candle in candles]
    parts = [
        (sma(roc(closes, 10), 10), 1.0),
        (sma(roc(closes, 15), 10), 2.0),
        (sma(roc(closes, 20), 10), 3.0),
        (sma(roc(closes, 30), 15), 4.0),
    ]
    line: list[float] = []
    for values in zip(*(series for series, _ in parts), strict=True):
        if any(isnan(value) for value in values):
            line.append(NAN)
            continue
        line.append(sum(value * weight for value, (_, weight) in zip(values, parts, strict=True)))
    signal = sma(line, 9)
    return [
        {"kst": kst_value, "signal": signal_value}
        for kst_value, signal_value in zip(line, signal, strict=True)
    ]


@dataclass(slots=True)
class KSTState:
    """O(1)-per-candle Know Sure Thing state over four smoothed rate-of-change legs."""

    min_history: int = field(init=False, default=53)
    _closes: deque[float] = field(init=False, default_factory=lambda: deque(maxlen=31))
    _legs: list[SmaState] = field(init=False, default_factory=list)
    _signal: SmaState = field(init=False, default_factory=lambda: SmaState(9))
    _value: KstValue = field(init=False, default_factory=lambda: {"kst": NAN, "signal": NAN})

    _SPANS: ClassVar[tuple[tuple[int, int, float], ...]] = (
        (10, 10, 1.0),
        (15, 10, 2.0),
        (20, 10, 3.0),
        (30, 15, 4.0),
    )

    def __post_init__(self) -> None:
        self._legs = [SmaState(smooth) for _, smooth, _ in self._SPANS]

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["signal"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._closes.clear()
        for state in self._legs:
            state.reset()
        self._signal.reset()
        self._value = {"kst": NAN, "signal": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> KstValue:
        self._closes.append(candle.close)
        smoothed: list[float] = []
        for (span, _, _), state in zip(self._SPANS, self._legs, strict=True):
            if len(self._closes) <= span:
                change = NAN
            else:
                previous = self._closes[len(self._closes) - 1 - span]
                change = (
                    NAN if previous == 0.0 else 100.0 * (self._closes[-1] - previous) / previous
                )
            smoothed.append(state.update(change))
        if any(isnan(value) for value in smoothed):
            line = NAN
        else:
            line = sum(
                value * weight for value, (_, _, weight) in zip(smoothed, self._SPANS, strict=True)
            )
        self._value = {"kst": line, "signal": self._signal.update(line)}
        return self.current()

    def current(self) -> KstValue:
        return dict(self._value)


def coppock_curve(
    candles: Sequence[Candle],
    long_period: int = 14,
    short_period: int = 11,
    smooth_period: int = 10,
) -> list[float]:
    """Smooth the sum of two rates of change with a weighted average (§2.25)."""
    if min(long_period, short_period, smooth_period) <= 0:
        raise ValueError("periods must be positive")
    closes = [candle.close for candle in candles]
    long_change = roc(closes, long_period)
    short_change = roc(closes, short_period)
    combined = [
        NAN if isnan(first) or isnan(second) else first + second
        for first, second in zip(long_change, short_change, strict=True)
    ]
    return wma(combined, smooth_period)


@dataclass(slots=True)
class CoppockCurveState:
    """O(period)-per-candle Coppock Curve state; the weighted average needs its window."""

    long_period: int = 14
    short_period: int = 11
    smooth_period: int = 10
    min_history: int = field(init=False)
    _closes: deque[float] = field(init=False)
    _combined: deque[float] = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if min(self.long_period, self.short_period, self.smooth_period) <= 0:
            raise ValueError("periods must be positive")
        self.min_history = self.long_period + self.smooth_period
        self._closes = deque(maxlen=self.long_period + 1)
        self._combined = deque(maxlen=self.smooth_period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._closes.clear()
        self._combined.clear()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        self._closes.append(candle.close)
        changes: list[float] = []
        for span in (self.long_period, self.short_period):
            if len(self._closes) <= span:
                changes.append(NAN)
                continue
            previous = self._closes[len(self._closes) - 1 - span]
            changes.append(
                NAN if previous == 0.0 else 100.0 * (self._closes[-1] - previous) / previous
            )
        combined = NAN if any(isnan(value) for value in changes) else sum(changes)
        self._combined.append(combined)
        if len(self._combined) < self.smooth_period or any(
            isnan(value) for value in self._combined
        ):
            self._value = NAN
            return self.current()
        denominator = self.smooth_period * (self.smooth_period + 1) / 2.0
        self._value = (
            sum(weight * value for weight, value in enumerate(self._combined, start=1))
            / denominator
        )
        return self.current()

    def current(self) -> float:
        return self._value
