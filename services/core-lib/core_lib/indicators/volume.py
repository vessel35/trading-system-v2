"""Define required volume indicators and the follow-up volume catalog."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from core_lib.types import Candle

from .primitives import SmaState, sma

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
    """O(1)-per-candle volume SMA state built on the shared rolling average."""

    period: int = 20
    min_history: int = field(init=False)
    _average: SmaState = field(init=False)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
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
        return self._average.update(candle.volume)

    def current(self) -> float:
        return self._average.current()
