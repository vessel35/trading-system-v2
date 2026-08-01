"""Define the trend indicators and the follow-up trend catalog."""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import exp, isnan, sqrt

from core_lib.types import Candle

from .momentum import CMOState, cmo
from .primitives import NAN, EmaState, SmaState, safe_divide
from .primitives import ema as ema_primitive
from .primitives import sma as sma_primitive
from .primitives import wma as wma_primitive

# Every trend indicator §1 of the calculation standard defines is now registered,
# so this category contributes nothing further to the not-yet-implemented catalog.
FOLLOW_UP_INDICATORS: tuple[str, ...] = ()


def ema(candles: Sequence[Candle], period: int) -> list[float]:
    """Compute close-price EMA using the §0.3 SMA seed."""
    return ema_primitive([candle.close for candle in candles], period)


@dataclass(slots=True)
class EMAState:
    """O(1)-per-candle incremental EMA state over close prices.

    The recursion itself lives in the primitive layer so this class only decides
    which price feeds it. Every indicator that smooths something reuses the same
    implementation rather than restating the seed-and-alpha rule.
    """

    period: int
    min_history: int = field(init=False)
    _average: EmaState = field(init=False)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period
        self._average = EmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return self._average.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._average.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        return self._average.update(candle.close)

    def current(self) -> float:
        return self._average.current()


def dema(candles: Sequence[Candle], period: int) -> list[float]:
    """Compute the double EMA, ``2 * EMA1 - EMA2`` (§1.1)."""
    closes = [candle.close for candle in candles]
    first = ema_primitive(closes, period)
    second = ema_primitive(first, period)
    return [
        NAN if isnan(one) or isnan(two) else 2.0 * one - two
        for one, two in zip(first, second, strict=True)
    ]


@dataclass(slots=True)
class DEMAState:
    """O(1)-per-candle double EMA state.

    The second EMA smooths the first one's output, so it only starts once the
    first has a value. Feeding the warm-up NaN through keeps the incremental
    path aligned with the vectorized one, which sees the same NaN prefix.
    """

    period: int
    min_history: int = field(init=False)
    _first: EmaState = field(init=False)
    _second: EmaState = field(init=False)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        # The first average needs `period` closes; the second needs `period`
        # values of the first, and they start arriving on that same candle.
        self.min_history = 2 * self.period - 1
        self._first = EmaState(self.period)
        self._second = EmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return self._second.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._first.reset()
        self._second.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        first = self._first.update(candle.close)
        second = self._second.update(first)
        return NAN if isnan(first) or isnan(second) else 2.0 * first - second

    def current(self) -> float:
        first = self._first.current()
        second = self._second.current()
        return NAN if isnan(first) or isnan(second) else 2.0 * first - second


def tema(candles: Sequence[Candle], period: int) -> list[float]:
    """Compute the triple EMA, ``3*E1 - 3*E2 + E3`` (§1.2)."""
    closes = [candle.close for candle in candles]
    first = ema_primitive(closes, period)
    second = ema_primitive(first, period)
    third = ema_primitive(second, period)
    return [
        NAN if isnan(one) or isnan(two) or isnan(three) else 3.0 * one - 3.0 * two + three
        for one, two, three in zip(first, second, third, strict=True)
    ]


@dataclass(slots=True)
class TEMAState:
    """O(1)-per-candle triple EMA state over three chained averages."""

    period: int
    min_history: int = field(init=False)
    _first: EmaState = field(init=False)
    _second: EmaState = field(init=False)
    _third: EmaState = field(init=False)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        # Each average waits for its input to exist, and the first value of each
        # arrives on the same candle its predecessor completes its period.
        self.min_history = 3 * self.period - 2
        self._first = EmaState(self.period)
        self._second = EmaState(self.period)
        self._third = EmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return self._third.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._first.reset()
        self._second.reset()
        self._third.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        first = self._first.update(candle.close)
        second = self._second.update(first)
        third = self._third.update(second)
        return self._combine(first, second, third)

    def current(self) -> float:
        return self._combine(
            self._first.current(),
            self._second.current(),
            self._third.current(),
        )

    @staticmethod
    def _combine(first: float, second: float, third: float) -> float:
        if isnan(first) or isnan(second) or isnan(third):
            return NAN
        return 3.0 * first - 3.0 * second + third


_KAMA_FAST = 2.0 / (2.0 + 1.0)
_KAMA_SLOW = 2.0 / (30.0 + 1.0)


