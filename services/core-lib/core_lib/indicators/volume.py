"""Define required volume indicators and the follow-up volume catalog."""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field

from core_lib.types import Candle

from .primitives import NAN, sma

FOLLOW_UP_INDICATORS = (
    "OBV",
    "A/D Line",
    "Chaikin Oscillator",
    "CMF",
    "MFI",
    "Force Index",
    "EMV",
    "Klinger Volume Oscillator",
    "NVI",
    "PVI",
)


def volume_sma(candles: Sequence[Candle], period: int = 20) -> list[float]:
    """Compute the moving average of base-asset volume."""
    return sma([candle.volume for candle in candles], period)


@dataclass(slots=True)
class VolumeSMAState:
    """O(1)-per-candle volume SMA state."""

    period: int = 20
    min_history: int = field(init=False)
    _window: deque[float] = field(init=False, default_factory=deque)
    _total: float = field(init=False, default=0.0)
    _value: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period

    @property
    def warmed_up(self) -> bool:
        return self._value is not None

    def seed(self, candles: Sequence[Candle]) -> None:
        self._window.clear()
        self._total = 0.0
        self._value = None
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        self._window.append(candle.volume)
        self._total += candle.volume
        if len(self._window) > self.period:
            self._total -= self._window.popleft()
        self._value = self._total / self.period if len(self._window) == self.period else None
        return self.current()

    def current(self) -> float:
        return self._value if self._value is not None else NAN
