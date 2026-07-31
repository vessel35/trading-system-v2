"""Registration list owned by the momentum category."""

from functools import partial

from core_lib.indicators import momentum
from core_lib.indicators.registry import IndicatorSpec

RSI_MIN_HISTORY = 15

SPECS: tuple[IndicatorSpec, ...] = (
    IndicatorSpec(
        name="RSI",
        params={"period": 14},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §2.1 + §0.5 (Wilder RMA)",
        min_history=15,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(momentum.rsi, period=14),
        _state_factory=partial(momentum.RSIState, period=14),
    ),
    IndicatorSpec(
        name="Stochastic",
        params={"period": 14, "smooth_period": 3},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §2.2 "
            "(fast %K/%D; flat range keeps previous, initially 50)"
        ),
        min_history=16,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(momentum.stochastic, period=14, smooth_period=3),
        _state_factory=partial(momentum.StochasticState, period=14, smooth_period=3),
    ),
    IndicatorSpec(
        name="MACD",
        params={"fast_period": 12, "slow_period": 26, "signal_period": 9},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §2.4 (12/26/9, EMA of MACD)",
        min_history=34,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(
            momentum.macd,
            fast_period=12,
            slow_period=26,
            signal_period=9,
        ),
        _state_factory=partial(
            momentum.MACDState,
            fast_period=12,
            slow_period=26,
            signal_period=9,
        ),
    ),
    IndicatorSpec(
        name="TSI",
        params={"long_period": 25, "short_period": 13},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §2.7 (double-smoothed momentum)",
        min_history=38,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(momentum.tsi, long_period=25, short_period=13),
        _state_factory=partial(momentum.TSIState, long_period=25, short_period=13),
    ),
    IndicatorSpec(
        name="CCI",
        params={"period": 20},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §2.10 (0.015 * mean deviation)",
        min_history=20,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(momentum.cci, period=20),
        _state_factory=partial(momentum.CCIState, period=20),
    ),
    IndicatorSpec(
        name="Awesome Oscillator",
        params={"fast_period": 5, "slow_period": 34},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §2.12 (SMA of HL2, 5 and 34)",
        min_history=34,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(momentum.awesome_oscillator, fast_period=5, slow_period=34),
        _state_factory=partial(
            momentum.AwesomeOscillatorState,
            fast_period=5,
            slow_period=34,
        ),
    ),
    IndicatorSpec(
        name="PPO",
        params={"fast_period": 12, "slow_period": 26, "signal_period": 9},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §2.5 (MACD scaled by the slow EMA)",
        min_history=34,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(
            momentum.ppo,
            fast_period=12,
            slow_period=26,
            signal_period=9,
        ),
        _state_factory=partial(
            momentum.PPOState,
            fast_period=12,
            slow_period=26,
            signal_period=9,
        ),
    ),
    IndicatorSpec(
        name="SMI",
        params={
            "period": 13,
            "long_period": 25,
            "short_period": 13,
            "signal_period": 3,
        },
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §2.27 "
            "(Blau 13/25/13 with a 3-period signal; the section asks the set to be stated)"
        ),
        min_history=51,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(
            momentum.smi,
            period=13,
            long_period=25,
            short_period=13,
            signal_period=3,
        ),
        _state_factory=partial(
            momentum.SMIState,
            period=13,
            long_period=25,
            short_period=13,
            signal_period=3,
        ),
    ),
    IndicatorSpec(
        name="Accelerator Oscillator",
        params={"fast_period": 5, "slow_period": 34, "smooth_period": 5},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §2.13 (AO - SMA(AO, 5))",
        min_history=38,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(
            momentum.accelerator_oscillator,
            fast_period=5,
            slow_period=34,
            smooth_period=5,
        ),
        _state_factory=partial(
            momentum.AcceleratorOscillatorState,
            fast_period=5,
            slow_period=34,
            smooth_period=5,
        ),
    ),
    IndicatorSpec(
        name="Stochastic RSI",
        params={
            "rsi_period": 14,
            "stochastic_period": 14,
            "smooth_k": 3,
            "smooth_d": 3,
        },
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §2.3 (stochastic of RSI, 3/3 smoothing)",
        min_history=RSI_MIN_HISTORY + 14 + 3 + 3 - 3,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(
            momentum.stochastic_rsi,
            rsi_period=14,
            stochastic_period=14,
            smooth_k=3,
            smooth_d=3,
        ),
        _state_factory=partial(
            momentum.StochasticRSIState,
            rsi_period=14,
            stochastic_period=14,
            smooth_k=3,
            smooth_d=3,
        ),
    ),
    IndicatorSpec(
        name="TRIX",
        params={"period": 15},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §2.6 (triple EMA, TA-Lib 100x scale)",
        min_history=44,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(momentum.trix, period=15),
        _state_factory=partial(momentum.TRIXState, period=15),
    ),
    IndicatorSpec(
        name="CMO",
        params={"period": 14},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §2.8 (unsmoothed sums)",
        min_history=15,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(momentum.cmo, period=14),
        _state_factory=partial(momentum.CMOState, period=14),
    ),
    IndicatorSpec(
        name="Williams %R",
        params={"period": 14},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §2.9 (stochastic read from the high)",
        min_history=14,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(momentum.williams_r, period=14),
        _state_factory=partial(momentum.WilliamsRState, period=14),
    ),
    IndicatorSpec(
        name="Ultimate Oscillator",
        params={"short_period": 7, "medium_period": 14, "long_period": 28},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §2.11 (7/14/28 weighted 4:2:1)",
        min_history=29,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(
            momentum.ultimate_oscillator,
            short_period=7,
            medium_period=14,
            long_period=28,
        ),
        _state_factory=partial(
            momentum.UltimateOscillatorState,
            short_period=7,
            medium_period=14,
            long_period=28,
        ),
    ),
    IndicatorSpec(
        name="Fisher Transform",
        params={"period": 9},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §2.14 "
            "(n=9 of the 9-10 the section allows; clamped at 0.999)"
        ),
        min_history=10,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(momentum.fisher_transform, period=9),
        _state_factory=partial(momentum.FisherTransformState, period=9),
    ),
    IndicatorSpec(
        name="KST",
        params={},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §2.24 (four weighted rate-of-change legs)",
        min_history=53,
        category="momentum",
        required_inputs=(),
        _vectorized=momentum.kst,
        _state_factory=momentum.KSTState,
    ),
    IndicatorSpec(
        name="Coppock Curve",
        params={"long_period": 14, "short_period": 11, "smooth_period": 10},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §2.25 (WMA of two rates of change)",
        min_history=24,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(
            momentum.coppock_curve,
            long_period=14,
            short_period=11,
            smooth_period=10,
        ),
        _state_factory=partial(
            momentum.CoppockCurveState,
            long_period=14,
            short_period=11,
            smooth_period=10,
        ),
    ),
    IndicatorSpec(
        name="Connors RSI",
        params={"rsi_period": 3, "streak_period": 2, "rank_period": 100},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §2.15 "
            "(RSI(C,3), RSI(streak,2), and the percentile of ROC(C,1), averaged in "
            "thirds. The section fixes the three periods but leaves two boundaries "
            "of the percentile open, and both are settled here: the ranked bar sits "
            "outside its own window, which spans the 100 changes before it as "
            "Connors' definition does, and the comparison is strict, so ties do not "
            "count as below)"
        ),
        min_history=102,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(
            momentum.connors_rsi,
            rsi_period=3,
            streak_period=2,
            rank_period=100,
        ),
        _state_factory=partial(
            momentum.ConnorsRSIState,
            rsi_period=3,
            streak_period=2,
            rank_period=100,
        ),
    ),
    IndicatorSpec(
        name="QStick",
        params={"period": 8},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §2.16 "
            "(rolling average of close minus open; n=8 is the low end of the 8-10 "
            "the section allows, following the choice already made for §2.14)"
        ),
        min_history=8,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(momentum.qstick, period=8),
        _state_factory=partial(momentum.QStickState, period=8),
    ),
    IndicatorSpec(
        name="Chande Forecast Oscillator",
        params={"period": 14},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §2.17 with the §14 regression "
            "(the section names no period, so this takes the 14 the repository "
            "already uses for RSI, ATR, and Williams %R)"
        ),
        min_history=14,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(momentum.chande_forecast_oscillator, period=14),
        _state_factory=partial(momentum.ChandeForecastOscillatorState, period=14),
    ),
    IndicatorSpec(
        name="DeMarker",
        params={"period": 14},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §2.18 "
            "(simple averages of DeMax and DeMin exactly as the section writes them, "
            "not Wilder smoothing; a window with neither a higher high nor a lower "
            "low keeps the previous value per §0.11 and §2.2, starting at 0.5)"
        ),
        min_history=15,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(momentum.demarker, period=14),
        _state_factory=partial(momentum.DeMarkerState, period=14),
    ),
    IndicatorSpec(
        name="DPO",
        params={"period": 20},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §2.19 "
            "(close displaced floor(n/2)+1 bars into the past minus SMA(C,n); the "
            "section names no period, so this takes the 20 already used for CCI and "
            "Bollinger Bands)"
        ),
        min_history=20,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(momentum.dpo, period=20),
        _state_factory=partial(momentum.DPOState, period=20),
    ),
    IndicatorSpec(
        name="Schaff Trend Cycle",
        params={"fast_period": 23, "slow_period": 50, "cycle_period": 10},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §2.20 "
            "(MACD(C,23,50) through two stochastic stages of 10, each smoothed by "
            "the 0.5-factor recursion the section attributes to the original author; "
            "§12 lists this indicator because implementations disagree on that "
            "constant and on clamping. Adopted: the 0.5 factor written in the "
            "section body, seeded with the first ratio of each stage. Rejected: the "
            "widespread variant that smooths with a period-length EMA instead, and "
            "the variant that clamps the intermediate stages, which is unnecessary "
            "here because a 0.5-factor average of values already inside 0-100 "
            "cannot leave that range)"
        ),
        min_history=68,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(
            momentum.schaff_trend_cycle,
            fast_period=23,
            slow_period=50,
            cycle_period=10,
        ),
        _state_factory=partial(
            momentum.SchaffTrendCycleState,
            fast_period=23,
            slow_period=50,
            cycle_period=10,
        ),
    ),
    IndicatorSpec(
        name="Relative Vigor Index",
        params={"period": 10},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §2.21 "
            "(Ehlers: symmetric four-term weighting of body over range, averaged "
            "over 10; not §3.7's Relative Volatility Index, which shares the "
            "abbreviation and nothing else)"
        ),
        min_history=16,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(momentum.relative_vigor_index, period=10),
        _state_factory=partial(momentum.RelativeVigorIndexState, period=10),
    ),
    IndicatorSpec(
        name="Laguerre RSI",
        params={"gamma": 0.5},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §2.22 "
            "(four-pole Laguerre cascade. The section writes the input as a bare P, "
            "the standard's placeholder for a caller-supplied series, so the close "
            "is a registration choice rather than a formula one. Gamma 0.5 is the "
            "low end of the 0.5-0.7 the section allows. The four stages start at the "
            "first close so the filter begins at rest instead of decaying out of an "
            "assumed zero, which the section does not fix either way, and a zero "
            "denominator yields zero because §2.22 states that substitute itself "
            "rather than leaving it to §0.11)"
        ),
        min_history=2,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(momentum.laguerre_rsi, gamma=0.5),
        _state_factory=partial(momentum.LaguerreRSIState, gamma=0.5),
    ),
    IndicatorSpec(
        name="Pretty Good Oscillator",
        params={"period": 89},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §2.23 "
            "(close less SMA(C,89), scaled by the §3.1 ATR of the same 89 bars)"
        ),
        min_history=89,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(momentum.pretty_good_oscillator, period=89),
        _state_factory=partial(momentum.PrettyGoodOscillatorState, period=89),
    ),
    IndicatorSpec(
        name="Center of Gravity",
        params={"period": 10},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §8.2 "
            "(weighted centroid of the last 10 closes, centred by (n+1)/2). The "
            "section writes the input as a bare P, which the standard uses as a "
            "placeholder for whatever series the caller supplies; it writes C where "
            "it means the close specifically. The close is registered here because "
            "§10's dependency map lists the indicators that consume the median "
            "price -- Awesome Oscillator, Alligator, Ichimoku, SuperTrend, Fisher "
            "Transform -- and does not list this one. Ehlers' original code does "
            "use the median price, so anyone revisiting the choice should start "
            "from that disagreement."
        ),
        min_history=10,
        category="momentum",
        required_inputs=(),
        _vectorized=partial(momentum.center_of_gravity, period=10),
        _state_factory=partial(momentum.CenterOfGravityState, period=10),
    ),
)
