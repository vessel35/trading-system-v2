"""Verify §7.5 of the candlestick pattern standard: the last ten sections.

Every expected value here is derived by hand from the standard and the arithmetic
that puts a bar on a threshold is written into the test that uses it, so a rule
and its check cannot drift together. `run` — which nearly every test calls —
judges the batch path and the incremental path and refuses to return until the
two agree bar for bar, so the parity claim is made on each hand-built series
rather than only on a generated one.

This group is the first to need `judgment.py` to do something it did not do for
the fifty-one sections before it, and the two additions are checked here as
carefully as the sections themselves.

**A confirmation deadline longer than one bar.** §5.5 gives the two Hikkake
sections Chesler's three bars. Four branches matter and each has its own test:
confirmed on the first bar, confirmed only on the third, not confirmed inside the
deadline at all, and a degenerate bar inside the deadline that cannot confirm
while a later bar inside the same deadline still can. A fifth claim is checked
with them — the confirmation belongs to the *first* bar that satisfies the rule,
so a second bar satisfying it later raises nothing.

**A window whose length is not fixed.** §7.5.5 admits two to five small candles.
All five forms are exercised, and so are the two index claims the section makes
about itself: index 12 can only be asked about `n = 2`, and index 15 is the first
bar where the `n = 5` form can be judged at all.

Three pairs of section are easy to confuse and are separated on purpose. §7.5.7
Tasuki Gap and §7.5.8 Gap Three Methods share their first two bars and are told
apart by where the third one closes, which makes them mutually exclusive. §7.5.6
keeps both of its bars white on the bearish side, where every other two-sided
section in the standard swaps the colours. And §7.5.9's polarity runs the way
that surprises: the bullish setup is the one whose last bar breaks *below* the
inside bar.

Section numbers in this file are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from math import isnan

import pytest
from core_lib.indicators.registry import DEFAULT_REGISTRY
from core_lib.patterns import long_and_gap, outputs, primitives, scales
from core_lib.patterns.judgment import (
    CONFIRMS_BEARISH_SIDE_ONLY,
    Match,
    PatternRule,
    PatternRuleState,
    confirms_by_close_direction,
    judge_series,
)
from core_lib.patterns.registry import PatternSpec
from core_lib.patterns.specs import DEFAULT_PATTERN_REGISTRY
from core_lib.types import Candle

TREND_WARM_UP_BARS = 9
"""§3.2: the ten-period average first exists at index 9, so nine bars precede it."""


def make_candle(index: int, open_price: float, high: float, low: float, close: float) -> Candle:
    open_time = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=index)
    return Candle(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe="1h",
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1000.0,
        quote_volume=None,
        trade_count=None,
    )


Shape = tuple[float, float, float, float]
"""One bar as (open, high, low, close), the form every hand-built candle takes here."""


def background(midpoint: float, count: int = TREND_WARM_UP_BARS) -> list[Shape]:
    """Return filler bars whose high-low midpoint is exactly `midpoint`.

    §3 compares the pattern's first day against a ten-period average of the
    midpoint. Nine filler bars at a constant `M` followed by the pattern's first
    day put the average on that first day at `(9 * M + f) / 10`, where `f` is its
    own midpoint, and `f` sits above that average exactly when `f > M`. So filler
    above the first day's midpoint makes a downtrend and filler below makes an
    uptrend, and the span of the pattern does not enter the arithmetic: a
    seven-bar section reads its first day the same way a three-bar one does.
    """
    return [(midpoint, midpoint + 1.0, midpoint - 1.0, midpoint)] * count


def series(shapes: Sequence[Shape]) -> list[Candle]:
    return [make_candle(index, *shape) for index, shape in enumerate(shapes)]


def assert_same_series(
    batch: Sequence[dict[str, float]],
    incremental: Sequence[dict[str, float]],
) -> None:
    assert len(batch) == len(incremental)
    for index, (left, right) in enumerate(zip(batch, incremental, strict=True)):
        assert left.keys() == right.keys(), f"index {index}"
        for key in left:
            if isnan(left[key]):
                assert isnan(right[key]), f"index {index} key {key}"
            else:
                assert left[key] == right[key], f"index {index} key {key}"


def run(rule: PatternRule, shapes: Sequence[Shape]) -> list[dict[str, float]]:
    """Return the batch series after checking the incremental path matches it."""
    candles = series(shapes)
    batch = judge_series(rule, candles)
    state = PatternRuleState(rule)
    incremental = [state.update(candle) for candle in candles]
    assert_same_series(batch, incremental)
    return batch


def matched(rule: PatternRule, shapes: Sequence[Shape], index: int = -1) -> dict[str, float]:
    """Assert the pattern held on one bar and return that bar's four outputs."""
    values = run(rule, shapes)[index]
    assert values[rule.name] == outputs.MATCHED
    return values


def not_matched(rule: PatternRule, shapes: Sequence[Shape], index: int = -1) -> dict[str, float]:
    """Assert the pattern was judged on one bar and did not hold there."""
    values = run(rule, shapes)[index]
    assert values[rule.name] == outputs.NOT_MATCHED
    return values


def confirmations(rule: PatternRule, shapes: Sequence[Shape]) -> list[float]:
    """Return the confirmation key bar by bar, with the warm-up bars dropped."""
    return [
        value[f"{rule.name}_confirm"]
        for value in run(rule, shapes)
        if not isnan(value[f"{rule.name}_confirm"])
    ]


# --- the bars most of §7.5 is built on ---------------------------------------
#
# Six sections open with a long first day, so two shapes do much of the work
# below. Both have a body of 30.00 in a range of 40.00 — past §2.1's half of the
# range — and a high-low midpoint of 120.00, which is what the filler is chosen
# against.

LONG_WHITE_FIRST: Shape = (105.0, 140.0, 100.0, 135.0)
"""Body 30.00 from 105.00 up to 135.00, range 40.00, midpoint 120.00."""

LONG_BLACK_FIRST: Shape = (135.0, 140.0, 100.0, 105.0)
"""The same bar the other way up: body 30.00 from 135.00 down to 105.00."""

DOWNTREND_FILLER = 130.0
"""Above the first day's midpoint of 120.00, so §3 answers `DOWNTREND`."""

UPTREND_FILLER = 110.0
"""Below that midpoint, so §3 answers `UPTREND`."""


# --- §7.5.1 Three-Line Strike ------------------------------------------------

THREE_LINE_STRIKE_BULLISH: list[Shape] = [
    *background(UPTREND_FILLER),
    (110.0, 135.0, 105.0, 125.0),
    (120.0, 140.0, 115.0, 135.0),
    (130.0, 145.0, 125.0, 142.0),
    (150.0, 152.0, 100.0, 105.0),
]
"""Three white bars with rising highs — 135.00, 140.00, 145.00 — then a long black one.

The first bar's midpoint of 120.00 sits above the filler at 110.00, so the trend
is up. The fourth bar opens at 150.00, above the third bar's high of 145.00; its
body of 45.00 in a range of 52.00 is long by §2.1's half; its low of 100.00 is
under the first bar's 105.00 and its close of 105.00 is under the first bar's
open of 110.00.
"""

THREE_LINE_STRIKE_BEARISH: list[Shape] = [
    *background(DOWNTREND_FILLER),
    (130.0, 135.0, 105.0, 110.0),
    (120.0, 125.0, 95.0, 100.0),
    (110.0, 115.0, 85.0, 90.0),
    (80.0, 140.0, 78.0, 138.0),
]
"""The mirror: three black bars with falling lows, then a long white bar closing at
138.00 — above the first black bar's *high* of 135.00, which is the asymmetry."""


