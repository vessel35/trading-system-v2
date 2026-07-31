"""What the tests expect of the volume category: its registrations and its values."""

# The combinations this category registers, written out by hand. Nothing here reads
# the registry back: a pin that derives its own subject cannot notice the subject
# moving. Adding an indicator means adding a line here as well as a spec in
# `core_lib/indicators/specs/volume.py`, and doing only one of the two fails.
IDENTIFIERS: frozenset[str] = frozenset(
    {
        "A/D Line",
        "CMF(period=20)",
        "Chaikin Oscillator(fast_period=3,slow_period=10)",
        "Force Index(period=13)",
        "OBV",
        "Volume SMA(period=20)",
    }
)

NAMES: frozenset[str] = frozenset(
    {
        "A/D Line",
        "CMF",
        "Chaikin Oscillator",
        "Force Index",
        "OBV",
        "Volume SMA",
    }
)

# How many of the standard's 82 systems the registrations above account for. It is
# one fewer than the number of names because §0.2 treats Volume SMA as a primitive
# input and leaves it outside the 82.
STANDARD_SYSTEMS = 5

UNDEFINED_OUTPUTS: dict[str, tuple[str, ...]] = {}

# TA-Lib 0.7.1 over the series `reference_candles` builds, except where a comment
# names a different implementation.
REFERENCE: dict[str, dict[int, float]] = {
    "A/D Line": {100: 612.8055609726664, 200: 1060.0240840685929, 299: 2281.663413045828},
    "Volume SMA(period=20)": {100: 130.0, 200: 126.25, 299: 133.75},
    # ta 0.11.0 ChaikinMoneyFlowIndicator.
    "CMF(period=20)": {
        100: -0.18378324771896384,
        200: 0.1184521618242292,
        299: 0.3089552759865531,
    },
    # TA-Lib's OBV starts the accumulation at the first candle's volume; §4.1
    # defines only the recursion, so the two differ by that constant. The
    # reference below has the offset removed, which still checks every step.
    "OBV": {100: 35.0, 200: 195.0, 299: 1740.0},
}

CONVERGING: dict[str, tuple[dict[int, float], dict[int, float]]] = {
    # TA-Lib's ADOSC inherits its ATR-style seeding difference through the A/D
    # averages, so this one converges as well.
    "Chaikin Oscillator(fast_period=3,slow_period=10)": (
        {100: 0.7392424925909609, 200: 167.5528602118775, 299: 135.60824398604382},
        {100: 1e-5, 200: 1e-9, 299: 1e-9},
    ),
    "Force Index(period=13)": (
        {100: -40.44860100473615, 200: 283.50551116115287, 299: 166.16610511712776},
        {100: 1e-3, 200: 1e-9, 299: 1e-9},
    ),
}

UNCOMPARED: dict[str, str] = {}
