"""Define required momentum indicators and the follow-up momentum catalog."""

from collections import deque
from collections.abc import Callable, Sequence
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
    linreg,
    ll,
    rma,
    roc,
    safe_divide,
    sma,
    tp,
    wma,
)
from .volatility import ATRState, atr

StochasticValue = dict[str, float]
MacdValue = dict[str, float]
PpoValue = dict[str, float]
SmiValue = dict[str, float]
StochRsiValue = dict[str, float]
KstValue = dict[str, float]
FisherValue = dict[str, float]
RviValue = dict[str, float]

FOLLOW_UP_INDICATORS = ("Special K",)


def _rsi_value(average_gain: float, average_loss: float) -> float:
    if average_loss == 0.0:
        return 100.0
    if average_gain == 0.0:
        return 0.0
    relative_strength = average_gain / average_loss
    return 100.0 - 100.0 / (1.0 + relative_strength)


def _rsi_from_values(values: Sequence[float], period: int) -> list[float]:
    """Compute Wilder RSI over any series, not only over closes (§2.1 + §0.5).

    §2.15 applies RSI a second time to a series of streak lengths rather than to
    prices, so the calculation has to be reachable without a candle. Keeping one
    body here is what stops that second application from becoming a second RSI.
    """

    if period <= 0:
        raise ValueError("period must be positive")
    gains = [NAN]
    losses = [NAN]
    for previous, current in zip(values, values[1:], strict=False):
        change = current - previous
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


def rsi(candles: Sequence[Candle], period: int = 14) -> list[float]:
    """Compute Wilder RSI from close-price deltas."""
    return _rsi_from_values([candle.close for candle in candles], period)


@dataclass(slots=True)
class _RSIValueState:
    """O(1)-per-value Wilder RSI over any series; the candle-facing state wraps it."""

    period: int = 14
    _previous: float | None = field(init=False, default=None)
    _gains: RmaState = field(init=False)
    _losses: RmaState = field(init=False)
    _value: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self._gains = RmaState(self.period)
        self._losses = RmaState(self.period)

    def reset(self) -> None:
        """Drop the previous observation and both Wilder averages."""
        self._previous = None
        self._gains.reset()
        self._losses.reset()
        self._value = None

    @property
    def warmed_up(self) -> bool:
        """Return whether both Wilder averages have produced a value."""
        return self._value is not None

    def update(self, value: float) -> float:
        """Advance one observation and return the current RSI."""
        if self._previous is None:
            self._previous = value
            return NAN

        change = value - self._previous
        self._previous = value
        average_gain = self._gains.update(max(change, 0.0))
        average_loss = self._losses.update(max(-change, 0.0))
        if not isnan(average_gain) and not isnan(average_loss):
            self._value = _rsi_value(average_gain, average_loss)
        return self.current()

    def current(self) -> float:
        """Return the latest RSI, or NaN while warming up."""
        return self._value if self._value is not None else NAN


@dataclass(slots=True)
class RSIState:
    """O(1)-per-candle Wilder RSI state."""

    period: int = 14
    min_history: int = field(init=False)
    _inner: _RSIValueState = field(init=False)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period + 1
        self._inner = _RSIValueState(self.period)

    @property
    def warmed_up(self) -> bool:
        return self._inner.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._inner.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        return self._inner.update(candle.close)

    def current(self) -> float:
        return self._inner.current()


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


def _macd_line(values: Sequence[float], fast_period: int, slow_period: int) -> list[float]:
    """Return the MACD line alone: the fast EMA minus the slow one (§2.4).

    §2.20 asks for `MACD(C, 23, 50)` with no signal line at all, so the line is
    separated from the three-output indicator rather than recomputed there.
    """

    if fast_period <= 0 or slow_period <= 0:
        raise ValueError("periods must be positive")
    if fast_period >= slow_period:
        raise ValueError("fast_period must be shorter than slow_period")
    fast = ema(values, fast_period)
    slow = ema(values, slow_period)
    return [
        NAN if isnan(quick) or isnan(slow_value) else quick - slow_value
        for quick, slow_value in zip(fast, slow, strict=True)
    ]


@dataclass(slots=True)
class _MacdLineState:
    """O(1)-per-value MACD line over two EMAs of the same series."""

    fast_period: int = 12
    slow_period: int = 26
    _fast: EmaState = field(init=False)
    _slow: EmaState = field(init=False)

    def __post_init__(self) -> None:
        if self.fast_period <= 0 or self.slow_period <= 0:
            raise ValueError("periods must be positive")
        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be shorter than slow_period")
        self._fast = EmaState(self.fast_period)
        self._slow = EmaState(self.slow_period)

    def reset(self) -> None:
        """Drop both averages."""
        self._fast.reset()
        self._slow.reset()

    def update(self, value: float) -> float:
        """Advance one observation and return the current MACD line."""
        fast = self._fast.update(value)
        slow = self._slow.update(value)
        return NAN if isnan(fast) or isnan(slow) else fast - slow


