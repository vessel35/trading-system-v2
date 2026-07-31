"""Registration list owned by the systems category."""

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
)
