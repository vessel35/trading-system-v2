"""What the tests expect of the volatility category: its registrations and its values."""

# The combinations this category registers, written out by hand. Nothing here reads
# the registry back: a pin that derives its own subject cannot notice the subject
# moving. Adding an indicator means adding a line here as well as a spec in
# `core_lib/indicators/specs/volatility.py`, and doing only one of the two fails.
IDENTIFIERS: frozenset[str] = frozenset(
    {
        "ATR(period=14)",
        "Acceleration Bands(period=20)",
        "Bollinger Bands(multiplier=2.0,period=20)",
        "Chaikin Volatility(period=10)",
        "Chandelier Exit(multiplier=3.0,period=22)",
        "Donchian Channel(period=20)",
        "Keltner Channel(atr_period=10,multiplier=2.0,period=20)",
        "Mass Index(period=9,sum_period=25)",
        "NATR(period=14)",
        "Relative Volatility Index(deviation_period=10,period=14)",
        "SuperTrend(multiplier=3.0,period=10)",
        "Ulcer Index(period=14)",
    }
)

NAMES: frozenset[str] = frozenset(
    {
        "ATR",
        "Acceleration Bands",
        "Bollinger Bands",
        "Chaikin Volatility",
        "Chandelier Exit",
        "Donchian Channel",
        "Keltner Channel",
        "Mass Index",
        "NATR",
        "Relative Volatility Index",
        "SuperTrend",
        "Ulcer Index",
    }
)

# How many of the standard's 93 systems the registrations above account for. It is
# two more than the number of names because the standard counts Bollinger Bands as
# three systems: the bands themselves, %B, and BandWidth. NATR is counted on its own
# line rather than folded into ATR, which §3.11 states explicitly.
STANDARD_SYSTEMS = 14

# §3.10 writes "분모 0 → 미정의" for %B, so a collapsed band has no relative position
# to report and the value stays NaN there. The spec declares this and the registry
# test checks that nothing else claims the same excuse.
#
# Nothing added since claims the excuse. §3.7, §3.8 and §3.9 each leave one zero
# denominator unaddressed, but all three of those indicators return a single number
# rather than a named set, and the engine's finiteness check can only skip a named
# key. Each of the three therefore names a substitute in its `pinned_impl` and
# `tests/test_indicator_volatility_flat_window.py` holds it to that value.
#
# §3.11 and §3.12 need no such choice made here: each writes its own substitute down,
# 0 for NATR when the close is zero and a ratio of 0 for Acceleration Bands when the
# high and the low sum to zero. Neither divisor is reachable through a `Candle`, which
# rejects a non-positive price, so `tests/test_indicator_parity.py` holds those two
# terms directly rather than through a candle stream.
UNDEFINED_OUTPUTS: dict[str, tuple[str, ...]] = {
    "Bollinger Bands(multiplier=2.0,period=20)": ("percent_b",),
}

