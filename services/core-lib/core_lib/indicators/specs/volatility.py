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
    IndicatorSpec(
        name="Keltner Channel",
        params={"period": 20, "atr_period": 10, "multiplier": 2.0},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §3.2 + §0.3 + §3.1 "
            "(modern branch adopted: EMA(C,20) centre with mult*ATR width; "
            "the original SMA(TP) +/- SMA(H-L) branch named in §3.2 and §12 is "
            "not implemented; ATR period 10 taken from the two the section "
            "offers)"
        ),
        min_history=20,
        category="volatility",
        required_inputs=(),
        _vectorized=partial(
            volatility.keltner_channel,
            period=20,
            atr_period=10,
            multiplier=2.0,
        ),
        _state_factory=partial(
            volatility.KeltnerChannelState,
            period=20,
            atr_period=10,
            multiplier=2.0,
        ),
    ),
    IndicatorSpec(
        name="Donchian Channel",
        params={"period": 20},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §3.3 + §0.8 "
            "(the current candle belongs to its own window, as §0.8 defines "
            "HH(n)_t over H_t..H_{t-n+1}; a breakout rule that needs the "
            "channel as it stood before this candle shifts this series itself)"
        ),
        min_history=20,
        category="volatility",
        required_inputs=(),
        _vectorized=partial(volatility.donchian_channel, period=20),
        _state_factory=partial(volatility.DonchianChannelState, period=20),
    ),
    IndicatorSpec(
        name="SuperTrend",
        params={"period": 10, "multiplier": 3.0},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §3.4 + §0.1 + §3.1 "
            "(the two trend states §3.4 names are encoded as direction=+1.0 for "
            "the rising state and direction=-1.0 for the falling one; the first "
            "candle with a defined ATR has no band to inherit and takes the "
            "basic bands, and enters the rising state only on a close above the "
            "upper band)"
        ),
        min_history=10,
        category="volatility",
        required_inputs=(),
        _vectorized=partial(volatility.supertrend, period=10, multiplier=3.0),
        _state_factory=partial(volatility.SuperTrendState, period=10, multiplier=3.0),
    ),
    IndicatorSpec(
        name="Chandelier Exit",
        params={"period": 22, "multiplier": 3.0},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §3.5 + §0.8 + §3.1",
        min_history=22,
        category="volatility",
        required_inputs=(),
        _vectorized=partial(volatility.chandelier_exit, period=22, multiplier=3.0),
        _state_factory=partial(volatility.ChandelierExitState, period=22, multiplier=3.0),
    ),
    IndicatorSpec(
        name="Ulcer Index",
        params={"period": 14},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §3.6 + §0.8 + §0.2 "
            "(the section names no default period, so 14 is taken from the "
            "period this repository already runs ATR and RSI at)"
        ),
        min_history=27,
        category="volatility",
        required_inputs=(),
        _vectorized=partial(volatility.ulcer_index, period=14),
        _state_factory=partial(volatility.UlcerIndexState, period=14),
    ),
    IndicatorSpec(
        name="Relative Volatility Index",
        params={"period": 14, "deviation_period": 10},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §3.7 + §0.7 + §0.5 "
            "(Dorsey's index over standard deviation, not the Ehlers Relative "
            "Vigor Index of §2.21; a window with no volatility either way has no "
            "share to report and reads as the midpoint 50, following the same "
            "convention §2.2 Stochastic already uses for a collapsed range)"
        ),
        min_history=23,
        category="volatility",
        required_inputs=(),
        _vectorized=partial(
            volatility.relative_volatility_index,
            period=14,
            deviation_period=10,
        ),
        _state_factory=partial(
            volatility.RelativeVolatilityIndexState,
            period=14,
            deviation_period=10,
        ),
    ),
    IndicatorSpec(
        name="Chaikin Volatility",
        params={"period": 10},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §3.8 + §0.3 + §0.10 "
            "(a zero base means the average range was itself zero, and a change "
            "from no volatility to no volatility is zero)"
        ),
        min_history=20,
        category="volatility",
        required_inputs=(),
        _vectorized=partial(volatility.chaikin_volatility, period=10),
        _state_factory=partial(volatility.ChaikinVolatilityState, period=10),
    ),
    IndicatorSpec(
        name="Mass Index",
        params={"period": 9, "sum_period": 25},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §3.9 + §0.3 "
            "(a zero denominator means every range in the window was zero, so "
            "numerator and denominator are the same quantity, the ratio is one, "
            "and the sum is the window length)"
        ),
        min_history=41,
        category="volatility",
        required_inputs=(),
        _vectorized=partial(volatility.mass_index, period=9, sum_period=25),
        _state_factory=partial(volatility.MassIndexState, period=9, sum_period=25),
    ),
)
