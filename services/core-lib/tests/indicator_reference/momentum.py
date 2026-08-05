"""What the tests expect of the momentum category: its registrations and its values."""

# The combinations this category registers, written out by hand. Nothing here reads
# the registry back: a pin that derives its own subject cannot notice the subject
# moving. Adding an indicator means adding a line here as well as a spec in
# `core_lib/indicators/specs/momentum.py`, and doing only one of the two fails.
IDENTIFIERS: frozenset[str] = frozenset(
    {
        "APO(fast_period=12,moving_average='sma',slow_period=26)",
        "Accelerator Oscillator(fast_period=5,slow_period=34,smooth_period=5)",
        "Awesome Oscillator(fast_period=5,slow_period=34)",
        "BOP(period=14)",
        "CCI(period=20)",
        "CMO(period=14)",
        "Center of Gravity(period=10)",
        "Chande Forecast Oscillator(period=14)",
        "Connors RSI(rank_period=100,rsi_period=3,streak_period=2)",
        "Coppock Curve(long_period=14,short_period=11,smooth_period=10)",
        "DPO(period=20)",
        "DeMarker(period=14)",
        "Fisher Transform(period=9)",
        "IMI(period=14)",
        "KST",
        "Laguerre RSI(gamma=0.5)",
        "MACD(fast_period=12,signal_period=9,slow_period=26)",
        "PPO(fast_period=12,signal_period=9,slow_period=26)",
        "Pretty Good Oscillator(period=89)",
        "QStick(period=8)",
        "RSI(period=14)",
        "Relative Vigor Index(period=10)",
        "SMI(long_period=25,period=13,short_period=13,signal_period=3)",
        "Schaff Trend Cycle(cycle_period=10,fast_period=23,slow_period=50)",
        "Stochastic RSI(rsi_period=14,smooth_d=3,smooth_k=3,stochastic_period=14)",
        "Stochastic Slow(period=14,smooth_period=3)",
        "Stochastic(period=14,smooth_period=3)",
        "TRIX(period=15)",
        "TSI(long_period=25,short_period=13)",
        "Ultimate Oscillator(long_period=28,medium_period=14,short_period=7)",
        "Williams %R(period=14)",
    }
)

NAMES: frozenset[str] = frozenset(
    {
        "APO",
        "Accelerator Oscillator",
        "Awesome Oscillator",
        "BOP",
        "CCI",
        "CMO",
        "Center of Gravity",
        "Chande Forecast Oscillator",
        "Connors RSI",
        "Coppock Curve",
        "DPO",
        "DeMarker",
        "Fisher Transform",
        "IMI",
        "KST",
        "Laguerre RSI",
        "MACD",
        "PPO",
        "Pretty Good Oscillator",
        "QStick",
        "RSI",
        "Relative Vigor Index",
        "SMI",
        "Schaff Trend Cycle",
        "Stochastic",
        "Stochastic RSI",
        "Stochastic Slow",
        "TRIX",
        "TSI",
        "Ultimate Oscillator",
        "Williams %R",
    }
)

# How many of the standard's 93 systems the registrations above account for. Every
# momentum name is one of the 89, so the count equals the number of names. Center of
# Gravity is one of them even though §11 files it under §8 Cycle rather than under §2:
# its calculation carries no phase pipeline, so it is registered here. Stochastic and
# Stochastic Slow are two of them rather than one, which is why they carry separate
# names: §2.2 counts the fast and the slow form as separate systems and §11 gives them
# a row each, so a second parameter combination under the one name would have left the
# count short by one.
STANDARD_SYSTEMS = 31

UNDEFINED_OUTPUTS: dict[str, tuple[str, ...]] = {}

