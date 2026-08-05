"""Port the seven TA-Lib 0.7.1 Hilbert functions into pure Python.

The batch and incremental paths intentionally have separate loops and separate
state transitions.  They share constants and the boundary objects between the
common Hilbert front end and the indicator-specific layers, but neither path calls
the other.  This keeps the batch path useful as an independent parity oracle.
"""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from math import atan, cos, sin

from core_lib.types import Candle

from .primitives import NAN

HilbertPoint = tuple[float, float, float, float]
MAMAValue = dict[str, float]
PhasorValue = dict[str, float]
SineValue = dict[str, float]

FOLLOW_UP_INDICATORS = ("Roofing Filter",)

_HILBERT_A = 0.0962
_HILBERT_B = 0.5769
_SHORT_WMA_ONLY_STEPS = 9
_LONG_WMA_ONLY_STEPS = 34
_RAD_TO_DEG = 180.0 / (4.0 * atan(1.0))
_PHASE_RAD_TO_DEG = 45.0 / atan(1.0)
_DEG_TO_RAD = 1.0 / _PHASE_RAD_TO_DEG
_TWO_PI = atan(1.0) * 8.0


def _validate_mama_limits(fastlimit: float, slowlimit: float) -> None:
    if not 0.01 <= fastlimit <= 0.99:
        raise ValueError("fastlimit must be between 0.01 and 0.99")
    if not 0.01 <= slowlimit <= 0.99:
        raise ValueError("slowlimit must be between 0.01 and 0.99")


def _mama_alpha(delta_phase: float, fastlimit: float, slowlimit: float) -> float:
    """Apply TA-Lib's ordered delta-phase branches, including the 1.0 edge."""
    if delta_phase < 1.0:
        delta_phase = 1.0
    if delta_phase > 1.0:
        alpha = fastlimit / delta_phase
        if alpha < slowlimit:
            alpha = slowlimit
        return alpha
    return fastlimit


