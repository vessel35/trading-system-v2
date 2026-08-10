"""Compute paired-price statistics and regression indicators."""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import sqrt

from core_lib.types import Candle

from .primitives import NAN

TA_EPSILON = 1e-14


def _validate_period(period: int) -> None:
    if isinstance(period, bool) or not isinstance(period, int):
        raise TypeError("period must be int")
    if not 1 <= period <= 100_000:
        raise ValueError("period must be between 1 and 100000")


def _validate_pairs(
    candles: Sequence[Candle],
    reference_candles: Sequence[Candle],
) -> None:
    if len(candles) != len(reference_candles):
        raise ValueError("primary and reference candle counts must match")
    if any(
        candle.close_time != reference_candle.close_time
        for candle, reference_candle in zip(candles, reference_candles, strict=True)
    ):
        raise ValueError("primary and reference candle close times must match")


def _simple_return(current: float, previous: float) -> float:
    if abs(previous) < TA_EPSILON:
        return 0.0
    return (current - previous) / previous


def paired_vectorized_requires_reference(_candles: Sequence[Candle]) -> list[float]:
    """Reject the single-series batch path for a paired-series indicator."""
    raise TypeError("paired indicator batch calculation requires a reference series")


@dataclass(slots=True)
class BetaState:
    """TA-Lib BETA over reference returns X and primary returns Y."""

    period: int = 5
    min_history: int = field(init=False)
    _returns: deque[tuple[float, float]] = field(init=False, default_factory=deque)
    _previous_primary: float | None = field(init=False, default=None)
    _previous_reference: float | None = field(init=False, default=None)
    _sum_xx: float = field(init=False, default=0.0)
    _sum_xy: float = field(init=False, default=0.0)
    _sum_x: float = field(init=False, default=0.0)
    _sum_y: float = field(init=False, default=0.0)
    _value: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        _validate_period(self.period)
        self.min_history = self.period + 1

    @property
    def warmed_up(self) -> bool:
        return self._value is not None

    def seed(
        self,
        candles: Sequence[Candle],
        reference_candles: Sequence[Candle],
    ) -> None:
        _validate_pairs(candles, reference_candles)
        self._returns.clear()
        self._previous_primary = None
        self._previous_reference = None
        self._sum_xx = 0.0
        self._sum_xy = 0.0
        self._sum_x = 0.0
        self._sum_y = 0.0
        self._value = None
        for candle, reference_candle in zip(candles, reference_candles, strict=True):
            self.update(candle, reference_candle)

    def update(self, candle: Candle, reference_candle: Candle) -> float:
        if candle.close_time != reference_candle.close_time:
            raise ValueError("primary and reference candle close times must match")

        primary = candle.close
        reference = reference_candle.close
        if self._previous_primary is None or self._previous_reference is None:
            self._previous_primary = primary
            self._previous_reference = reference
            return NAN

        x = _simple_return(reference, self._previous_reference)
        y = _simple_return(primary, self._previous_primary)
        self._previous_primary = primary
        self._previous_reference = reference
        self._returns.append((x, y))
        self._sum_xx += x * x
        self._sum_xy += x * y
        self._sum_x += x
        self._sum_y += y

        if len(self._returns) < self.period:
            return NAN

        count = float(self.period)
        denominator = count * self._sum_xx - self._sum_x * self._sum_x
        if abs(denominator) < TA_EPSILON:
            self._value = 0.0
        else:
            self._value = (count * self._sum_xy - self._sum_x * self._sum_y) / denominator

        trailing_x, trailing_y = self._returns.popleft()
        self._sum_xx -= trailing_x * trailing_x
        self._sum_xy -= trailing_x * trailing_y
        self._sum_x -= trailing_x
        self._sum_y -= trailing_y
        return self._value

    def current(self) -> float:
        return NAN if self._value is None else self._value


@dataclass(slots=True)
class CorrelState:
    """TA-Lib Pearson correlation over reference X and primary Y prices."""

    period: int = 30
    min_history: int = field(init=False)
    _prices: deque[tuple[float, float]] = field(init=False, default_factory=deque)
    _sum_x: float = field(init=False, default=0.0)
    _sum_y: float = field(init=False, default=0.0)
    _sum_xx: float = field(init=False, default=0.0)
    _sum_yy: float = field(init=False, default=0.0)
    _sum_xy: float = field(init=False, default=0.0)
    _value: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        _validate_period(self.period)
        self.min_history = self.period

    @property
    def warmed_up(self) -> bool:
        return self._value is not None

    def seed(
        self,
        candles: Sequence[Candle],
        reference_candles: Sequence[Candle],
    ) -> None:
        _validate_pairs(candles, reference_candles)
        self._prices.clear()
        self._sum_x = 0.0
        self._sum_y = 0.0
        self._sum_xx = 0.0
        self._sum_yy = 0.0
        self._sum_xy = 0.0
        self._value = None
        for candle, reference_candle in zip(candles, reference_candles, strict=True):
            self.update(candle, reference_candle)

    def update(self, candle: Candle, reference_candle: Candle) -> float:
        if candle.close_time != reference_candle.close_time:
            raise ValueError("primary and reference candle close times must match")

        if len(self._prices) == self.period:
            trailing_x, trailing_y = self._prices.popleft()
            self._sum_x -= trailing_x
            self._sum_y -= trailing_y
            self._sum_xx -= trailing_x * trailing_x
            self._sum_yy -= trailing_y * trailing_y
            self._sum_xy -= trailing_x * trailing_y

        x = reference_candle.close
        y = candle.close
        self._prices.append((x, y))
        self._sum_x += x
        self._sum_y += y
        self._sum_xx += x * x
        self._sum_yy += y * y
        self._sum_xy += x * y

        if len(self._prices) < self.period:
            return NAN

        count = float(self.period)
        variance_x = self._sum_xx - self._sum_x * self._sum_x / count
        variance_y = self._sum_yy - self._sum_y * self._sum_y / count
        denominator = variance_x * variance_y
        if denominator < TA_EPSILON:
            self._value = 0.0
        else:
            self._value = (self._sum_xy - self._sum_x * self._sum_y / count) / sqrt(denominator)
        return self._value

    def current(self) -> float:
        return NAN if self._value is None else self._value


def beta(
    candles: Sequence[Candle],
    reference_candles: Sequence[Candle],
    period: int = 5,
) -> list[float]:
    """Compute BETA with reference returns as X and primary returns as Y."""
    _validate_pairs(candles, reference_candles)
    state = BetaState(period)
    return [
        state.update(candle, reference_candle)
        for candle, reference_candle in zip(candles, reference_candles, strict=True)
    ]


def correl(
    candles: Sequence[Candle],
    reference_candles: Sequence[Candle],
    period: int = 30,
) -> list[float]:
    """Compute Pearson correlation over matched primary/reference closes."""
    _validate_pairs(candles, reference_candles)
    state = CorrelState(period)
    return [
        state.update(candle, reference_candle)
        for candle, reference_candle in zip(candles, reference_candles, strict=True)
    ]
