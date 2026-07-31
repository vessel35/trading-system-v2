"""Define required volume indicators and the follow-up volume catalog."""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isnan

from core_lib.types import Candle

from .primitives import (
    NAN,
    CumulativeState,
    EmaState,
    SmaState,
    ema,
    hl2,
    safe_divide,
    sma,
    tp,
)

KlingerValue = dict[str, float]

# Every volume indicator the standard specifies is now registered, so nothing
# remains in this category's follow-up catalog.
FOLLOW_UP_INDICATORS: tuple[str, ...] = ()


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


def _money_flow_index_value(positive: float, negative: float) -> float:
    """Turn §4.5's two classified money flows into the index itself.

    §4.5 writes `MFI = 100 - 100/(1 + PMF/NMF)`, which has no value when NMF is
    zero. §0.11 names 100 for the RSI family when the opposing side is empty,
    and 100 is also what the expression approaches as NMF falls towards zero, so
    the substitute here is the standard's own answer rather than a new one. A
    window in which neither side received any flow has no ratio in either
    direction; this repository reads that emptiness the way its RSI reads the
    same emptiness in §2.1, which answers 100 there as well.
    """

    if negative == 0.0:
        return 100.0
    if positive == 0.0:
        return 0.0
    return 100.0 - 100.0 / (1.0 + positive / negative)


def money_flow_index(candles: Sequence[Candle], period: int = 14) -> list[float]:
    """Weigh typical-price direction by traded volume (§4.5).

    The name is written out rather than shortened because §6.4's Market
    Facilitation Index is commonly abbreviated the same way, and the two are
    unrelated calculations.
    """

    if period <= 0:
        raise ValueError("period must be positive")
    prices = tp(candles)
    positive: list[float] = []
    negative: list[float] = []
    for index, candle in enumerate(candles):
        if index == 0:
            # A raw money flow has no direction until there is an earlier
            # typical price to compare it with.
            positive.append(NAN)
            negative.append(NAN)
            continue
        flow = prices[index] * candle.volume
        positive.append(flow if prices[index] > prices[index - 1] else 0.0)
        negative.append(flow if prices[index] < prices[index - 1] else 0.0)
    # The two sums of §4.5 run over one shared window, so their averages stand in
    # for them: dividing both by the same length leaves the ratio unchanged, and
    # it lets the shared rolling average carry the window.
    positive_average = sma(positive, period)
    negative_average = sma(negative, period)
    return [
        NAN if isnan(gain) or isnan(loss) else _money_flow_index_value(gain, loss)
        for gain, loss in zip(positive_average, negative_average, strict=True)
    ]


@dataclass(slots=True)
class MoneyFlowIndexState:
    """O(1)-per-candle Money Flow Index state over two rolling averages."""

    period: int = 14
    min_history: int = field(init=False)
    _previous_price: float | None = field(init=False, default=None)
    _positive: SmaState = field(init=False)
    _negative: SmaState = field(init=False)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        # The first candle carries no direction, so a full window of classified
        # flows lands one candle after the period itself.
        self.min_history = self.period + 1
        self._positive = SmaState(self.period)
        self._negative = SmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return self._negative.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._previous_price = None
        self._positive.reset()
        self._negative.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        price = tp((candle,))[0]
        if self._previous_price is None:
            gain = self._positive.update(NAN)
            loss = self._negative.update(NAN)
        else:
            flow = price * candle.volume
            gain = self._positive.update(flow if price > self._previous_price else 0.0)
            loss = self._negative.update(flow if price < self._previous_price else 0.0)
        self._previous_price = price
        return NAN if isnan(gain) or isnan(loss) else _money_flow_index_value(gain, loss)

    def current(self) -> float:
        gain = self._positive.current()
        loss = self._negative.current()
        return NAN if isnan(gain) or isnan(loss) else _money_flow_index_value(gain, loss)


def _ease_of_movement_raw(
    candle: Candle,
    distance_moved: float,
    scale: int,
) -> float:
    """Return one candle's unsmoothed ease of movement (§4.7).

    §4.7 writes the raw value as `DistanceMoved / BoxRatio` with
    `BoxRatio = (V / scale) / (H - L)`. Dividing by that quotient is multiplying
    by its reciprocal, so the same value is written here as a single division by
    volume. The two forms agree wherever both are defined, and the single
    division is what makes the degenerate candles expressible: a candle with no
    range has an infinite box ratio, whose reciprocal is the zero this form
    produces on its own.

    §4.7 names no substitute for a candle that traded nothing, and the engine
    accepts no non-finite scalar after warm-up. A candle with no volume offers
    nothing to weigh the move against, so it enters the average as zero rather
    than as an invented amount of ease.
    """

    box = distance_moved * (candle.high - candle.low) * scale
    return safe_divide(box, candle.volume, on_zero=0.0)


