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


def safe_divide(numerator: float, denominator: float, *, on_zero: float) -> float:
    """Divide, returning ``on_zero`` when the denominator is zero.

    The standard (§0.11) does not fix one repository-wide answer for a zero
    denominator: it lists zero, a saturated value, and the previous value as the
    choices actual implementations make, and says each indicator's own section
    states which one applies. So the substitute stays a required argument here.
    A caller has to name the value its indicator's section prescribes, which
    keeps that decision visible at the call site instead of hidden in a default.

    The backtest engine rejects a non-finite indicator value once warm-up is
    over, so ``on_zero`` must be finite. NaN belongs to warm-up alone.
    """

    if isnan(numerator) or isnan(denominator):
        return NAN
    if denominator == 0.0:
        if isnan(on_zero):
            raise ValueError("on_zero must be finite; NaN is reserved for warm-up")
        return on_zero
    return numerator / denominator


def hl2(candles: Sequence[Candle]) -> Series:
    """Return median price, ``(high + low) / 2`` (§0.1)."""
    return [(candle.high + candle.low) / 2.0 for candle in candles]


def hlcc4(candles: Sequence[Candle]) -> Series:
    """Return weighted close, ``(high + low + 2 * close) / 4`` (§0.1)."""
    return [(candle.high + candle.low + 2.0 * candle.close) / 4.0 for candle in candles]


def ohlc4(candles: Sequence[Candle]) -> Series:
    """Return the OHLC average, ``(open + high + low + close) / 4`` (§0.1)."""
    return [(candle.open + candle.high + candle.low + candle.close) / 4.0 for candle in candles]


class _RollingPopulationStdev:
    """Numerically stable rolling population deviation using Welford moments."""

    def __init__(self, period: int) -> None:
        _validate_period(period)
        self.period = period
        self._window: deque[float] = deque()
        self._count = 0
        self._invalid = 0
        self._mean = 0.0
        self._m2 = 0.0

    def reset(self) -> None:
        """Clear all observations and moments."""
        self._window.clear()
        self._count = 0
        self._invalid = 0
        self._mean = 0.0
        self._m2 = 0.0

    def _add(self, value: float) -> None:
        self._count += 1
        delta = value - self._mean
        self._mean += delta / self._count
        self._m2 += delta * (value - self._mean)

    def _remove(self, value: float) -> None:
        if self._count == 1:
            self._count = 0
            self._mean = 0.0
            self._m2 = 0.0
            return
        new_count = self._count - 1
        new_mean = self._mean - (value - self._mean) / new_count
        new_m2 = self._m2 - (value - self._mean) * (value - new_mean)
        self._count = new_count
        self._mean = new_mean
        self._m2 = max(0.0, new_m2)

    def update(self, value: float) -> float:
        """Add one value, evict the oldest, and return the current deviation."""
        self._window.append(value)
        if isnan(value):
            self._invalid += 1
        else:
            self._add(value)
        if len(self._window) > self.period:
            removed = self._window.popleft()
            if isnan(removed):
                self._invalid -= 1
            else:
                self._remove(removed)
        return self.current()

    @property
    def warmed_up(self) -> bool:
        """Return whether a full, valid window is present."""
        return len(self._window) == self.period and not self._invalid and self._count == self.period

    def current(self) -> float:
        """Return sqrt(M2/n) for a complete valid window, otherwise NaN."""
        if not self.warmed_up:
            return NAN
        return sqrt(max(0.0, self._m2) / self.period)


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
    state = _RollingPopulationStdev(period)
    return [state.update(value) for value in values]


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


def mom(values: Sequence[float], period: int) -> Series:
    """Return the raw momentum ``P_t - P_{t-n}`` (§0.10)."""
    _validate_period(period)
    result: Series = [NAN] * min(period, len(values))
    for index in range(period, len(values)):
        previous = values[index - period]
        current = values[index]
        result.append(NAN if isnan(previous) or isnan(current) else current - previous)
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


class SmaState:
    """O(1)-per-value rolling simple average (§0.2).

    The vectorized ``sma`` above and this state must agree value for value; the
    parity tests hold that. Keeping one algorithm here rather than inside each
    indicator is what stops the same sliding window from being written again for
    every indicator that averages something.
    """

    def __init__(self, period: int) -> None:
        _validate_period(period)
        self.period = period
        self._window: deque[float] = deque()
        self._total = 0.0
        self._invalid = 0

    def reset(self) -> None:
        """Clear the window."""
        self._window.clear()
        self._total = 0.0
        self._invalid = 0

    @property
    def warmed_up(self) -> bool:
        """Return whether a full, valid window is present."""
        return len(self._window) == self.period and self._invalid == 0

    def update(self, value: float) -> float:
        """Add one value, evict the oldest, and return the current average."""
        self._window.append(value)
        if isnan(value):
            self._invalid += 1
        else:
            self._total += value
        if len(self._window) > self.period:
            removed = self._window.popleft()
            if isnan(removed):
                self._invalid -= 1
            else:
                self._total -= removed
        return self.current()

    def current(self) -> float:
        """Return the average of a complete valid window, otherwise NaN."""
        return self._total / self.period if self.warmed_up else NAN