def _kama_smoothing(efficiency: float) -> float:
    return (efficiency * (_KAMA_FAST - _KAMA_SLOW) + _KAMA_SLOW) ** 2


def kama(candles: Sequence[Candle], period: int = 10) -> list[float]:
    """Adapt an average's speed to how directly price moved (§1.7)."""
    if period <= 0:
        raise ValueError("period must be positive")
    closes = [candle.close for candle in candles]
    result: list[float] = []
    current: float | None = None
    for index, close in enumerate(closes):
        if index < period:
            result.append(NAN)
            continue
        change = abs(close - closes[index - period])
        volatility = sum(
            abs(closes[step] - closes[step - 1]) for step in range(index - period + 1, index + 1)
        )
        # §1.7 states the degenerate rule: a window that never moved has an
        # efficiency ratio of zero, which parks the average at its slow speed.
        efficiency = safe_divide(change, volatility, on_zero=0.0)
        if current is None:
            current = closes[index - 1]
        current += _kama_smoothing(efficiency) * (close - current)
        result.append(current)
    return result


@dataclass(slots=True)
class KAMAState:
    """O(period)-per-candle KAMA state; the efficiency ratio needs its window."""

    period: int = 10
    min_history: int = field(init=False)
    _closes: deque[float] = field(init=False)
    _value: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period + 1
        self._closes = deque(maxlen=self.period + 1)

    @property
    def warmed_up(self) -> bool:
        return self._value is not None

    def seed(self, candles: Sequence[Candle]) -> None:
        self._closes.clear()
        self._value = None
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        self._closes.append(candle.close)
        if len(self._closes) <= self.period:
            return self.current()
        change = abs(self._closes[-1] - self._closes[0])
        volatility = sum(
            abs(self._closes[index] - self._closes[index - 1])
            for index in range(1, len(self._closes))
        )
        efficiency = safe_divide(change, volatility, on_zero=0.0)
        if self._value is None:
            self._value = self._closes[-2]
        self._value += _kama_smoothing(efficiency) * (self._closes[-1] - self._value)
        return self.current()

    def current(self) -> float:
        return self._value if self._value is not None else NAN


_T3_STAGES = 6


def _t3_coefficients(volume_factor: float) -> tuple[float, float, float, float]:
    """Return the §1.3 expanded coefficients ``c1..c4`` for one volume factor.

    §1.3 gives T3 twice: as ``GD(GD(GD(P)))`` and as a weighted sum of the third
    through sixth links of one EMA chain. The two are the same calculation because
    the EMA is linear, and the expanded form is the one written with explicit
    constants, so it is the one transcribed here.
    """

    squared = volume_factor * volume_factor
    cubed = squared * volume_factor
    return (
        -cubed,
        3.0 * squared + 3.0 * cubed,
        -6.0 * squared - 3.0 * volume_factor - 3.0 * cubed,
        1.0 + 3.0 * volume_factor + cubed + 3.0 * squared,
    )


def _t3_combine(
    coefficients: tuple[float, float, float, float],
    third: float,
    fourth: float,
    fifth: float,
    sixth: float,
) -> float:
    sixth_weight, fifth_weight, fourth_weight, third_weight = coefficients
    if isnan(third) or isnan(fourth) or isnan(fifth) or isnan(sixth):
        return NAN
    return (
        sixth_weight * sixth + fifth_weight * fifth + fourth_weight * fourth + third_weight * third
    )


def t3(
    candles: Sequence[Candle],
    period: int = 21,
    volume_factor: float = 0.7,
) -> list[float]:
    """Apply Tillson's generalized DEMA three times over one EMA chain (§1.3)."""
    if period <= 0:
        raise ValueError("period must be positive")
    chain: list[list[float]] = []
    series = [candle.close for candle in candles]
    for _ in range(_T3_STAGES):
        series = ema_primitive(series, period)
        chain.append(series)
    coefficients = _t3_coefficients(volume_factor)
    return [
        _t3_combine(coefficients, third, fourth, fifth, sixth)
        for third, fourth, fifth, sixth in zip(chain[2], chain[3], chain[4], chain[5], strict=True)
    ]


