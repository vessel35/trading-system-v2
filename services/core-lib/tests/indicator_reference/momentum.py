"""What the tests expect of the momentum category: its registrations and its values."""

# The combinations this category registers, written out by hand. Nothing here reads
# the registry back: a pin that derives its own subject cannot notice the subject
# moving. Adding an indicator means adding a line here as well as a spec in
# `core_lib/indicators/specs/momentum.py`, and doing only one of the two fails.
IDENTIFIERS: frozenset[str] = frozenset(
    {
        "Accelerator Oscillator(fast_period=5,slow_period=34,smooth_period=5)",
        "Awesome Oscillator(fast_period=5,slow_period=34)",
        "CCI(period=20)",
        "CMO(period=14)",
        "Coppock Curve(long_period=14,short_period=11,smooth_period=10)",
        "Fisher Transform(period=9)",
        "KST",
        "MACD(fast_period=12,signal_period=9,slow_period=26)",
        "PPO(fast_period=12,signal_period=9,slow_period=26)",
        "RSI(period=14)",
        "SMI(long_period=25,period=13,short_period=13,signal_period=3)",
        "Stochastic RSI(rsi_period=14,smooth_d=3,smooth_k=3,stochastic_period=14)",
        "Stochastic(period=14,smooth_period=3)",
        "TRIX(period=15)",
        "TSI(long_period=25,short_period=13)",
        "Ultimate Oscillator(long_period=28,medium_period=14,short_period=7)",
        "Williams %R(period=14)",
    }
)

NAMES: frozenset[str] = frozenset(
    {
        "Accelerator Oscillator",
        "Awesome Oscillator",
        "CCI",
        "CMO",
        "Coppock Curve",
        "Fisher Transform",
        "KST",
        "MACD",
        "PPO",
        "RSI",
        "SMI",
        "Stochastic",
        "Stochastic RSI",
        "TRIX",
        "TSI",
        "Ultimate Oscillator",
        "Williams %R",
    }
)

# How many of the standard's 82 systems the registrations above account for. Every
# momentum name is one of the 82, so the count equals the number of names.
STANDARD_SYSTEMS = 17

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
}