def test_three_line_strike_undoes_three_bars_and_keeps_the_trend_direction() -> None:
    """Check §7.5.1's five rules, and the direction reading that surprises.

    The section is a continuation, so three white bars swallowed by a long black
    one report `+1.0` after an advance. The colour of the fourth bar is not the
    direction; the trend is.
    """
    values = matched(long_and_gap.THREE_LINE_STRIKE, THREE_LINE_STRIKE_BULLISH)
    assert values["pat_three_line_strike_dir"] == outputs.BULLISH

    # Rule 4 wants a new high on the fourth open: 145.00 is the third bar's high,
    # so opening there rather than above it is not "at a new high".
    opens_on_the_third_high: Shape = (145.0, 147.0, 100.0, 105.0)
    not_matched(
        long_and_gap.THREE_LINE_STRIKE,
        [*THREE_LINE_STRIKE_BULLISH[:-1], opens_on_the_third_high],
    )

    # Rule 2's highs are strict: a third bar peaking at 140.00 matches the second
    # bar's high instead of clearing it.
    level_high: Shape = (130.0, 140.0, 125.0, 138.0)
    not_matched(
        long_and_gap.THREE_LINE_STRIKE,
        [*THREE_LINE_STRIKE_BULLISH[:-2], level_high, (150.0, 152.0, 100.0, 105.0)],
    )


def test_the_bearish_three_line_strike_closes_over_the_first_high_and_not_the_first_open() -> None:
    """Check the one asymmetry §7.5.1 states, and that it is only that one.

    Morris writes the bearish side as closing "above the high of the first black
    day", so the mirror of the bullish "under the first open" reads the high. The
    first black bar opens at 130.00 and peaks at 135.00; a fourth bar closing at
    132.00 clears the open and not the high, and the section does not hold.
    """
    values = matched(long_and_gap.THREE_LINE_STRIKE, THREE_LINE_STRIKE_BEARISH)
    assert values["pat_three_line_strike_dir"] == outputs.BEARISH

    closes_over_the_open_only: Shape = (80.0, 140.0, 78.0, 132.0)
    not_matched(
        long_and_gap.THREE_LINE_STRIKE,
        [*THREE_LINE_STRIKE_BEARISH[:-1], closes_over_the_open_only],
    )


# --- §7.5.2 Breakaway --------------------------------------------------------

BREAKAWAY_BULLISH: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    (100.0, 102.0, 90.0, 92.0),
    (95.0, 96.0, 85.0, 88.0),
    (90.0, 92.0, 80.0, 82.0),
    (84.0, 104.0, 82.0, 102.0),
]
"""A long black bar, a body gap down, two falling closes, then a long white recovery.

The second bar's body top of 100.00 sits below the first body's bottom of 105.00,
which is §1.3's body gap. Closes then run 92.00, 88.00, 82.00. The fifth bar's
body of 18.00 in a range of 22.00 is long, and its close of 102.00 lands strictly
inside the window between 100.00 and 105.00.
"""

BREAKAWAY_BEARISH: list[Shape] = [
    *background(UPTREND_FILLER),
    LONG_WHITE_FIRST,
    (145.0, 150.0, 143.0, 148.0),
    (146.0, 155.0, 144.0, 152.0),
    (150.0, 158.0, 148.0, 156.0),
    (160.0, 162.0, 138.0, 140.0),
]
"""The mirror: the gap runs up from 135.00 to 145.00 and the fifth bar closes at
140.00, back inside it."""


def test_breakaway_closes_back_into_the_gap_that_opened_the_run() -> None:
    """Check §7.5.2's five rules on both sides, and rule 5's two bounds.

    The window is the space between the first body's bottom of 105.00 and the
    second body's top of 100.00, and the fifth close has to land strictly inside
    it. §4.2 makes both comparisons strict, so a close of exactly 105.00 sits on
    the first body rather than inside the gap.
    """
    values = matched(long_and_gap.BREAKAWAY, BREAKAWAY_BULLISH)
    assert values["pat_breakaway_dir"] == outputs.BULLISH

    closes_on_the_first_body: Shape = (84.0, 106.0, 82.0, 105.0)
    not_matched(long_and_gap.BREAKAWAY, [*BREAKAWAY_BULLISH[:-1], closes_on_the_first_body])

    values = matched(long_and_gap.BREAKAWAY, BREAKAWAY_BEARISH)
    assert values["pat_breakaway_dir"] == outputs.BEARISH


def test_breakaway_asks_the_middle_bars_for_falling_closes_and_no_colour() -> None:
    """Check rule 4, which Morris writes as a recommendation about colour.

    He asks for closes that carry the trend on and adds "It is better if" the
    bars are black, so decision C leaves the colour out. The two middle bars
    below are white and close lower all the same, and the section still holds.
    """
    white_middles: list[Shape] = [(86.0, 96.0, 85.0, 88.0), (78.0, 92.0, 77.0, 82.0)]
    assert matched(
        long_and_gap.BREAKAWAY,
        [
            *BREAKAWAY_BULLISH[:-3],
            *white_middles,
            BREAKAWAY_BULLISH[-1],
        ],
    )

    # A third bar closing at 94.00 is above the second bar's 92.00, and rule 4 is
    # the one condition those two bars carry.
    rising_middle: Shape = (86.0, 96.0, 85.0, 94.0)
    not_matched(
        long_and_gap.BREAKAWAY,
        [*BREAKAWAY_BULLISH[:-3], rising_middle, BREAKAWAY_BULLISH[-2], BREAKAWAY_BULLISH[-1]],
    )


# --- §7.5.3 Ladder Bottom ----------------------------------------------------

LADDER_BOTTOM_FOURTH: Shape = (95.0, 105.0, 88.0, 92.0)
"""Black, with an upper shadow of 10.00 in a range of 17.00 — far past §2.5's 1.70."""

LADDER_BOTTOM: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    (125.0, 128.0, 95.0, 100.0),
    (115.0, 118.0, 85.0, 90.0),
    LADDER_BOTTOM_FOURTH,
    (100.0, 115.0, 99.0, 112.0),
]
"""Three long black bars stepping down, a black bar with a tail, then a white open above it.

The three opens run 135.00, 125.00, 115.00 and the three closes 105.00, 100.00,
90.00, all falling. Their bodies of 30.00, 25.00 and 25.00 in ranges of 40.00 and
33.00 are long by §2.1. The last bar opens at 100.00, above the fourth bar's body
top of 95.00, which rule 4 compares as a position rather than as a gap.
"""


def test_ladder_bottom_wants_a_tail_on_its_fourth_bar_and_an_open_above_its_body() -> None:
    """Check §7.5.3's four rules, including the one place a scale is read negatively."""
    values = matched(long_and_gap.LADDER_BOTTOM, LADDER_BOTTOM)
    assert values["pat_ladder_bottom_dir"] == outputs.BULLISH
    assert values["pat_ladder_bottom_confirm"] == outputs.NOT_MATCHED

    # Rule 4 is a comparison against the body top of 95.00, not a gap: an open of
    # 95.00 sits on it and the section does not hold, while 100.00 does.
    opens_on_the_body_top: Shape = (95.0, 115.0, 94.0, 112.0)
    not_matched(long_and_gap.LADDER_BOTTOM, [*LADDER_BOTTOM[:-1], opens_on_the_body_top])

    # Rule 2 asks the three opens to keep falling: a second open of 136.00 is
    # above the first bar's 135.00 while every other condition still holds.
    rising_open: Shape = (136.0, 138.0, 95.0, 100.0)
    not_matched(
        long_and_gap.LADDER_BOTTOM,
        [*LADDER_BOTTOM[: TREND_WARM_UP_BARS + 1], rising_open, *LADDER_BOTTOM[-3:]],
    )