@dataclass(slots=True)
class T3State:
    """O(1)-per-candle T3 state over six chained EMAs."""

    period: int = 21
    volume_factor: float = 0.7
    min_history: int = field(init=False)
    _chain: tuple[EmaState, ...] = field(init=False)
    _coefficients: tuple[float, float, float, float] = field(init=False)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        # Each link waits for the one before it, and each one's first value lands on
        # the candle where its input completes another full period.
        self.min_history = _T3_STAGES * self.period - (_T3_STAGES - 1)
        self._chain = tuple(EmaState(self.period) for _ in range(_T3_STAGES))
        self._coefficients = _t3_coefficients(self.volume_factor)

    @property
    def warmed_up(self) -> bool:
        return self._chain[-1].warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        for state in self._chain:
            state.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        value = candle.close
        for state in self._chain:
            value = state.update(value)
        return self.current()

    def current(self) -> float:
        return _t3_combine(
            self._coefficients,
            self._chain[2].current(),
            self._chain[3].current(),
            self._chain[4].current(),
            self._chain[5].current(),
        )


@dataclass(slots=True)
class _RollingWma:
    """Rolling weighted average that delegates to the §0.4 primitive.

    The primitive layer has no incremental weighted average yet and is shared by
    every category, so this keeps the window here and hands the arithmetic to
    ``wma`` rather than restating §0.4 inside the trend module. The cost is one
    pass over the window per candle, the same shape ``KAMAState`` already carries.
    """

    period: int
    _window: deque[float] = field(init=False)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self._window = deque(maxlen=self.period)

    def reset(self) -> None:
        self._window.clear()

    def update(self, value: float) -> float:
        self._window.append(value)
        if len(self._window) < self.period:
            return NAN
        return wma_primitive(list(self._window), self.period)[-1]


def _hma_lengths(period: int) -> tuple[int, int]:
    """Return the half window and the smoothing window §1.4 prescribes."""
    if period <= 1:
        raise ValueError("period must be greater than one")
    # §1.4: the half window is integerized and the smoothing window is the rounded
    # square root. Both are written as roundings of the same period, not as free
    # parameters, so they are derived here instead of being registered.
    return period // 2, round(sqrt(period))


def hma(candles: Sequence[Candle], period: int = 9) -> list[float]:
    """Weight the recent half of the window twice, then smooth it (§1.4)."""
    half, root = _hma_lengths(period)
    closes = [candle.close for candle in candles]
    fast = wma_primitive(closes, half)
    slow = wma_primitive(closes, period)
    lead = [
        NAN if isnan(quick) or isnan(steady) else 2.0 * quick - steady
        for quick, steady in zip(fast, slow, strict=True)
    ]
    return wma_primitive(lead, root)


@dataclass(slots=True)
class HMAState:
    """Hull moving average state over three rolling weighted averages."""

    period: int = 9
    min_history: int = field(init=False)
    _fast: _RollingWma = field(init=False)
    _slow: _RollingWma = field(init=False)
    _smoother: _RollingWma = field(init=False)
    _value: float = field(init=False, default=NAN)

    def __post_init__(self) -> None:
        half, root = _hma_lengths(self.period)
        # The lead series starts once the longer of the two averages exists, and the
        # smoother then needs `root` of those values.
        self.min_history = self.period + root - 1
        self._fast = _RollingWma(half)
        self._slow = _RollingWma(self.period)
        self._smoother = _RollingWma(root)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value)

    def seed(self, candles: Sequence[Candle]) -> None:
        self._fast.reset()
        self._slow.reset()
        self._smoother.reset()
        self._value = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        quick = self._fast.update(candle.close)
        steady = self._slow.update(candle.close)
        lead = NAN if isnan(quick) or isnan(steady) else 2.0 * quick - steady
        self._value = self._smoother.update(lead)
        return self.current()

    def current(self) -> float:
        return self._value


def _zlema_lag(period: int) -> int:
    """Return the §1.5 lag, ``floor((n - 1) / 2)``."""
    if period <= 0:
        raise ValueError("period must be positive")
    return (period - 1) // 2


def zlema(candles: Sequence[Candle], period: int = 21) -> list[float]:
    """Smooth a lag-corrected price rather than the price itself (§1.5)."""
    lag = _zlema_lag(period)
    closes = [candle.close for candle in candles]
    corrected = [
        NAN if index < lag else close + (close - closes[index - lag])
        for index, close in enumerate(closes)
    ]
    return ema_primitive(corrected, period)


