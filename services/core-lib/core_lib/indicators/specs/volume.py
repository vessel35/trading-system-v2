"""Registration list owned by the volume category."""

from functools import partial

from core_lib.indicators import volume
from core_lib.indicators.registry import IndicatorSpec

SPECS: tuple[IndicatorSpec, ...] = (
    IndicatorSpec(
        name="A/D Line",
        params={},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §4.2 (H=L keeps the multiplier at 0)",
        min_history=1,
        category="volume",
        required_inputs=(),
        _vectorized=volume.ad_line,
        _state_factory=volume.ADLineState,
    ),
    IndicatorSpec(
        name="Chaikin Oscillator",
        params={"fast_period": 3, "slow_period": 10},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §4.3 (EMA(ADL,3) - EMA(ADL,10))",
        min_history=10,
        category="volume",
        required_inputs=(),
        _vectorized=partial(volume.chaikin_oscillator, fast_period=3, slow_period=10),
        _state_factory=partial(
            volume.ChaikinOscillatorState,
            fast_period=3,
            slow_period=10,
        ),
    ),
    IndicatorSpec(
        name="CMF",
        params={"period": 20},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §4.4 (money flow volume over volume)",
        min_history=20,
        category="volume",
        required_inputs=(),
        _vectorized=partial(volume.cmf, period=20),
        _state_factory=partial(volume.CMFState, period=20),
    ),
    IndicatorSpec(
        name="OBV",
        params={},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §4.1 (signed volume accumulation)",
        min_history=1,
        category="volume",
        required_inputs=(),
        _vectorized=volume.obv,
        _state_factory=volume.OBVState,
    ),
    IndicatorSpec(
        name="Force Index",
        params={"period": 13},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §4.6 (EMA of price change times volume)",
        min_history=14,
        category="volume",
        required_inputs=(),
        _vectorized=partial(volume.force_index, period=13),
        _state_factory=partial(volume.ForceIndexState, period=13),
    ),
    IndicatorSpec(
        name="Volume SMA",
        params={"period": 20},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §0.2 (volume input)",
        min_history=20,
        category="volume",
        required_inputs=(),
        _vectorized=partial(volume.volume_sma, period=20),
        _state_factory=partial(volume.VolumeSMAState, period=20),
    ),
)