def ease_of_movement(
    candles: Sequence[Candle],
    period: int = 14,
    scale: int = 100_000_000,
) -> list[float]:
    """Smooth how far the median price moved per unit of volume (§4.7)."""

    if period <= 0:
        raise ValueError("period must be positive")
    if scale <= 0:
        raise ValueError("scale must be positive")
    median = hl2(candles)
    raw: list[float] = []
    for index, candle in enumerate(candles):
        if index == 0:
            # Distance moved needs an earlier median price to measure against.
            raw.append(NAN)
            continue
        raw.append(_ease_of_movement_raw(candle, median[index] - median[index - 1], scale))
    return sma(raw, period)


@dataclass(slots=True)
class EaseOfMovementState:
    """O(1)-per-candle Ease of Movement state over one rolling average."""

    period: int = 14
    scale: int = 100_000_000
    min_history: int = field(init=False)
    _previous_median: float | None = field(init=False, default=None)
    _average: SmaState = field(init=False)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        if self.scale <= 0:
            raise ValueError("scale must be positive")
        # The first candle has no distance moved, so the window closes one
        # candle after the period itself.
        self.min_history = self.period + 1
        self._average = SmaState(self.period)

    @property
    def warmed_up(self) -> bool:
        return self._average.warmed_up

    def seed(self, candles: Sequence[Candle]) -> None:
        self._previous_median = None
        self._average.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        median = hl2((candle,))[0]
        if self._previous_median is None:
            raw = NAN
        else:
            raw = _ease_of_movement_raw(candle, median - self._previous_median, self.scale)
        self._previous_median = median
        return self._average.update(raw)

    def current(self) -> float:
        return self._average.current()


def _hlc_sum(candle: Candle) -> float:
    """Return `H + L + C`, the quantity §4.8's trend test compares."""
    return candle.high + candle.low + candle.close


def _klinger_step(
    candle: Candle,
    previous: Candle,
    previous_trend: float | None,
    cumulative_range: float,
) -> tuple[float, float, float]:
    """Advance §4.8 by one candle, returning its Volume Force, trend and cm.

    §4.8 carries cm forward while the trend holds and restarts it from the two
    most recent ranges when the trend turns. On the first transition there is no
    earlier trend at all, so `trend_t == trend_{t-1}` cannot hold and the else
    branch the standard already writes is the one that applies: cm becomes
    `dm_{t-1} + dm_t`. That reading fills in nothing the standard left blank; it
    only decides which of the two branches §4.8 wrote covers the first candle.

    §12 records that implementations disagree over both this initialization and
    the absolute value in the Volume Force. The form above is §4.8's own, with
    the absolute value around `2*(dm/cm) - 1` and the trend sign applied outside
    it, and the variants that drop the absolute value or seed cm differently are
    not followed here.
    """

    span = candle.high - candle.low
    trend = 1.0 if _hlc_sum(candle) > _hlc_sum(previous) else -1.0
    if previous_trend is not None and trend == previous_trend:
        cumulative = cumulative_range + span
    else:
        cumulative = (previous.high - previous.low) + span
    if cumulative == 0.0:
        # cm accumulates non-negative ranges, so it reaches zero only when this
        # candle's own range is zero with it. §4.8 gives no substitute for the
        # ratio there, and a candle that spanned nothing exerted no force, which
        # is what this records instead of an invented ratio.
        return 0.0, trend, cumulative
    force = candle.volume * abs(2.0 * (span / cumulative) - 1.0) * trend * 100.0
    return force, trend, cumulative


def klinger_volume_oscillator(
    candles: Sequence[Candle],
    short_period: int = 34,
    long_period: int = 55,
    signal_period: int = 13,
) -> list[KlingerValue]:
    """Contrast two smoothings of §4.8's Volume Force and signal the result."""

    if short_period <= 0 or long_period <= 0 or signal_period <= 0:
        raise ValueError("periods must be positive")
    if short_period >= long_period:
        raise ValueError("short_period must be shorter than long_period")
    forces: list[float] = []
    trend: float | None = None
    cumulative = 0.0
    for index, candle in enumerate(candles):
        if index == 0:
            # The trend test needs an earlier candle, so no force exists yet.
            forces.append(NAN)
            continue
        force, trend, cumulative = _klinger_step(candle, candles[index - 1], trend, cumulative)
        forces.append(force)
    fast = ema(forces, short_period)
    slow = ema(forces, long_period)
    oscillator = [
        NAN if isnan(quick) or isnan(base) else quick - base
        for quick, base in zip(fast, slow, strict=True)
    ]
    signal = ema(oscillator, signal_period)
    return [
        {"kvo": value, "signal": smoothed}
        for value, smoothed in zip(oscillator, signal, strict=True)
    ]