@dataclass(slots=True)
class ZLEMAState:
    """Zero-lag EMA state; the correction needs only the candle `lag` bars back."""

    period: int = 21
    min_history: int = field(init=False)
    _lag: int = field(init=False)
    _closes: deque[float] = field(init=False)
    _average: EmaState = field(init=False)

    def __post_init__(self) -> None:
        self._lag = _zlema_lag(self.period)
        # The corrected price starts at candle `lag`, and the average then needs a
        # full period of it before §0.3's seed completes.
        self.min_history = self._lag + self.period
        self._closes = deque(maxlen=self._lag + 1)
        self._average = EmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return self._average.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._closes.clear()
        self._average.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        self._closes.append(candle.close)
        if len(self._closes) <= self._lag:
            return self._average.update(NAN)
        return self._average.update(candle.close + (candle.close - self._closes[0]))

    def current(self) -> float:
        return self._average.current()


def _alma_weights(period: int, offset: float, sigma: float) -> tuple[list[float], float]:
    """Return the §1.6 Gaussian weights, oldest first, with their sum."""
    if period <= 0:
        raise ValueError("period must be positive")
    if sigma <= 0.0:
        raise ValueError("sigma must be positive")
    peak = offset * (period - 1)
    width = period / sigma
    weights = [exp(-((index - peak) ** 2) / (2.0 * width * width)) for index in range(period)]
    total = sum(weights)
    if total == 0.0:
        # Every weight underflowed, which leaves no window to average at all. That
        # is a parameter error rather than a degenerate bar, so it is refused here
        # instead of being turned into a per-candle substitute value.
        raise ValueError("alma weights underflowed to zero")
    return weights, total


def _alma_value(window: Sequence[float], weights: Sequence[float], total: float) -> float:
    if any(isnan(value) for value in window):
        return NAN
    return sum(weight * value for weight, value in zip(weights, window, strict=True)) / total


def alma(
    candles: Sequence[Candle],
    period: int = 9,
    offset: float = 0.85,
    sigma: float = 6.0,
) -> list[float]:
    """Weight the window by a Gaussian centred by ``offset`` (§1.6)."""
    weights, total = _alma_weights(period, offset, sigma)
    closes = [candle.close for candle in candles]
    result: list[float] = []
    for index in range(len(closes)):
        if index + 1 < period:
            result.append(NAN)
            continue
        result.append(_alma_value(closes[index - period + 1 : index + 1], weights, total))
    return result


@dataclass(slots=True)
class ALMAState:
    """Arnaud Legoux moving average state over one fixed Gaussian kernel."""

    period: int = 9
    offset: float = 0.85
    sigma: float = 6.0
    min_history: int = field(init=False)
    _weights: list[float] = field(init=False)
    _total: float = field(init=False)
    _window: deque[float] = field(init=False)

    def __post_init__(self) -> None:
        self._weights, self._total = _alma_weights(self.period, self.offset, self.sigma)
        self.min_history = self.period
        self._window = deque(maxlen=self.period)

    @property
    def warmed_up(self) -> bool:
        return len(self._window) == self.period

    def seed(self, candles: Sequence[Candle]) -> None:
        self._window.clear()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        self._window.append(candle.close)
        return self.current()

    def current(self) -> float:
        if not self.warmed_up:
            return NAN
        return _alma_value(list(self._window), self._weights, self._total)


def _vidya_start(period: int, volatility_period: int) -> int:
    """Return the first index at which §1.8's recursion can run.

    §1.8 states no seed. The recursion is EMA's with ``alpha`` scaled by ``k``, so
    the seed §0.3 states for EMA is the one reused: the average of the ``period``
    closes ending at the first candle where ``k`` also exists.
    """
    if period <= 0:
        raise ValueError("period must be positive")
    if volatility_period <= 0:
        raise ValueError("volatility_period must be positive")
    return max(period - 1, volatility_period)


def vidya(
    candles: Sequence[Candle],
    period: int = 21,
    volatility_period: int = 9,
) -> list[float]:
    """Scale an EMA's alpha by Chande momentum, as §1.8 writes it.

    §12 lists VIDYA as an indicator whose ``k`` differs between implementations.
    The body of §1.8 defines ``k`` as ``|CMO(P, m)| / 100`` and its note records
    that Chande's original used a ratio of a short to a long standard deviation.
    The body is what this follows; the standard-deviation ratio is not implemented.
    """
    start = _vidya_start(period, volatility_period)
    closes = [candle.close for candle in candles]
    seeds = sma_primitive(closes, period)
    factors = cmo(candles, volatility_period)
    alpha = 2.0 / (period + 1.0)
    result: list[float] = [NAN] * len(closes)
    current: float | None = None
    for index in range(start, len(closes)):
        if current is None:
            current = seeds[index]
        else:
            rate = alpha * abs(factors[index]) / 100.0
            current = rate * closes[index] + (1.0 - rate) * current
        result[index] = current
    return result


