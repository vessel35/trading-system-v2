"""Registration list for the TA-Lib-pinned Hilbert cycle functions."""

from functools import partial

from core_lib.indicators import cycle
from core_lib.indicators.registry import IndicatorSpec

_SOURCE = "TA-Lib v0.7.1"
_UNSTABLE = "unstable period fixed at 0"

SPECS: tuple[IndicatorSpec, ...] = (
    IndicatorSpec(
        name="HT_DCPERIOD",
        params={},
        version="1.0.0",
        pinned_impl=(
            f"technical_indicators_calc_spec.md §8.6; {_SOURCE} ta_HT_DCPERIOD.c; {_UNSTABLE}"
        ),
        min_history=33,
        category="cycle",
        required_inputs=(),
        _vectorized=cycle.ht_dcperiod,
        _state_factory=cycle.HTDCPeriodState,
    ),
    IndicatorSpec(
        name="HT_DCPHASE",
        params={},
        version="1.0.0",
        pinned_impl=(
            f"technical_indicators_calc_spec.md §8.7; {_SOURCE} ta_HT_DCPHASE.c; {_UNSTABLE}"
        ),
        min_history=64,
        category="cycle",
        required_inputs=(),
        _vectorized=cycle.ht_dcphase,
        _state_factory=cycle.HTDCPhaseState,
    ),
    IndicatorSpec(
        name="HT_PHASOR",
        params={},
        version="1.0.0",
        pinned_impl=(
            f"technical_indicators_calc_spec.md §8.8; {_SOURCE} ta_HT_PHASOR.c; {_UNSTABLE}"
        ),
        min_history=33,
        category="cycle",
        required_inputs=(),
        _vectorized=cycle.ht_phasor,
        _state_factory=cycle.HTPhasorState,
    ),
    IndicatorSpec(
        name="HT_SINE",
        params={},
        version="1.0.0",
        pinned_impl=(
            f"technical_indicators_calc_spec.md §8.4; {_SOURCE} ta_HT_SINE.c; {_UNSTABLE}"
        ),
        min_history=64,
        category="cycle",
        required_inputs=(),
        _vectorized=cycle.ht_sine,
        _state_factory=cycle.HTSineState,
    ),
    IndicatorSpec(
        name="HT_TRENDLINE",
        params={},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §8.4; "
            f"{_SOURCE} ta_HT_TRENDLINE.c; {_UNSTABLE}; raw close trendline"
        ),
        min_history=64,
        category="cycle",
        required_inputs=(),
        _vectorized=cycle.ht_trendline,
        _state_factory=cycle.HTTrendlineState,
    ),
    IndicatorSpec(
        name="HT_TRENDMODE",
        params={},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §8.9; "
            f"{_SOURCE} ta_HT_TRENDMODE.c; {_UNSTABLE}; first 63 outputs NaN, "
            "then cycle 0.0 or trend 1.0"
        ),
        min_history=64,
        category="cycle",
        required_inputs=(),
        _vectorized=cycle.ht_trendmode,
        _state_factory=cycle.HTTrendModeState,
    ),
    IndicatorSpec(
        name="MAMA",
        params={"fastlimit": 0.5, "slowlimit": 0.05},
        version="1.0.0",
        pinned_impl=(f"technical_indicators_calc_spec.md §8.1; {_SOURCE} ta_MAMA.c; {_UNSTABLE}"),
        min_history=33,
        category="cycle",
        required_inputs=(),
        _vectorized=partial(cycle.mama, fastlimit=0.5, slowlimit=0.05),
        _state_factory=partial(cycle.MAMAState, fastlimit=0.5, slowlimit=0.05),
    ),
)