def test_the_fourth_bars_tail_is_measured_by_the_negation_of_section_two_five() -> None:
    """Check §7.5.3's rendering of "has an upper shadow" and where its threshold falls.

    Morris gives no size, and §7.5.3 refuses to read the words as `US > 0`
    because floating-point noise would pass. So the condition is the negation of
    §2.5: the shadow has to be more than a tenth of the range.

    The two bars below sit either side of that line. An upper shadow of exactly
    1.00 in a range of 10.00 *is* §2.5's very short shadow, so its negation fails
    and the section does not hold; 1.20 in a range of 10.20 is past the 1.02
    allowed and the section holds.
    """
    exactly_a_tenth: Shape = (95.0, 96.0, 86.0, 92.0)
    not_matched(
        long_and_gap.LADDER_BOTTOM,
        [*LADDER_BOTTOM[:-2], exactly_a_tenth, LADDER_BOTTOM[-1]],
    )

    just_past_a_tenth: Shape = (95.0, 96.2, 86.0, 92.0)
    assert matched(
        long_and_gap.LADDER_BOTTOM,
        [*LADDER_BOTTOM[:-2], just_past_a_tenth, LADDER_BOTTOM[-1]],
    )


def test_a_degenerate_bar_does_not_satisfy_the_negated_scale() -> None:
    """Check the trap §2.7 wrote its window gate for, on the rule that would spring it.

    §2.5 answers False for a four-price bar, so the negation rule 3 uses answers
    True — a bar with no shadow at all would be read as a bar that has one. The
    assertion below states that plainly, and the section still reports 0.0,
    because §2.7 puts a gate over the whole window before any rule is looked at.

    §1.2 would also reject this bar, since a four-price bar has no colour and
    rule 3 asks for black. That is §2.7's point: it says in so many words that
    neither device is enough on its own, and here they overlap.
    """
    four_price_bar: Shape = (95.0, 95.0, 95.0, 95.0)
    candle = series([four_price_bar])[0]
    assert primitives.is_degenerate(candle)
    assert not scales.no_upper_shadow(candle)
    assert not primitives.is_black(candle)

    values = not_matched(
        long_and_gap.LADDER_BOTTOM,
        [*LADDER_BOTTOM[:-2], four_price_bar, LADDER_BOTTOM[-1]],
    )
    assert values["pat_ladder_bottom_dir"] == outputs.DIRECTIONLESS


# --- §7.5.4 Mat Hold ---------------------------------------------------------

MAT_HOLD_BULLISH: list[Shape] = [
    *background(UPTREND_FILLER),
    LONG_WHITE_FIRST,
    (145.0, 148.0, 138.0, 140.0),
    (138.0, 139.0, 128.0, 130.0),
    (129.0, 131.0, 120.0, 126.0),
    (130.0, 155.0, 129.0, 152.0),
]
"""A long white bar, a black bar gapping above its body, then two more black bars.

The second bar's body bottom of 140.00 clears the first body's top of 135.00. The
third bar closes at 130.00, inside the first body of 105.00 to 135.00. The fourth
bar's body of 3.00 in a range of 11.00 is short by §2.2's 3.67, it closes at
126.00 under the third bar's 130.00, and its low of 120.00 stays above the first
bar's 100.00. The fifth bar closes at 152.00, above the highest of the three
black highs — 148.00, 139.00 and 131.00.
"""

MAT_HOLD_BEARISH: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    (95.0, 102.0, 92.0, 100.0),
    (102.0, 112.0, 101.0, 110.0),
    (111.0, 120.0, 109.0, 114.0),
    (110.0, 111.0, 85.0, 88.0),
]
"""The mirror: the fifth bar closes at 88.00, below the lowest of the three white
lows — 92.00, 101.00 and 109.00."""


def test_mat_hold_breaks_out_past_the_highest_of_the_three_small_bars() -> None:
    """Check §7.5.4's six rules, and rule 6 as the commentary states it.

    Morris's rule section asks the fifth day for a new closing high and his
    commentary asks it to close above the highest high of the three black days.
    Decision C takes the narrower, so a close of 148.00 — level with the second
    bar's high — is not enough, and 152.00 is.
    """
    values = matched(long_and_gap.MAT_HOLD, MAT_HOLD_BULLISH)
    assert values["pat_mat_hold_dir"] == outputs.BULLISH

    closes_on_the_highest_high: Shape = (130.0, 155.0, 129.0, 148.0)
    not_matched(long_and_gap.MAT_HOLD, [*MAT_HOLD_BULLISH[:-1], closes_on_the_highest_high])

    values = matched(long_and_gap.MAT_HOLD, MAT_HOLD_BEARISH)
    assert values["pat_mat_hold_dir"] == outputs.BEARISH

    closes_on_the_lowest_low: Shape = (110.0, 111.0, 85.0, 92.0)
    not_matched(long_and_gap.MAT_HOLD, [*MAT_HOLD_BEARISH[:-1], closes_on_the_lowest_low])


def test_mat_hold_keeps_its_fourth_bar_short_and_inside_the_first_range() -> None:
    """Check rule 5's three separate demands on the fourth bar.

    A body of 12.00 in a range of 14.00 is long rather than short and fails the
    first. A low of 99.00 is under the first bar's 100.00 and fails the third,
    which is what "still within the range of the first white body" bounds.
    """
    long_fourth: Shape = (131.0, 132.0, 118.0, 119.0)
    not_matched(
        long_and_gap.MAT_HOLD,
        [*MAT_HOLD_BULLISH[:-2], long_fourth, MAT_HOLD_BULLISH[-1]],
    )

    drops_below_the_first_low: Shape = (129.0, 131.0, 99.0, 126.0)
    not_matched(
        long_and_gap.MAT_HOLD,
        [*MAT_HOLD_BULLISH[:-2], drops_below_the_first_low, MAT_HOLD_BULLISH[-1]],
    )


# --- §7.5.5 Rising / Falling Three Methods -----------------------------------

RISING_MIDDLES: list[Shape] = [
    (132.0, 136.0, 128.0, 130.0),
    (130.0, 134.0, 126.0, 128.0),
    (128.0, 132.0, 124.0, 126.0),
    (126.0, 130.0, 122.0, 124.0),
    (124.0, 128.0, 120.0, 122.0),
]
"""Five small bars, each with a body of 2.00 in a range of 8.00 — short by §2.2's 2.67.

Their highs run from 136.00 down and their lows stay at or above 120.00, so all
five sit inside the first bar's range of 100.00 to 140.00 whichever of them a
form happens to use.
"""

RISING_LAST: Shape = (125.0, 150.0, 120.0, 148.0)
"""White, body 23.00 in a range of 30.00 — long — and closing above the first close."""


def rising_three_methods(small_candles: int) -> list[Shape]:
    """Return the Rising form with `n` small candles between the two long ones."""
    return [
        *background(UPTREND_FILLER),
        LONG_WHITE_FIRST,
        *RISING_MIDDLES[:small_candles],
        RISING_LAST,
    ]


FALLING_THREE_METHODS: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    (110.0, 114.0, 106.0, 108.0),
    (112.0, 116.0, 108.0, 110.0),
    (114.0, 118.0, 110.0, 112.0),
    (115.0, 120.0, 90.0, 92.0),
]
"""The mirror at `n = 3`: three small bars inside 100.00 to 140.00, then a long
black bar closing at 92.00, under the first bar's close of 105.00."""