def _batch_hilbert_core(
    closes: Sequence[float],
    wma_only_steps: int,
) -> list[HilbertPoint | None]:
    """Run the batch-only WMA, Hilbert, Re/Im, and period pipeline.

    A point is ``(smoothPrice, I1, Q1, period)``.  The long-lookback functions
    pass 34 WMA-only steps, while the 32-lookback functions pass nine, exactly as
    their respective C functions do before entering the Hilbert loop.
    """
    points: list[HilbertPoint | None] = [None] * len(closes)
    if len(closes) < 3:
        return points

    period_wma_sub = closes[0]
    period_wma_sum = closes[0]
    period_wma_sub += closes[1]
    period_wma_sum += closes[1] * 2.0
    period_wma_sub += closes[2]
    period_wma_sum += closes[2] * 3.0
    trailing_wma_value = 0.0

    hilbert_index = 0
    detrender_buffers = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    q1_buffers = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    ji_buffers = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    jq_buffers = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    previous_detrender = [0.0, 0.0]
    previous_detrender_input = [0.0, 0.0]
    previous_q1 = [0.0, 0.0]
    previous_q1_input = [0.0, 0.0]
    previous_ji = [0.0, 0.0]
    previous_ji_input = [0.0, 0.0]
    previous_jq = [0.0, 0.0]
    previous_jq_input = [0.0, 0.0]
    i1_previous_2 = [0.0, 0.0]
    i1_previous_3 = [0.0, 0.0]
    previous_q2 = 0.0
    previous_i2 = 0.0
    re = 0.0
    im = 0.0
    period = 0.0
    first_hilbert_index = 3 + wma_only_steps

    for index in range(3, len(closes)):
        value = closes[index]
        period_wma_sub += value
        period_wma_sub -= trailing_wma_value
        period_wma_sum += value * 4.0
        trailing_wma_value = closes[index - 3]
        smooth_price = period_wma_sum * 0.1
        period_wma_sum -= period_wma_sub
        if index < first_hilbert_index:
            continue

        adjusted_previous_period = 0.075 * period + 0.54
        parity = 0 if index % 2 == 0 else 1
        opposite_parity = 1 - parity

        hilbert_temp = _HILBERT_A * smooth_price
        detrender = -detrender_buffers[parity][hilbert_index]
        detrender_buffers[parity][hilbert_index] = hilbert_temp
        detrender += hilbert_temp
        detrender -= previous_detrender[parity]
        previous_detrender[parity] = _HILBERT_B * previous_detrender_input[parity]
        detrender += previous_detrender[parity]
        previous_detrender_input[parity] = smooth_price
        detrender *= adjusted_previous_period

        hilbert_temp = _HILBERT_A * detrender
        q1 = -q1_buffers[parity][hilbert_index]
        q1_buffers[parity][hilbert_index] = hilbert_temp
        q1 += hilbert_temp
        q1 -= previous_q1[parity]
        previous_q1[parity] = _HILBERT_B * previous_q1_input[parity]
        q1 += previous_q1[parity]
        previous_q1_input[parity] = detrender
        q1 *= adjusted_previous_period

        inphase = i1_previous_3[parity]
        hilbert_temp = _HILBERT_A * inphase
        ji = -ji_buffers[parity][hilbert_index]
        ji_buffers[parity][hilbert_index] = hilbert_temp
        ji += hilbert_temp
        ji -= previous_ji[parity]
        previous_ji[parity] = _HILBERT_B * previous_ji_input[parity]
        ji += previous_ji[parity]
        previous_ji_input[parity] = inphase
        ji *= adjusted_previous_period

        hilbert_temp = _HILBERT_A * q1
        jq = -jq_buffers[parity][hilbert_index]
        jq_buffers[parity][hilbert_index] = hilbert_temp
        jq += hilbert_temp
        jq -= previous_jq[parity]
        previous_jq[parity] = _HILBERT_B * previous_jq_input[parity]
        jq += previous_jq[parity]
        previous_jq_input[parity] = q1
        jq *= adjusted_previous_period

        if parity == 0:
            hilbert_index += 1
            if hilbert_index == 3:
                hilbert_index = 0

        q2 = 0.2 * (q1 + ji) + 0.8 * previous_q2
        i2 = 0.2 * (inphase - jq) + 0.8 * previous_i2
        i1_previous_3[opposite_parity] = i1_previous_2[opposite_parity]
        i1_previous_2[opposite_parity] = detrender

        re = 0.2 * (i2 * previous_i2 + q2 * previous_q2) + 0.8 * re
        im = 0.2 * (i2 * previous_q2 - q2 * previous_i2) + 0.8 * im
        previous_q2 = q2
        previous_i2 = i2
        previous_period = period
        if im != 0.0 and re != 0.0:
            period = 360.0 / (atan(im / re) * _RAD_TO_DEG)
        upper = 1.5 * previous_period
        if period > upper:
            period = upper
        lower = 0.67 * previous_period
        if period < lower:
            period = lower
        if period < 6.0:
            period = 6.0
        elif period > 50.0:
            period = 50.0
        period = 0.2 * period + 0.8 * previous_period
        points[index] = (smooth_price, inphase, q1, period)

    return points


