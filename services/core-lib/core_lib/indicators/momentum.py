"""Define required momentum indicators and the follow-up momentum catalog."""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isnan

from core_lib.types import Candle

from .primitives import NAN, hh, ll, rma, sma

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
    _delta_count: int = field(init=False, default=0)
    _gain_sum: float = field(init=False, default=0.0)
    _loss_sum: float = field(init=False, default=0.0)
    _average_gain: float | None = field(init=False, default=None)
    _average_loss: float | None = field(init=False, default=None)
    _value: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period + 1

    @property
    def warmed_up(self) -> bool:
        return self._value is not None

    def seed(self, candles: Sequence[Candle]) -> None:
        self._previous_close = None
        self._delta_count = 0
        self._gain_sum = 0.0
        self._loss_sum = 0.0
        self._average_gain = None
        self._average_loss = None
        self._value = None
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        if self._previous_close is None:
            self._previous_close = candle.close
            return NAN

        change = candle.close - self._previous_close
        self._previous_close = candle.close
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        if self._average_gain is None or self._average_loss is None:
            self._delta_count += 1
            self._gain_sum += gain
            self._loss_sum += loss
            if self._delta_count == self.period:
                self._average_gain = self._gain_sum / self.period
                self._average_loss = self._loss_sum / self.period
        else:
            self._average_gain += (gain - self._average_gain) / self.period
            self._average_loss += (loss - self._average_loss) / self.period

        if self._average_gain is not None and self._average_loss is not None:
            self._value = _rsi_value(self._average_gain, self._average_loss)
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
        price_range = high - low
        current_k = previous_k if price_range == 0.0 else 100.0 * (candle.close - low) / price_range
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
    _index: int = field(init=False, default=-1)
    _highs: deque[tuple[int, float]] = field(init=False, default_factory=deque)
    _lows: deque[tuple[int, float]] = field(init=False, default_factory=deque)
    _percent_k_window: deque[float] = field(init=False, default_factory=deque)
    _previous_k: float = field(init=False, default=50.0)
    _value: StochasticValue = field(
        init=False,
        default_factory=lambda: {"percent_k": NAN, "percent_d": NAN},
    )

    def __post_init__(self) -> None:
        if self.period <= 0 or self.smooth_period <= 0:
            raise ValueError("periods must be positive")
        self.min_history = self.period + self.smooth_period - 1

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["percent_d"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._index = -1
        self._highs.clear()
        self._lows.clear()
        self._percent_k_window.clear()
        self._previous_k = 50.0
        self._value = {"percent_k": NAN, "percent_d": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> StochasticValue:
        self._index += 1
        while self._highs and self._highs[-1][1] <= candle.high:
            self._highs.pop()
        self._highs.append((self._index, candle.high))
        while self._lows and self._lows[-1][1] >= candle.low:
            self._lows.pop()
        self._lows.append((self._index, candle.low))

        minimum_index = self._index - self.period + 1
        while self._highs and self._highs[0][0] < minimum_index:
            self._highs.popleft()
        while self._lows and self._lows[0][0] < minimum_index:
            self._lows.popleft()

        if self._index + 1 < self.period:
            self._value = {"percent_k": NAN, "percent_d": NAN}
            return self.current()

        highest = self._highs[0][1]
        lowest = self._lows[0][1]
        price_range = highest - lowest
        current_k = (
            self._previous_k
            if price_range == 0.0
            else 100.0 * (candle.close - lowest) / price_range
        )
        self._previous_k = current_k
        self._percent_k_window.append(current_k)
        if len(self._percent_k_window) > self.smooth_period:
            self._percent_k_window.popleft()
        current_d = (
            sum(self._percent_k_window) / self.smooth_period
            if len(self._percent_k_window) == self.smooth_period
            else NAN
        )
        self._value = {"percent_k": current_k, "percent_d": current_d}
        return self.current()

    def current(self) -> StochasticValue:
        return dict(self._value)
