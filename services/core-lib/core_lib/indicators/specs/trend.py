"""Registration list owned by the trend category."""

from functools import partial

from core_lib.indicators import trend
from core_lib.indicators.registry import IndicatorSpec

SPECS: tuple[IndicatorSpec, ...] = (
    *(
        IndicatorSpec(
            name="EMA",
            params={"period": period},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §0.3 (SMA seed, recursive)",
            min_history=period,
            category="trend",
            required_inputs=(),
            _vectorized=partial(trend.ema, period=period),
            _state_factory=partial(trend.EMAState, period=period),
        )
        for period in (9, 21, 55, 200)
    ),
    IndicatorSpec(
        name="DEMA",
        params={"period": 21},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §1.1 (2*EMA1 - EMA2)",
        min_history=41,
        category="trend",
        required_inputs=(),
        _vectorized=partial(trend.dema, period=21),
        _state_factory=partial(trend.DEMAState, period=21),
    ),
    IndicatorSpec(
        name="TEMA",
        params={"period": 21},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §1.2 (3*E1 - 3*E2 + E3)",
        min_history=61,
        category="trend",
        required_inputs=(),
        _vectorized=partial(trend.tema, period=21),
        _state_factory=partial(trend.TEMAState, period=21),
    ),
    IndicatorSpec(
        name="KAMA",
        params={"period": 10},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §1.7 (efficiency ratio, 2/30 constants)",
        min_history=11,
        category="trend",
        required_inputs=(),
        _vectorized=partial(trend.kama, period=10),
        _state_factory=partial(trend.KAMAState, period=10),
    ),
    IndicatorSpec(
        name="T3",
        params={"period": 21, "volume_factor": 0.7},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §1.3 (expanded c1..c4 over six chained EMAs; "
            "volume factor 0.7 is the section's own default, period 21 follows DEMA and TEMA)"
        ),
        min_history=121,
        category="trend",
        required_inputs=(),
        _vectorized=partial(trend.t3, period=21, volume_factor=0.7),
        _state_factory=partial(trend.T3State, period=21, volume_factor=0.7),
    ),
    IndicatorSpec(
        name="HMA",
        params={"period": 9},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §1.4 "
            "(WMA(2*WMA(n/2) - WMA(n), round(sqrt(n))), period 9)"
        ),
        min_history=11,
        category="trend",
        required_inputs=(),
        _vectorized=partial(trend.hma, period=9),
        _state_factory=partial(trend.HMAState, period=9),
    ),
    IndicatorSpec(
        name="ZLEMA",
        params={"period": 21},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §1.5 (EMA of the lag-corrected price, §0.3 SMA seed)"
        ),
        min_history=31,
        category="trend",
        required_inputs=(),
        _vectorized=partial(trend.zlema, period=21),
        _state_factory=partial(trend.ZLEMAState, period=21),
    ),
    IndicatorSpec(
        name="ALMA",
        params={"period": 9, "offset": 0.85, "sigma": 6.0},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §1.6 "
            "(Gaussian window; offset 0.85 and sigma 6 are the section's own defaults)"
        ),
        min_history=9,
        category="trend",
        required_inputs=(),
        _vectorized=partial(trend.alma, period=9, offset=0.85, sigma=6.0),
        _state_factory=partial(trend.ALMAState, period=9, offset=0.85, sigma=6.0),
    ),
    IndicatorSpec(
        name="VIDYA",
        params={"period": 21, "volatility_period": 9},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §1.8 body: k = |CMO(P, m)| / 100 adopted; "
            "the note's original Chande k, a short-to-long standard deviation ratio, "
            "is not implemented. §12 lists this split. Volatility period 9 is the "
            "section's own value; period 21 follows DEMA and TEMA. Seed follows §0.3"
        ),
        min_history=21,
        category="trend",
        required_inputs=(),
        _vectorized=partial(trend.vidya, period=21, volatility_period=9),
        _state_factory=partial(trend.VIDYAState, period=21, volatility_period=9),
    ),
    IndicatorSpec(
        name="McGinley Dynamic",
        params={"period": 21},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §1.9 (self-referencing divisor; "
            "§0.3 seed and §0.11 hold-previous on a vanished denominator)"
        ),
        min_history=21,
        category="trend",
        required_inputs=(),
        _vectorized=partial(trend.mcginley_dynamic, period=21),
        _state_factory=partial(trend.McGinleyDynamicState, period=21),
    ),
    IndicatorSpec(
        name="Guppy GMMA",
        params={},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §1.10 "
            "(EMA 3/5/8/10/12/15 and 30/35/40/45/50/60, all twelve fixed by the section)"
        ),
        min_history=60,
        category="trend",
        required_inputs=(),
        _vectorized=trend.guppy_gmma,
        _state_factory=trend.GuppyGMMAState,
    ),
)
