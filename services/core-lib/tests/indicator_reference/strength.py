"""What the tests expect of the strength category: its registrations and its values."""

# The combinations this category registers, written out by hand. Nothing here reads
# the registry back: a pin that derives its own subject cannot notice the subject
# moving. Adding an indicator means adding a line here as well as a spec in
# `core_lib/indicators/specs/strength.py`, and doing only one of the two fails.
IDENTIFIERS: frozenset[str] = frozenset(
    {
        "Aroon(period=25)",
        "Choppiness Index(period=14)",
        "DMI(period=14)",
        "Random Walk Index(period=14)",
        "Vortex Indicator(period=14)",
    }
)

NAMES: frozenset[str] = frozenset(
    {
        "Aroon",
        "Choppiness Index",
        "DMI",
        "Random Walk Index",
        "Vortex Indicator",
    }
)

# How many of the standard's 89 systems the registrations above account for. Every
# name is among the 89, so the count equals the number of names. §5.5's QQE is the
# one §5 section still unregistered, because its trailing band rule lives in the
# original code rather than in the standard.
STANDARD_SYSTEMS = 5

UNDEFINED_OUTPUTS: dict[str, tuple[str, ...]] = {}

# TA-Lib 0.7.1 over the series `reference_candles` builds.
REFERENCE: dict[str, dict[int, float]] = {
    "Aroon(period=25).down": {100: 76.0, 200: 56.0, 299: 32.0},
    "Aroon(period=25).up": {100: 20.0, 200: 0.0, 299: 100.0},
    "Aroon(period=25).oscillator": {100: -56.0, 200: -56.0, 299: 68.0},
    # ta 0.11.0 VortexIndicator; neither TA-Lib nor Tulip implements §5.2. It
    # drops the first candle's rotational movements the same way this repository
    # does, so from the first full window onward the two agree exactly.
    "Vortex Indicator(period=14).vi_plus": {
        100: 0.7618157744239104,
        200: 1.3307182177637067,
        299: 1.3881997457908102,
    },
    "Vortex Indicator(period=14).vi_minus": {
        100: 1.2776432914814224,
        200: 0.6400946934609275,
        299: 0.6162512162195292,
    },
    # None of the three libraries implements §5.4, so the comparison is built the
    # way the Bollinger derivatives were: every input comes from TA-Lib — TRANGE
    # for the ranges, SUM for their total and MAX/MIN for the window span — and
    # only §5.4's logarithm is applied on top. That checks the summation, the
    # extremes and the scaling against an outside implementation; it cannot check
    # the shape of the logarithm itself, which no library states.
    "Choppiness Index(period=14)": {
        100: 43.44712731074623,
        200: 31.148292121253906,
        299: 33.01718297581936,
    },
}

# The four directional-movement series inherit the ATR seed difference described in
# the volatility module: §0.6 gives the first True Range a value TA-Lib skips, and
# Wilder smoothing forgets that seed geometrically rather than at once.
CONVERGING: dict[str, tuple[dict[int, float], dict[int, float]]] = {
    "DMI(period=14).plus_di": (
        {100: 13.156990718429295, 200: 30.157413246696365, 299: 28.562937269215965},
        {100: 1e-2, 200: 1e-5, 299: 1e-8},
    ),
    "DMI(period=14).minus_di": (
        {100: 20.812833752708965, 200: 13.786118423716923, 299: 5.048650216175285},
        {100: 1e-2, 200: 1e-5, 299: 1e-8},
    ),
    "DMI(period=14).adx": (
        {100: 34.80316386849876, 200: 39.48336090910632, 299: 50.09187506981947},
        {100: 1e-1, 200: 1e-3, 299: 1e-6},
    ),
    # ADXR averages today's ADX with one from a period ago, so it carries the
    # seed difference twice and settles the slowest of the four.
    "DMI(period=14).adxr": (
        {100: 39.71081558037664, 200: 43.08908778158345, 299: 35.80714657054307},
        {100: 2.0, 200: 1.5, 299: 1.0},
    ),
    # No library implements §5.6 either, so this comparison divides the raw
    # displacements by TA-Lib's own ATR times sqrt(14). TA-Lib seeds ATR from the
    # second candle onward while §0.6 gives the first candle a True Range of its
    # own, which is the same seed difference the volatility module records for
    # ATR, and it reaches these two lines through the divisor. Like the
    # Choppiness entry above, this checks the divisor and the scaling rather than
    # the shape of §5.6's numerators.
    "Random Walk Index(period=14).high": (
        {100: -0.6747137912094339, 200: 1.4894228356260941, 299: 1.8420056120585506},
        {100: 1e-4, 200: 1e-7, 299: 1e-10},
    ),
    "Random Walk Index(period=14).low": (
        {100: 1.232138064345918, 200: -0.9941559437886748, 299: -1.3157939200099484},
        {100: 1e-4, 200: 1e-7, 299: 1e-10},
    ),
}

UNCOMPARED: dict[str, str] = {}