# TA-Lib 0.7.1 over the series `reference_candles` builds, except where a comment
# names a different implementation.
REFERENCE: dict[str, dict[int, float]] = {
    "RSI(period=14)": {100: 39.03775391018262, 200: 68.81760894074445, 299: 86.16456410411202},
    "CCI(period=20)": {100: -59.78940846427027, 200: 168.67297510556497, 299: 89.17019608473291},
    "Stochastic(period=14,smooth_period=3).percent_k": {
        100: 22.922432270572614,
        200: 94.41021271624996,
        299: 92.4036997995627,
    },
    "Stochastic(period=14,smooth_period=3).percent_d": {
        100: 16.81693187062552,
        200: 94.98993171268778,
        299: 94.5198296360486,
    },
    # TA-Lib `STOCH` with both smoothing types left at 0, its simple average, which is
    # what §2.2 writes for the slow form. Its `slowk` output repeating the fast form's
    # `percent_d` above is the section's own statement that Slow %K is SMA(%K_raw, 3);
    # the outside implementation reproduces the shared part rather than agreeing by
    # coincidence.
    "Stochastic Slow(period=14,smooth_period=3).percent_k": {
        100: 16.81693187062552,
        200: 94.98993171268778,
        299: 94.5198296360486,
    },
    "Stochastic Slow(period=14,smooth_period=3).percent_d": {
        100: 13.271154782317765,
        200: 94.1920542618875,
        299: 95.141646631846,
    },
    # TA-Lib `APO` with matype 0, its simple average, which is §2.28's default. Both
    # averages here are simple, so no seed convention separates the two
    # implementations and the values agree outright rather than converging.
    "APO(fast_period=12,moving_average='sma',slow_period=26)": {
        100: -12.233083550113264,
        200: -1.655007703166163,
        299: 14.38920123588639,
    },
    # TA-Lib `SMA` of TA-Lib `BOP` over 14. TA-Lib's own BOP publishes only the raw
    # per-bar ratio, while §2.29's line is that ratio smoothed by a 14-bar simple
    # average, so the smoothing is composed from a second TA-Lib call rather than
    # taken from ours. The raw ratio was checked on its own at the same bars and
    # agrees to floating point: 0.2698273424439349, 0.5260783445951543, and
    # -0.1033960641356627.
    "BOP(period=14)": {
        100: -0.1794589278315722,
        200: 0.321284890719359,
        299: 0.33068976584693877,
    },
    # TA-Lib `IMI`. Tulip 0.4.0 has no Intraday Momentum Index and neither does
    # ta 0.11.0, so TA-Lib is the only comparison, and it is a direct one.
    "IMI(period=14)": {
        100: 13.867559056816777,
        200: 95.8804894872111,
        299: 98.16683449496749,
    },
    # Tulip Indicators 0.4.0, also named by §13. TA-Lib has no Awesome Oscillator.
    "Awesome Oscillator(fast_period=5,slow_period=34)": {
        100: -11.999670053215588,
        200: 0.5021993216117951,
        299: 22.51620241873372,
    },
    # TA-Lib's PPO takes a moving-average type; §2.5 uses EMA, so matype=1.
    "PPO(fast_period=12,signal_period=9,slow_period=26).ppo": {
        100: -2.5366845796303528,
        200: -0.2650808063722667,
        299: 7.017926029894158,
    },
    "PPO(fast_period=12,signal_period=9,slow_period=26).signal": {
        100: -1.247947717943005,
        200: -4.3558678969393965,
        299: 5.97573734406127,
    },
    "PPO(fast_period=12,signal_period=9,slow_period=26).histogram": {
        100: -1.2887368616873478,
        200: 4.0907870905671295,
        299: 1.0421886858328886,
    },
    "TRIX(period=15)": {
        100: -0.13458503111154485,
        200: -0.7196595662381178,
        299: 0.9286485247771648,
    },
    "Williams %R(period=14)": {
        100: -77.07756772942739,
        200: -5.589787283750039,
        299: -7.596300200437285,
    },
    "Ultimate Oscillator(long_period=28,medium_period=14,short_period=7)": {
        100: 50.227904778901134,
        200: 70.38564770040983,
        299: 64.86926324831096,
    },
    # Tulip 0.4.0. TA-Lib smooths this one the way it smooths RSI, while §2.8
    # says explicitly that the sums stay unsmoothed, which is what Tulip does.
    "CMO(period=14)": {
        100: -72.26488188636644,
        200: 91.7609789744222,
        299: 96.33366898993499,
    },
    # ta 0.11.0 KSTIndicator with the §2.24 parameter set.
    "KST.kst": {
        100: -15.584451285377055,
        200: -127.95894551008244,
        299: 259.51840423440854,
    },
    "KST.signal": {
        100: 75.413494699978,
        200: -228.39291569173233,
        299: 198.36969701978893,
    },
    # Tulip 0.4.0 `qstick`. Neither TA-Lib nor ta implements it.
    "QStick(period=8)": {
        100: -0.024686518604795538,
        200: 3.5348972686554383,
        299: 1.3282700316515026,
    },
    # TA-Lib `LINEARREG`, which is §14's regression estimate at the current bar,
    # combined by §2.17's own arithmetic. Tulip's `fosc` is not usable here: its
    # value at bar t is `100 * (C_t - TSF_{t-1}) / C_t`, the close measured against
    # a forecast made one bar earlier for this bar, while §2.17 measures it against
    # `LinRegForecast(C, n)_t` and §14 fixes that as `a + b·(n-1)` on the window
    # ending at t. Tulip and TA-Lib agree exactly on both regression primitives, so
    # the disagreement is which one the oscillator is built from, not how either is
    # computed, and the standard names the one used here.
    "Chande Forecast Oscillator(period=14)": {
        100: 4.321074438754073,
        200: 2.771348816886443,
        299: -3.9321280082885948,
    },
    # Tulip 0.4.0 `dpo`; ta 0.11.0's DPOIndicator reproduces the same numbers to
    # 1e-13 relative. Both displace the average backwards, as §2.19 does.
    "DPO(period=20)": {
        100: -0.3103935873994584,
        200: -10.66458953523873,
        299: -4.3443609016831335,
    },
    # TA-Lib `SMA` over Tulip 0.4.0 `atr`, combined by §2.23's arithmetic. TA-Lib's
    # own ATR is the wrong comparison for the denominator because it drops the first
    # bar, whereas §0.6 defines `TR_0 = H_0 - L_0` and §0.5 seeds from the first n of
    # those; Tulip does exactly that, which is why the composed value matches to
    # floating point while a TA-Lib ATR leaves a residual near 2e-3.
    "Pretty Good Oscillator(period=89)": {
        100: -0.5741993230107165,
        200: 0.9298965935080497,
        299: 4.912925604376189,
    },
}

