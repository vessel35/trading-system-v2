"""What the tests expect of the paired statistics category and its values."""

IDENTIFIERS: frozenset[str] = frozenset({"BETA(period=5)", "CORREL(period=30)"})
NAMES: frozenset[str] = frozenset({"BETA", "CORREL"})
STANDARD_SYSTEMS = 2
UNDEFINED_OUTPUTS: dict[str, tuple[str, ...]] = {}
REFERENCE: dict[str, dict[int, float]] = {
    # TA-Lib v0.7.1 with `paired_reference_candles` as inReal0 (X) and
    # `reference_candles` as inReal1 (Y). The input order matters for BETA.
    "BETA(period=5)": {
        100: -0.4809290806781768,
        200: 0.08493265297423128,
        299: -2.7042317660836295,
    },
    "CORREL(period=30)": {
        100: 0.35585898266771465,
        200: -0.3556750051256,
        299: 0.4588834235110546,
    },
}
CONVERGING: dict[str, tuple[dict[int, float], dict[int, float]]] = {}
UNCOMPARED: dict[str, str] = {}
