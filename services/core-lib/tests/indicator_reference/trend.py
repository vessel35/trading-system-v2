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
        "ALMA(offset=0.85,period=9,sigma=6.0)",
        "DEMA(period=21)",
        "EMA(period=200)",
        "EMA(period=21)",
        "EMA(period=55)",
        "EMA(period=9)",
        "Guppy GMMA",
        "HMA(period=9)",
        "KAMA(period=10)",
        "McGinley Dynamic(period=21)",
        "T3(period=21,volume_factor=0.7)",
        "TEMA(period=21)",
        "VIDYA(period=21,volatility_period=9)",
        "ZLEMA(period=21)",
    }
)

NAMES: frozenset[str] = frozenset(
    {
        "ALMA",
        "DEMA",
        "EMA",
        "Guppy GMMA",
        "HMA",
        "KAMA",
        "McGinley Dynamic",
        "T3",
        "TEMA",
        "VIDYA",
        "ZLEMA",
    }
)

# How many of the standard's 82 systems the registrations above account for. It is
# one fewer than the number of names because §0.3 classifies EMA as a primitive and
# leaves it outside the 82. With §1 fully implemented the trend category now covers
# §1.1 through §1.10, which is ten of the 82.
STANDARD_SYSTEMS = 10

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
    # Index 100 is absent because T3 over a period of 21 needs 121 candles before it
    # has a value at all, and TA-Lib reports the same warm-up.
    "T3(period=21,volume_factor=0.7)": {
        200: 96.07300441322712,
        299: 121.33156148404757,
    },
    # Tulip Indicators 0.4.0; neither TA-Lib nor ta implements the Hull average. A
    # period of 9 also removes the one place the two could legitimately disagree:
    # §1.4 rounds the square root of the period while Tulip truncates it, and 9 is a
    # perfect square, so both read the smoothing window as 3.
    "HMA(period=9)": {
        100: 113.27176566167567,
        200: 115.70956324101572,
        299: 145.88640411557643,
    },
    # §1.10 defines Guppy as twelve exponential averages and nothing else, so each
    # output is compared against TA-Lib's EMA at the period the section names.
    "Guppy GMMA.short_3": {
        100: 113.43696374555648,
        200: 112.30197654165877,
        299: 143.9861031655571,
    },
    "Guppy GMMA.short_5": {
        100: 113.30311178801556,
        200: 108.9514973538846,
        299: 143.1173950777212,
    },
    "Guppy GMMA.short_8": {
        100: 114.11933144342053,
        200: 105.07976376460935,
        299: 140.76977088568933,
    },
    "Guppy GMMA.short_10": {
        100: 114.99668110177822,
        200: 103.39450854590105,
        299: 138.98790796306855,
    },
    "Guppy GMMA.short_12": {
        100: 115.8968619712622,
        200: 102.32044237798897,
        299: 137.23973350410168,
    },
    "Guppy GMMA.short_15": {
        100: 117.06259860768935,
        200: 101.55456664985456,
        299: 134.81624008124103,
    },
    "Guppy GMMA.long_30": {
        100: 119.02052565304515,
        200: 103.4019038079165,
        299: 126.5852862194982,
    },
    "Guppy GMMA.long_35": {
        100: 119.03531162299308,
        200: 104.40100033827072,
        299: 124.91370096297071,
    },
    "Guppy GMMA.long_40": {
        100: 119.01165909327777,
        200: 105.31825416302988,
        299: 123.58517069013774,
    },
    "Guppy GMMA.long_45": {
        100: 118.95193699965141,
        200: 106.13364378119694,
        299: 122.5176154830976,
    },
    "Guppy GMMA.long_50": {
        100: 118.89861541454606,
        200: 106.85045757909946,
        299: 121.64937764771854,
    },
    "Guppy GMMA.long_60": {
        100: 119.3420646338462,
        200: 108.05268773186901,
        299: 120.34036928762218,
    },
}

CONVERGING: dict[str, tuple[dict[int, float], dict[int, float]]] = {
    # Tulip Indicators 0.4.0. Tulip starts the recursion at the first lag-corrected
    # candle and seeds it with that single price, while §0.3 seeds a recursive
    # average with the simple average of its first full period. The corrected price
    # and the smoothing constant are the same on both sides, so the gap is the seed
    # being forgotten geometrically: 2.4e-2, then 1.7e-6, then 1.4e-10.
    "ZLEMA(period=21)": (
        {100: 109.6069057763911, 200: 103.26990911018589, 299: 147.67432262556812},
        {100: 1e-1, 200: 1e-5, 299: 1e-9},
    ),
}

UNCOMPARED: dict[str, str] = {
    "ALMA(offset=0.85,period=9,sigma=6.0)": (
        "None of TA-Lib 0.7.1, Tulip Indicators 0.4.0, or ta 0.11.0 implements the "
        "Arnaud Legoux average; the function lists were read rather than assumed. "
        "§1.6 is a fixed Gaussian kernel over a closed window with no recursion, so "
        "there is no seed convention that a comparison would have settled."
    ),
    "VIDYA(period=21,volatility_period=9)": (
        "Tulip Indicators has a VIDYA, but it takes a short period, a long period, "
        "and an alpha, which is the original Chande definition where k is the ratio "
        "of a short standard deviation to a long one. §1.8's body defines k as "
        "|CMO(P, m)| / 100 and that is what this repository implements, so the two "
        "compute different quantities and their values are not comparable. Running "
        "Tulip's version over the same candles gives 118.46385005457596 at index 100 "
        "against our 118.87233333886456, a difference of definition rather than of "
        "seed. Neither TA-Lib nor ta implements VIDYA at all."
    ),
    "McGinley Dynamic(period=21)": (
        "None of the three implements it. Tulip's `md` is a mean deviation, not the "
        "McGinley Dynamic, so the name is a coincidence rather than a reference. "
        "§1.9's divisor contains the previous output raised to the fourth power, "
        "which no compared primitive covers, so this indicator is left uncompared "
        "rather than checked against a part of itself."
    ),
}