# MACD: §2.4 subtracts two EMAs, each seeded by §0.3 at its own period. TA-Lib starts
# both averages together at the slow period instead, so its fast average has a shorter
# recursion behind it at the crossover point.
#
# TSI joins it for the same reason: the `ta` library seeds its averages from the first
# observation, while §0.3 seeds from the period's simple average.
CONVERGING: dict[str, tuple[dict[int, float], dict[int, float]]] = {
    "MACD(fast_period=12,signal_period=9,slow_period=26).macd": (
        {100: -3.0164352183961114, 200: -0.27195274827619187, 299: 8.999784744708393},
        {100: 1e-3, 200: 1e-6, 299: 1e-8},
    ),
    "MACD(fast_period=12,signal_period=9,slow_period=26).signal": (
        {100: -1.466565769969698, 200: -4.423246005049017, 299: 7.432807556915248},
        {100: 1e-3, 200: 1e-6, 299: 1e-8},
    ),
    "MACD(fast_period=12,signal_period=9,slow_period=26).histogram": (
        {100: -1.5498694484264135, 200: 4.151293256772825, 299: 1.566977187793145},
        {100: 1e-3, 200: 1e-6, 299: 1e-8},
    ),
    # ta 0.11.0; TA-Lib has no True Strength Index.
    "TSI(long_period=25,short_period=13)": (
        {100: -20.993702022418233, 200: -2.993467178933585, 299: 67.24009457384477},
        {100: 4e-1, 200: 1e-4, 299: 1e-7},
    ),
    "Stochastic RSI(rsi_period=14,smooth_d=3,smooth_k=3,stochastic_period=14).percent_k": (
        {100: 23.584229569176472, 200: 100.0, 299: 96.49913220407035},
        {100: 1e-1, 200: 1e-6, 299: 1e-6},
    ),
    "Stochastic RSI(rsi_period=14,smooth_d=3,smooth_k=3,stochastic_period=14).percent_d": (
        {100: 14.84804215780516, 200: 100.0, 299: 98.76676684819944},
        {100: 1e-1, 200: 1e-6, 299: 1e-6},
    ),
}

