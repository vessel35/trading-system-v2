"""What the tests expect of the trend category: its registrations and its values.

Each module in this package declares the same names so the package can merge them
without asking which categories happen to have entries. An empty collection is a
statement that the category has nothing of that kind, not an oversight.
"""

# The combinations this category registers, written out by hand. Nothing here reads
# the registry back: a pin that derives its own subject cannot notice the subject
# moving. Adding an indicator means adding a line here as well as a spec in
# `core_lib/indicators/specs/trend.py`, and doing only one of the two fails.
IDENTIFIERS: frozenset[str] = frozenset(
    {
        "DEMA(period=21)",
        "EMA(period=200)",
        "EMA(period=21)",
        "EMA(period=55)",
        "EMA(period=9)",
        "KAMA(period=10)",
        "TEMA(period=21)",
    }
)

NAMES: frozenset[str] = frozenset({"DEMA", "EMA", "KAMA", "TEMA"})

# How many of the standard's 82 systems the registrations above account for. It is
# one fewer than the number of names because §0.3 classifies EMA as a primitive and
# leaves it outside the 82.
STANDARD_SYSTEMS = 3

UNDEFINED_OUTPUTS: dict[str, tuple[str, ...]] = {}

# TA-Lib 0.7.1 over the series `reference_candles` builds.
REFERENCE: dict[str, dict[int, float]] = {
    "EMA(period=9)": {100: 114.54475915444709, 200: 104.15248782563998, 299: 139.881793061695},
    "EMA(period=21)": {100: 118.4661916884445, 200: 101.73018752590491, 299: 130.8116157709897},
    "EMA(period=55)": {100: 119.00040346526784, 200: 107.48356798999689, 299: 120.93480737137257},
    "EMA(period=200)": {200: 114.62267045315066, 299: 116.82135764947657},
    "DEMA(period=21)": {100: 115.60911921449878, 200: 99.04014813313854, 299: 142.38341794759424},
    "TEMA(period=21)": {
        100: 110.5316275392987,
        200: 103.44342539321069,
        299: 147.90149272889016,
    },
    "KAMA(period=10)": {
        100: 112.70229470734732,
        200: 110.77951322216872,
        299: 143.8303533700434,
    },
}

CONVERGING: dict[str, tuple[dict[int, float], dict[int, float]]] = {}

UNCOMPARED: dict[str, str] = {}
