"""What the tests expect of the systems category: its registrations and its values."""

# Two of these combinations carry enough parameters that their identifier does not
# fit on one line, and §6.1 and §6.3 register the same six because §6.3 is built from
# §6.1's lines. Writing that parameter text once keeps the two spellings from drifting
# apart; every character of it is still typed here rather than read back from the
# registry, which is what lets the comparison notice a registration moving.
_LINE_PARAMS = "jaw_period=13,jaw_shift=8,lips_period=5,lips_shift=3,teeth_period=8,teeth_shift=5"
_CLOUD_PARAMS = "base_period=26,conversion_period=9,displacement=26,span_b_period=52"

_ICHIMOKU = f"Ichimoku Kinko Hyo({_CLOUD_PARAMS})"
_ALLIGATOR = f"Alligator({_LINE_PARAMS})"
_GATOR = f"Gator Oscillator({_LINE_PARAMS})"
_IMPULSE = "Elder Impulse System(ema_period=13,fast_period=12,signal_period=9,slow_period=26)"
_WOODIES = "Woodies CCI(period=14,turbo_period=6)"

# The combinations this category registers, written out by hand. Nothing here reads
# the registry back: a pin that derives its own subject cannot notice the subject
# moving. Adding an indicator means adding a line here as well as a spec in
# `core_lib/indicators/specs/systems.py`, and doing only one of the two fails.
IDENTIFIERS: frozenset[str] = frozenset(
    {
        "Elder Ray(period=13)",
        "Parabolic SAR(maximum=0.2,step=0.02)",
        _ICHIMOKU,
        _ALLIGATOR,
        _GATOR,
        "Fractals(period=5)",
        "Market Facilitation Index",
        _IMPULSE,
        "TD Sequential(lookback=4)",
        "Woodies CCI(period=14,turbo_period=6)",
    }
)

NAMES: frozenset[str] = frozenset(
    {
        "Elder Ray",
        "Parabolic SAR",
        "Ichimoku Kinko Hyo",
        "Alligator",
        "Gator Oscillator",
        "Fractals",
        "Market Facilitation Index",
        "Elder Impulse System",
        "TD Sequential",
        "Woodies CCI",
    }
)

# How many of the standard's 93 systems the registrations above account for. §11
# counts every one of these ten separately: four of them under §6 Bill Williams
# (Alligator, Fractals, Gator, Market Facilitation Index) and six under §9 (Parabolic
# SAR, Ichimoku, Elder Ray, Elder Impulse, TD Sequential, Woodies CCI), so the count
# equals the number of names.
#
# Two of the ten register part of what their section describes rather than all of it,
# and each says so in its `pinned_impl`. TD Sequential registers §9.5's setup and not
# its countdown, because §9.5 states the countdown's length and comparison but defers
# the rules that cancel and restart it to DeMark's original work. Woodies CCI
# registers §9.6's two lengths and its zone lines and not its zero-line patterns,
# because §9.6 names ZLR, TLB and GB100 without defining them. §11 still counts each
# as one system, so the count above is unaffected; the partial coverage is recorded
# where a reader of the registry will see it.
STANDARD_SYSTEMS = 10

UNDEFINED_OUTPUTS: dict[str, tuple[str, ...]] = {}