class _RecursiveAverageState:
    """Shared SMA-seeded recursion behind EMA (§0.3) and Wilder RMA (§0.5).

    The seed is summed with the same builtin `sum` the vectorized
    `_recursive_average` uses, rather than accumulated one value at a time. From
    Python 3.12 onwards `sum` adds floats with Neumaier compensation, so a loop
    that adds them one at a time parts from it in the last bits, and the two
    execution paths are required to produce the same number.

    That gap went unnoticed for a long time because it is a last-bit gap and the
    parity tolerance is relative. It first crossed the tolerance in the Klinger
    oscillator of §4.8, whose value is the difference of two averages seeded over
    34 and 55 Volume Force values of order 1e5: the subtraction cancels the large
    part and leaves the last-bit difference standing alone, which turns a relative
    1e-16 in the seed into a relative 1e-12 in the result. Registered EMAs of
    period 55 and 200 never showed it because nothing subtracts one from another.
    `test_indicator_primitives.py` states the property directly, so it no longer
    depends on which indicator happens to subtract two long averages.
    """

    def __init__(self, period: int, alpha: float) -> None:
        _validate_period(period)
        self.period = period
        self._alpha = alpha
        self._seed: list[float] = []
        self._value: float | None = None

    def reset(self) -> None:
        """Drop the seed and the recursive value."""
        self._seed = []
        self._value = None

    @property
    def warmed_up(self) -> bool:
        """Return whether the seed completed and a value exists."""
        return self._value is not None

    def update(self, value: float) -> float:
        """Advance one observation and return the current average."""
        if isnan(value):
            if self._value is None:
                self._seed = []
            return NAN
        if self._value is None:
            self._seed.append(value)
            if len(self._seed) == self.period:
                self._value = sum(self._seed) / self.period
                # The window is only needed until the recursion takes over.
                self._seed = []
        else:
            self._value += self._alpha * (value - self._value)
        return self.current()

    def current(self) -> float:
        """Return the recursive average, or NaN before the seed completes."""
        return self._value if self._value is not None else NAN


class EmaState(_RecursiveAverageState):
    """O(1)-per-value EMA with the standard's SMA seed (§0.3)."""

    def __init__(self, period: int) -> None:
        _validate_period(period)
        super().__init__(period, 2.0 / (period + 1.0))


class RmaState(_RecursiveAverageState):
    """O(1)-per-value Wilder smoothing (§0.5); RMA(n) is not EMA(n)."""

    def __init__(self, period: int) -> None:
        _validate_period(period)
        super().__init__(period, 1.0 / period)


class RollingExtremeState:
    """O(1)-amortized rolling highest or lowest over a window (§0.8)."""

    def __init__(self, period: int, *, highest: bool) -> None:
        _validate_period(period)
        self.period = period
        self._highest = highest
        self._candidates: deque[tuple[int, float]] = deque()
        self._window: deque[float] = deque()
        self._index = -1
        self._invalid = 0

    def reset(self) -> None:
        """Clear the window and the monotonic candidate queue."""
        self._candidates.clear()
        self._window.clear()
        self._index = -1
        self._invalid = 0

    @property
    def warmed_up(self) -> bool:
        """Return whether a full, valid window is present."""
        return len(self._window) == self.period and self._invalid == 0

    def update(self, value: float) -> float:
        """Add one value and return the extreme of the current window."""
        self._index += 1
        self._window.append(value)
        if isnan(value):
            self._invalid += 1
            self._candidates.clear()
        else:
            while self._candidates and (
                self._candidates[-1][1] <= value
                if self._highest
                else self._candidates[-1][1] >= value
            ):
                self._candidates.pop()
            self._candidates.append((self._index, value))
        if len(self._window) > self.period:
            removed = self._window.popleft()
            if isnan(removed):
                self._invalid -= 1
        oldest_index = self._index - self.period + 1
        while self._candidates and self._candidates[0][0] < oldest_index:
            self._candidates.popleft()
        return self.current()

    def current(self) -> float:
        """Return the window extreme, or NaN while warming up."""
        if not self.warmed_up or not self._candidates:
            return NAN
        return self._candidates[0][1]


class CumulativeState:
    """Running total that preserves NaN positions (§0.9)."""

    def __init__(self) -> None:
        self._total = 0.0
        self._seen = False

    def reset(self) -> None:
        """Clear the running total."""
        self._total = 0.0
        self._seen = False

    @property
    def warmed_up(self) -> bool:
        """Return whether at least one finite value was accumulated."""
        return self._seen

    def update(self, value: float) -> float:
        """Add one value to the total and return it."""
        if isnan(value):
            return NAN
        self._total += value
        self._seen = True
        return self._total

    def current(self) -> float:
        """Return the running total, or NaN before the first finite value."""
        return self._total if self._seen else NAN


class RocState:
    """Rolling percentage rate of change over ``period`` observations (§0.10)."""

    def __init__(self, period: int, *, percentage: bool = True) -> None:
        _validate_period(period)
        self.period = period
        self._percentage = percentage
        self._window: deque[float] = deque(maxlen=period + 1)

    def reset(self) -> None:
        """Clear the observation window."""
        self._window.clear()

    @property
    def warmed_up(self) -> bool:
        """Return whether the window spans the full lookback."""
        return len(self._window) == self.period + 1

    def update(self, value: float) -> float:
        """Add one value and return the change against the lookback."""
        self._window.append(value)
        return self.current()

    def current(self) -> float:
        """Return the change, or NaN while warming up or on invalid input."""
        if not self.warmed_up:
            return NAN
        previous = self._window[0]
        current = self._window[-1]
        if isnan(previous) or isnan(current):
            return NAN
        if not self._percentage:
            return current - previous
        # The standard leaves a zero base undefined for ROC; warm-up NaN is the
        # only honest answer because no substitute value is prescribed (§0.10).
        return NAN if previous == 0.0 else 100.0 * (current - previous) / previous


StdevState = _RollingPopulationStdev