@pytest.mark.parametrize("small_candles", [2, 3, 4, 5])
def test_all_five_admissible_forms_of_three_methods_hold(small_candles: int) -> None:
    """Check §7.5.5 at every `n` Nison's range allows, from four bars to seven.

    The window grows by one bar per form and the judged bar moves with it, so the
    series is 13 bars long at `n = 2` and 16 at `n = 5`. Nothing else changes:
    the same two long bars open and close every form.
    """
    shapes = rising_three_methods(small_candles)
    assert len(shapes) == TREND_WARM_UP_BARS + small_candles + 2

    values = matched(long_and_gap.RISE_FALL_THREE_METHODS, shapes)
    assert values["pat_rise_fall_three_methods_dir"] == outputs.BULLISH


def test_falling_three_methods_is_the_same_section_turned_over() -> None:
    """Check the bearish side, and that a middle bar leaving the first range fails.

    Rule 4 is what makes the small bars a pause: each stays inside the first
    bar's high-low range of 100.00 to 140.00. A middle bar reaching 141.00 is
    outside it, and the section drops from `n = 3` to nothing rather than falling
    back on a different `n` — the other forms need a long bar where that middle
    one sits.
    """
    values = matched(long_and_gap.RISE_FALL_THREE_METHODS, FALLING_THREE_METHODS)
    assert values["pat_rise_fall_three_methods_dir"] == outputs.BEARISH

    reaches_above_the_first: Shape = (112.0, 141.0, 108.0, 110.0)
    not_matched(
        long_and_gap.RISE_FALL_THREE_METHODS,
        [
            *FALLING_THREE_METHODS[: TREND_WARM_UP_BARS + 2],
            reaches_above_the_first,
            *FALLING_THREE_METHODS[-2:],
        ],
    )


def test_the_forms_of_three_methods_become_judgeable_one_after_another() -> None:
    """Check the index claim §7.5.5 makes about its own warm-up.

    `min_history` is 13, from the shortest form, so index 12 is the first bar
    with a value at all — and at that index only `n = 2` can be asked, because
    §3 judges the trend on the pattern's first day and the first day of an
    `n = 5` form would be index 6, where the ten-period average does not exist
    yet. The first bar able to carry the longest form is index 15.

    The two series below differ by one filler bar and nothing else. With eight
    the `n = 5` shape is judged at index 14 and cannot hold; with nine it is
    judged at index 15 and does. That is the section's own statement, checked
    rather than assumed, and §7.5.5 calls it deliberate: warming up at 16 would
    throw away the `n = 2` forms that do hold from index 12.
    """
    shortest = rising_three_methods(2)
    values = run(long_and_gap.RISE_FALL_THREE_METHODS, shortest)
    assert isnan(values[11]["pat_rise_fall_three_methods"])
    assert values[12]["pat_rise_fall_three_methods"] == outputs.MATCHED

    longest = rising_three_methods(5)
    values = run(long_and_gap.RISE_FALL_THREE_METHODS, longest)
    # Judged from index 12 on, and holding only where the whole form fits.
    assert [values[index]["pat_rise_fall_three_methods"] for index in range(12, 16)] == [
        outputs.NOT_MATCHED,
        outputs.NOT_MATCHED,
        outputs.NOT_MATCHED,
        outputs.MATCHED,
    ]

    one_bar_short = [
        *background(UPTREND_FILLER, count=TREND_WARM_UP_BARS - 1),
        LONG_WHITE_FIRST,
        *RISING_MIDDLES,
        RISING_LAST,
    ]
    assert len(one_bar_short) == 15
    not_matched(long_and_gap.RISE_FALL_THREE_METHODS, one_bar_short)


def test_two_forms_of_three_methods_can_never_hold_on_the_same_bar() -> None:
    """Check that §7.5.5's tie-break is an ordering and never an actual choice.

    The section says the smallest `n` is adopted when several hold, so that one
    bar cannot report the pattern twice. The two scales make that situation
    unreachable: the first bar of the `n` form is the second small bar of the
    `n + 1` form, and §2.1 wants a body past half the range where §2.2 wants one
    under a third of it. No bar is both.

    The arithmetic is checked here on the bars the cases use. The convention
    stays as the standard writes it — an unreachable tie-break is not a defect —
    but nothing below depends on which form the loop would have preferred.
    """
    first_bar = series([LONG_WHITE_FIRST])[0]
    middle_bar = series([RISING_MIDDLES[0]])[0]
    assert scales.long_body(first_bar) and not scales.short_body(first_bar)
    assert scales.short_body(middle_bar) and not scales.long_body(middle_bar)

    for small_candles in (2, 3, 4):
        shapes = rising_three_methods(small_candles)
        judged = run(long_and_gap.RISE_FALL_THREE_METHODS, shapes)
        held = [
            index
            for index, value in enumerate(judged)
            if value["pat_rise_fall_three_methods"] == outputs.MATCHED
        ]
        assert held == [len(shapes) - 1]


# --- §7.5.6 Up/Down-gap Side-by-side White Lines -----------------------------

SIDE_BY_SIDE_SECOND: Shape = (145.0, 152.0, 144.0, 150.0)
"""White, body 5.00 from 145.00 up to 150.00, gapping above the first body's 135.00."""

SIDE_BY_SIDE_WHITE_UP: list[Shape] = [
    *background(UPTREND_FILLER),
    LONG_WHITE_FIRST,
    SIDE_BY_SIDE_SECOND,
    (145.2, 153.0, 144.0, 150.5),
]
"""The third bar opens 0.20 from the second bar's 145.00, inside §2.6's `Equal`
tolerance of 0.27 on its range of 9.00, and its body of 5.30 is within half of
the second bar's 5.00 either way."""

SIDE_BY_SIDE_WHITE_DOWN: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    (95.0, 102.0, 94.0, 100.0),
    (95.2, 103.0, 94.0, 100.5),
]
"""The mirror: the gap runs down from the first body's bottom of 105.00 to a body
top of 100.00, and the two side-by-side bars stay white."""


def test_side_by_side_white_lines_open_level_within_the_doji_tolerance() -> None:
    """Check §7.5.6's five rules, and rule 4 as `Equal` rather than `Near`.

    Nison writes "the same open" and Morris "at about the same price", so
    decision C takes the narrower. On the third bar's range of 9.00 that
    tolerance is 0.27: an open 0.20 from the second bar's is inside it and one
    0.50 away is not, though §2.6's `Near`, at 0.90, would have admitted both.
    """
    values = matched(long_and_gap.GAP_SIDE_BY_SIDE_WHITE, SIDE_BY_SIDE_WHITE_UP)
    assert values["pat_gap_side_by_side_white_dir"] == outputs.BULLISH

    opens_half_a_point_away: Shape = (145.5, 153.0, 144.0, 150.5)
    not_matched(
        long_and_gap.GAP_SIDE_BY_SIDE_WHITE,
        [*SIDE_BY_SIDE_WHITE_UP[:-1], opens_half_a_point_away],
    )

    # Rule 5 bounds the two bodies at a ratio of two: 1.90 against 5.00 needs at
    # least 2.50 to count as similar.
    much_smaller_body: Shape = (145.1, 153.0, 144.0, 147.0)
    not_matched(
        long_and_gap.GAP_SIDE_BY_SIDE_WHITE,
        [*SIDE_BY_SIDE_WHITE_UP[:-1], much_smaller_body],
    )


def test_the_down_gap_form_keeps_both_of_its_bars_white() -> None:
    """Check the asymmetry Nison states and §7.5.6 carries.

    Every other two-sided section here swaps the colours for its bearish form.
    This one turns the gap and the trend over and leaves the bars white, because
    Nison writes that side-by-side white lines in a downtrend are read as bearish
    in spite of their colour.
    """
    second, third = series(SIDE_BY_SIDE_WHITE_DOWN[-2:])
    assert primitives.is_white(second) and primitives.is_white(third)

    values = matched(long_and_gap.GAP_SIDE_BY_SIDE_WHITE, SIDE_BY_SIDE_WHITE_DOWN)
    assert values["pat_gap_side_by_side_white_dir"] == outputs.BEARISH


