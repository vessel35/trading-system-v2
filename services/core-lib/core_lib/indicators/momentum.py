"""Define required momentum indicators and the follow-up momentum catalog."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isnan

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
)

StochasticValue = dict[str, float]

FOLLOW_UP_INDICATORS = (
    "Stochastic RSI",
    "MACD",
    "PPO",
    "TRIX",
    "TSI",
    "SMI",
    "CMO",
    "Williams %R",
    "CCI",
    "Ultimate Oscillator",
    "Awesome Oscillator",
    "Accelerator Oscillator",
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