class _HilbertStateCore:
    """Incremental-only counterpart to :func:`_batch_hilbert_core`."""

    def __init__(self, wma_only_steps: int) -> None:
        self._wma_only_steps = wma_only_steps
        self.reset()

    def reset(self) -> None:
        self._count = 0
        self._wma_closes: deque[float] = deque(maxlen=4)
        self._period_wma_sub = 0.0
        self._period_wma_sum = 0.0
        self._trailing_wma_value = 0.0
        self._hilbert_index = 0
        self._detrender_buffers = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        self._q1_buffers = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        self._ji_buffers = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        self._jq_buffers = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        self._previous_detrender = [0.0, 0.0]
        self._previous_detrender_input = [0.0, 0.0]
        self._previous_q1 = [0.0, 0.0]
        self._previous_q1_input = [0.0, 0.0]
        self._previous_ji = [0.0, 0.0]
        self._previous_ji_input = [0.0, 0.0]
        self._previous_jq = [0.0, 0.0]
        self._previous_jq_input = [0.0, 0.0]
        self._i1_previous_2 = [0.0, 0.0]
        self._i1_previous_3 = [0.0, 0.0]
        self._previous_q2 = 0.0
        self._previous_i2 = 0.0
        self._re = 0.0
        self._im = 0.0
        self._period = 0.0

    def update(self, close: float) -> HilbertPoint | None:
        index = self._count
        self._count += 1
        self._wma_closes.append(close)
        if index == 0:
            self._period_wma_sub = close
            self._period_wma_sum = close
            return None
        if index == 1:
            self._period_wma_sub += close
            self._period_wma_sum += close * 2.0
            return None
        if index == 2:
            self._period_wma_sub += close
            self._period_wma_sum += close * 3.0
            return None

        self._period_wma_sub += close
        self._period_wma_sub -= self._trailing_wma_value
        self._period_wma_sum += close * 4.0
        self._trailing_wma_value = self._wma_closes[0]
        smooth_price = self._period_wma_sum * 0.1
        self._period_wma_sum -= self._period_wma_sub
        if index < 3 + self._wma_only_steps:
            return None

        adjusted_previous_period = 0.075 * self._period + 0.54
        parity = 0 if index % 2 == 0 else 1
        opposite_parity = 1 - parity

        hilbert_temp = _HILBERT_A * smooth_price
        detrender = -self._detrender_buffers[parity][self._hilbert_index]
        self._detrender_buffers[parity][self._hilbert_index] = hilbert_temp
        detrender += hilbert_temp
        detrender -= self._previous_detrender[parity]
        self._previous_detrender[parity] = _HILBERT_B * self._previous_detrender_input[parity]
        detrender += self._previous_detrender[parity]
        self._previous_detrender_input[parity] = smooth_price
        detrender *= adjusted_previous_period

        hilbert_temp = _HILBERT_A * detrender
        q1 = -self._q1_buffers[parity][self._hilbert_index]
        self._q1_buffers[parity][self._hilbert_index] = hilbert_temp
        q1 += hilbert_temp
        q1 -= self._previous_q1[parity]
        self._previous_q1[parity] = _HILBERT_B * self._previous_q1_input[parity]
        q1 += self._previous_q1[parity]
        self._previous_q1_input[parity] = detrender
        q1 *= adjusted_previous_period

        inphase = self._i1_previous_3[parity]
        hilbert_temp = _HILBERT_A * inphase
        ji = -self._ji_buffers[parity][self._hilbert_index]
        self._ji_buffers[parity][self._hilbert_index] = hilbert_temp
        ji += hilbert_temp
        ji -= self._previous_ji[parity]
        self._previous_ji[parity] = _HILBERT_B * self._previous_ji_input[parity]
        ji += self._previous_ji[parity]
        self._previous_ji_input[parity] = inphase
        ji *= adjusted_previous_period

        hilbert_temp = _HILBERT_A * q1
        jq = -self._jq_buffers[parity][self._hilbert_index]
        self._jq_buffers[parity][self._hilbert_index] = hilbert_temp
        jq += hilbert_temp
        jq -= self._previous_jq[parity]
        self._previous_jq[parity] = _HILBERT_B * self._previous_jq_input[parity]
        jq += self._previous_jq[parity]
        self._previous_jq_input[parity] = q1
        jq *= adjusted_previous_period

        if parity == 0:
            self._hilbert_index += 1
            if self._hilbert_index == 3:
                self._hilbert_index = 0

        q2 = 0.2 * (q1 + ji) + 0.8 * self._previous_q2
        i2 = 0.2 * (inphase - jq) + 0.8 * self._previous_i2
        self._i1_previous_3[opposite_parity] = self._i1_previous_2[opposite_parity]
        self._i1_previous_2[opposite_parity] = detrender

        self._re = 0.2 * (i2 * self._previous_i2 + q2 * self._previous_q2) + 0.8 * self._re
        self._im = 0.2 * (i2 * self._previous_q2 - q2 * self._previous_i2) + 0.8 * self._im
        self._previous_q2 = q2
        self._previous_i2 = i2
        previous_period = self._period
        if self._im != 0.0 and self._re != 0.0:
            self._period = 360.0 / (atan(self._im / self._re) * _RAD_TO_DEG)
        upper = 1.5 * previous_period
        if self._period > upper:
            self._period = upper
        lower = 0.67 * previous_period
        if self._period < lower:
            self._period = lower
        if self._period < 6.0:
            self._period = 6.0
        elif self._period > 50.0:
            self._period = 50.0
        self._period = 0.2 * self._period + 0.8 * previous_period
        return smooth_price, inphase, q1, self._period