# --- §7.5.7 Tasuki Gap and §7.5.8 Upside/Downside Gap Three Methods ----------

TASUKI_SECOND: Shape = (145.0, 175.0, 143.0, 170.0)
"""White, body 25.00 from 145.00 to 170.00 — within half of the first body's 30.00
either way — and its bottom clears the first body's top of 135.00."""

TASUKI_GAP_UP: list[Shape] = [
    *background(UPTREND_FILLER),
    LONG_WHITE_FIRST,
    TASUKI_SECOND,
    (165.0, 168.0, 136.0, 138.0),
]
"""The third bar opens at 165.00, inside the second body, and closes at 138.00 —
into the window between 135.00 and 145.00 without crossing it."""

TASUKI_GAP_DOWN: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    (95.0, 97.0, 65.0, 70.0),
    (72.0, 104.0, 70.0, 102.0),
]
"""The mirror: the window runs from 95.00 up to 105.00 and the white third bar
closes at 102.00, inside it."""

GAP_THREE_METHODS_UP: list[Shape] = [
    *background(UPTREND_FILLER),
    LONG_WHITE_FIRST,
    (145.0, 170.0, 143.0, 165.0),
    (160.0, 162.0, 118.0, 120.0),
]
"""Two long white bars with a body gap, then a black bar that bridges them.

The second bar's body of 20.00 in a range of 27.00 is long by §2.1. The third
opens at 160.00 inside that body and closes at 120.00 inside the first body of
105.00 to 135.00, which is what §7.5.8 means by filling the gap.
"""

GAP_THREE_METHODS_DOWN: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    (95.0, 97.0, 70.0, 72.0),
    (78.0, 130.0, 76.0, 128.0),
]


def test_tasuki_gap_reaches_into_the_window_without_closing_it() -> None:
    """Check §7.5.7's five rules, including the two conditions Nison adds.

    Rule 5 is a pair of bounds and both matter. The third close has to come back
    into the window — under the second body's bottom of 145.00 — and stop there,
    above the first body's top of 135.00. A close of 145.00 sits on the body
    rather than inside the window, and a close of 132.00 is under the window,
    which Nison says voids the pattern outright.
    """
    values = matched(long_and_gap.TASUKI_GAP, TASUKI_GAP_UP)
    assert values["pat_tasuki_gap_dir"] == outputs.BULLISH

    closes_on_the_second_body: Shape = (165.0, 168.0, 143.0, 145.0)
    not_matched(long_and_gap.TASUKI_GAP, [*TASUKI_GAP_UP[:-1], closes_on_the_second_body])

    closes_under_the_window: Shape = (165.0, 168.0, 130.0, 132.0)
    not_matched(long_and_gap.TASUKI_GAP, [*TASUKI_GAP_UP[:-1], closes_under_the_window])

    values = matched(long_and_gap.TASUKI_GAP, TASUKI_GAP_DOWN)
    assert values["pat_tasuki_gap_dir"] == outputs.BEARISH


def test_the_two_bars_of_the_tasuki_must_be_of_similar_size() -> None:
    """Check the size condition decision C took from Nison.

    §2.6 bounds the ratio of the two bodies at two, so against the first body of
    30.00 the second has to be at least 15.00. A second body of 10.00 leaves
    every other rule standing and this one broken.
    """
    small_second: Shape = (145.0, 175.0, 143.0, 155.0)
    not_matched(
        long_and_gap.TASUKI_GAP,
        [*TASUKI_GAP_UP[:-2], small_second, (150.0, 152.0, 136.0, 138.0)],
    )


def test_tasuki_gap_and_gap_three_methods_exclude_each_other() -> None:
    """Check the boundary §7.5.8 draws against §7.5.7, in both directions.

    The two open the same way — a body gap between two bars carrying the trend —
    and part company on the third close. §7.5.7 keeps it inside the window, above
    the first body's top of 135.00; §7.5.8 sends it past that, into the first
    body. No close does both, so neither section reaches the other's bars.
    """
    values = matched(long_and_gap.GAP_THREE_METHODS, GAP_THREE_METHODS_UP)
    assert values["pat_gap_three_methods_dir"] == outputs.BULLISH

    not_matched(long_and_gap.TASUKI_GAP, GAP_THREE_METHODS_UP)
    not_matched(long_and_gap.GAP_THREE_METHODS, TASUKI_GAP_UP)

    values = matched(long_and_gap.GAP_THREE_METHODS, GAP_THREE_METHODS_DOWN)
    assert values["pat_gap_three_methods_dir"] == outputs.BEARISH


def test_gap_three_methods_wants_both_of_its_first_bars_long() -> None:
    """Check rule 2, which is one of the two places §7.5.8 differs from §7.5.7.

    A second bar with a body of 10.00 in a range of 27.00 is not long by §2.1's
    half, and the section fails while the gap and the third bar are untouched.
    """
    short_second: Shape = (145.0, 170.0, 143.0, 155.0)
    not_matched(
        long_and_gap.GAP_THREE_METHODS,
        [*GAP_THREE_METHODS_UP[:-2], short_second, (150.0, 152.0, 118.0, 120.0)],
    )


# --- §7.5.9 Hikkake and §7.5.10 Modified Hikkake -----------------------------

HIKKAKE_BULLISH: list[Shape] = [
    (100.0, 120.0, 80.0, 110.0),
    (105.0, 115.0, 90.0, 108.0),
    (100.0, 112.0, 85.0, 88.0),
]
"""A context bar, an inside bar at 115.00/90.00, then a bar breaking below both ends.

The inside bar's high of 115.00 is under the context bar's 120.00 and its low of
90.00 above the context bar's 80.00, which is rule 1. The third bar's high of
112.00 and low of 85.00 are both under the inside bar's, which rule 2 calls the
bullish setup — the break that is about to fail is the downward one.
"""

HIKKAKE_BEARISH: list[Shape] = [
    (100.0, 120.0, 80.0, 110.0),
    (105.0, 115.0, 90.0, 108.0),
    (110.0, 118.0, 92.0, 116.0),
]
"""The same first two bars with a third whose high and low are both above the
inside bar's, which is the bearish setup."""

WIDENING_BARS: list[Shape] = [
    (100.0, 114.0, 70.0, 100.0),
    (100.0, 114.5, 60.0, 100.0),
    (100.0, 114.8, 55.0, 100.0),
]
"""Filler that confirms nothing and forms nothing.

Each high stays under the inside bar's 115.00, so none of them confirms the
bullish setup, and each range covers the one before it, so no bar among them is
an inside bar and no second setup appears to muddy the confirmation key.
"""


def test_hikkake_reads_only_the_highs_and_the_lows() -> None:
    """Check §7.5.9's two rules and the polarity that is easy to invert.

    Chesler's pattern ignores the open-to-close relationship entirely, so nothing
    here asks for a colour or a body. The bullish setup breaks *below* the inside
    bar and the bearish setup above it, because the pattern trades the failure of
    the break rather than the break.
    """
    values = matched(long_and_gap.HIKKAKE, HIKKAKE_BULLISH)
    assert values["pat_hikkake_dir"] == outputs.BULLISH

    values = matched(long_and_gap.HIKKAKE, HIKKAKE_BEARISH)
    assert values["pat_hikkake_dir"] == outputs.BEARISH

    # Rule 1 is two strict inequalities: a high level with the context bar's
    # 120.00 leaves the second bar not inside it.
    level_high: Shape = (105.0, 120.0, 90.0, 108.0)
    not_matched(long_and_gap.HIKKAKE, [HIKKAKE_BULLISH[0], level_high, HIKKAKE_BULLISH[2]])

    # Rule 2 wants both ends to move the same way. A third bar with a lower low
    # and a higher high covers the inside bar instead of breaking one side of it,
    # and answers neither setup.
    engulfs_the_inside_bar: Shape = (100.0, 116.0, 85.0, 88.0)
    not_matched(
        long_and_gap.HIKKAKE,
        [*HIKKAKE_BULLISH[:-1], engulfs_the_inside_bar],
    )


