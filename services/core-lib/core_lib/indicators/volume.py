"""Define required volume indicators and the follow-up volume catalog."""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isnan

from core_lib.types import Candle

from .primitives import NAN, CumulativeState, EmaState, SmaState, ema, safe_divide, sma

FOLLOW_UP_INDICATORS = (
    "MFI",
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


def _money_flow_volume(candle: Candle) -> float:
    """Return one candle's money flow volume; §4.2 keeps a rangeless candle at zero."""
    multiplier = safe_divide(
        (candle.close - candle.low) - (candle.high - candle.close),
        candle.high - candle.low,
        on_zero=0.0,
    )
    return multiplier * candle.volume


def chaikin_oscillator(
    candles: Sequence[Candle],
    fast_period: int = 3,
    slow_period: int = 10,
) -> list[float]:
    """Compute the Chaikin Oscillator over the A/D Line (§4.3)."""
    if fast_period <= 0 or slow_period <= 0:
        raise ValueError("periods must be positive")
    if fast_period >= slow_period:
        raise ValueError("fast_period must be shorter than slow_period")
    line = ad_line(candles)
    fast = ema(line, fast_period)
    slow = ema(line, slow_period)
    return [
        NAN if isnan(quick) or isnan(base) else quick - base
        for quick, base in zip(fast, slow, strict=True)
    ]


@dataclass(slots=True)
class ChaikinOscillatorState:
    """O(1)-per-candle Chaikin Oscillator state over the accumulated line."""

    fast_period: int = 3
    slow_period: int = 10
    min_history: int = field(init=False)
    _line: ADLineState = field(init=False)
    _fast: EmaState = field(init=False)
    _slow: EmaState = field(init=False)

    def __post_init__(self) -> None:
        if self.fast_period <= 0 or self.slow_period <= 0:
            raise ValueError("periods must be positive")
        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be shorter than slow_period")
        self.min_history = self.slow_period
        self._line = ADLineState()
        self._fast = EmaState(self.fast_period)
        self._slow = EmaState(self.slow_period)

    @property
    def warmed_up(self) -> bool:
        return self._slow.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._line.seed(())
        self._fast.reset()
        self._slow.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        line = self._line.update(candle)
        fast = self._fast.update(line)
        slow = self._slow.update(line)
        return NAN if isnan(fast) or isnan(slow) else fast - slow

    def current(self) -> float:
        fast = self._fast.current()
        slow = self._slow.current()
        return NAN if isnan(fast) or isnan(slow) else fast - slow


def cmf(candles: Sequence[Candle], period: int = 20) -> list[float]:
    """Compute Chaikin Money Flow, money flow volume over volume (§4.4)."""
    if period <= 0:
        raise ValueError("period must be positive")
    flows: deque[float] = deque(maxlen=period)
    volumes: deque[float] = deque(maxlen=period)
    result: list[float] = []
    for candle in candles:
        flows.append(_money_flow_volume(candle))
        volumes.append(candle.volume)
        if len(flows) < period:
            result.append(NAN)
            continue
        # A window with no volume at all has no money flow to weigh, which the
        # ratio reads as neutral. §4.4 names no substitute, so this is decided here.
        result.append(safe_divide(sum(flows), sum(volumes), on_zero=0.0))
    return result


@dataclass(slots=True)
class CMFState:
    """O(1)-per-candle Chaikin Money Flow state over two rolling sums."""

    period: int = 20
    min_history: int = field(init=False)
    _flows: SmaState = field(init=False)
    _volumes: SmaState = field(init=False)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period
        self._flows = SmaState(self.period)
        self._volumes = SmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return self._volumes.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._flows.reset()
        self._volumes.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        flow = self._flows.update(_money_flow_volume(candle))
        volume = self._volumes.update(candle.volume)
        if isnan(flow) or isnan(volume):
            return NAN
        # Both averages share the same window length, so their ratio is the ratio
        # of the sums the standard writes.
        return safe_divide(flow, volume, on_zero=0.0)

    def current(self) -> float:
        flow = self._flows.current()
        volume = self._volumes.current()
        if isnan(flow) or isnan(volume):
            return NAN
        return safe_divide(flow, volume, on_zero=0.0)


def obv(candles: Sequence[Candle]) -> list[float]:
    """Accumulate volume with the sign of each close-to-close move (§4.1)."""
    total = CumulativeState()
    result: list[float] = []
    previous_close: float | None = None
    for candle in candles:
        if previous_close is None:
            contribution = 0.0
        elif candle.close > previous_close:
            contribution = candle.volume
        elif candle.close < previous_close:
            contribution = -candle.volume
        else:
            contribution = 0.0
        previous_close = candle.close
        result.append(total.update(contribution))
    return result


@dataclass(slots=True)
class OBVState:
    """O(1)-per-candle On-Balance Volume state."""

    min_history: int = field(init=False, default=1)
    _total: CumulativeState = field(init=False, default_factory=CumulativeState)
    _previous_close: float | None = field(init=False, default=None)

    @property
    def warmed_up(self) -> bool:
        return self._total.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._total.reset()
        self._previous_close = None
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        if self._previous_close is None or candle.close == self._previous_close:
            contribution = 0.0
        elif candle.close > self._previous_close:
            contribution = candle.volume
        else:
            contribution = -candle.volume
        self._previous_close = candle.close
        return self._total.update(contribution)

    def current(self) -> float:
        return self._total.current()


def force_index(candles: Sequence[Candle], period: int = 13) -> list[float]:
    """Smooth price change weighted by volume (§4.6)."""
    if period <= 0:
        raise ValueError("period must be positive")
    raw = [NAN]
    for previous, current in zip(candles, candles[1:], strict=False):
        raw.append((current.close - previous.close) * current.volume)
    return ema(raw, period)


@dataclass(slots=True)
class ForceIndexState:
    """O(1)-per-candle Force Index state over one smoothed series."""

    period: int = 13
    min_history: int = field(init=False)
    _previous_close: float | None = field(init=False, default=None)
    _average: EmaState = field(init=False)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.min_history = self.period + 1
        self._average = EmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return self._average.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._previous_close = None
        self._average.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        if self._previous_close is None:
            self._previous_close = candle.close
            return self._average.update(NAN)
        raw = (candle.close - self._previous_close) * candle.volume
        self._previous_close = candle.close
        return self._average.update(raw)

    def current(self) -> float:
        return self._average.current()
