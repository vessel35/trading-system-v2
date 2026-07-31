"""Registration list owned by the volatility category."""

from functools import partial

from core_lib.indicators import volatility
from core_lib.indicators.registry import IndicatorSpec

SPECS: tuple[IndicatorSpec, ...] = (
    IndicatorSpec(
        name="ATR",
        params={"period": 14},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §3.1 + §0.6 + §0.5",
        min_history=14,
        category="volatility",
        required_inputs=(),
        _vectorized=partial(volatility.atr, period=14),
        _state_factory=partial(volatility.ATRState, period=14),
    ),
    IndicatorSpec(
        name="Bollinger Bands",
        params={"period": 20, "multiplier": 2.0},
        version="1.0.1",
        pinned_impl=(
            "technical_indicators_calc_spec.md §3.10 + §0.7 "
            "(population stdev, rolling Welford moments)"
        ),
        min_history=20,
        category="volatility",
        required_inputs=(),
        _vectorized=partial(
            volatility.bollinger_bands,
            period=20,
            multiplier=2.0,
        ),
        _state_factory=partial(
            volatility.BollingerBandsState,
            period=20,
            multiplier=2.0,
        ),
        # §3.10: "%B ... 분모 0 → 미정의". A flat window collapses the band,
        # and the standard declines to name a substitute, so %B stays NaN
        # there instead of being given an invented number.
        undefined_outputs=("percent_b",),
    ),
)
