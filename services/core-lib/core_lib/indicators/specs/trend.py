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
)
