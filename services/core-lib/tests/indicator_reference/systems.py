"""What the tests expect of the systems category: its registrations and its values."""

# The combinations this category registers, written out by hand. Nothing here reads
# the registry back: a pin that derives its own subject cannot notice the subject
# moving. Adding an indicator means adding a line here as well as a spec in
# `core_lib/indicators/specs/systems.py`, and doing only one of the two fails.
IDENTIFIERS: frozenset[str] = frozenset(
    {
        "Elder Ray(period=13)",
        "Parabolic SAR(maximum=0.2,step=0.02)",
    }
)

NAMES: frozenset[str] = frozenset({"Elder Ray", "Parabolic SAR"})

# How many of the standard's 82 systems the registrations above account for. Both
# names are among the 82, so the count equals the number of names.
STANDARD_SYSTEMS = 2

UNDEFINED_OUTPUTS: dict[str, tuple[str, ...]] = {}

# TA-Lib 0.7.1 over the series `reference_candles` builds.
REFERENCE: dict[str, dict[int, float]] = {
    "Parabolic SAR(maximum=0.2,step=0.02)": {
        100: 108.96711637478809,
        200: 95.11455805836829,
        299: 139.52708817671194,
    },
}

CONVERGING: dict[str, tuple[dict[int, float], dict[int, float]]] = {}

UNCOMPARED: dict[str, str] = {
    "Elder Ray(period=13).bull_power": (
        "No available implementation. §9.3 subtracts a smoothed close from each "
        "extreme, and that smoothed close is the compared EMA."
    ),
    "Elder Ray(period=13).bear_power": ("As above, with the low instead of the high."),
}