@dataclass(frozen=True, slots=True)
class _PhasePoint:
    smooth_period: float
    phase: float


def _batch_phase_layer(points: Sequence[HilbertPoint | None]) -> list[_PhasePoint | None]:
    """Compute the batch dominant-cycle phase selection layer."""
    result: list[_PhasePoint | None] = [None] * len(points)
    smooth_period = 0.0
    smooth_prices = [0.0] * 50
    smooth_price_index = 0
    phase = 0.0
    for index, point in enumerate(points):
        if point is None:
            continue
        smooth_price, _, _, period = point
        smooth_period = 0.33 * period + 0.67 * smooth_period
        smooth_prices[smooth_price_index] = smooth_price
        cycle_period = int(smooth_period + 0.5)
        real_part = 0.0
        imaginary_part = 0.0
        price_index = smooth_price_index
        for offset in range(cycle_period):
            angle = float(offset) * _TWO_PI / float(cycle_period)
            price = smooth_prices[price_index]
            real_part += sin(angle) * price
            imaginary_part += cos(angle) * price
            price_index = 49 if price_index == 0 else price_index - 1
        if abs(imaginary_part) > 0.0:
            phase = atan(real_part / imaginary_part) * _PHASE_RAD_TO_DEG
        elif abs(imaginary_part) <= 0.01:
            if real_part < 0.0:
                phase -= 90.0
            elif real_part > 0.0:
                phase += 90.0
        phase += 90.0
        phase += 360.0 / smooth_period
        if imaginary_part < 0.0:
            phase += 180.0
        if phase > 315.0:
            phase -= 360.0
        result[index] = _PhasePoint(smooth_period, phase)
        smooth_price_index += 1
        if smooth_price_index > 49:
            smooth_price_index = 0
    return result


