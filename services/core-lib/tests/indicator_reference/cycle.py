"""TA-Lib 0.7.1 reference values for the seven pinned Hilbert functions."""

_MAMA = "MAMA(fastlimit=0.5,slowlimit=0.05)"

IDENTIFIERS: frozenset[str] = frozenset(
    {
        "HT_DCPERIOD",
        "HT_DCPHASE",
        "HT_PHASOR",
        "HT_SINE",
        "HT_TRENDLINE",
        "HT_TRENDMODE",
        _MAMA,
    }
)

NAMES: frozenset[str] = frozenset(
    {
        "HT_DCPERIOD",
        "HT_DCPHASE",
        "HT_PHASOR",
        "HT_SINE",
        "HT_TRENDLINE",
        "HT_TRENDMODE",
        "MAMA",
    }
)

# §11 counts MAMA/FAMA as one system and HT_SINE/HT_TRENDLINE together as
# Sinewave/ITrend. The remaining four functions are one system each.
STANDARD_SYSTEMS = 6

UNDEFINED_OUTPUTS: dict[str, tuple[str, ...]] = {}

# Captured by running TA-Lib 0.7.1 over `reference_candles`. Unlike every other
# category, §0.12 makes these seven C files the calculation source, not merely an
# outside comparison. The extra HT_TRENDMODE point at 68 captures the cycle state
# as well as the trend state present at the three shared sample indices.
REFERENCE: dict[str, dict[int, float]] = {
    "HT_DCPERIOD": {
        100: 34.32072027977639,
        200: 36.78736433058124,
        299: 28.96116981732977,
    },
    "HT_DCPHASE": {
        100: 290.82905103424196,
        200: 24.42106318098179,
        299: 152.279549719366,
    },
    "HT_PHASOR.inphase": {
        100: -7.556408195779168,
        200: 17.909495585544327,
        299: 13.186006337717208,
    },
    "HT_PHASOR.quadrature": {
        100: 16.960837960208693,
        200: 14.334888953139199,
        299: -9.277155452967948,
    },
    "HT_SINE.sine": {
        100: -0.9346455041542449,
        200: 0.41343918912274585,
        299: 0.4651580349894065,
    },
    "HT_SINE.leadsine": {
        100: -0.409460503252314,
        200: 0.9361888171646754,
        299: -0.29703407740235044,
    },
    "HT_TRENDLINE": {
        100: 123.35561621477714,
        200: 107.90803080758697,
        299: 121.7226077549036,
    },
    "HT_TRENDMODE": {68: 0.0, 100: 1.0, 200: 1.0, 299: 1.0},
    f"{_MAMA}.mama": {
        100: 114.90356352702632,
        200: 98.87237136545686,
        299: 139.2345001447337,
    },
    f"{_MAMA}.fama": {
        100: 119.0674410237951,
        200: 102.24004988142946,
        299: 124.22440676741788,
    },
}

CONVERGING: dict[str, tuple[dict[int, float], dict[int, float]]] = {}

UNCOMPARED: dict[str, str] = {}
