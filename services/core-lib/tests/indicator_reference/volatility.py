"""What the tests expect of the volatility category: its registrations and its values."""

# The combinations this category registers, written out by hand. Nothing here reads
# the registry back: a pin that derives its own subject cannot notice the subject
# moving. Adding an indicator means adding a line here as well as a spec in
# `core_lib/indicators/specs/volatility.py`, and doing only one of the two fails.
IDENTIFIERS: frozenset[str] = frozenset(
    {
        "ATR(period=14)",
        "Bollinger Bands(multiplier=2.0,period=20)",
    }
)

NAMES: frozenset[str] = frozenset({"ATR", "Bollinger Bands"})

# How many of the standard's 82 systems the registrations above account for. It is
# two more than the number of names because the standard counts Bollinger Bands as
# three systems: the bands themselves, %B, and BandWidth.
STANDARD_SYSTEMS = 4

# §3.10 writes "분모 0 → 미정의" for %B, so a collapsed band has no relative position
# to report and the value stays NaN there. The spec declares this and the registry
# test checks that nothing else claims the same excuse.
UNDEFINED_OUTPUTS: dict[str, tuple[str, ...]] = {
    "Bollinger Bands(multiplier=2.0,period=20)": ("percent_b",),
}

# TA-Lib 0.7.1 over the series `reference_candles` builds.
REFERENCE: dict[str, dict[int, float]] = {
    "Bollinger Bands(multiplier=2.0,period=20).middle": {
        100: 122.36709457641125,
        200: 94.40787360648436,
        299: 127.34389233173165,
    },
    "Bollinger Bands(multiplier=2.0,period=20).upper": {
        100: 144.12910126270955,
        200: 114.22091638155808,
        299: 155.70673588042882,
    },
    "Bollinger Bands(multiplier=2.0,period=20).lower": {
        100: 100.60508789011293,
        200: 74.59483083141063,
        299: 98.98104878303448,
    },
    # Derived from TA-Lib's own bands with the §3.10 formulas, since TA-Lib
    # returns the three bands only.
    "Bollinger Bands(multiplier=2.0,period=20).percent_b": {
        100: 0.3115115882700029,
        200: 1.0428100055449034,
        299: 0.792549081776074,
    },
    "Bollinger Bands(multiplier=2.0,period=20).bandwidth": {
        100: 0.355683964902986,
        200: 0.4197328468102024,
        299: 0.4454527504909585,
    },
}

# ATR: §0.6 defines the first True Range as `H_0 - L_0` because there is no previous
# close, and §3.1 smooths from there. TA-Lib skips that first bar. The seeds differ,
# and Wilder smoothing forgets its seed geometrically.
CONVERGING: dict[str, tuple[dict[int, float], dict[int, float]]] = {
    "ATR(period=14)": (
        {100: 5.158327444974086, 200: 6.200936691650489, 299: 5.280931651521358},
        {100: 1e-3, 200: 1e-6, 299: 1e-8},
    ),
}

UNCOMPARED: dict[str, str] = {}