class _PhaseStateLayer:
    """Incremental-only dominant-cycle phase selection layer."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.smooth_period = 0.0
        self.phase = 0.0
        self._smooth_prices = [0.0] * 50
        self._smooth_price_index = 0

    def update(self, smooth_price: float, period: float) -> _PhasePoint:
        self.smooth_period = 0.33 * period + 0.67 * self.smooth_period
        self._smooth_prices[self._smooth_price_index] = smooth_price
        cycle_period = int(self.smooth_period + 0.5)
        real_part = 0.0
        imaginary_part = 0.0
        price_index = self._smooth_price_index
        for offset in range(cycle_period):
            angle = float(offset) * _TWO_PI / float(cycle_period)
            price = self._smooth_prices[price_index]
            real_part += sin(angle) * price
            imaginary_part += cos(angle) * price
            price_index = 49 if price_index == 0 else price_index - 1
        if abs(imaginary_part) > 0.0:
            self.phase = atan(real_part / imaginary_part) * _PHASE_RAD_TO_DEG
        elif abs(imaginary_part) <= 0.01:
            if real_part < 0.0:
                self.phase -= 90.0
            elif real_part > 0.0:
                self.phase += 90.0
        self.phase += 90.0
        self.phase += 360.0 / self.smooth_period
        if imaginary_part < 0.0:
            self.phase += 180.0
        if self.phase > 315.0:
            self.phase -= 360.0
        point = _PhasePoint(self.smooth_period, self.phase)
        self._smooth_price_index += 1
        if self._smooth_price_index > 49:
            self._smooth_price_index = 0
        return point


def _batch_trendline_layer(
    closes: Sequence[float],
    points: Sequence[HilbertPoint | None],
    phases: Sequence[_PhasePoint | None] | None = None,
) -> list[float | None]:
    """Compute the batch raw-price instantaneous-trendline layer."""
    result: list[float | None] = [None] * len(points)
    smooth_period = 0.0
    trend_1 = 0.0
    trend_2 = 0.0
    trend_3 = 0.0
    for index, point in enumerate(points):
        if point is None:
            continue
        if phases is None:
            smooth_period = 0.33 * point[3] + 0.67 * smooth_period
        else:
            phase_point = phases[index]
            if phase_point is None:
                continue
            smooth_period = phase_point.smooth_period
        cycle_period = int(smooth_period + 0.5)
        average = 0.0
        for offset in range(cycle_period):
            average += closes[index - offset]
        if cycle_period > 0:
            average /= float(cycle_period)
        trendline = (4.0 * average + 3.0 * trend_1 + 2.0 * trend_2 + trend_3) / 10.0
        trend_3 = trend_2
        trend_2 = trend_1
        trend_1 = average
        result[index] = trendline
    return result


class _TrendlineStateLayer:
    """Incremental raw-price trendline layer with a bounded 50-price buffer."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._closes: deque[float] = deque(maxlen=50)
        self._trend_1 = 0.0
        self._trend_2 = 0.0
        self._trend_3 = 0.0

    def remember(self, close: float) -> None:
        self._closes.append(close)

    def update(self, smooth_period: float) -> float:
        cycle_period = int(smooth_period + 0.5)
        average = 0.0
        for offset in range(cycle_period):
            average += self._closes[-1 - offset]
        if cycle_period > 0:
            average /= float(cycle_period)
        trendline = (
            4.0 * average + 3.0 * self._trend_1 + 2.0 * self._trend_2 + self._trend_3
        ) / 10.0
        self._trend_3 = self._trend_2
        self._trend_2 = self._trend_1
        self._trend_1 = average
        return trendline


def ht_dcperiod(candles: Sequence[Candle]) -> list[float]:
    """Return TA-Lib 0.7.1 HT_DCPERIOD with unstable period fixed at zero."""
    points = _batch_hilbert_core(
        [candle.close for candle in candles],
        _SHORT_WMA_ONLY_STEPS,
    )
    result = [NAN] * len(candles)
    smooth_period = 0.0
    for index, point in enumerate(points):
        if point is None:
            continue
        smooth_period = 0.33 * point[3] + 0.67 * smooth_period
        if index >= 32:
            result[index] = smooth_period
    return result


def ht_dcphase(candles: Sequence[Candle]) -> list[float]:
    """Return TA-Lib 0.7.1 HT_DCPHASE with a 63-bar lookback."""
    points = _batch_hilbert_core(
        [candle.close for candle in candles],
        _LONG_WMA_ONLY_STEPS,
    )
    phases = _batch_phase_layer(points)
    return [
        phase.phase if index >= 63 and phase is not None else NAN
        for index, phase in enumerate(phases)
    ]


def ht_phasor(candles: Sequence[Candle]) -> list[PhasorValue]:
    """Return TA-Lib 0.7.1 HT_PHASOR's I1 and Q1 pair."""
    points = _batch_hilbert_core(
        [candle.close for candle in candles],
        _SHORT_WMA_ONLY_STEPS,
    )
    result: list[PhasorValue] = []
    for index, point in enumerate(points):
        if index < 32 or point is None:
            result.append({"inphase": NAN, "quadrature": NAN})
        else:
            result.append({"inphase": point[1], "quadrature": point[2]})
    return result


def ht_sine(candles: Sequence[Candle]) -> list[SineValue]:
    """Return TA-Lib 0.7.1 HT_SINE's sine and 45-degree lead sine."""
    points = _batch_hilbert_core(
        [candle.close for candle in candles],
        _LONG_WMA_ONLY_STEPS,
    )
    phases = _batch_phase_layer(points)
    result: list[SineValue] = []
    for index, phase in enumerate(phases):
        if index < 63 or phase is None:
            result.append({"sine": NAN, "leadsine": NAN})
        else:
            result.append(
                {
                    "sine": sin(phase.phase * _DEG_TO_RAD),
                    "leadsine": sin((phase.phase + 45.0) * _DEG_TO_RAD),
                }
            )
    return result


