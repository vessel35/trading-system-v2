"""Define required trend indicators and the follow-up trend catalog."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from core_lib.types import Candle

from .primitives import EmaState
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