def test_the_hikkake_confirmation_is_the_price_passing_the_inside_bar() -> None:
    """Check §5.5's fourth row: the content of this confirmation comes from the source.

    It is not the general close comparison. The bullish setup is confirmed when
    the price moves above the inside bar's high of 115.00, so a bar reaching
    118.00 confirms it even though its close is lower than the setup bar's, and a
    bar whose whole range sits under 115.00 does not confirm however it closes.
    """
    reaches_past_the_inside_high: Shape = (90.0, 118.0, 88.0, 116.0)
    values = run(long_and_gap.HIKKAKE, [*HIKKAKE_BULLISH, reaches_past_the_inside_high])
    assert values[-2]["pat_hikkake"] == outputs.MATCHED
    assert values[-2]["pat_hikkake_confirm"] == outputs.NOT_MATCHED
    assert values[-1]["pat_hikkake"] == outputs.NOT_MATCHED
    assert values[-1]["pat_hikkake_confirm"] == outputs.MATCHED

    # A close above the setup bar's 88.00 is what §5.5's general rule would have
    # asked for, and it is not what this section asks for.
    closes_higher_without_reaching: Shape = (100.0, 114.0, 70.0, 100.0)
    values = run(long_and_gap.HIKKAKE, [*HIKKAKE_BULLISH, closes_higher_without_reaching])
    assert values[-1]["pat_hikkake_confirm"] == outputs.NOT_MATCHED

    # The bearish setup reads the other end: below the inside bar's low of 90.00.
    drops_under_the_inside_low: Shape = (95.0, 100.0, 88.0, 90.0)
    values = run(long_and_gap.HIKKAKE, [*HIKKAKE_BEARISH, drops_under_the_inside_low])
    assert values[-1]["pat_hikkake_confirm"] == outputs.MATCHED


def test_the_three_bar_deadline_opens_on_each_of_the_three_bars() -> None:
    """Check §5.5's three-bar deadline in the three ways it can end.

    The confirmation lands on the first bar that reaches past 115.00. The three
    cases below put that bar first, third, and nowhere: in the last one a bar
    reaching 130.00 arrives on the fourth bar after the match, one too late, and
    the key stays down for good.
    """
    on_the_first: Shape = (90.0, 118.0, 88.0, 116.0)
    assert confirmations(long_and_gap.HIKKAKE, [*HIKKAKE_BULLISH, on_the_first]) == [0.0, 1.0]

    on_the_third: Shape = (100.0, 118.0, 96.0, 116.0)
    assert confirmations(
        long_and_gap.HIKKAKE,
        [*HIKKAKE_BULLISH, *WIDENING_BARS[:2], on_the_third],
    ) == [0.0, 0.0, 0.0, 1.0]

    too_late: Shape = (100.0, 130.0, 96.0, 128.0)
    assert confirmations(
        long_and_gap.HIKKAKE,
        [*HIKKAKE_BULLISH, *WIDENING_BARS, too_late],
    ) == [0.0, 0.0, 0.0, 0.0, 0.0]


def test_the_confirmation_lands_on_the_first_bar_that_satisfies_it() -> None:
    """Check that a deadline of three bars still raises the key exactly once.

    Both bars below reach past the inside bar's high of 115.00 and both are
    inside the deadline. The first carries the confirmation and the second raises
    nothing, because the match it would confirm has already been confirmed.
    """
    first: Shape = (90.0, 118.0, 88.0, 116.0)
    second: Shape = (95.0, 119.0, 90.0, 117.0)
    assert confirmations(long_and_gap.HIKKAKE, [*HIKKAKE_BULLISH, first, second]) == [
        0.0,
        1.0,
        0.0,
    ]


def test_a_degenerate_bar_inside_the_deadline_leaves_the_rest_of_it_standing() -> None:
    """Check the sentence §5.5 wrote for exactly this group.

    A four-price bar cannot be a confirming bar — §2.7 will not judge on it, so
    §5.5 will not take a confirmation from it — and at a one-bar deadline that
    closes the question. Here the deadline is three, so the bar after it can
    still confirm, and §5.5 says so in as many words.

    The degenerate bar sits at 116.00, above the inside bar's high of 115.00, so
    it would have confirmed had the rule been applied to it.
    """
    degenerate: Shape = (116.0, 116.0, 116.0, 116.0)
    following: Shape = (100.0, 118.0, 96.0, 116.0)
    assert primitives.is_degenerate(series([degenerate])[0])
    assert confirmations(long_and_gap.HIKKAKE, [*HIKKAKE_BULLISH, degenerate, following]) == [
        0.0,
        0.0,
        1.0,
    ]


MODIFIED_HIKKAKE_BULLISH: list[Shape] = [
    (100.0, 140.0, 60.0, 100.0),
    (110.0, 120.0, 80.0, 80.0),
    (100.0, 115.0, 90.0, 108.0),
    (100.0, 112.0, 85.0, 88.0),
]
"""§7.5.9's three bars with a context bar in front of them.

The context bar closes at 80.00, exactly its own low, which rule 2 asks of the
bullish form; its range of 40.00 is under the 80.00 of the bar before it, which
is rule 3. The last three bars are the basic section's own bullish setup.
"""

MODIFIED_HIKKAKE_BEARISH: list[Shape] = [
    (100.0, 140.0, 60.0, 100.0),
    (90.0, 120.0, 80.0, 120.0),
    (100.0, 115.0, 90.0, 108.0),
    (110.0, 118.0, 92.0, 116.0),
]
"""The mirror: the context bar closes at 120.00, exactly its own high."""


def test_modified_hikkake_inherits_the_basic_section_and_adds_two_demands() -> None:
    """Check §7.5.10's three rules, the first of which is §7.5.9 entire.

    Rule 1 reaches the registered basic rule rather than restating it, so the
    inheritance cannot go stale: the same three bars hold there on their own.
    """
    values = matched(long_and_gap.HIKKAKE_MODIFIED, MODIFIED_HIKKAKE_BULLISH)
    assert values["pat_hikkake_modified_dir"] == outputs.BULLISH
    assert matched(long_and_gap.HIKKAKE, MODIFIED_HIKKAKE_BULLISH[1:])

    values = matched(long_and_gap.HIKKAKE_MODIFIED, MODIFIED_HIKKAKE_BEARISH)
    assert values["pat_hikkake_modified_dir"] == outputs.BEARISH


def test_the_context_bar_closes_exactly_on_its_range_end() -> None:
    """Check rule 2, which stays an equality because Chesler writes "must".

    §4.2 would otherwise send "closes at the end of its range" to §2.5's very
    short shadow, and §7.5.10 refuses that: widening a stated equality changes
    the source. A close 1.00 above the low is well inside §2.5's allowance of
    4.00 on a range of 40.00, and the section still does not hold.
    """
    closes_just_off_the_low: Shape = (110.0, 120.0, 80.0, 81.0)
    candle = series([closes_just_off_the_low])[0]
    assert scales.no_lower_shadow(candle)

    not_matched(
        long_and_gap.HIKKAKE_MODIFIED,
        [MODIFIED_HIKKAKE_BULLISH[0], closes_just_off_the_low, *MODIFIED_HIKKAKE_BULLISH[2:]],
    )