def ht_trendline(candles: Sequence[Candle]) -> list[float]:
    """Return TA-Lib 0.7.1 HT_TRENDLINE over raw close prices."""
    closes = [candle.close for candle in candles]
    points = _batch_hilbert_core(closes, _LONG_WMA_ONLY_STEPS)
    trendlines = _batch_trendline_layer(closes, points)
    return [
        value if index >= 63 and value is not None else NAN
        for index, value in enumerate(trendlines)
    ]


def ht_trendmode(candles: Sequence[Candle]) -> list[float]:
    """Return TA-Lib 0.7.1 HT_TRENDMODE encoded as NaN, 0.0, or 1.0."""
    closes = [candle.close for candle in candles]
    points = _batch_hilbert_core(closes, _LONG_WMA_ONLY_STEPS)
    phases = _batch_phase_layer(points)
    trendlines = _batch_trendline_layer(closes, points, phases)
    result = [NAN] * len(candles)
    previous_phase = 0.0
    previous_sine = 0.0
    previous_lead_sine = 0.0
    days_in_trend = 0
    for index, (point, phase, trendline) in enumerate(zip(points, phases, trendlines, strict=True)):
        if point is None or phase is None or trendline is None:
            continue
        sine_value = sin(phase.phase * _DEG_TO_RAD)
        lead_sine = sin((phase.phase + 45.0) * _DEG_TO_RAD)
        trend = 1.0
        if (
            sine_value > lead_sine
            and previous_sine <= previous_lead_sine
            or sine_value < lead_sine
            and previous_sine >= previous_lead_sine
        ):
            days_in_trend = 0
            trend = 0.0
        days_in_trend += 1
        if days_in_trend < 0.5 * phase.smooth_period:
            trend = 0.0
        phase_change = phase.phase - previous_phase
        if phase.smooth_period != 0.0 and (
            phase_change > 0.67 * 360.0 / phase.smooth_period
            and phase_change < 1.5 * 360.0 / phase.smooth_period
        ):
            trend = 0.0
        if trendline != 0.0 and abs((point[0] - trendline) / trendline) >= 0.015:
            trend = 1.0
        if index >= 63:
            result[index] = trend
        previous_phase = phase.phase
        previous_sine = sine_value
        previous_lead_sine = lead_sine
    return result


def mama(
    candles: Sequence[Candle],
    fastlimit: float = 0.5,
    slowlimit: float = 0.05,
) -> list[MAMAValue]:
    """Return TA-Lib 0.7.1 MAMA and FAMA with its exact alpha branches."""
    _validate_mama_limits(fastlimit, slowlimit)
    points = _batch_hilbert_core(
        [candle.close for candle in candles],
        _SHORT_WMA_ONLY_STEPS,
    )
    result: list[MAMAValue] = []
    mama_value = 0.0
    fama_value = 0.0
    previous_phase = 0.0
    for index, (candle, point) in enumerate(zip(candles, points, strict=True)):
        if point is not None:
            inphase = point[1]
            phase = atan(point[2] / inphase) * _RAD_TO_DEG if inphase != 0.0 else 0.0
            alpha = _mama_alpha(previous_phase - phase, fastlimit, slowlimit)
            previous_phase = phase
            mama_value = alpha * candle.close + (1.0 - alpha) * mama_value
            half_alpha = alpha * 0.5
            fama_value = half_alpha * mama_value + (1.0 - half_alpha) * fama_value
        if index < 32:
            result.append({"mama": NAN, "fama": NAN})
        else:
            result.append({"mama": mama_value, "fama": fama_value})
    return result


