"""Define required trend indicators and the follow-up trend catalog."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from core_lib.types import Candle

from .primitives import NAN
from .primitives import ema as ema_primitive

FOLLOW_UP_INDICATORS = (
    "DEMA",
    "TEMA",
    "T3",
    "HMA",
    "ZLEMA",
    "ALMA",
    "KAMA",
    "VIDYA",
    "McGinley Dynamic",
    "Guppy GMMA",
)


def ema(candles: Sequence[Candle], period: int) -> list[float]:
    """Compute close-price EMA using the §0.3 SMA seed."""
    return ema_primitive([candle.close for candle in candles], period)


@dataclass(slots=True)
class EMAState:
    """O(1)-per-candle incremental EMA state."""

    period: int
    min_history: int = field(init=False)
    _count: int = field(init=False, default=0)
    _seed_sum: float = field(init=False, default=0.0)
    _value: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period

    @property
    def warmed_up(self) -> bool:
        return self._value is not None

    def seed(self, candles: Sequence[Candle]) -> None:
        self._count = 0
        self._seed_sum = 0.0
        self._value = None
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        if self._value is None:
            self._count += 1
            self._seed_sum += candle.close
            if self._count == self.period:
                self._value = self._seed_sum / self.period
        else:
            alpha = 2.0 / (self.period + 1.0)
            self._value += alpha * (candle.close - self._value)
        return self.current()

    def current(self) -> float:
        return self._value if self._value is not None else NAN
