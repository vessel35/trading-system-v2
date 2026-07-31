"""Registration list owned by the strength (directional movement) category."""

from functools import partial

from core_lib.indicators import strength
from core_lib.indicators.registry import IndicatorSpec

SPECS: tuple[IndicatorSpec, ...] = (
    IndicatorSpec(
        name="DMI",
        params={"period": 14},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §5.1 (+DI, -DI, ADX, ADXR)",
        min_history=42,
        category="strength",
        required_inputs=(),
        _vectorized=partial(strength.dmi, period=14),
        _state_factory=partial(strength.DMIState, period=14),
    ),
    IndicatorSpec(
        name="Aroon",
        params={"period": 25},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §5.3 (age of the window extremes)",
        min_history=26,
        category="strength",
        required_inputs=(),
        _vectorized=partial(strength.aroon, period=25),
        _state_factory=partial(strength.AroonState, period=25),
    ),
    IndicatorSpec(
        name="Vortex Indicator",
        params={"period": 14},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §5.2 (both rotational sums over the summed "
            "True Range of the same 14 candles; the first candle carries no rotation, so its "
            "True Range leaves the window with it, as §5.1's system already does)"
        ),
        min_history=15,
        category="strength",
        required_inputs=(),
        _vectorized=partial(strength.vortex, period=14),
        _state_factory=partial(strength.VortexState, period=14),
    ),
    IndicatorSpec(
        name="Choppiness Index",
        params={"period": 14},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §5.4 (summed True Range against the window "
            "span, scaled by log10(14); §0.6 gives the first candle its own True Range)"
        ),
        min_history=14,
        category="strength",
        required_inputs=(),
        _vectorized=partial(strength.choppiness_index, period=14),
        _state_factory=partial(strength.ChoppinessIndexState, period=14),
    ),
    IndicatorSpec(
        name="Random Walk Index",
        params={"period": 14},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §5.6 (displacement over 14 candles divided by "
            "ATR(14) times sqrt(14), using §3.1's registered ATR). §5.6 states no default "
            "period and mentions a variant that maximizes over several lookbacks; the single "
            "combination registered here uses 14 because §5.6's divisor is the ATR this "
            "repository already registers at 14, and the variant is not implemented."
        ),
        min_history=15,
        category="strength",
        required_inputs=(),
        _vectorized=partial(strength.random_walk_index, period=14),
        _state_factory=partial(strength.RandomWalkIndexState, period=14),
    ),
)