class HTDCPeriodState:
    min_history = 33

    def __init__(self) -> None:
        self._core = _HilbertStateCore(_SHORT_WMA_ONLY_STEPS)
        self._count = 0
        self._smooth_period = 0.0
        self._current = NAN

    @property
    def warmed_up(self) -> bool:
        return self._count >= self.min_history

    def seed(self, candles: Sequence[Candle]) -> None:
        self._core.reset()
        self._count = 0
        self._smooth_period = 0.0
        self._current = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        point = self._core.update(candle.close)
        self._count += 1
        if point is not None:
            self._smooth_period = 0.33 * point[3] + 0.67 * self._smooth_period
        if self.warmed_up:
            self._current = self._smooth_period
        return self.current()

    def current(self) -> float:
        return self._current


class HTDCPhaseState:
    min_history = 64

    def __init__(self) -> None:
        self._core = _HilbertStateCore(_LONG_WMA_ONLY_STEPS)
        self._phase = _PhaseStateLayer()
        self._count = 0
        self._current = NAN

    @property
    def warmed_up(self) -> bool:
        return self._count >= self.min_history

    def seed(self, candles: Sequence[Candle]) -> None:
        self._core.reset()
        self._phase.reset()
        self._count = 0
        self._current = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        point = self._core.update(candle.close)
        self._count += 1
        if point is not None:
            phase = self._phase.update(point[0], point[3])
            if self.warmed_up:
                self._current = phase.phase
        return self.current()

    def current(self) -> float:
        return self._current


