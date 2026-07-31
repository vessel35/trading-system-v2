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
        "Ease of Movement(period=14,scale=100000000)",
        "Force Index(period=13)",
        "Klinger Volume Oscillator(long_period=55,short_period=34,signal_period=13)",
        "Money Flow Index(period=14)",
        "Negative Volume Index",
        "OBV",
        "Positive Volume Index",
        "Volume SMA(period=20)",
    }
)

NAMES: frozenset[str] = frozenset(
    {
        "A/D Line",
        "CMF",
        "Chaikin Oscillator",
        "Ease of Movement",
        "Force Index",
        "Klinger Volume Oscillator",
        "Money Flow Index",
        "Negative Volume Index",
        "OBV",
        "Positive Volume Index",
        "Volume SMA",
    }
)

# How many of the standard's 82 systems the registrations above account for. It is
# one fewer than the number of names because §0.2 treats Volume SMA as a primitive
# input and leaves it outside the 82. With §4.5, §4.7, §4.8, §4.9 and §4.10 added,
# every volume indicator the standard specifies is now registered.
STANDARD_SYSTEMS = 10

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
    # TA-Lib MFI. Tulip Indicators 0.4.0 `ti.mfi` agrees with it to a relative
    # 5e-16 on the same series, so the two implementations read §4.5 the same way.
    "Money Flow Index(period=14)": {
        100: 28.964285441095683,
        200: 80.76028387078841,
        299: 94.05667848163627,
    },
    # ta 0.11.0 EaseOfMovementIndicator.sma_ease_of_movement, which uses §4.7's
    # example scale of 100000000. Tulip's `ti.emv` computes the same unsmoothed
    # value at a scale of 10000 and agrees once that factor of 10000 is removed.
    "Ease of Movement(period=14,scale=100000000)": {
        100: -6523021.961652775,
        200: 12050159.760972707,
        299: 11952445.900746258,
    },
    # Tulip Indicators 0.4.0 `ti.nvi`. ta 0.11.0's NegativeVolumeIndexIndicator
    # produces the same numbers to a relative 3e-16, so both compound the close
    # change the way §4.9 writes it rather than adding the percentage.
    "Negative Volume Index": {
        100: 991.9559538207153,
        200: 1011.9065253002941,
        299: 1016.5198903857322,
    },
    # Tulip Indicators 0.4.0 `ti.pvi`; neither TA-Lib nor ta implements §4.10.
    "Positive Volume Index": {
        100: 1142.323617816234,
        200: 1137.0062198154667,
        299: 1405.4563575152085,
    },
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
    # Tulip Indicators 0.4.0 `ti.kvo`, the only outside implementation of §4.8
    # among the three. It initializes cm the way §4.8's else branch does on the
    # first transition, so the Volume Force series itself agrees; what differs is
    # the seed of the exponential averages laid over it. Tulip starts an EMA at
    # its first observation while §0.3 starts it from the simple average of the
    # first n, and the recursion forgets that difference geometrically, which is
    # why the gap below closes instead of holding.
    "Klinger Volume Oscillator(long_period=55,short_period=34,signal_period=13).kvo": (
        {100: -710.7921899625235, 200: 621.0480674663745, 299: 1474.7217528004976},
        {100: 5.5e1, 200: 3e0, 299: 1e-1},
    ),
    # Tulip publishes no signal line for §4.8, so the comparison applies Tulip's
    # own `ti.ema` at the period §4.8 fixes to Tulip's own oscillator. Both
    # smoothings are therefore Tulip's, and the same seed difference reaches this
    # line through the oscillator it smooths.
    "Klinger Volume Oscillator(long_period=55,short_period=34,signal_period=13).signal": (
        {100: -834.1560917893563, 200: -323.5287791017653, 299: 933.793715095044},
        {100: 5.5e1, 200: 4e0, 299: 2e-1},
    ),
}

UNCOMPARED: dict[str, str] = {}
