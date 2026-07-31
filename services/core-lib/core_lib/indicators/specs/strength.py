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
)