class HTPhasorState:
    min_history = 33

    def __init__(self) -> None:
        self._core = _HilbertStateCore(_SHORT_WMA_ONLY_STEPS)
        self._count = 0
        self._current: PhasorValue = {"inphase": NAN, "quadrature": NAN}

    @property
    def warmed_up(self) -> bool:
        return self._count >= self.min_history

    def seed(self, candles: Sequence[Candle]) -> None:
        self._core.reset()
        self._count = 0
        self._current = {"inphase": NAN, "quadrature": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> PhasorValue:
        point = self._core.update(candle.close)
        self._count += 1
        if self.warmed_up and point is not None:
            self._current = {"inphase": point[1], "quadrature": point[2]}
        return self.current()

    def current(self) -> PhasorValue:
        return dict(self._current)


class HTSineState:
    min_history = 64

    def __init__(self) -> None:
        self._core = _HilbertStateCore(_LONG_WMA_ONLY_STEPS)
        self._phase = _PhaseStateLayer()
        self._count = 0
        self._current: SineValue = {"sine": NAN, "leadsine": NAN}

    @property
    def warmed_up(self) -> bool:
        return self._count >= self.min_history

    def seed(self, candles: Sequence[Candle]) -> None:
        self._core.reset()
        self._phase.reset()
        self._count = 0
        self._current = {"sine": NAN, "leadsine": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> SineValue:
        point = self._core.update(candle.close)
        self._count += 1
        if point is not None:
            phase = self._phase.update(point[0], point[3])
            if self.warmed_up:
                self._current = {
                    "sine": sin(phase.phase * _DEG_TO_RAD),
                    "leadsine": sin((phase.phase + 45.0) * _DEG_TO_RAD),
                }
        return self.current()

    def current(self) -> SineValue:
        return dict(self._current)


class HTTrendlineState:
    min_history = 64

    def __init__(self) -> None:
        self._core = _HilbertStateCore(_LONG_WMA_ONLY_STEPS)
        self._trendline = _TrendlineStateLayer()
        self._count = 0
        self._smooth_period = 0.0
        self._current = NAN

    @property
    def warmed_up(self) -> bool:
        return self._count >= self.min_history

    def seed(self, candles: Sequence[Candle]) -> None:
        self._core.reset()
        self._trendline.reset()
        self._count = 0
        self._smooth_period = 0.0
        self._current = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        self._trendline.remember(candle.close)
        point = self._core.update(candle.close)
        self._count += 1
        if point is not None:
            self._smooth_period = 0.33 * point[3] + 0.67 * self._smooth_period
            trendline = self._trendline.update(self._smooth_period)
            if self.warmed_up:
                self._current = trendline
        return self.current()

    def current(self) -> float:
        return self._current


class HTTrendModeState:
    min_history = 64

    def __init__(self) -> None:
        self._core = _HilbertStateCore(_LONG_WMA_ONLY_STEPS)
        self._phase = _PhaseStateLayer()
        self._trendline = _TrendlineStateLayer()
        self._count = 0
        self._days_in_trend = 0
        self._previous_phase = 0.0
        self._previous_sine = 0.0
        self._previous_lead_sine = 0.0
        self._current = NAN

    @property
    def warmed_up(self) -> bool:
        return self._count >= self.min_history

    def seed(self, candles: Sequence[Candle]) -> None:
        self._core.reset()
        self._phase.reset()
        self._trendline.reset()
        self._count = 0
        self._days_in_trend = 0
        self._previous_phase = 0.0
        self._previous_sine = 0.0
        self._previous_lead_sine = 0.0
        self._current = NAN
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float:
        self._trendline.remember(candle.close)
        point = self._core.update(candle.close)
        self._count += 1
        if point is None:
            return self.current()
        phase = self._phase.update(point[0], point[3])
        trendline = self._trendline.update(phase.smooth_period)
        sine_value = sin(phase.phase * _DEG_TO_RAD)
        lead_sine = sin((phase.phase + 45.0) * _DEG_TO_RAD)
        trend = 1.0
        if (
            sine_value > lead_sine
            and self._previous_sine <= self._previous_lead_sine
            or sine_value < lead_sine
            and self._previous_sine >= self._previous_lead_sine
        ):
            self._days_in_trend = 0
            trend = 0.0
        self._days_in_trend += 1
        if self._days_in_trend < 0.5 * phase.smooth_period:
            trend = 0.0
        phase_change = phase.phase - self._previous_phase
        if phase.smooth_period != 0.0 and (
            phase_change > 0.67 * 360.0 / phase.smooth_period
            and phase_change < 1.5 * 360.0 / phase.smooth_period
        ):
            trend = 0.0
        if trendline != 0.0 and abs((point[0] - trendline) / trendline) >= 0.015:
            trend = 1.0
        if self.warmed_up:
            self._current = trend
        self._previous_phase = phase.phase
        self._previous_sine = sine_value
        self._previous_lead_sine = lead_sine
        return self.current()

    def current(self) -> float:
        return self._current


class MAMAState:
    min_history = 33

    def __init__(self, fastlimit: float = 0.5, slowlimit: float = 0.05) -> None:
        _validate_mama_limits(fastlimit, slowlimit)
        self.fastlimit = fastlimit
        self.slowlimit = slowlimit
        self._core = _HilbertStateCore(_SHORT_WMA_ONLY_STEPS)
        self._count = 0
        self._mama = 0.0
        self._fama = 0.0
        self._previous_phase = 0.0
        self._current: MAMAValue = {"mama": NAN, "fama": NAN}

    @property
    def warmed_up(self) -> bool:
        return self._count >= self.min_history

    def seed(self, candles: Sequence[Candle]) -> None:
        self._core.reset()
        self._count = 0
        self._mama = 0.0
        self._fama = 0.0
        self._previous_phase = 0.0
        self._current = {"mama": NAN, "fama": NAN}
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> MAMAValue:
        point = self._core.update(candle.close)
        self._count += 1
        if point is not None:
            inphase = point[1]
            phase = atan(point[2] / inphase) * _RAD_TO_DEG if inphase != 0.0 else 0.0
            alpha = _mama_alpha(
                self._previous_phase - phase,
                self.fastlimit,
                self.slowlimit,
            )
            self._previous_phase = phase
            self._mama = alpha * candle.close + (1.0 - alpha) * self._mama
            half_alpha = alpha * 0.5
            self._fama = half_alpha * self._mama + (1.0 - half_alpha) * self._fama
        if self.warmed_up:
            self._current = {"mama": self._mama, "fama": self._fama}
        return self.current()

    def current(self) -> MAMAValue:
        return dict(self._current)
