"""Registration list owned by the systems category.

Every combination below takes its numbers from the standard's own text, so none of
them needed a period chosen from what the repository already uses: §9.2 writes 9,
26, 52 and a 26-candle displacement; §6.1 writes 13/8, 8/5 and 5/3; §6.2 writes a
five-candle pattern; §9.4 names an EMA of 13 and the §2.4 MACD, whose registered
combination is 12/26/9; §9.5 compares a close with the close four candles earlier;
and §9.6 names 14 and 6.

Two registrations are deliberately partial and say so in `pinned_impl`, because the
standard states part of the system and defers the rest. TD Sequential registers the
setup only, and Woodies CCI registers the two lengths and the zone lines only.
"""

from functools import partial

from core_lib.indicators import systems
from core_lib.indicators.registry import IndicatorSpec

SPECS: tuple[IndicatorSpec, ...] = (
    IndicatorSpec(
        name="Elder Ray",
        params={"period": 13},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §9.3 (extremes against a smoothed close)",
        min_history=13,
        category="systems",
        required_inputs=(),
        _vectorized=partial(systems.elder_ray, period=13),
        _state_factory=partial(systems.ElderRayState, period=13),
    ),
    IndicatorSpec(
        name="Parabolic SAR",
        params={"step": 0.02, "maximum": 0.2},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §9.1 (0.02 step to a 0.20 cap)",
        min_history=2,
        category="systems",
        required_inputs=(),
        _vectorized=partial(systems.parabolic_sar, step=0.02, maximum=0.2),
        _state_factory=partial(systems.ParabolicSARState, step=0.02, maximum=0.2),
    ),
    IndicatorSpec(
        name="Ichimoku Kinko Hyo",
        params={
            "conversion_period": 9,
            "base_period": 26,
            "span_b_period": 52,
            "displacement": 26,
        },
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §9.2 (9/26/52, +26 displacement; the "
            "Senkou spans carry the midpoint computed 26 candles earlier and the "
            "Chikou span is not published because it would repeat the candle's close)"
        ),
        min_history=78,
        category="systems",
        required_inputs=(),
        _vectorized=partial(
            systems.ichimoku,
            conversion_period=9,
            base_period=26,
            span_b_period=52,
            displacement=26,
        ),
        _state_factory=partial(
            systems.IchimokuState,
            conversion_period=9,
            base_period=26,
            span_b_period=52,
            displacement=26,
        ),
    ),
    IndicatorSpec(
        name="Alligator",
        params={
            "jaw_period": 13,
            "jaw_shift": 8,
            "teeth_period": 8,
            "teeth_shift": 5,
            "lips_period": 5,
            "lips_shift": 3,
        },
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §6.1 (SMMA of §0.1 median price at "
            "13/8, 8/5, 5/3; each line carries the value computed its shift earlier)"
        ),
        min_history=21,
        category="systems",
        required_inputs=(),
        _vectorized=partial(
            systems.alligator,
            jaw_period=13,
            jaw_shift=8,
            teeth_period=8,
            teeth_shift=5,
            lips_period=5,
            lips_shift=3,
        ),
        _state_factory=partial(
            systems.AlligatorState,
            jaw_period=13,
            jaw_shift=8,
            teeth_period=8,
            teeth_shift=5,
            lips_period=5,
            lips_shift=3,
        ),
    ),
    IndicatorSpec(
        name="Gator Oscillator",
        params={
            "jaw_period": 13,
            "jaw_shift": 8,
            "teeth_period": 8,
            "teeth_shift": 5,
            "lips_period": 5,
            "lips_shift": 3,
        },
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §6.3 (gaps between the §6.1 lines, "
            "upper above zero and lower below)"
        ),
        min_history=21,
        category="systems",
        required_inputs=(),
        _vectorized=partial(
            systems.gator_oscillator,
            jaw_period=13,
            jaw_shift=8,
            teeth_period=8,
            teeth_shift=5,
            lips_period=5,
            lips_shift=3,
        ),
        _state_factory=partial(
            systems.GatorOscillatorState,
            jaw_period=13,
            jaw_shift=8,
            teeth_period=8,
            teeth_shift=5,
            lips_period=5,
            lips_shift=3,
        ),
    ),
    IndicatorSpec(
        name="Fractals",
        params={"period": 5},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §6.2 (five-candle pattern; the flags "
            "at each candle describe the candle two earlier, 1.0 set and 0.0 clear)"
        ),
        min_history=5,
        category="systems",
        required_inputs=(),
        _vectorized=partial(systems.fractals, period=5),
        _state_factory=partial(systems.FractalsState, period=5),
    ),
    IndicatorSpec(
        name="Market Facilitation Index",
        params={},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §6.4 (candle range over volume; a "
            "zero volume reads as zero under §0.11 because §6.4 names no substitute)"
        ),
        min_history=1,
        category="systems",
        required_inputs=(),
        _vectorized=systems.market_facilitation_index,
        _state_factory=systems.MarketFacilitationIndexState,
    ),
    IndicatorSpec(
        name="Elder Impulse System",
        params={
            "ema_period": 13,
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
        },
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §9.4 (EMA 13 slope with the §2.4 "
            "12/26/9 histogram slope; green 1.0, blue 0.0, red -1.0)"
        ),
        min_history=35,
        category="systems",
        required_inputs=(),
        _vectorized=partial(
            systems.elder_impulse,
            ema_period=13,
            fast_period=12,
            slow_period=26,
            signal_period=9,
        ),
        _state_factory=partial(
            systems.ElderImpulseState,
            ema_period=13,
            fast_period=12,
            slow_period=26,
            signal_period=9,
        ),
    ),
    IndicatorSpec(
        name="TD Sequential",
        params={"lookback": 4},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §9.5, setup only (consecutive closes "
            "against the close four candles earlier, negative for the falling buy "
            "setup and positive for the rising sell setup, completing at nine); the "
            "countdown is not implemented because §9.5 defers its cancellation and "
            "restart rules to DeMark's original work"
        ),
        min_history=5,
        category="systems",
        required_inputs=(),
        _vectorized=partial(systems.td_sequential, lookback=4),
        _state_factory=partial(systems.TDSequentialState, lookback=4),
    ),
    IndicatorSpec(
        name="Woodies CCI",
        params={"period": 14, "turbo_period": 6},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §9.6, values and zones only (the "
            "§2.10 CCI at 14 and 6 plus the band the slower one sits in, numbered "
            "-2 to 2 outward from the +-100 and +-200 lines); the zero-line patterns "
            "§9.6 names as ZLR, TLB and GB100 are not implemented because the "
            "section names them without defining them"
        ),
        min_history=14,
        category="systems",
        required_inputs=(),
        _vectorized=partial(systems.woodies_cci, period=14, turbo_period=6),
        _state_factory=partial(systems.WoodiesCCIState, period=14, turbo_period=6),
    ),
)