@dataclass(slots=True)
class VIDYAState:
    """Variable index dynamic average state over a seed window and a CMO."""

    period: int = 21
    volatility_period: int = 9
    min_history: int = field(init=False)
    _alpha: float = field(init=False)
    _start: int = field(init=False)
    _index: int = field(init=False, default=-1)
    _seed: SmaState = field(init=False)
    _volatility: CMOState = field(init=False)
    _value: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self._start = _vidya_start(self.period, self.volatility_period)
        self.min_history = self._start + 1
        self._alpha = 2.0 / (self.period + 1.0)
        self._seed = SmaState(self.period)
        self._volatility = CMOState(self.volatility_period)

    @property
    def warmed_up(self) -> bool:
        return self._value is not None

    def seed(self, candles: Sequence[Candle]) -> None:
        self._index = -1
        self._value = None
        self._seed.reset()
        self._volatility.seed(())
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        self._index += 1
        average = self._seed.update(candle.close)
        factor = self._volatility.update(candle)
        if self._index < self._start:
            return self.current()
        if self._value is None:
            self._value = average
            return self.current()
        rate = self._alpha * abs(factor) / 100.0
        self._value = rate * candle.close + (1.0 - rate) * self._value
        return self.current()

    def current(self) -> float:
        return self._value if self._value is not None else NAN


def _mcginley_step(price: float, previous: float, period: int) -> float:
    """Return the next §1.9 value from the previous finalized one.

    §1.9 states no substitute for a zero denominator, and §0.11 lists holding the
    previous value as one of the choices an implementation may take. That is the
    one taken here: a denominator that vanishes leaves the average where it was
    rather than inventing a jump. The fourth power is reached by multiplication
    because a float power that overflows raises in Python, while the product
    saturates to infinity and the division below then reads as no step at all.
    """

    ratio = safe_divide(price, previous, on_zero=0.0)
    squared = ratio * ratio
    denominator = period * squared * squared
    return previous + safe_divide(price - previous, denominator, on_zero=0.0)


def mcginley_dynamic(candles: Sequence[Candle], period: int = 21) -> list[float]:
    """Track price with a divisor that reacts to how far price has run (§1.9)."""
    if period <= 0:
        raise ValueError("period must be positive")
    closes = [candle.close for candle in candles]
    seeds = sma_primitive(closes, period)
    result: list[float] = [NAN] * len(closes)
    current: float | None = None
    for index in range(period - 1, len(closes)):
        # §1.9 states no seed either, so the §0.3 rule for a recursive average
        # applies here as it does to VIDYA: start from the average of the first
        # `period` closes and recurse from there.
        if current is None:
            current = seeds[index]
        else:
            current = _mcginley_step(closes[index], current, period)
        result[index] = current
    return result


@dataclass(slots=True)
class McGinleyDynamicState:
    """O(1)-per-candle McGinley Dynamic state over one seed window."""

    period: int = 21
    min_history: int = field(init=False)
    _seed: SmaState = field(init=False)
    _value: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period
        self._seed = SmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return self._value is not None

    def seed(self, candles: Sequence[Candle]) -> None:
        self._seed.reset()
        self._value = None
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        average = self._seed.update(candle.close)
        if isnan(average):
            return self.current()
        if self._value is None:
            self._value = average
        else:
            self._value = _mcginley_step(candle.close, self._value, self.period)
        return self.current()

    def current(self) -> float:
        return self._value if self._value is not None else NAN


GuppyValue = dict[str, float]

GUPPY_SHORT_PERIODS: tuple[int, ...] = (3, 5, 8, 10, 12, 15)
GUPPY_LONG_PERIODS: tuple[int, ...] = (30, 35, 40, 45, 50, 60)