def macd(
    candles: Sequence[Candle],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> list[MacdValue]:
    """Compute MACD, its signal line, and the histogram (§2.4)."""
    if signal_period <= 0:
        raise ValueError("periods must be positive")
    closes = [candle.close for candle in candles]
    line = _macd_line(closes, fast_period, slow_period)
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
    _line: _MacdLineState = field(init=False)
    _signal: EmaState = field(init=False)
    _value: MacdValue = field(
        init=False,
        default_factory=lambda: {"macd": NAN, "signal": NAN, "histogram": NAN},
    )

    def __post_init__(self) -> None:
        if self.signal_period <= 0:
            raise ValueError("periods must be positive")
        # The MACD line starts with the slow average; the signal then needs its
        # own period of MACD values, the first of which lands on that candle.
        self.min_history = self.slow_period + self.signal_period - 1
        self._line = _MacdLineState(self.fast_period, self.slow_period)
        self._signal = EmaState(self.signal_period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["signal"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._line.reset()
        self._signal.reset()
        self._value = {"macd": NAN, "signal": NAN, "histogram": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> MacdValue:
        line = self._line.update(candle.close)
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


def _streak_series(values: Sequence[float]) -> list[float]:
    """Return §2.15's signed run length: how many bars the direction has held.

    The first bar has no predecessor and therefore no direction, so it starts the
    series at zero, and an unchanged value resets the run the same way.
    """

    result: list[float] = []
    streak = 0.0
    previous: float | None = None
    for value in values:
        if previous is None or value == previous:
            streak = 0.0
        elif value > previous:
            streak = streak + 1.0 if streak > 0.0 else 1.0
        else:
            streak = streak - 1.0 if streak < 0.0 else -1.0
        result.append(streak)
        previous = value
    return result


def _percent_rank(window: Sequence[float], value: float, period: int) -> float:
    """Return the percentage of a completed window that sits below ``value``.

    §2.15 asks for "the percentile of ROC(C,1) within the most recent 100 bars"
    and stops there, which leaves two boundaries open. Both are settled here and
    stated rather than left to be read off the code:

    - The ranked bar is **not** a member of the window it is ranked against. The
      window passed in holds bars t-100 through t-1, following Connors' own
      definition, which ranks the current change against the previous hundred. A
      self-inclusive window would cap the result at 99 because a value is never
      below itself; this one reaches the full 0-100 range.
    - The comparison is **strict**. A change equal to one already in the window
      does not count that bar as below it, so a run of identical changes ranks at
      zero rather than climbing on ties.

    Neither choice departs from §2.15, which fixes neither; picking the other side
    of either boundary would also be within it.
    """

    if len(window) < period or isnan(value) or any(isnan(item) for item in window):
        return NAN
    below = sum(1 for item in window if item < value)
    return 100.0 * below / period


def connors_rsi(
    candles: Sequence[Candle],
    rsi_period: int = 3,
    streak_period: int = 2,
    rank_period: int = 100,
) -> list[float]:
    """Average a price RSI, a streak RSI, and a rate-of-change percentile (§2.15)."""
    if min(rsi_period, streak_period, rank_period) <= 0:
        raise ValueError("periods must be positive")
    closes = [candle.close for candle in candles]
    price_rsi = _rsi_from_values(closes, rsi_period)
    streak_rsi = _rsi_from_values(_streak_series(closes), streak_period)
    changes = roc(closes, 1)
    result: list[float] = []
    for index in range(len(closes)):
        start = index - rank_period
        rank = (
            NAN if start < 0 else _percent_rank(changes[start:index], changes[index], rank_period)
        )
        parts = (price_rsi[index], streak_rsi[index], rank)
        result.append(NAN if any(isnan(part) for part in parts) else sum(parts) / 3.0)
    return result


@dataclass(slots=True)
class ConnorsRSIState:
    """O(rank_period)-per-candle Connors RSI state; the percentile needs its window."""

    rsi_period: int = 3
    streak_period: int = 2
    rank_period: int = 100
    min_history: int = field(init=False)
    _price: _RSIValueState = field(init=False)
    _streak_rsi: _RSIValueState = field(init=False)
    _previous_close: float | None = field(init=False, default=None)
    _streak: float = field(init=False, default=0.0)
    _changes: deque[float] = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if min(self.rsi_period, self.streak_period, self.rank_period) <= 0:
            raise ValueError("periods must be positive")
        # The percentile is the slowest leg: it ranks the current change against the
        # `rank_period` changes before it, and the very first bar has no change at
        # all, so the window is only complete one bar later than the count suggests.
        self.min_history = max(self.rsi_period, self.streak_period, self.rank_period + 1) + 1
        self._price = _RSIValueState(self.rsi_period)
        self._streak_rsi = _RSIValueState(self.streak_period)
        self._changes = deque(maxlen=self.rank_period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._price.reset()
        self._streak_rsi.reset()
        self._previous_close = None
        self._streak = 0.0
        self._changes.clear()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        close = candle.close
        previous = self._previous_close
        if previous is None or close == previous:
            self._streak = 0.0
        elif close > previous:
            self._streak = self._streak + 1.0 if self._streak > 0.0 else 1.0
        else:
            self._streak = self._streak - 1.0 if self._streak < 0.0 else -1.0
        if previous is None or previous == 0.0:
            change = NAN
        else:
            change = 100.0 * (close - previous) / previous

        price_rsi = self._price.update(close)
        streak_rsi = self._streak_rsi.update(self._streak)
        # Ranked before the append, so the window holds the changes strictly
        # before this bar, matching the batch path's `changes[start:index]`.
        rank = _percent_rank(self._changes, change, self.rank_period)
        self._changes.append(change)
        self._previous_close = close

        parts = (price_rsi, streak_rsi, rank)
        self._value = NAN if any(isnan(part) for part in parts) else sum(parts) / 3.0
        return self.current()

    def current(self) -> float:
        return self._value


def qstick(candles: Sequence[Candle], period: int = 8) -> list[float]:
    """Average the candle body, close minus open (§2.16)."""
    return sma([candle.close - candle.open for candle in candles], period)


@dataclass(slots=True)
class QStickState:
    """O(1)-per-candle QStick state over the rolling average of the body."""

    period: int = 8
    min_history: int = field(init=False)
    _average: SmaState = field(init=False)

    def __post_init__(self) -> None:
        self.min_history = self.period
        self._average = SmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return self._average.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._average.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        return self._average.update(candle.close - candle.open)

    def current(self) -> float:
        return self._average.current()


def chande_forecast_oscillator(candles: Sequence[Candle], period: int = 14) -> list[float]:
    """Measure the close against its own regression estimate (§2.17 + §14)."""
    closes = [candle.close for candle in candles]
    forecasts = linreg(closes, period)
    return [
        NAN if isnan(forecast) else safe_divide(100.0 * (close - forecast), close, on_zero=0.0)
        for close, forecast in zip(closes, forecasts, strict=True)
    ]


@dataclass(slots=True)
class ChandeForecastOscillatorState:
    """O(period)-per-candle Chande Forecast state; the regression needs its window."""

    period: int = 14
    min_history: int = field(init=False)
    _closes: deque[float] = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period
        self._closes = deque(maxlen=self.period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._closes.clear()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        self._closes.append(candle.close)
        if len(self._closes) < self.period:
            self._value = NAN
            return self.current()
        # The regression itself comes from the primitive rather than from a second
        # least-squares written out here, which is what keeps the two paths equal.
        forecast = linreg(list(self._closes), self.period)[-1]
        self._value = (
            NAN
            if isnan(forecast)
            else safe_divide(100.0 * (candle.close - forecast), candle.close, on_zero=0.0)
        )
        return self.current()

    def current(self) -> float:
        return self._value


def _demarker_value(high_average: float, low_average: float, previous: float) -> float:
    """Return DeMax's share of the two averages, keeping the previous value when flat.

    §2.18 gives no substitute for a window in which neither the high rose nor the low
    fell. §0.11 offers the previous value as one of the three answers an indicator may
    name, and §2.2 already sets that precedent in this document for a flat window, so
    that is the branch taken here; the caller starts it at the neutral 0.5.
    """

    return safe_divide(high_average, high_average + low_average, on_zero=previous)


DEMARKER_FLAT_START = 0.5


def demarker(candles: Sequence[Candle], period: int = 14) -> list[float]:
    """Compare rising highs with falling lows over a window (§2.18)."""
    rising = [NAN]
    falling = [NAN]
    for previous, current in zip(candles, candles[1:], strict=False):
        rising.append(max(current.high - previous.high, 0.0))
        falling.append(max(previous.low - current.low, 0.0))
    high_averages = sma(rising, period)
    low_averages = sma(falling, period)
    result: list[float] = []
    previous_value = DEMARKER_FLAT_START
    for high_average, low_average in zip(high_averages, low_averages, strict=True):
        if isnan(high_average) or isnan(low_average):
            result.append(NAN)
            continue
        value = _demarker_value(high_average, low_average, previous_value)
        previous_value = value
        result.append(value)
    return result


@dataclass(slots=True)
class DeMarkerState:
    """O(1)-per-candle DeMarker state over two rolling averages."""

    period: int = 14
    min_history: int = field(init=False)
    _rising: SmaState = field(init=False)
    _falling: SmaState = field(init=False)
    _previous_high: float | None = field(init=False, default=None)
    _previous_low: float | None = field(init=False, default=None)
    _previous_value: float = field(init=False, default=DEMARKER_FLAT_START)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        # Both differences need a preceding candle, so the averages start one bar
        # later than their own period.
        self.min_history = self.period + 1
        self._rising = SmaState(self.period)
        self._falling = SmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._rising.reset()
        self._falling.reset()
        self._previous_high = None
        self._previous_low = None
        self._previous_value = DEMARKER_FLAT_START
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        if self._previous_high is None or self._previous_low is None:
            rising = NAN
            falling = NAN
        else:
            rising = max(candle.high - self._previous_high, 0.0)
            falling = max(self._previous_low - candle.low, 0.0)
        self._previous_high = candle.high
        self._previous_low = candle.low
        high_average = self._rising.update(rising)
        low_average = self._falling.update(falling)
        if isnan(high_average) or isnan(low_average):
            self._value = NAN
            return self.current()
        self._value = _demarker_value(high_average, low_average, self._previous_value)
        self._previous_value = self._value
        return self.current()

    def current(self) -> float:
        return self._value


def dpo_shift(period: int) -> int:
    """Return §2.19's displacement, ``floor(n/2) + 1`` bars into the past."""
    if period <= 0:
        raise ValueError("period must be positive")
    return period // 2 + 1


def dpo(candles: Sequence[Candle], period: int = 20) -> list[float]:
    """Subtract a moving average from a past close to strip the trend (§2.19).

    The displacement reaches backwards. A chart that draws the average shifted
    forward is describing where the line is plotted, not which bars it is computed
    from; taking that literally would put bars after `t` into the value at `t`.
    Every term here is indexed at or before `t`.
    """

    shift = dpo_shift(period)
    closes = [candle.close for candle in candles]
    averages = sma(closes, period)
    result: list[float] = []
    for index, average in enumerate(averages):
        if isnan(average) or index < shift:
            result.append(NAN)
        else:
            result.append(closes[index - shift] - average)
    return result


@dataclass(slots=True)
class DPOState:
    """O(1)-per-candle Detrended Price Oscillator state."""

    period: int = 20
    min_history: int = field(init=False)
    _shift: int = field(init=False)
    _average: SmaState = field(init=False)
    _closes: deque[float] = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        self._shift = dpo_shift(self.period)
        self.min_history = max(self.period, self._shift + 1)
        self._average = SmaState(self.period)
        self._closes = deque(maxlen=self._shift + 1)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._average.reset()
        self._closes.clear()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        self._closes.append(candle.close)
        average = self._average.update(candle.close)
        if isnan(average) or len(self._closes) <= self._shift:
            self._value = NAN
            return self.current()
        # The deque is exactly `shift + 1` long, so its oldest entry is the close
        # `shift` bars back; nothing newer than the current candle is read.
        self._value = self._closes[0] - average
        return self.current()

    def current(self) -> float:
        return self._value


SCHAFF_SMOOTHING_FACTOR = 0.5


def _schaff_stage(values: Sequence[float], period: int) -> list[float]:
    """Run one stochastic-then-smooth stage of §2.20 over a series.

    §2.20 applies §2.2's ratio to a series rather than to candles, so the window's
    high and low come from the series itself. The flat-window rule is §2.2's: keep
    the previous ratio, starting at 50. The smoothing is the 0.5-factor recursion
    §2.20 attributes to the original author, seeded with the first ratio because the
    section fixes no seed of its own.
    """

    if period <= 0:
        raise ValueError("period must be positive")
    highest = hh(values, period)
    lowest = ll(values, period)
    result: list[float] = []
    previous_ratio = 50.0
    smoothed: float | None = None
    for value, high, low in zip(values, highest, lowest, strict=True):
        if isnan(value) or isnan(high) or isnan(low):
            result.append(NAN)
            continue
        ratio = safe_divide(100.0 * (value - low), high - low, on_zero=previous_ratio)
        previous_ratio = ratio
        smoothed = (
            ratio if smoothed is None else smoothed + SCHAFF_SMOOTHING_FACTOR * (ratio - smoothed)
        )
        result.append(smoothed)
    return result


@dataclass(slots=True)
class _SchaffStageState:
    """O(1)-per-value form of one §2.20 stage."""

    period: int = 10
    _highest: RollingExtremeState = field(init=False)
    _lowest: RollingExtremeState = field(init=False)
    _previous_ratio: float = field(init=False, default=50.0)
    _smoothed: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self._highest = RollingExtremeState(self.period, highest=True)
        self._lowest = RollingExtremeState(self.period, highest=False)

    def reset(self) -> None:
        """Clear both extremes and the smoothing recursion."""
        self._highest.reset()
        self._lowest.reset()
        self._previous_ratio = 50.0
        self._smoothed = None

    def update(self, value: float) -> float:
        """Advance one observation and return the smoothed ratio."""
        high = self._highest.update(value)
        low = self._lowest.update(value)
        if isnan(value) or isnan(high) or isnan(low):
            return NAN
        ratio = safe_divide(100.0 * (value - low), high - low, on_zero=self._previous_ratio)
        self._previous_ratio = ratio
        self._smoothed = (
            ratio
            if self._smoothed is None
            else self._smoothed + SCHAFF_SMOOTHING_FACTOR * (ratio - self._smoothed)
        )
        return self._smoothed


def schaff_trend_cycle(
    candles: Sequence[Candle],
    fast_period: int = 23,
    slow_period: int = 50,
    cycle_period: int = 10,
) -> list[float]:
    """Run a MACD line through two smoothed stochastic stages (§2.20)."""
    closes = [candle.close for candle in candles]
    line = _macd_line(closes, fast_period, slow_period)
    return _schaff_stage(_schaff_stage(line, cycle_period), cycle_period)


@dataclass(slots=True)
class SchaffTrendCycleState:
    """O(1)-per-candle Schaff Trend Cycle state over the MACD line and two stages."""

    fast_period: int = 23
    slow_period: int = 50
    cycle_period: int = 10
    min_history: int = field(init=False)
    _line: _MacdLineState = field(init=False)
    _first: _SchaffStageState = field(init=False)
    _second: _SchaffStageState = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if self.cycle_period <= 0:
            raise ValueError("periods must be positive")
        # The MACD line arrives with the slow average, and each stage then costs a
        # further window of its own before its first ratio exists.
        self.min_history = self.slow_period + 2 * (self.cycle_period - 1)
        self._line = _MacdLineState(self.fast_period, self.slow_period)
        self._first = _SchaffStageState(self.cycle_period)
        self._second = _SchaffStageState(self.cycle_period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._line.reset()
        self._first.reset()
        self._second.reset()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        self._value = self._second.update(self._first.update(self._line.update(candle.close)))
        return self.current()

    def current(self) -> float:
        return self._value


def _symmetric_weighted(window: Sequence[float]) -> float:
    """Return §2.21's four-term symmetric average of a window ordered oldest first."""
    return (window[3] + 2.0 * window[2] + 2.0 * window[1] + window[0]) / 6.0


SWMA_LENGTH = 4


def _swma(values: Sequence[float]) -> list[float]:
    """Apply §2.21's symmetric four-term weighting across a series."""
    result: list[float] = []
    window: deque[float] = deque(maxlen=SWMA_LENGTH)
    for value in values:
        window.append(value)
        if len(window) < SWMA_LENGTH or any(isnan(item) for item in window):
            result.append(NAN)
            continue
        result.append(_symmetric_weighted(window))
    return result


def relative_vigor_index(candles: Sequence[Candle], period: int = 10) -> list[RviValue]:
    """Weigh the body against the range with a symmetric filter (§2.21).

    This is Ehlers' Relative Vigor Index. §3.7 carries Dorsey's Relative Volatility
    Index under a colliding abbreviation and a completely different calculation.
    """

    numerators = sma(_swma([candle.close - candle.open for candle in candles]), period)
    denominators = sma(_swma([candle.high - candle.low for candle in candles]), period)
    line = [
        NAN
        if isnan(numerator) or isnan(denominator)
        # A window whose bars all have zero range carries no vigor to report, and
        # §0.11 lists zero as one of the substitutes a section may name.
        else safe_divide(numerator, denominator, on_zero=0.0)
        for numerator, denominator in zip(numerators, denominators, strict=True)
    ]
    signal = _swma(line)
    return [
        {"rvi": value, "signal": signal_value}
        for value, signal_value in zip(line, signal, strict=True)
    ]


@dataclass(slots=True)
class RelativeVigorIndexState:
    """O(1)-per-candle Relative Vigor Index state over three symmetric filters."""

    period: int = 10
    min_history: int = field(init=False)
    _bodies: deque[float] = field(init=False)
    _ranges: deque[float] = field(init=False)
    _line_window: deque[float] = field(init=False)
    _numerator: SmaState = field(init=False)
    _denominator: SmaState = field(init=False)
    _value: RviValue = field(
        init=False,
        default_factory=lambda: {"rvi": NAN, "signal": NAN},
    )

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        # Three filters stack: the body filter costs three bars, the rolling average
        # its own period, and the signal filter three more.
        self.min_history = self.period + 2 * (SWMA_LENGTH - 1)
        self._bodies = deque(maxlen=SWMA_LENGTH)
        self._ranges = deque(maxlen=SWMA_LENGTH)
        self._line_window = deque(maxlen=SWMA_LENGTH)
        self._numerator = SmaState(self.period)
        self._denominator = SmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["signal"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._bodies.clear()
        self._ranges.clear()
        self._line_window.clear()
        self._numerator.reset()
        self._denominator.reset()
        self._value = {"rvi": NAN, "signal": NAN}
        for candle in candles:
            self.update(candle)

    def _filtered(self, window: deque[float]) -> float:
        if len(window) < SWMA_LENGTH or any(isnan(item) for item in window):
            return NAN
        return _symmetric_weighted(window)

    def update(self, candle: Candle) -> RviValue:
        self._bodies.append(candle.close - candle.open)
        self._ranges.append(candle.high - candle.low)
        numerator = self._numerator.update(self._filtered(self._bodies))
        denominator = self._denominator.update(self._filtered(self._ranges))
        line = (
            NAN
            if isnan(numerator) or isnan(denominator)
            else safe_divide(numerator, denominator, on_zero=0.0)
        )
        self._line_window.append(line)
        self._value = {"rvi": line, "signal": self._filtered(self._line_window)}
        return self.current()

    def current(self) -> RviValue:
        return dict(self._value)


LAGUERRE_STAGES = 4


def _laguerre_step(price: float, stages: list[float], gamma: float) -> tuple[list[float], float]:
    """Advance §2.22's four-pole cascade one bar and return the new stages and value."""
    previous_zero, previous_one, previous_two, previous_three = stages
    zero = (1.0 - gamma) * price + gamma * previous_zero
    one = -gamma * zero + previous_zero + gamma * previous_one
    two = -gamma * one + previous_one + gamma * previous_two
    three = -gamma * two + previous_two + gamma * previous_three
    rising = 0.0
    falling = 0.0
    for upper, lower in ((zero, one), (one, two), (two, three)):
        if upper > lower:
            rising += upper - lower
        else:
            falling += lower - upper
    # §2.22 states the substitute itself: a denominator of zero yields zero.
    return [zero, one, two, three], safe_divide(rising, rising + falling, on_zero=0.0)


def laguerre_rsi(candles: Sequence[Candle], gamma: float = 0.5) -> list[float]:
    """Run price through a four-pole Laguerre filter and read it as an RSI (§2.22).

    §2.22 writes the input as a bare `P` and fixes no starting state for the four
    stages. Every stage starts at the first close, which puts the filter at rest
    instead of letting an assumed zero decay through the early bars, and that first
    bar is reported as warm-up because it carries no price difference for the
    difference sums to see.
    """

    if not 0.0 <= gamma < 1.0:
        raise ValueError("gamma must be in [0, 1)")
    result: list[float] = []
    stages: list[float] | None = None
    for candle in candles:
        price = candle.close
        if stages is None:
            stages = [price] * LAGUERRE_STAGES
            result.append(NAN)
            continue
        stages, value = _laguerre_step(price, stages, gamma)
        result.append(value)
    return result


@dataclass(slots=True)
class LaguerreRSIState:
    """O(1)-per-candle Laguerre RSI state over the four-pole cascade."""

    gamma: float = 0.5
    min_history: int = field(init=False, default=2)
    _stages: list[float] | None = field(init=False, default=None)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if not 0.0 <= self.gamma < 1.0:
            raise ValueError("gamma must be in [0, 1)")

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._stages = None
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        if self._stages is None:
            self._stages = [candle.close] * LAGUERRE_STAGES
            self._value = NAN
            return self.current()
        self._stages, self._value = _laguerre_step(candle.close, self._stages, self.gamma)
        return self.current()

    def current(self) -> float:
        return self._value


def pretty_good_oscillator(candles: Sequence[Candle], period: int = 89) -> list[float]:
    """Scale the close's distance from its average by Average True Range (§2.23)."""
    closes = [candle.close for candle in candles]
    averages = sma(closes, period)
    ranges = atr(candles, period)
    return [
        NAN
        if isnan(average) or isnan(true_range)
        # A stretch with no true range has no oscillation to scale; §0.11 lists
        # zero as one of the substitutes a section may name, and §2.23 names none.
        else safe_divide(close - average, true_range, on_zero=0.0)
        for close, average, true_range in zip(closes, averages, ranges, strict=True)
    ]


@dataclass(slots=True)
class PrettyGoodOscillatorState:
    """O(1)-per-candle Pretty Good Oscillator state over an average and an ATR."""

    period: int = 89
    min_history: int = field(init=False)
    _average: SmaState = field(init=False)
    _range: ATRState = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        self.min_history = self.period
        self._average = SmaState(self.period)
        self._range = ATRState(self.period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._average.reset()
        self._range.seed(())
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        average = self._average.update(candle.close)
        true_range = self._range.update(candle)
        self._value = (
            NAN
            if isnan(average) or isnan(true_range)
            else safe_divide(candle.close - average, true_range, on_zero=0.0)
        )
        return self.current()

    def current(self) -> float:
        return self._value


def _center_of_gravity_value(window: Sequence[float], period: int) -> float:
    """Return §8.2's weighted centroid of a window ordered oldest first."""
    numerator = sum((1.0 + offset) * window[period - 1 - offset] for offset in range(period))
    denominator = sum(window)
    return -safe_divide(numerator, denominator, on_zero=0.0) + (period + 1) / 2.0


def center_of_gravity(candles: Sequence[Candle], period: int = 10) -> list[float]:
    """Locate the window's weighted centre of mass and centre it on zero (§8.2)."""
    if period <= 0:
        raise ValueError("period must be positive")
    result: list[float] = []
    window: deque[float] = deque(maxlen=period)
    for candle in candles:
        window.append(candle.close)
        if len(window) < period:
            result.append(NAN)
            continue
        result.append(_center_of_gravity_value(window, period))
    return result


@dataclass(slots=True)
class CenterOfGravityState:
    """O(period)-per-candle Center of Gravity state; every weight moves each bar."""

    period: int = 10
    min_history: int = field(init=False)
    _window: deque[float] = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period
        self._window = deque(maxlen=self.period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._window.clear()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        self._window.append(candle.close)
        if len(self._window) < self.period:
            self._value = NAN
            return self.current()
        self._value = _center_of_gravity_value(self._window, self.period)
        return self.current()

    def current(self) -> float:
        return self._value


def stochastic_slow(
    candles: Sequence[Candle],
    period: int = 14,
    smooth_period: int = 3,
) -> list[StochasticValue]:
    """Compute slow Stochastic %K and %D (§2.2).

    §2.2 writes Slow %K as `SMA(%K_raw, 3)`, which is the very line the fast form
    already publishes as its %D, and Slow %D as that line smoothed once more. So
    the fast calculation above is consumed rather than repeated: the rolling
    high-low window, the flat-range convention, and the first smoothing all stay
    written once. The section is explicit that sharing `%K_raw` is a sharing of
    calculation and not a reason to merge the two into one indicator, because the
    pair of lines each one publishes differs.
    """

    fast = stochastic(candles, period, smooth_period)
    percent_k = [value["percent_d"] for value in fast]
    percent_d = sma(percent_k, smooth_period)
    return [
        {"percent_k": current_k, "percent_d": current_d}
        for current_k, current_d in zip(percent_k, percent_d, strict=True)
    ]


@dataclass(slots=True)
class StochasticSlowState:
    """O(1)-per-candle slow Stochastic state layered on the fast state."""

    period: int = 14
    smooth_period: int = 3
    min_history: int = field(init=False)
    _fast: StochasticState = field(init=False)
    _smoothed: SmaState = field(init=False)
    _value: StochasticValue = field(
        init=False,
        default_factory=lambda: {"percent_k": NAN, "percent_d": NAN},
    )

    def __post_init__(self) -> None:
        if self.period <= 0 or self.smooth_period <= 0:
            raise ValueError("periods must be positive")
        self._fast = StochasticState(period=self.period, smooth_period=self.smooth_period)
        # One more smoothing window sits on top of the fast state's own warm-up.
        self.min_history = self._fast.min_history + self.smooth_period - 1
        self._smoothed = SmaState(self.smooth_period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["percent_d"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._fast.seed(())
        self._smoothed.reset()
        self._value = {"percent_k": NAN, "percent_d": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> StochasticValue:
        percent_k = self._fast.update(candle)["percent_d"]
        percent_d = self._smoothed.update(percent_k)
        self._value = {"percent_k": percent_k, "percent_d": percent_d}
        return self.current()

    def current(self) -> StochasticValue:
        return dict(self._value)


_MovingAverageState = SmaState | EmaState | RmaState

# §2.28 leaves the kind of moving average open as a user parameter, so the ones the
# repository can serve on both execution paths are listed rather than hard-coded at
# the call site. §0.4's WMA is absent: `primitives.py` publishes no incremental state
# for it, only a private one inside the trend category, and writing a second weighted
# window here would duplicate a primitive. Adding WMA means publishing that primitive
# first, not re-deriving it in this module.
_APO_MOVING_AVERAGES: dict[str, Callable[[Sequence[float], int], list[float]]] = {
    "sma": sma,
    "ema": ema,
    "rma": rma,
}

_APO_MOVING_AVERAGE_STATES: dict[str, Callable[[int], _MovingAverageState]] = {
    "sma": SmaState,
    "ema": EmaState,
    "rma": RmaState,
}


def _validate_apo(fast_period: int, slow_period: int, moving_average: str) -> None:
    if fast_period <= 0 or slow_period <= 0:
        raise ValueError("periods must be positive")
    if fast_period >= slow_period:
        raise ValueError("fast_period must be shorter than slow_period")
    if moving_average not in _APO_MOVING_AVERAGES:
        raise ValueError(
            f"unsupported moving average: {moving_average!r}; "
            f"expected one of {sorted(_APO_MOVING_AVERAGES)}"
        )


def apo(
    candles: Sequence[Candle],
    fast_period: int = 12,
    slow_period: int = 26,
    moving_average: str = "sma",
) -> list[float]:
    """Subtract a slow moving average of the close from a fast one (§2.28).

    The kind of moving average is a parameter because §2.28 defines the indicator
    that way, and the default is the simple average the section fixes. The section
    states the consequence of the alternative outright: with EMA at 12 and 26 the
    result is the §2.4 MACD line value for value, which is why the default is not
    EMA and why that combination is not registered under this name.

    There is no division here, so no zero-denominator case exists, and warm-up is
    the slower average's own.
    """

    _validate_apo(fast_period, slow_period, moving_average)
    average = _APO_MOVING_AVERAGES[moving_average]
    closes = [candle.close for candle in candles]
    fast = average(closes, fast_period)
    slow = average(closes, slow_period)
    return [
        NAN if isnan(quick) or isnan(slow_value) else quick - slow_value
        for quick, slow_value in zip(fast, slow, strict=True)
    ]


@dataclass(slots=True)
class APOState:
    """O(1)-per-candle Absolute Price Oscillator state over two moving averages."""

    fast_period: int = 12
    slow_period: int = 26
    moving_average: str = "sma"
    min_history: int = field(init=False)
    _fast: _MovingAverageState = field(init=False)
    _slow: _MovingAverageState = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        _validate_apo(self.fast_period, self.slow_period, self.moving_average)
        factory = _APO_MOVING_AVERAGE_STATES[self.moving_average]
        self.min_history = self.slow_period
        self._fast = factory(self.fast_period)
        self._slow = factory(self.slow_period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._fast.reset()
        self._slow.reset()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        fast = self._fast.update(candle.close)
        slow = self._slow.update(candle.close)
        self._value = NAN if isnan(fast) or isnan(slow) else fast - slow
        return self.current()

    def current(self) -> float:
        return self._value


def _bop_raw(candle: Candle) -> float:
    # §2.29: when the high equals the low the open and the close sit at that same
    # value, so the numerator is zero as well and neither side pushed price. The
    # section fixes 0 for that bar, the convention §4.2 already uses for a
    # collapsed range in the Money Flow Multiplier.
    return safe_divide(candle.close - candle.open, candle.high - candle.low, on_zero=0.0)


def bop(candles: Sequence[Candle], period: int = 14) -> list[float]:
    """Measure the body against the bar's whole range and smooth it (§2.29).

    §2.29 adopts the short form `(C - O)/(H - L)`, noting that the author's six
    bull-and-bear terms collapse to it algebraically rather than approximately, so
    the six terms are not computed here.
    """

    if period <= 0:
        raise ValueError("period must be positive")
    return sma([_bop_raw(candle) for candle in candles], period)


@dataclass(slots=True)
class BOPState:
    """O(1)-per-candle Balance of Power state over one rolling average."""

    period: int = 14
    min_history: int = field(init=False)
    _smoothed: SmaState = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period
        self._smoothed = SmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._smoothed.reset()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        self._value = self._smoothed.update(_bop_raw(candle))
        return self.current()

    def current(self) -> float:
        return self._value


def _imi_value(up_average: float, down_average: float) -> float:
    if isnan(up_average) or isnan(down_average):
        return NAN
    # §2.30 divides the summed gains by the summed gains and losses. The rolling
    # average primitive divides both by the same window length, which leaves the
    # ratio unchanged, so the sums are not written a second time here; §2.8's CMO
    # reads its own sums the same way.
    #
    # The section names three substitutes and says they follow §2.1's convention,
    # so all three are written out the way `_rsi_value` writes them. Leaving the
    # empty-loss end to the arithmetic does not reach it: `100.0 * up / (up + 0.0)`
    # rounds the multiplication before it divides, so it lands a unit in the last
    # place away from 100 for most window totals, and on the far side of the 0-100
    # range the same section states. A window where every bar closed at its open
    # empties both sides at once, and §2.30 fixes the neutral 50 for it, no
    # pressure standing on either side.
    if down_average == 0.0 and up_average > 0.0:
        return 100.0
    if up_average == 0.0 and down_average > 0.0:
        return 0.0
    return safe_divide(100.0 * up_average, up_average + down_average, on_zero=50.0)


def imi(candles: Sequence[Candle], period: int = 14) -> list[float]:
    """Compute the Intraday Momentum Index from open-to-close bodies (§2.30).

    §2.30 applies RSI's shape inside a single bar rather than across two, so the
    gap between one bar's close and the next bar's open never enters the value,
    and the sums stay unsmoothed instead of passing through Wilder's average.
    """

    if period <= 0:
        raise ValueError("period must be positive")
    gains = [max(candle.close - candle.open, 0.0) for candle in candles]
    losses = [max(candle.open - candle.close, 0.0) for candle in candles]
    return [
        _imi_value(up_average, down_average)
        for up_average, down_average in zip(sma(gains, period), sma(losses, period), strict=True)
    ]


@dataclass(slots=True)
class IMIState:
    """O(1)-per-candle Intraday Momentum Index state over two rolling sums."""

    period: int = 14
    min_history: int = field(init=False)
    _gains: SmaState = field(init=False)
    _losses: SmaState = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period
        self._gains = SmaState(self.period)
        self._losses = SmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._gains.reset()
        self._losses.reset()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        up_average = self._gains.update(max(candle.close - candle.open, 0.0))
        down_average = self._losses.update(max(candle.open - candle.close, 0.0))
        self._value = _imi_value(up_average, down_average)
        return self.current()

    def current(self) -> float:
        return self._value