def test_the_context_bar_is_narrower_than_the_bar_before_it() -> None:
    """Check rule 3, a strict comparison of two high-low ranges.

    The context bar's range is 40.00, so a preceding bar of exactly 40.00 leaves
    the two equal and the section does not hold.
    """
    same_range: Shape = (100.0, 120.0, 80.0, 100.0)
    not_matched(
        long_and_gap.HIKKAKE_MODIFIED,
        [same_range, *MODIFIED_HIKKAKE_BULLISH[1:]],
    )


def test_the_modified_section_measures_its_confirmation_against_the_same_inside_bar() -> None:
    """Check that the four-bar window does not shift which bar the deadline reads.

    The inside bar is the second-to-last bar of either window, so both sections
    confirm on the price passing 115.00, and both allow three bars for it.
    """
    on_the_third: Shape = (100.0, 118.0, 96.0, 116.0)
    assert confirmations(
        long_and_gap.HIKKAKE_MODIFIED,
        [*MODIFIED_HIKKAKE_BULLISH, *WIDENING_BARS[:2], on_the_third],
    ) == [0.0, 0.0, 0.0, 1.0]


# --- the ten as a registered catalog ------------------------------------------

SECTION_MIN_HISTORY = {
    # Written out from each §7.5 section's own `min_history` line rather than
    # recomputed. Eight sections require §3's trend and land at 12, 13 or 14 by
    # their span; the two Hikkake sections require none, so §6's other formula
    # gives them their span itself.
    "pat_three_line_strike": 13,
    "pat_breakaway": 14,
    "pat_ladder_bottom": 14,
    "pat_mat_hold": 14,
    "pat_rise_fall_three_methods": 13,
    "pat_gap_side_by_side_white": 12,
    "pat_tasuki_gap": 12,
    "pat_gap_three_methods": 12,
    "pat_hikkake": 3,
    "pat_hikkake_modified": 4,
}

SECTION_RULES: dict[str, PatternRule] = {
    rule.name: rule
    for rule in (
        long_and_gap.THREE_LINE_STRIKE,
        long_and_gap.BREAKAWAY,
        long_and_gap.LADDER_BOTTOM,
        long_and_gap.MAT_HOLD,
        long_and_gap.RISE_FALL_THREE_METHODS,
        long_and_gap.GAP_SIDE_BY_SIDE_WHITE,
        long_and_gap.TASUKI_GAP,
        long_and_gap.GAP_THREE_METHODS,
        long_and_gap.HIKKAKE,
        long_and_gap.HIKKAKE_MODIFIED,
    )
}

REGISTERED_SPECS: tuple[PatternSpec, ...] = tuple(
    spec for spec in DEFAULT_PATTERN_REGISTRY.list() if spec.name in SECTION_MIN_HISTORY
)

PATTERNS_REGISTERED_BEFORE = 51
"""§7.1's eleven, §7.2's six, §7.3's sixteen, and §7.4's eighteen."""


def test_the_registry_gained_exactly_the_ten_sections_of_seven_five() -> None:
    """Check the registered catalog against §8.1's last row and its total.

    §8.1 counts one entry per TA-Lib function, so Rising/Falling Three Methods is
    one section and not five: the range of `n` is a range of spans inside one
    pattern, and `CDLRISEFALL3METHODS` is one function.
    """
    assert len(REGISTERED_SPECS) == 10
    assert {spec.name for spec in REGISTERED_SPECS} == set(SECTION_MIN_HISTORY)
    # No pattern takes a parameter, so an identity is its bare name.
    assert {spec.identifier for spec in REGISTERED_SPECS} == set(SECTION_MIN_HISTORY)

    assert len(DEFAULT_PATTERN_REGISTRY.list()) == PATTERNS_REGISTERED_BEFORE + 10
    assert len(DEFAULT_PATTERN_REGISTRY.list()) == 61


def test_each_section_warms_up_where_its_own_line_says() -> None:
    """Check §6's two formulas against the per-section values, not against themselves.

    §8.3's distribution reaches its last three rows here: three sections at 12,
    two at 13, three at 14, and the two trendless ones at 3 and 4. §7.5.5 is at
    13 from its shortest form and not at 16 from its longest, which is the whole
    point of the note that section carries.
    """
    assert {spec.name: spec.min_history for spec in REGISTERED_SPECS} == SECTION_MIN_HISTORY

    counted = sorted(SECTION_MIN_HISTORY.values())
    assert counted.count(12) == 3
    assert counted.count(13) == 2
    assert counted.count(14) == 3
    assert counted.count(3) == 1
    assert counted.count(4) == 1


def test_the_indicator_tally_is_untouched_by_this_change() -> None:
    """Check that registering the last ten patterns moved nothing in the other registry."""
    indicator_names = {spec.name for spec in DEFAULT_REGISTRY.list()}
    assert indicator_names.isdisjoint(DEFAULT_PATTERN_REGISTRY.names())
    assert all(not name.startswith(outputs.NAME_PREFIX) for name in indicator_names)


CONFIRMATION_GRADES = {
    # Read off each section's own `확인` header line. `None` is a grade of `No` on
    # both sides, a direction is a section graded on that side and `No` on the
    # other, and "hikkake" is a section whose source states the content itself.
    "pat_three_line_strike": outputs.BEARISH,  # No bullish, Suggested bearish
    "pat_breakaway": "both",  # Suggested on both sides
    "pat_ladder_bottom": None,  # No
    "pat_mat_hold": outputs.BEARISH,  # No bullish, Suggested bearish
    "pat_rise_fall_three_methods": outputs.BEARISH,  # No rising, Suggested falling
    "pat_gap_side_by_side_white": "both",  # Suggested up-gap, Required down-gap
    "pat_tasuki_gap": "both",  # Suggested upward, Required downward
    "pat_gap_three_methods": outputs.BEARISH,  # No upside, Required downside
    "pat_hikkake": "hikkake",  # Required, content and deadline from Chesler
    "pat_hikkake_modified": "hikkake",
}


def test_confirmation_is_computed_only_where_a_source_graded_it() -> None:
    """Check §5.5's conventions against all ten header lines.

    The wiring splits four ways here where the earlier groups split three: three
    sections on the general rule, four on the bearish side alone, one on nothing,
    and two on the rule their own source states.
    """
    assert set(CONFIRMATION_GRADES) == set(SECTION_RULES)
    for name, grade in CONFIRMATION_GRADES.items():
        rule = SECTION_RULES[name]
        if grade is None:
            assert rule.confirm is None, name
        elif grade == "both":
            assert rule.confirm is confirms_by_close_direction, name
        elif grade == "hikkake":
            assert rule.confirm not in (None, confirms_by_close_direction), name
        else:
            assert rule.confirm is CONFIRMS_BEARISH_SIDE_ONLY, name

    counted = list(CONFIRMATION_GRADES.values())
    assert counted.count("both") == 3
    assert counted.count(outputs.BEARISH) == 4
    assert counted.count(None) == 1
    assert counted.count("hikkake") == 2


def test_only_the_two_hikkake_sections_carry_a_deadline_longer_than_one_bar() -> None:
    """Check §5.5's deadline column, and that the default leaves it where it was.

    Chesler's three bars reach exactly two sections. Every other rule in the
    standard — the fifty-one written before this group and the eight written with
    it — leaves the field at its default of one, which is the value that makes
    `judgment.py` behave as it did before the field existed.
    """
    deadlines = {name: rule.confirm_within_bars for name, rule in SECTION_RULES.items()}
    assert deadlines["pat_hikkake"] == 3
    assert deadlines["pat_hikkake_modified"] == 3
    assert sorted(deadlines.values()) == [1] * 8 + [3, 3]

    assert PatternRule("pat_x", 1, False, lambda window, trend: None).confirm_within_bars == 1


