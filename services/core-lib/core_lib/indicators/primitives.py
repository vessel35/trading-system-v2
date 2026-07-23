"""Provide reusable indicator calculation primitives."""

from collections import deque
from collections.abc import Sequence
from math import isnan, sqrt

from core_lib.types import Candle

Series = list[float]

NAN = float("nan")


def _validate_period(period: int) -> None:
    if isinstance(period, bool) or not isinstance(period, int):
        raise TypeError("period must be int")
    if period <= 0:
        raise ValueError("period must be positive")


def sma(values: Sequence[float], period: int) -> Series:
    """Return the rolling simple average with a NaN warm-up."""
    _validate_period(period)
    result: Series = []
    window: deque[float] = deque()
    total = 0.0
    invalid = 0
    for value in values:
        window.append(value)
        if isnan(value):
            invalid += 1
        else:
            total += value
        if len(window) > period:
            removed = window.popleft()
            if isnan(removed):
                invalid -= 1
            else:
                total -= removed
        result.append(total / period if len(window) == period and invalid == 0 else NAN)
    return result


def _recursive_average(values: Sequence[float], period: int, alpha: float) -> Series:
    _validate_period(period)
    result: Series = []
    seed: deque[float] = deque(maxlen=period)
    current: float | None = None
    for value in values:
        if isnan(value):
            result.append(NAN)
            if current is None:
                seed.clear()
            continue
        if current is None:
            seed.append(value)
            if len(seed) < period:
                result.append(NAN)
                continue
            current = sum(seed) / period
        else:
            current += alpha * (value - current)
        result.append(current)
    return result


def ema(values: Sequence[float], period: int) -> Series:
    """Return an SMA-seeded recursive EMA with ``adjust=False`` semantics."""
    _validate_period(period)
    return _recursive_average(values, period, 2.0 / (period + 1.0))


def wma(values: Sequence[float], period: int) -> Series:
    """Return a linearly weighted moving average."""
    _validate_period(period)
    denominator = period * (period + 1) / 2.0
    result: Series = []
    window: deque[float] = deque(maxlen=period)
    for value in values:
        window.append(value)
        if len(window) < period or any(isnan(item) for item in window):
            result.append(NAN)
            continue
        result.append(
            sum(weight * item for weight, item in enumerate(window, start=1)) / denominator
        )
    return result


def rma(values: Sequence[float], period: int) -> Series:
    """Return Wilder's SMA-seeded recursive moving average."""
    _validate_period(period)
    return _recursive_average(values, period, 1.0 / period)


def tr(candles: Sequence[Candle]) -> Series:
    """Return True Range for each candle."""
    result: Series = []
    previous_close: float | None = None
    for candle in candles:
        if previous_close is None:
            value = candle.high - candle.low
        else:
            value = max(
                candle.high - candle.low,
                abs(candle.high - previous_close),
                abs(candle.low - previous_close),
            )
        result.append(value)
        previous_close = candle.close
    return result


def tp(candles: Sequence[Candle]) -> Series:
    """Return typical price, ``(high + low + close) / 3``."""
    return [(candle.high + candle.low + candle.close) / 3.0 for candle in candles]


def stdev(values: Sequence[float], period: int) -> Series:
    """Return rolling population standard deviation with divisor ``n``."""
    _validate_period(period)
    result: Series = []
    window: deque[float] = deque()
    total = 0.0
    total_squares = 0.0
    invalid = 0
    for value in values:
        window.append(value)
        if isnan(value):
            invalid += 1
        else:
            total += value
            total_squares += value * value
        if len(window) > period:
            removed = window.popleft()
            if isnan(removed):
                invalid -= 1
            else:
                total -= removed
                total_squares -= removed * removed
        if len(window) != period or invalid:
            result.append(NAN)
            continue
        variance = max(0.0, total_squares / period - (total / period) ** 2)
        result.append(sqrt(variance))
    return result


def _rolling_extreme(values: Sequence[float], period: int, *, highest: bool) -> Series:
    _validate_period(period)
    candidates: deque[tuple[int, float]] = deque()
    result: Series = []
    for index, value in enumerate(values):
        if isnan(value):
            candidates.clear()
        else:
            if highest:
                while candidates and candidates[-1][1] <= value:
                    candidates.pop()
            else:
                while candidates and candidates[-1][1] >= value:
                    candidates.pop()
            candidates.append((index, value))
        minimum_index = index - period + 1
        while candidates and candidates[0][0] < minimum_index:
            candidates.popleft()
        if index + 1 < period or not candidates:
            result.append(NAN)
        else:
            window = values[minimum_index : index + 1]
            result.append(NAN if any(isnan(item) for item in window) else candidates[0][1])
    return result


def hh(values: Sequence[float], period: int) -> Series:
    """Return the rolling highest value."""
    return _rolling_extreme(values, period, highest=True)


def ll(values: Sequence[float], period: int) -> Series:
    """Return the rolling lowest value."""
    return _rolling_extreme(values, period, highest=False)


def cumulative(values: Sequence[float]) -> Series:
    """Return a cumulative sum while preserving NaN positions."""
    result: Series = []
    total = 0.0
    for value in values:
        if isnan(value):
            result.append(NAN)
            continue
        total += value
        result.append(total)
    return result


def roc(values: Sequence[float], period: int) -> Series:
    """Return percentage rate of change over ``period`` observations."""
    _validate_period(period)
    result = [NAN] * min(period, len(values))
    for index in range(period, len(values)):
        previous = values[index - period]
        current = values[index]
        if isnan(previous) or isnan(current) or previous == 0.0:
            result.append(NAN)
        else:
            result.append(100.0 * (current - previous) / previous)
    return result


def linreg(values: Sequence[float], period: int) -> Series:
    """Return the rolling least-squares forecast at the current observation."""
    _validate_period(period)
    result: Series = []
    sum_x = period * (period - 1) / 2.0
    sum_x_squared = period * (period - 1) * (2 * period - 1) / 6.0
    denominator = period * sum_x_squared - sum_x * sum_x
    for index in range(len(values)):
        if index + 1 < period:
            result.append(NAN)
            continue
        window = values[index - period + 1 : index + 1]
        if any(isnan(item) for item in window):
            result.append(NAN)
            continue
        sum_y = sum(window)
        sum_xy = sum(x * value for x, value in enumerate(window))
        slope = (period * sum_xy - sum_x * sum_y) / denominator if period > 1 else 0.0
        intercept = (sum_y - slope * sum_x) / period
        result.append(intercept + slope * (period - 1))
    return result
