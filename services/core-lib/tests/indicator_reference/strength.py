"""What the tests expect of the strength category: its registrations and its values."""

# The combinations this category registers, written out by hand. Nothing here reads
# the registry back: a pin that derives its own subject cannot notice the subject
# moving. Adding an indicator means adding a line here as well as a spec in
# `core_lib/indicators/specs/strength.py`, and doing only one of the two fails.
IDENTIFIERS: frozenset[str] = frozenset(
    {
        "Aroon(period=25)",
        "DMI(period=14)",
    }
)

NAMES: frozenset[str] = frozenset({"Aroon", "DMI"})

# How many of the standard's 82 systems the registrations above account for. Both
# names are among the 82, so the count equals the number of names.
STANDARD_SYSTEMS = 2

UNDEFINED_OUTPUTS: dict[str, tuple[str, ...]] = {}

# TA-Lib 0.7.1 over the series `reference_candles` builds.
REFERENCE: dict[str, dict[int, float]] = {
    "Aroon(period=25).down": {100: 76.0, 200: 56.0, 299: 32.0},
    "Aroon(period=25).up": {100: 20.0, 200: 0.0, 299: 100.0},
    "Aroon(period=25).oscillator": {100: -56.0, 200: -56.0, 299: 68.0},
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
}

UNCOMPARED: dict[str, str] = {}