def _guppy_layout() -> tuple[tuple[str, int], ...]:
    """Return each output name paired with the §1.10 period it averages.

    §1.10 gives no single formula, only two groups of exponential averages, so the
    output names carry the group a trader reads the line as belonging to. The short
    group stands for trader behaviour and the long group for investor behaviour,
    and a caller comparing the two groups needs to tell them apart by name.
    """
    return tuple((f"short_{period}", period) for period in GUPPY_SHORT_PERIODS) + tuple(
        (f"long_{period}", period) for period in GUPPY_LONG_PERIODS
    )


def guppy_gmma(candles: Sequence[Candle]) -> list[GuppyValue]:
    """Return the twelve exponential averages §1.10 arranges into two groups."""
    closes = [candle.close for candle in candles]
    layout = _guppy_layout()
    columns = {name: ema_primitive(closes, period) for name, period in layout}
    return [{name: columns[name][index] for name, _ in layout} for index in range(len(candles))]


@dataclass(slots=True)
class GuppyGMMAState:
    """O(1)-per-candle Guppy state over twelve independent EMA primitives."""

    min_history: int = field(init=False)
    _averages: tuple[tuple[str, EmaState], ...] = field(init=False)

    def __post_init__(self) -> None:
        layout = _guppy_layout()
        self.min_history = max(period for _, period in layout)
        self._averages = tuple((name, EmaState(period)) for name, period in layout)

    @property
    def warmed_up(self) -> bool:
        return all(state.warmed_up for _, state in self._averages)

    def seed(self, candles: Sequence[Candle]) -> None:
        for _, state in self._averages:
            state.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> GuppyValue:
        return {name: state.update(candle.close) for name, state in self._averages}

    def current(self) -> GuppyValue:
        return {name: state.current() for name, state in self._averages}


def _trima_lengths(period: int) -> tuple[int, int]:
    """Return the two §1.11 simple-average lengths that overlap into one window.

    Overlapping averages of length `a` and `b` reach across `a + b - 1` candles,
    so a window of exactly `period` candles forces `a + b = period + 1`. What
    picks one split out of those is §1.11's other requirement, that the weights
    rise to the middle of the window and fall back to its end as a triangle. The
    overlap holds its maximum for `abs(a - b) + 1` bars, so a triangle with no
    plateau running past its apex needs `abs(a - b) <= 1`, which leaves
    `period/2` and `period/2 + 1` for an even period and `(period + 1)/2` twice
    for an odd one. Symmetry is not the condition that does this work: the
    overlap of two rectangular windows is symmetric for every `a` and `b`, so a
    period of 6 admits `[1,1,1,1,1,1]`, `[1,2,2,2,2,1]` and `[1,2,3,3,2,1]`
    alike, and only the triangle requirement rejects the first two. §1.11 also
    rejects the other reading, which uses `floor(period/2) + 1` on both sides and
    stretches an even period's window to `period + 1` candles.
    """
    if period <= 0:
        raise ValueError("period must be positive")
    if period % 2 == 0:
        return period // 2, period // 2 + 1
    half = (period + 1) // 2
    return half, half


def trima(candles: Sequence[Candle], period: int = 21) -> list[float]:
    """Average the close twice so the window's weights form a triangle (§1.11).

    Nothing here restates a simple average: both passes are the §0.2 primitive,
    and the second one reads the first one's NaN warm-up as an incomplete window,
    which is what leaves the first `period - 1` candles undefined.
    """
    first, second = _trima_lengths(period)
    closes = [candle.close for candle in candles]
    return sma_primitive(sma_primitive(closes, first), second)


@dataclass(slots=True)
class TRIMAState:
    """O(1)-per-candle triangular average state over two chained simple averages.

    Chaining the two primitive states keeps the cost per candle constant: each
    one evicts a single value from its own window, so no triangular weight is
    ever multiplied out. §1.11 carries no recursion, so there is no seed rule
    beyond the two windows filling up.
    """

    period: int = 21
    min_history: int = field(init=False)
    _inner: SmaState = field(init=False)
    _outer: SmaState = field(init=False)

    def __post_init__(self) -> None:
        first, second = _trima_lengths(self.period)
        # The inner average consumes `first` candles and the outer one then needs
        # `second` of its outputs, which is `first + second - 1 = period` candles.
        self.min_history = self.period
        self._inner = SmaState(first)
        self._outer = SmaState(second)

    @property
    def warmed_up(self) -> bool:
        return self._outer.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._inner.reset()
        self._outer.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        return self._outer.update(self._inner.update(candle.close))

    def current(self) -> float:
        return self._outer.current()