# TA-Lib 0.7.1 over the series `reference_candles` builds, except where noted.
#
# The alignment this repository publishes and the alignment a charting library
# publishes are not the same statement, so the entries below record which index of
# the outside series each of ours was read against. `core_lib/indicators/systems.py`
# explains why our index is the chart position rather than the computation moment.
REFERENCE: dict[str, dict[int, float]] = {
    "Parabolic SAR(maximum=0.2,step=0.02)": {
        100: 108.96711637478809,
        200: 95.11455805836829,
        299: 139.52708817671194,
    },
    # ta 0.11.0 `IchimokuIndicator(high, low, 9, 26, 52)`. Its conversion and base
    # lines are unshifted and were read at the same index as ours. Its `ichimoku_a`
    # and `ichimoku_b` were read from an instance built with `visual=True`, which is
    # the option that moves each span forward by the 26-candle displacement so the
    # value sitting at an index is the one computed 26 candles earlier. That is
    # exactly the alignment §9.2's own note describes and the one we publish, so the
    # two series are compared index for index with no offset applied by hand. Reading
    # `visual=False` at the same index would compare values 26 candles apart.
    f"{_ICHIMOKU}.tenkan": {
        100: 113.95672082051834,
        200: 100.7792136940782,
        299: 137.33037056616845,
    },
    f"{_ICHIMOKU}.kijun": {
        100: 126.66744620320412,
        200: 105.11828393994776,
        299: 125.92276282284439,
    },
    f"{_ICHIMOKU}.senkou_a": {
        100: 112.73823821890915,
        200: 126.14244084307312,
        299: 108.92259222513812,
    },
    f"{_ICHIMOKU}.senkou_b": {
        100: 110.96158419008108,
        200: 109.8843222498133,
        299: 112.69057204028235,
    },
    # Tulip Indicators 0.4.0 `wilders` over the median price, which §0.5 states is
    # the same recursion §6.1 calls SMMA. Tulip publishes each average at the candle
    # that computed it and applies no shift, so each of our indices was read against
    # Tulip's index minus that line's shift: the jaw at index 100 against
    # `wilders(median, 13)` at 92, the teeth at 100 against `wilders(median, 8)` at
    # 95, and the lips at 100 against `wilders(median, 5)` at 97.
    f"{_ALLIGATOR}.jaw": {
        100: 124.93977659120202,
        200: 100.61830135741609,
        299: 115.23637943383326,
    },
    f"{_ALLIGATOR}.teeth": {
        100: 121.63913477645461,
        200: 93.44253257942509,
        299: 124.72443555905552,
    },
    f"{_ALLIGATOR}.lips": {
        100: 115.96147862611267,
        200: 94.7422920452486,
        299: 134.63038751670385,
    },
    # §6.3 applied to the Tulip lines above at the same indices, the way the
    # Bollinger derivatives take TA-Lib's bands and apply §3.10. No library carries
    # the Gator itself, but the arithmetic that turns §6.1's lines into it is two
    # subtractions the standard writes out in full.
    f"{_GATOR}.upper": {
        100: 3.300641814747408,
        200: 7.175768777990996,
        299: 9.488056125222258,
    },
    f"{_GATOR}.lower": {
        100: -5.677656150341946,
        200: -1.299759465823513,
        299: -9.905951957648327,
    },
    # §9.4 applied to TA-Lib's `EMA(close, 13)` and the histogram of its
    # `MACD(close, 12, 26, 9)`, again in the manner of the Bollinger derivatives:
    # the section is a comparison of two slopes, so an outside library supplying both
    # slopes decides the colour without our own calculation entering it.
    #
    # A classification cannot live in the CONVERGING table, which asks a numeric gap
    # to shrink, so the seed-window difference already recorded for MACD shows up here
    # as a disagreement over a small stretch instead. Of the 266 indices where both
    # sides have a histogram and a previous histogram, 265 agree; index 47 is the one
    # that does not. There TA-Lib's histogram slope is +5.73e-3 and ours is -3.90e-2,
    # because TA-Lib seeds both MACD averages together at the slow period while §2.4
    # seeds each at its own, leaving the two histograms 2.84e-1 apart 14 candles after
    # the histogram first exists. By index 100 that seed is forgotten and the three
    # sampled points agree.
    _IMPULSE: {100: 0.0, 200: 1.0, 299: 0.0},
    # TA-Lib 0.7.1 `CCI(high, low, close, timeperiod)` at the two lengths §9.6 names.
    # The zone is §9.6's own ±100 and ±200 lines applied to TA-Lib's 14-length value.
    f"{_WOODIES}.cci": {
        100: -32.98977219039359,
        200: 142.12259530061118,
        299: 73.9267888488236,
    },
    f"{_WOODIES}.turbo": {
        100: 159.0988519232185,
        200: 118.62502443804698,
        299: 41.04640281634377,
    },
    f"{_WOODIES}.zone": {100: 0.0, 200: 1.0, 299: 0.0},
}

CONVERGING: dict[str, tuple[dict[int, float], dict[int, float]]] = {}

UNCOMPARED: dict[str, str] = {
    "Elder Ray(period=13).bull_power": (
        "No available implementation. §9.3 subtracts a smoothed close from each "
        "extreme, and that smoothed close is the compared EMA."
    ),
    "Elder Ray(period=13).bear_power": ("As above, with the low instead of the high."),
    "Fractals(period=5).up": (
        "None of the three libraries carries §6.2's pattern. TA-Lib's pattern family "
        "is the CDL functions, every one of which reads a candle's own open, close "
        "and shadows to name a candlestick shape, where §6.2 compares one candle's "
        "high with the highs of the two candles each side of it and reads nothing "
        "inside any candle. Tulip Indicators and ta carry no fractal of any kind. "
        "The flags are checked instead against §6.2's inequality applied by hand to "
        "constructed candles, in `test_indicator_parity.py`."
    ),
    "Fractals(period=5).down": ("As above, with the lows instead of the highs."),
    "Market Facilitation Index": (
        "The abbreviation collides and the two indicators behind it are unrelated. "
        "TA-Lib's `MFI` and ta's `money_flow_index` are §4.5's Money Flow Index, "
        "which accumulates typical-price-weighted volume over a 14-candle window "
        "into a 0-to-100 oscillator. §6.4 divides one candle's own range by its own "
        "volume, keeps no window, and is unbounded above. Comparing them would "
        "compare two different calculations that share three letters. Checked "
        "instead against §6.4 applied by hand in `test_indicator_parity.py`."
    ),
    "TD Sequential(lookback=4)": (
        "No implementation in any of the three libraries; TA-Lib and Tulip carry no "
        "DeMark indicator at all, and ta's catalogue is trend, momentum, volatility "
        "and volume series with no counting system among them. The setup count is "
        "checked instead against §9.5's rule applied by hand to constructed candles "
        "whose direction is decided in the test, in `test_indicator_parity.py`."
    ),
}