# Values an outside implementation produced over the series `reference_candles` builds.
# The library behind each entry is named beside it; where no library carries the whole
# indicator, the entry says which outside parts were composed and which clause of the
# standard combined them.
REFERENCE: dict[str, dict[int, float]] = {
    # §3.1. Tulip Indicators 0.4.0's `atr(high, low, close, 14)`. Tulip is the comparison
    # here rather than TA-Lib because it keeps both conventions §3.1 depends on: §0.6's
    # first True Range `H_0 - L_0`, and §0.5's seed of the mean of the first fourteen.
    # TA-Lib skips that first bar, so its seed window starts one candle later and its
    # values differ by 8.0e-05 at index 100, 4.0e-08 at index 200 and 3.1e-11 at index
    # 299 — a gap that only shrinks, which is why this entry used to be a converging
    # comparison. Against Tulip nothing is left to converge: the two agree to 0.0,
    # 1.4e-16 and 1.7e-16 at the three points, the largest difference anywhere in the
    # series is 1.9e-16, and both produce their first value at index 13.
    "ATR(period=14)": {
        100: 5.157915393251702,
        200: 6.20093644248758,
        299: 5.280931651359102,
    },
    # TA-Lib 0.7.1.
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
    # §3.2. No single library produces the standard's Keltner: ta 0.11.0 has one, but
    # its centre is `close.ewm(span=20, adjust=False)`, which seeds on the first close
    # rather than on the mean of the first twenty that §0.3 names as the standard seed.
    # So the comparison is composed from the two libraries that each match one clause
    # of §3.2 exactly: TA-Lib 0.7.1's `EMA(close, 20)` for the centre and ta 0.11.0's
    # `AverageTrueRange(window=10)` for the width, combined by `Middle +/- 2*ATR`. That
    # ATR agrees with ours to the last bit at all three points while TA-Lib's own does
    # not, because ta counts §0.6's first range `H_0 - L_0` and TA-Lib skips that bar.
    #
    # ta's own KeltnerChannel was compared as well, and the gap it leaves is its EMA
    # seed being forgotten: relative differences of 7.1e-06, 3.7e-10 and 1.4e-14 on the
    # centre at indices 100, 200 and 299. That is recorded here rather than pinned,
    # because a seed still visible at index 100 belongs in a converging comparison and
    # the composed pin below is exact.
    "Keltner Channel(atr_period=10,multiplier=2.0,period=20).middle": {
        100: 118.3106623477395,
        200: 101.60756614290707,
        299: 131.40418629384843,
    },
    "Keltner Channel(atr_period=10,multiplier=2.0,period=20).upper": {
        100: 128.23798061261795,
        200: 114.36623046752212,
        299: 141.87809271181516,
    },
    "Keltner Channel(atr_period=10,multiplier=2.0,period=20).lower": {
        100: 108.38334408286104,
        200: 88.84890181829203,
        299: 120.9302798758817,
    },
    # §3.3. TA-Lib 0.7.1's `MAX(high, 20)` and `MIN(low, 20)`, with §3.3's midpoint.
    # ta 0.11.0's DonchianChannel produces the same three numbers to the last bit, and
    # both put the current candle inside its own window, which is what §0.8 defines.
    "Donchian Channel(period=20).upper": {
        100: 143.52767517919457,
        200: 117.96730932368271,
        299: 146.50787849073555,
    },
    "Donchian Channel(period=20).lower": {
        100: 108.96711637478809,
        200: 81.2932840712458,
        299: 105.33764715495325,
    },
    "Donchian Channel(period=20).middle": {
        100: 126.24739577699134,
        200: 99.63029669746425,
        299: 125.92276282284439,
    },
    # §3.5. None of the three libraries carries this indicator, so the comparison is
    # composed from outside parts, one per term of §3.5: TA-Lib 0.7.1's `MAX(high, 22)`
    # and `MIN(low, 22)` for the extremes and ta 0.11.0's `AverageTrueRange(window=22)`
    # for the width. Only the multiply-and-subtract is ours, which is the same shape of
    # derivation the Bollinger %B entry above already uses.
    "Chandelier Exit(multiplier=3.0,period=22).long": {
        100: 128.33239745992182,
        200: 100.00642912123095,
        299: 130.54285121537993,
    },
    "Chandelier Exit(multiplier=3.0,period=22).short": {
        100: 125.00249494648642,
        200: 99.25416427369754,
        299: 121.30267443030888,
    },
    # §3.6. ta 0.11.0's `UlcerIndex(close, window=14)`, which is §3.6 term for term: the
    # rolling highest close, the percentage drawdown from it, and the square root of the
    # mean of its squares. Its rolling maximum admits a partial window at the very
    # start, so its series begins earlier than ours; by index 26 every window is full.
    "Ulcer Index(period=14)": {
        100: 16.956320935050165,
        200: 18.909837434022872,
        299: 0.10487544845243055,
    },
    # §3.7. No library carries Dorsey's index, so the comparison is composed from Tulip
    # Indicators 0.4.0: `stddev(close, 10)` for §0.7's population deviation and
    # `wilders(x, 14)` for §0.5's smoothing, with §3.7's split between rising and
    # falling deviation done outside. Tulip's Wilder smoothing seeds on the mean of the
    # first fourteen values as §0.5 requires, which is why nothing here has a seed gap:
    # the residues are 2.9e-14, 4.6e-14 and 4.7e-14, flat rather than shrinking, so they
    # are floating-point noise rather than a convention difference.
    "Relative Volatility Index(deviation_period=10,period=14)": {
        100: 40.370008928686715,
        200: 61.44501150945211,
        299: 76.54998926573766,
    },
    # §3.8. TA-Lib 0.7.1's `EMA(high - low, 10)` with §3.8's own rate of change applied
    # to it. Tulip Indicators 0.4.0 does carry the whole indicator as `cvi`, and it
    # agrees to 5.8e-10, 2.2e-16 and 0.0 at the three points; the residue at index 100
    # is Tulip seeding its EMA on the first value instead of on the mean of the first
    # ten. The pin uses TA-Lib because §0.3 names that seed as the standard one, not
    # because it is the closer of the two.
    "Chaikin Volatility(period=10)": {
        100: -21.802797588290716,
        200: 32.71905108656287,
        299: -14.935053246853624,
    },
    # §3.9. TA-Lib 0.7.1's `EMA(high - low, 9)` and a second `EMA` over it, with §3.9's
    # ratio and twenty-five-bar sum applied outside. Both Tulip Indicators 0.4.0's
    # `mass` and ta 0.11.0's `MassIndex` compute the whole indicator and agree with ours
    # to 3.8e-09 at index 100 and to about 3e-16 at indices 200 and 299; both seed their
    # exponential averages on the first value rather than on the mean of the first nine,
    # which is the entire residue and is why it shrinks.
    "Mass Index(period=9,sum_period=25)": {
        100: 23.780883440330193,
        200: 26.131150030718743,
        299: 25.44530841651264,
    },
    # §3.11. Tulip Indicators 0.4.0's `natr(high, low, close, 14)`. Tulip is the
    # comparison for the same reason it is for ATR above: §3.11 divides the finished
    # ATR by the close, so it inherits whichever seed window the ATR underneath used,
    # and Tulip is the one library that keeps both conventions §3.1 depends on — §0.6's
    # first True Range `H_0 - L_0` and §0.5's seed of the mean of the first fourteen.
    # The two agree to 0.0, 1.7e-16 and 1.2e-16 at the three points, the largest
    # difference anywhere in the 287 overlapping bars is 2.7e-15, and both produce their
    # first value at index 13.
    #
    # TA-Lib 0.7.1's `NATR(high, low, close, 14)` was computed as well and reads
    # 4.518375372634951, 5.349448436846692 and 3.6688693492746975 at the three points,
    # relative gaps of 8.0e-05, 4.0e-08 and 3.1e-11. That is the ATR seed gap already
    # documented above and nothing else: TA-Lib skips the first bar, so its seed window
    # starts one candle later and its series begins at index 14. The gap only shrinks,
    # which is what a forgotten seed does and what a different formula does not. It is
    # recorded here rather than pinned as a converging entry, because the Tulip
    # comparison above is exact and the three tables may not both hold one output.
    "NATR(period=14)": {
        100: 4.51801444084562,
        200: 5.349448221897854,
        299: 3.6688693491619717,
    },
    # §3.12. TA-Lib 0.7.1's `ACCBANDS(high, low, close, timeperiod=20)`, which carries
    # the whole indicator. The agreement is exact to floating point at every one of the
    # 281 overlapping bars: the largest relative difference is 2.6e-16 on the upper band,
    # 2.1e-15 on the middle and 2.2e-15 on the lower, and both series begin at index 19.
    # This is what confirms §3.12's widening factor of 4, since a factor derived any
    # other way from Headley's `1000 * 0.001` form would move the two outer bands while
    # leaving the middle one, a plain `SMA(C, 20)`, exactly where it is.
    "Acceleration Bands(period=20).upper": {
        100: 136.1832241814359,
        200: 109.94879639464662,
        299: 140.28018126622834,
    },
    "Acceleration Bands(period=20).middle": {
        100: 122.36709457641125,
        200: 94.40787360648436,
        299: 127.34389233173165,
    },
    "Acceleration Bands(period=20).lower": {
        100: 110.19810050756271,
        200: 78.97262898431636,
        299: 112.94914421818078,
    },
}