def test_only_three_methods_admits_more_than_one_span() -> None:
    """Check that the variable window reaches exactly one section.

    §7.5.5 is offered four spans through seven; every other rule here reports the
    single span its `bar_count` fixes, which is what the span loop collapses to
    when `longest_bar_count` is left alone.
    """
    spans = {name: rule.spans for name, rule in SECTION_RULES.items()}
    assert spans["pat_rise_fall_three_methods"] == (4, 5, 6, 7)
    for name, admissible in spans.items():
        if name == "pat_rise_fall_three_methods":
            continue
        assert admissible == (SECTION_RULES[name].bar_count,), name

    assert PatternRule("pat_x", 3, False, lambda window, trend: None).spans == (3,)


def test_a_rule_rejects_a_deadline_or_a_longest_span_that_makes_no_sense() -> None:
    """Check the two guards on the fields this group added."""

    def never(window: Sequence[Candle], trend: float) -> Match | None:
        return None

    with pytest.raises(ValueError, match="at least one bar"):
        PatternRule("pat_x", 3, False, never, confirm_within_bars=0)

    with pytest.raises(ValueError, match="shorter than bar_count"):
        PatternRule("pat_x", 4, False, never, longest_bar_count=3)


# --- warm-up, the two paths, and degenerate bars, over every section ----------

MATCHING_CASES: dict[str, list[Shape]] = {
    # One hand-built series per section, each holding on its last bar.
    "pat_three_line_strike": THREE_LINE_STRIKE_BULLISH,
    "pat_breakaway": BREAKAWAY_BULLISH,
    "pat_ladder_bottom": LADDER_BOTTOM,
    "pat_mat_hold": MAT_HOLD_BULLISH,
    "pat_rise_fall_three_methods": FALLING_THREE_METHODS,
    "pat_gap_side_by_side_white": SIDE_BY_SIDE_WHITE_UP,
    "pat_tasuki_gap": TASUKI_GAP_UP,
    "pat_gap_three_methods": GAP_THREE_METHODS_UP,
    "pat_hikkake": HIKKAKE_BULLISH,
    "pat_hikkake_modified": MODIFIED_HIKKAKE_BULLISH,
}

LONG_SERIES: list[Shape] = [
    *[shape for case in MATCHING_CASES.values() for shape in case],
    *THREE_LINE_STRIKE_BEARISH,
    *BREAKAWAY_BEARISH,
    *MAT_HOLD_BEARISH,
    *rising_three_methods(5),
    *SIDE_BY_SIDE_WHITE_DOWN,
    *TASUKI_GAP_DOWN,
    *GAP_THREE_METHODS_DOWN,
    *HIKKAKE_BEARISH,
    *WIDENING_BARS,
    *background(150.0, count=12),
]
"""Every hand-built case laid end to end, plus the bearish sides and a quiet tail.

The trend average runs continuously across the whole thing rather than being
restarted per case, so the blocks do not each reproduce the verdict they produce
in isolation. That is the point: this series exists to drive the two execution
paths over a long, varied input — including the variable window of §7.5.5 and the
three-bar deadline of §7.5.9 — and the per-section claims are made on the cases
themselves.
"""


@pytest.mark.parametrize("name", sorted(MATCHING_CASES), ids=lambda name: name)
def test_every_section_matches_on_its_own_hand_built_case(name: str) -> None:
    """Check that all ten are reachable, one hand-built series each.

    Without this the parity and warm-up sweeps below could pass while comparing
    two series of nothing but non-matches.
    """
    assert set(MATCHING_CASES) == set(SECTION_RULES)
    assert matched(SECTION_RULES[name], MATCHING_CASES[name])


@pytest.mark.parametrize("spec", REGISTERED_SPECS, ids=lambda spec: spec.name)
def test_the_two_execution_paths_agree_bar_for_bar(spec: PatternSpec) -> None:
    """Check the batch oracle against the incremental state over the long series."""
    candles = series(LONG_SERIES)
    batch = spec.compute_vectorized(candles)
    state = spec.make_state()
    assert_same_series(batch, [state.update(candle) for candle in candles])


@pytest.mark.parametrize("spec", REGISTERED_SPECS, ids=lambda spec: spec.name)
def test_nan_stops_exactly_at_the_warm_up_boundary(spec: PatternSpec) -> None:
    """Check §5.3: NaN before `min_history - 1`, a finite number from there on."""
    candles = series(LONG_SERIES)
    values = spec.compute_vectorized(candles)
    boundary = spec.min_history - 1

    for index in range(boundary):
        assert all(isnan(value) for value in values[index].values()), f"index {index}"
    assert all(not isnan(value) for later in values[boundary:] for value in later.values())


def test_the_five_warm_up_lengths_of_this_group_start_on_five_different_bars() -> None:
    """Check §6's split inside this group, on one series, index by index.

    Fourteen bars carry every length at once. The two trendless sections answer
    from indexes 2 and 3, because §6 gives them their span alone. The three-bar
    trend sections answer from index 11, the four-bar ones from 12 — §7.5.5 among
    them, from its shortest form — and the five-bar ones from 13.
    """
    candles = series(LADDER_BOTTOM)
    assert len(candles) == 14

    first_finite = {}
    for name, rule in SECTION_RULES.items():
        values = judge_series(rule, candles)
        first_finite[name] = next(
            index for index, value in enumerate(values) if not isnan(value[name])
        )

    assert first_finite["pat_hikkake"] == 2
    assert first_finite["pat_hikkake_modified"] == 3
    assert first_finite["pat_tasuki_gap"] == 11
    assert first_finite["pat_rise_fall_three_methods"] == 12
    assert first_finite["pat_ladder_bottom"] == 13
    assert first_finite == {name: value - 1 for name, value in SECTION_MIN_HISTORY.items()}


@pytest.mark.parametrize("spec", REGISTERED_SPECS, ids=lambda spec: spec.name)
def test_a_degenerate_bar_is_judged_and_not_matched(spec: PatternSpec) -> None:
    """Check §2.7 and §5.3 together: a four-price bar reports 0.0, never NaN."""
    shapes = list(LONG_SERIES[: spec.min_history + 4])
    shapes[-1] = (500.0, 500.0, 500.0, 500.0)
    candles = series(shapes)
    assert primitives.is_degenerate(candles[-1])

    values = spec.compute_vectorized(candles)[-1]
    assert values == {key: 0.0 for key in outputs.output_keys(spec.name)}


@pytest.mark.parametrize("spec", REGISTERED_SPECS, ids=lambda spec: spec.name)
def test_seeding_a_state_reaches_the_same_place_replaying_does(spec: PatternSpec) -> None:
    """Check that `seed` is a replay and leaves no residue from an earlier one."""
    candles = series(LONG_SERIES)[:60]
    replayed = spec.make_state()
    for candle in candles:
        replayed.update(candle)

    seeded = spec.make_state()
    seeded.seed(candles)
    seeded.seed(candles)

    assert_same_series([replayed.current()], [seeded.current()])


@pytest.mark.parametrize("spec", REGISTERED_SPECS, ids=lambda spec: spec.name)
def test_no_section_reads_a_bar_after_the_one_it_reports_on(spec: PatternSpec) -> None:
    """Check §5.4 structurally: truncating the series leaves earlier values alone.

    Judging a prefix and judging the whole series must agree everywhere the
    prefix reaches. A rule reaching forward — writing a confirmation back onto
    the bar it confirms, or letting a three-bar deadline decide a value early —
    would show up here as two different answers for the same index.
    """
    candles = series(LONG_SERIES)
    whole = spec.compute_vectorized(candles)
    prefix_length = spec.min_history + 20
    prefix = spec.compute_vectorized(candles[:prefix_length])

    assert_same_series(whole[:prefix_length], prefix)