UNCOMPARED: dict[str, str] = {
    "Accelerator Oscillator(fast_period=5,slow_period=34,smooth_period=5)": (
        "None of TA-Lib, Tulip, or ta implements it. Its inputs are covered: the "
        "Awesome Oscillator it subtracts from is compared against Tulip, and the "
        "rolling average it subtracts is a compared primitive."
    ),
    "SMI(long_period=25,period=13,short_period=13,signal_period=3).smi": (
        "None of the three implements the Stochastic Momentum Index, and §2.27 "
        "notes that platforms disagree on its parameters, so even a third-party "
        "value would need its parameter set restated before it could be compared."
    ),
    "SMI(long_period=25,period=13,short_period=13,signal_period=3).signal": (
        "Smoothing of an uncompared series; it inherits the gap above."
    ),
    "Fisher Transform(period=9).fisher": (
        "Tulip has a Fisher Transform, but its values drift further from ours the "
        "longer the series runs (2e-5, then 1e-3, then 7e-1), which is a different "
        "recursion rather than a different seed. §2.14 writes the smoothing and the "
        "clamp we implement, so the standard decides and the outside value is not "
        "usable as a reference here."
    ),
    "Fisher Transform(period=9).signal": ("The delayed value of an uncompared series."),
    "Coppock Curve(long_period=14,short_period=11,smooth_period=10)": (
        "No available implementation. §2.25 is a weighted average of two rates of "
        "change, and both parts are compared primitives."
    ),
    "Connors RSI(rank_period=100,rsi_period=3,streak_period=2)": (
        "None of TA-Lib, Tulip, or ta implements Connors RSI, and §2.15's third leg "
        "is the part an outside value would have to settle: the section says only "
        "'the percentile of ROC(C,1) within the most recent 100 bars' and does not "
        "say whether the ranked bar belongs to the window it is ranked against. Both "
        "RSI legs were checked separately against TA-Lib over this series and agree "
        "to floating point: RSI(C,3) gives 76.7145829014062, 99.6209085092708, and "
        "76.39889064033267 at the sampled bars, and RSI(streak,2) gives "
        "79.68716286283903, 99.93914262494233, and 5.000158790094742. What those "
        "leave over from our value is exactly 86.0 and 34.0 at bars 200 and 299, "
        "whole counts out of 100 as a percentile of that window has to be, so the "
        "unverified part is the window convention rather than the arithmetic."
    ),
    "DeMarker(period=14)": (
        "None of the three implements DeMarker. Composing one would not be a "
        "comparison either: §2.18's content is the definition of DeMax and DeMin, "
        "which no library provides, and everything left over is a rolling average "
        "that is already compared through other indicators."
    ),
    "Schaff Trend Cycle(cycle_period=10,fast_period=23,slow_period=50)": (
        "ta 0.11.0 has STCIndicator, and with smooth1 and smooth2 set to 3 its "
        "smoothing factor is 2/(3+1), the 0.5 that §2.20 writes. It was run, and the "
        "only structural difference is §0.3's EMA seed: ta starts both MACD averages "
        "at the first close, while §0.3 seeds them with the simple average of their "
        "first n. Re-running ta's pipeline on TA-Lib's SMA-seeded EMAs reproduces our "
        "values exactly at all three sampled bars, which is what places the "
        "difference in the seed rather than in the formula. The stock comparison is "
        "not entered as converging because the residual is not monotone: the gaps are "
        "1.5e-3, then 3.9e-9, then 1.0e-6. Two stochastic stages sit between the seed "
        "and the output, and each rescales whatever is left by its own window's range, "
        "so a shrinking gap is not something this indicator can be asserted to have."
    ),
    "Relative Vigor Index(period=10).rvi": (
        "None of the three implements Ehlers' Relative Vigor Index. The symmetric "
        "four-term weighting §2.21 defines is not available as a primitive in any of "
        "them either, so there is nothing outside to compare the numerator and "
        "denominator against. Tulip's `rvi` does not exist; what shares the "
        "abbreviation is Dorsey's Relative Volatility Index in §3.7, a different "
        "calculation owned by the volatility category."
    ),
    "Relative Vigor Index(period=10).signal": (
        "The symmetric filter applied to an uncompared series; it inherits the gap above."
    ),
    "Laguerre RSI(gamma=0.5)": (
        "None of the three implements a Laguerre filter of any kind, so neither the "
        "four-pole cascade nor the difference sums §2.22 builds on it have an outside "
        "counterpart. The value stays inside 0 and 1 across the series and saturates "
        "at both ends, which is what a gamma at the fast end of §2.22's range does on "
        "long one-way runs."
    ),
    "Center of Gravity(period=10)": (
        "None of the three implements Ehlers' Center of Gravity. §8.2 is a weighted "
        "centroid with no shared part left over once the weighting is removed, so "
        "there is nothing to compose it from either."
    ),
}