# Nothing in this category needs the converging comparison any more. ATR used to sit
# here against TA-Lib, whose seed window starts one candle later than §0.6 and §0.5
# describe, so the check could only ask whether the gap kept shrinking. Tulip Indicators
# keeps both conventions, so the ATR entry moved into the exact comparison above. A
# shrinking gap rules out a different formula; it never sees the last digits, and this
# category no longer settles for that.
CONVERGING: dict[str, tuple[dict[int, float], dict[int, float]]] = {}

# SuperTrend is the one indicator in this category no outside comparison reaches.
# TA-Lib 0.7.1, Tulip Indicators 0.4.0 and ta 0.11.0 were each searched by name and
# none of them implements it. Composing it from their parts does not help either: the
# ATR input is the only piece they supply, and that piece is already pinned exactly
# elsewhere in this file, since ta's ATR at both periods equals ours to the last bit at
# all three sample points. What stays unchecked is §3.4's own content, which is the band
# lock carrying the previous bar's band forward and the trend state persisting until a
# close crosses a band. Reproducing that outside would mean writing the same recursion a
# second time and comparing it with itself, which proves nothing.
_SUPERTREND_REASON = (
    "no outside implementation exists: TA-Lib 0.7.1, Tulip Indicators 0.4.0 and ta "
    "0.11.0 were each searched by name and none carries SuperTrend. The ATR input is "
    "the only part they could supply and it is pinned exactly through the Keltner and "
    "Chandelier entries; §3.4's band lock and trend carry cannot be composed from "
    "library parts without restating the same recursion and comparing it with itself."
)

UNCOMPARED: dict[str, str] = {
    "SuperTrend(multiplier=3.0,period=10).supertrend": _SUPERTREND_REASON,
    "SuperTrend(multiplier=3.0,period=10).direction": _SUPERTREND_REASON,
    "SuperTrend(multiplier=3.0,period=10).upper": _SUPERTREND_REASON,
    "SuperTrend(multiplier=3.0,period=10).lower": _SUPERTREND_REASON,
}
