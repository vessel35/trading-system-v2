"""Define required volume indicators and the follow-up volume catalog."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from core_lib.types import Candle

from .primitives import CumulativeState, SmaState, safe_divide, sma

FOLLOW_UP_INDICATORS = (
    "OBV",
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


def ad_line(candles: Sequence[Candle]) -> list[float]:
    """Compute the Accumulation/Distribution Line (§4.2).

    The standard states the degenerate case for this one: when high equals low
    the money flow multiplier is zero, so a candle with no range contributes
    nothing rather than being undefined.
    """
    total = CumulativeState()
    result: list[float] = []
    for candle in candles:
        multiplier = safe_divide(
            (candle.close - candle.low) - (candle.high - candle.close),
            candle.high - candle.low,
            on_zero=0.0,
        )
        result.append(total.update(multiplier * candle.volume))
    return result


@dataclass(slots=True)
class ADLineState:
    """O(1)-per-candle Accumulation/Distribution Line state."""

    min_history: int = field(init=False, default=1)
    _total: CumulativeState = field(init=False, default_factory=CumulativeState)

    @property
    def warmed_up(self) -> bool:
        return self._total.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._total.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        multiplier = safe_divide(
            (candle.close - candle.low) - (candle.high - candle.close),
            candle.high - candle.low,
            on_zero=0.0,
        )
        return self._total.update(multiplier * candle.volume)

    def current(self) -> float:
        return self._total.current()