@dataclass(slots=True)
class KlingerVolumeOscillatorState:
    """O(1)-per-candle Klinger state over three exponential averages."""

    short_period: int = 34
    long_period: int = 55
    signal_period: int = 13
    min_history: int = field(init=False)
    _previous: Candle | None = field(init=False, default=None)
    _trend: float | None = field(init=False, default=None)
    _cumulative: float = field(init=False, default=0.0)
    _fast: EmaState = field(init=False)
    _slow: EmaState = field(init=False)
    _signal: EmaState = field(init=False)
    _value: KlingerValue = field(
        init=False,
        default_factory=lambda: {"kvo": NAN, "signal": NAN},
    )

    def __post_init__(self) -> None:
        if self.short_period <= 0 or self.long_period <= 0 or self.signal_period <= 0:
            raise ValueError("periods must be positive")
        if self.short_period >= self.long_period:
            raise ValueError("short_period must be shorter than long_period")
        # The first candle carries no Volume Force, so the slow average closes
        # one candle later than its own period, and the signal needs its own
        # period of oscillator values after that.
        self.min_history = self.long_period + self.signal_period
        self._fast = EmaState(self.short_period)
        self._slow = EmaState(self.long_period)
        self._signal = EmaState(self.signal_period)

    @property
    def warmed_up(self) -> bool:
        return not isnan(self._value["signal"])

    def seed(self, candles: Sequence[Candle]) -> None:
        self._previous = None
        self._trend = None
        self._cumulative = 0.0
        for state in (self._fast, self._slow, self._signal):
            state.reset()
        self._value = {"kvo": NAN, "signal": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> KlingerValue:
        if self._previous is None:
            force = NAN
        else:
            force, self._trend, self._cumulative = _klinger_step(
                candle,
                self._previous,
                self._trend,
                self._cumulative,
            )
        self._previous = candle
        fast = self._fast.update(force)
        slow = self._slow.update(force)
        oscillator = NAN if isnan(fast) or isnan(slow) else fast - slow
        self._value = {"kvo": oscillator, "signal": self._signal.update(oscillator)}
        return self.current()

    def current(self) -> KlingerValue:
        return dict(self._value)


# §4.9 and §4.10 both start their accumulation here.
VOLUME_INDEX_SEED = 1000.0


def _volume_index_step(
    candle: Candle,
    previous: Candle,
    value: float,
    *,
    on_rising_volume: bool,
) -> float:
    """Advance §4.9's or §4.10's accumulation by one candle."""

    moved = candle.volume > previous.volume if on_rising_volume else candle.volume < previous.volume
    if not moved:
        return value
    # Neither section names a substitute for a zero earlier close, and a price of
    # zero is outside what they describe. Reading the change as nothing holds the
    # index still rather than inventing a move for it.
    change = safe_divide(candle.close - previous.close, previous.close, on_zero=0.0)
    return value * (1.0 + change)


def _volume_index(candles: Sequence[Candle], *, on_rising_volume: bool) -> list[float]:
    """Accumulate the shared recursion behind §4.9 and §4.10."""

    result: list[float] = []
    value = VOLUME_INDEX_SEED
    for index, candle in enumerate(candles):
        if index > 0:
            value = _volume_index_step(
                candle,
                candles[index - 1],
                value,
                on_rising_volume=on_rising_volume,
            )
        result.append(value)
    return result


def negative_volume_index(candles: Sequence[Candle]) -> list[float]:
    """Compound the price change only on candles whose volume fell (§4.9)."""
    return _volume_index(candles, on_rising_volume=False)


def positive_volume_index(candles: Sequence[Candle]) -> list[float]:
    """Compound the price change only on candles whose volume rose (§4.10)."""
    return _volume_index(candles, on_rising_volume=True)


@dataclass(slots=True)
class VolumeIndexState:
    """O(1)-per-candle state behind §4.9's NVI and §4.10's PVI.

    The two sections differ in one comparison, whether volume fell or rose, and
    agree on everything else, so one state carries both rather than two copies
    of the same recursion. The seed is already a value, so the first candle is
    the first warm one.
    """

    on_rising_volume: bool
    min_history: int = field(init=False, default=1)
    _previous: Candle | None = field(init=False, default=None)
    _value: float = field(init=False, default=VOLUME_INDEX_SEED)

    @property
    def warmed_up(self) -> bool:
        return self._previous is not None

    def seed(self, candles: Sequence[Candle]) -> None:
        self._previous = None
        self._value = VOLUME_INDEX_SEED
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        if self._previous is not None:
            self._value = _volume_index_step(
                candle,
                self._previous,
                self._value,
                on_rising_volume=self.on_rising_volume,
            )
        self._previous = candle
        return self.current()

    def current(self) -> float:
        return self._value if self._previous is not None else NAN
