"""Verify §7.4 of the candlestick pattern standard: the eighteen three-bar sections.

Every expected value here is derived by hand from the standard and the arithmetic
that puts a bar on a threshold is written into the test that uses it, so a rule
and its check cannot drift together. `run` — which nearly every test calls —
judges the batch path and the incremental path and refuses to return until the
two agree bar for bar, so the parity claim is made on each hand-built series
rather than only on a generated one.

Four groups of section are easy to confuse and are separated on purpose. §7.4.1
Morning Star and §7.4.3 Morning Doji Star differ only in whether the middle bar
is a doji, which makes the second section strictly narrower than the first.
§7.4.5 Abandoned Baby puts the star family's arrangement behind two gaps that
include the shadows, and is neither a subset nor a superset of it because it asks
for no long body and no penetration. §7.4.7 Two Crows and §7.4.8 Upside Gap Two
Crows are told apart by where the third bar closes, and exclude each other.
§7.4.10 Three Black Crows and §7.4.11 Identical Three Crows differ in where each
bar opens — strictly inside the previous body against on the previous close.

Confirmation is not uniform across the group and §5.5 is why: it computes one
only where a source graded one, and Morris grades some sections differently on
their two sides. Twelve sections here take the general rule, three compute it on
their bearish side alone, and three compute none at all. The three cases are
checked as a table and then exercised on live bars.

Section numbers in this file are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from math import isnan

import pytest
from core_lib.indicators.registry import DEFAULT_REGISTRY
from core_lib.patterns import outputs, primitives, scales, three_candle, two_candle
from core_lib.patterns.judgment import (
    CONFIRMS_BEARISH_SIDE_ONLY,
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
    four-bar section reads its first day the same way a three-bar one does.
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


# --- the bars most of §7.4 is built on ---------------------------------------
#
# Nine sections open with a long first day, so two shapes do much of the work
# below. Both have a body of 40.00 in a range of 50.00 — past §2.1's half of the
# range — and a high-low midpoint of 120.00, which is what the filler is chosen
# against.

LONG_BLACK_FIRST: Shape = (140.0, 145.0, 95.0, 100.0)
"""Body 40.00 from 140.00 down to 100.00, range 50.00, midpoint 120.00, low 95.00."""

LONG_WHITE_FIRST: Shape = (100.0, 145.0, 95.0, 140.0)
"""The same bar the other way up: body 40.00 from 100.00 to 140.00."""

DOWNTREND_FILLER = 130.0
"""Above the first day's midpoint of 120.00, so §3 answers `DOWNTREND`."""

UPTREND_FILLER = 110.0
"""Below that midpoint, so §3 answers `UPTREND`."""


# --- §7.4.1 Morning Star and §7.4.2 Evening Star -----------------------------

MORNING_STAR_BODY: Shape = (90.0, 92.0, 85.0, 88.0)
"""Body 2.00 in a range of 7.00 — short by §2.2, whose ceiling here is 2.33.

Its body top of 90.00 sits below the first body's bottom of 100.00, which is
§1.3's body gap. Its own body of 2.00 is far past §2.3's doji tolerance of 0.21,
so this bar is the short body of §7.4.1 and not the doji of §7.4.3.
"""

MORNING_STAR_THIRD: Shape = (95.0, 130.0, 94.0, 125.0)
"""White, closing at 125.00 — above the first body's midpoint of 120.00."""

MORNING_STAR: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    MORNING_STAR_BODY,
    MORNING_STAR_THIRD,
]

EVENING_STAR: list[Shape] = [
    *background(UPTREND_FILLER),
    LONG_WHITE_FIRST,
    (150.0, 157.0, 148.0, 152.0),
    (145.0, 146.0, 110.0, 115.0),
]
"""The mirror: the star's body of 2.00 in a range of 9.00 sits above 140.00 and
the third bar closes at 115.00, under the first body's midpoint of 120.00."""


def test_morning_star_gaps_a_small_body_below_and_then_recovers_past_the_midpoint() -> None:
    """Check §7.4.1's five rules, of which rule 5 is the one decision C added.

    Morris's four rules never ask the third day to penetrate the first body and
    Nison's description does, so the penetration is required. Its depth is the
    50 percent §7.4.1 carried over from Piercing, and a close of 125.00 clears
    the first body's midpoint of 120.00.
    """
    values = matched(three_candle.MORNING_STAR, MORNING_STAR)
    assert values["pat_morning_star_dir"] == outputs.BULLISH
    assert values["pat_morning_star_strength"] == outputs.FULL_STRENGTH

    # A close of 120.00 sits exactly on the midpoint, and rule 5 is strict.
    on_the_midpoint: Shape = (95.0, 130.0, 94.0, 120.0)
    not_matched(
        three_candle.MORNING_STAR,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, MORNING_STAR_BODY, on_the_midpoint],
    )

    # A star whose body runs 100.00 to 102.00 overlaps the first body's bottom
    # of 100.00, so §1.3's body gap is gone while the bar stays short.
    no_gap: Shape = (100.0, 104.0, 97.0, 102.0)
    not_matched(
        three_candle.MORNING_STAR,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, no_gap, MORNING_STAR_THIRD],
    )


def test_the_star_is_not_asked_for_a_colour() -> None:
    """Check that rule 3 measures the middle bar and never names its colour.

    Both a white star and a colourless one are admitted. §1.2 gives a bar with
    equal open and close no colour at all, so any rule naming one would reject
    it, and §7.4.1's rule 3 deliberately does not.
    """
    white_star: Shape = (88.0, 92.0, 85.0, 90.0)
    assert matched(
        three_candle.MORNING_STAR,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, white_star, MORNING_STAR_THIRD],
    )

    colourless_star: Shape = (90.0, 92.0, 85.0, 90.0)
    assert matched(
        three_candle.MORNING_STAR,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, colourless_star, MORNING_STAR_THIRD],
    )


def test_evening_star_is_the_same_section_turned_over() -> None:
    """Check §7.4.2, including that the trend decides which side can hold at all."""
    values = matched(three_candle.EVENING_STAR, EVENING_STAR)
    assert values["pat_evening_star_dir"] == outputs.BEARISH

    # The same three bars after a decline are not the bullish side of anything:
    # §7.4.1 wants its first day black and its third day white.
    after_a_decline = [*background(150.0), *EVENING_STAR[TREND_WARM_UP_BARS:]]
    not_matched(three_candle.EVENING_STAR, after_a_decline)
    not_matched(three_candle.MORNING_STAR, after_a_decline)


# --- §7.4.3 Morning Doji Star and §7.4.4 Evening Doji Star -------------------

MORNING_DOJI: Shape = (90.0, 96.0, 84.0, 90.0)
"""No body at all in a range of 12.00: a doji by §2.3 and still gapped below 100.00."""

MORNING_DOJI_STAR: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    MORNING_DOJI,
    MORNING_STAR_THIRD,
]

EVENING_DOJI_STAR: list[Shape] = [
    *background(UPTREND_FILLER),
    LONG_WHITE_FIRST,
    (150.0, 156.0, 144.0, 150.0),
    (145.0, 146.0, 110.0, 115.0),
]


def test_the_doji_star_sections_differ_from_the_plain_ones_in_one_rule() -> None:
    """Check §7.4.3 against §7.4.1, which it nests inside rather than sits beside.

    §2.3's doji body is at most 3 percent of the range and §2.2's short body is
    anything under a third of it, so every doji is also a short body and every
    bar reaching §7.4.3 also reaches §7.4.1. The reverse fails: the star of
    §7.4.1's own case has a body of 2.00 in a range of 7.00, where §2.3 would
    allow at most 0.21.
    """
    values = matched(three_candle.MORNING_DOJI_STAR, MORNING_DOJI_STAR)
    assert values["pat_morning_doji_star_dir"] == outputs.BULLISH
    assert matched(three_candle.MORNING_STAR, MORNING_DOJI_STAR)

    not_matched(three_candle.MORNING_DOJI_STAR, MORNING_STAR)

    values = matched(three_candle.EVENING_DOJI_STAR, EVENING_DOJI_STAR)
    assert values["pat_evening_doji_star_dir"] == outputs.BEARISH
    assert matched(three_candle.EVENING_STAR, EVENING_DOJI_STAR)


def test_the_doji_stars_shadows_are_not_bounded() -> None:
    """Check that §7.3.4's removed rule 5 did not return through §7.4.3's reference.

    §7.4.3 rule 3 points at that rule, and §7.3.4 has since been corrected to
    four rules because the condition admits no bar at all: §2.4 measures a shadow
    against the body, and a doji body of at most 3 percent of the range leaves
    the two shadows sharing at least 97 percent of it, so every doji has shadows
    of at least two bodies.

    The star below makes that concrete — body 0.00, upper shadow 6.00, lower
    shadow 6.00 — so §2.4 answers true for both through §1.4's zero-body rule and
    a negated §2.4 would reject it. The section still holds.
    """
    star = series([MORNING_DOJI])[0]
    assert scales.doji(star)
    assert primitives.body(star) == 0.0
    assert scales.long_upper_shadow(star) and scales.long_lower_shadow(star)

    assert matched(three_candle.MORNING_DOJI_STAR, MORNING_DOJI_STAR)


# --- §7.4.5 Abandoned Baby ---------------------------------------------------

ABANDONED_DOJI: Shape = (90.0, 92.0, 84.0, 90.0)
"""A doji whose high of 92.00 is below the first bar's low of 95.00: §1.3's range gap."""

ABANDONED_THIRD: Shape = (95.0, 130.0, 93.0, 125.0)
"""White, and its low of 93.00 is above the doji's high of 92.00, so the tails clear."""

ABANDONED_BABY: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    ABANDONED_DOJI,
    ABANDONED_THIRD,
]

ABANDONED_BABY_BEARISH: list[Shape] = [
    *background(UPTREND_FILLER),
    LONG_WHITE_FIRST,
    (150.0, 156.0, 148.0, 150.0),
    (145.0, 147.0, 110.0, 115.0),
]
"""The mirror: the doji's low of 148.00 clears the first high of 145.00, and the
third bar's high of 147.00 stays under that doji's low."""


def test_abandoned_baby_gaps_across_the_whole_range_on_both_sides() -> None:
    """Check §7.4.5's rules 3 and 5, the one place in the standard reading a range gap.

    Both sources put the shadows inside the gap, so the doji's high of 92.00 has
    to clear the first bar's low of 95.00 and the third bar's low of 93.00 has to
    clear that doji's high. Moving the third bar's low to 91.00 overlaps the doji
    by a shadow and nothing else, and the section fails.
    """
    values = matched(three_candle.ABANDONED_BABY, ABANDONED_BABY)
    assert values["pat_abandoned_baby_dir"] == outputs.BULLISH

    shadows_overlap: Shape = (95.0, 130.0, 91.0, 125.0)
    not_matched(
        three_candle.ABANDONED_BABY,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, ABANDONED_DOJI, shadows_overlap],
    )

    values = matched(three_candle.ABANDONED_BABY, ABANDONED_BABY_BEARISH)
    assert values["pat_abandoned_baby_dir"] == outputs.BEARISH


def test_abandoned_baby_is_neither_a_subset_nor_a_superset_of_the_star_sections() -> None:
    """Check the relation §7.4.5 has with §7.4.1 and §7.4.3, in both directions.

    A range gap implies a body gap — a high below the previous low puts the whole
    body there too — so an abandoned baby always satisfies the star's rule 3. It
    still need not be a morning star, because §7.4.5 asks the first day for no
    length and the third day for no penetration. The first case below has a first
    body of 12.00 in a range of 50.00, which §2.1 will not call long.

    The other direction fails on the doji: §7.4.1's own star has a body of 2.00
    where §2.3 allows 0.21, so a morning star is not automatically an abandoned
    baby even when its bars happen to clear each other.
    """
    short_black_first: Shape = (112.0, 145.0, 95.0, 100.0)
    with_a_short_first_day = [
        *background(DOWNTREND_FILLER),
        short_black_first,
        ABANDONED_DOJI,
        ABANDONED_THIRD,
    ]
    assert matched(three_candle.ABANDONED_BABY, with_a_short_first_day)
    not_matched(three_candle.MORNING_STAR, with_a_short_first_day)

    not_matched(three_candle.ABANDONED_BABY, MORNING_STAR)

    # And where the first day is long and the third does penetrate, all three
    # sections hold on the same bars. Nothing is worked around: each is written
    # as its own section says, and the overlap follows.
    assert matched(three_candle.ABANDONED_BABY, ABANDONED_BABY)
    assert matched(three_candle.MORNING_STAR, ABANDONED_BABY)
    assert matched(three_candle.MORNING_DOJI_STAR, ABANDONED_BABY)


# --- §7.4.6 Tri Star ---------------------------------------------------------

TRI_STAR: list[Shape] = [
    *background(DOWNTREND_FILLER),
    (120.0, 124.0, 116.0, 120.0),
    (110.0, 114.0, 106.0, 110.0),
    (118.0, 122.0, 114.0, 118.0),
]
"""Three bodyless dojis whose middle body of 110.00 sits below both neighbours.

The first bar's midpoint is 120.00 against filler at 130.00, so the trend is
down. Every bar has a range of 8.00 and no body at all, which §2.3 admits.
"""


def test_tri_star_puts_three_dojis_in_the_arrangement_of_a_star() -> None:
    """Check §7.4.6's two rules and the gap kind §2.8 assigns it.

    No source says which gap this is, so §2.8 makes it the body gap — and §7.4.6
    warns that the choice matters more here than anywhere else, because three
    dojis have almost no bodies to gap between. The middle body at 110.00 clears
    both neighbours at 120.00 and 118.00 by that measure while the three ranges
    overlap heavily, so a range reading would reject the same bars.
    """
    values = matched(three_candle.TRI_STAR, TRI_STAR)
    assert values["pat_tri_star_dir"] == outputs.BULLISH

    middle, last = series(TRI_STAR[-2:])
    assert primitives.gap_up_body(middle, last)
    assert not primitives.gap_up_range(middle, last)

    # A middle doji at 119.00 no longer clears the first body at 120.00.
    no_gap: Shape = (119.0, 123.0, 115.0, 119.0)
    not_matched(
        three_candle.TRI_STAR,
        [*background(DOWNTREND_FILLER), TRI_STAR[-3], no_gap, TRI_STAR[-1]],
    )

    # A middle bar with a body of 1.00 in a range of 8.00 is past §2.3's
    # tolerance of 0.24 and stops being a doji, which is all rule 2 asks.
    not_a_doji: Shape = (110.0, 114.0, 106.0, 111.0)
    not_matched(
        three_candle.TRI_STAR,
        [*background(DOWNTREND_FILLER), TRI_STAR[-3], not_a_doji, TRI_STAR[-1]],
    )


# --- §7.4.7 Two Crows and §7.4.8 Upside Gap Two Crows ------------------------

TWO_CROWS_SECOND: Shape = (160.0, 162.0, 144.0, 145.0)
"""Black, its body from 145.00 to 160.00 wholly above the first body's top of 140.00."""

TWO_CROWS: list[Shape] = [
    *background(UPTREND_FILLER),
    LONG_WHITE_FIRST,
    TWO_CROWS_SECOND,
    (155.0, 156.0, 118.0, 120.0),
]
"""The third bar opens at 155.00 inside the second body and closes at 120.00
inside the first body of 100.00 to 140.00, which is what closes the gap."""

UPSIDE_GAP_TWO_CROWS: list[Shape] = [
    *background(UPTREND_FILLER),
    LONG_WHITE_FIRST,
    TWO_CROWS_SECOND,
    (165.0, 166.0, 141.0, 142.0),
]
"""The same first two bars with a third that opens above the second open of
160.00, closes under the second close of 145.00, and stays above the first close
of 140.00 — so the gap is left open."""


def test_two_crows_closes_the_gap_and_upside_gap_two_crows_leaves_it_open() -> None:
    """Check §7.4.7 and §7.4.8 against each other, which is what rule 5 is for.

    Both open with a long white bar and a black bar gapping above its body.
    §7.4.7 then asks the third close back inside the first body — strictly
    between 100.00 and 140.00 — and §7.4.8 asks it to stay above the first close
    of 140.00. The two cannot both hold, because a close above 140.00 is not
    below the first body's top of 140.00.
    """
    values = matched(three_candle.TWO_CROWS, TWO_CROWS)
    assert values["pat_two_crows_dir"] == outputs.BEARISH
    not_matched(three_candle.UPSIDE_GAP_TWO_CROWS, TWO_CROWS)

    values = matched(three_candle.UPSIDE_GAP_TWO_CROWS, UPSIDE_GAP_TWO_CROWS)
    assert values["pat_upside_gap_two_crows_dir"] == outputs.BEARISH
    not_matched(three_candle.TWO_CROWS, UPSIDE_GAP_TWO_CROWS)


def test_two_crows_asks_the_third_bar_to_open_inside_the_second_body() -> None:
    """Check §7.4.7's rule 4, whose "inside" §4.2 makes two strict comparisons.

    An open of exactly 160.00 sits on the second body's top rather than inside
    it, so the section does not hold; 155.00 does. The rest of the bar is
    unchanged between the two.
    """
    opens_on_the_body_top: Shape = (160.0, 161.0, 118.0, 120.0)
    not_matched(
        three_candle.TWO_CROWS,
        [*background(UPTREND_FILLER), LONG_WHITE_FIRST, TWO_CROWS_SECOND, opens_on_the_body_top],
    )


def test_upside_gap_two_crows_wants_the_third_body_around_the_second() -> None:
    """Check §7.4.8's rule 4, which Nison states in prices rather than through §4.1.

    He writes the third bar as opening above the second open and closing under
    the second close, so both comparisons are strict and §4.1's boundary case —
    one body end coinciding — is not admitted. A third bar opening at exactly
    160.00 therefore fails.
    """
    opens_level_with_the_second: Shape = (160.0, 166.0, 141.0, 142.0)
    not_matched(
        three_candle.UPSIDE_GAP_TWO_CROWS,
        [
            *background(UPTREND_FILLER),
            LONG_WHITE_FIRST,
            TWO_CROWS_SECOND,
            opens_level_with_the_second,
        ],
    )


# --- §7.4.9 Three White Soldiers and §7.4.10 Three Black Crows ---------------

THREE_WHITE_SOLDIERS: list[Shape] = [
    *background(DOWNTREND_FILLER),
    (100.0, 121.0, 99.0, 120.0),
    (110.0, 131.0, 109.0, 130.0),
    (120.0, 141.0, 119.0, 140.0),
]
"""Three white bars of body 20.00 in a range of 22.00 — long by §2.1's half.

Each upper shadow is 1.00 against §2.5's allowance of 2.20, so each closes at or
near its high. Each open sits strictly inside the previous body, and the first
bar's midpoint of 110.00 is below the filler at 130.00.
"""

THREE_BLACK_CROWS: list[Shape] = [
    *background(UPTREND_FILLER),
    (140.0, 141.0, 119.0, 120.0),
    (130.0, 131.0, 109.0, 110.0),
    (120.0, 121.0, 99.0, 100.0),
]
"""The mirror, with lower shadows of 1.00 and a first midpoint of 130.00."""


def test_three_white_soldiers_step_up_through_each_others_bodies() -> None:
    """Check §7.4.9's five rules, and rule 5 as §2.5 renders "at or near the high"."""
    values = matched(three_candle.THREE_WHITE_SOLDIERS, THREE_WHITE_SOLDIERS)
    assert values["pat_three_white_soldiers_dir"] == outputs.BULLISH

    # An upper shadow of 3.00 in a range of 24.00 is past §2.5's 2.40, and the
    # body of 20.00 is still long, so rule 5 alone rejects the bar.
    tall_upper_shadow: Shape = (120.0, 143.0, 119.0, 140.0)
    not_matched(
        three_candle.THREE_WHITE_SOLDIERS,
        [*background(DOWNTREND_FILLER), *THREE_WHITE_SOLDIERS[-3:-1], tall_upper_shadow],
    )

    # An open of 135.00 is above the previous body's top of 130.00, so rule 4
    # fails while the three closes still rise.
    opens_above_the_previous_body: Shape = (135.0, 141.0, 134.0, 140.0)
    not_matched(
        three_candle.THREE_WHITE_SOLDIERS,
        [
            *background(DOWNTREND_FILLER),
            *THREE_WHITE_SOLDIERS[-3:-1],
            opens_above_the_previous_body,
        ],
    )


def test_three_black_crows_carries_the_rule_the_soldiers_do_not_have() -> None:
    """Check §7.4.10, whose rule 3 asks each close to be a new low.

    §7.4.10 records that the two sections are not mirror images: Morris gives the
    crows this rule and the soldiers only an advance. Here the difference is not
    observable in a single series, so what this checks is the bearish side's own
    five rules and its direction.
    """
    values = matched(three_candle.THREE_BLACK_CROWS, THREE_BLACK_CROWS)
    assert values["pat_three_black_crows_dir"] == outputs.BEARISH

    # A third close of 115.00 is above the second close of 110.00, so the
    # staircase stops descending even though every other rule still holds.
    closes_higher: Shape = (120.0, 121.0, 114.0, 115.0)
    not_matched(
        three_candle.THREE_BLACK_CROWS,
        [*background(UPTREND_FILLER), *THREE_BLACK_CROWS[-3:-1], closes_higher],
    )


# --- §7.4.11 Identical Three Crows -------------------------------------------

IDENTICAL_THREE_CROWS: list[Shape] = [
    *background(UPTREND_FILLER),
    (140.0, 141.0, 119.0, 120.0),
    (120.0, 121.0, 99.0, 100.0),
    (100.0, 101.0, 79.0, 80.0),
]
"""Each bar opens at exactly the previous close: 120.00, then 100.00.

Bodies are 20.00 in ranges of 22.00, so all three are long, and the first bar's
midpoint of 130.00 sits above the filler at 110.00.
"""


def test_identical_three_crows_open_on_the_previous_close_and_the_others_open_inside() -> None:
    """Check §7.4.11 against §7.4.10, which is the pair the two sections divide.

    §7.4.10's rule 4 asks each open to sit strictly inside the previous body and
    this section asks it to sit on the previous close, within §2.6's tolerance.
    An open exactly on the close is not strictly inside, so the crows of §7.4.10
    do not reach these bars; and §7.4.11's `Equal` tolerance of 0.66 on a range
    of 22.00 is far short of the 10.00 that separates §7.4.10's opens from its
    closes, so the reverse fails too.
    """
    values = matched(three_candle.IDENTICAL_THREE_CROWS, IDENTICAL_THREE_CROWS)
    assert values["pat_identical_three_crows_dir"] == outputs.BEARISH

    not_matched(three_candle.THREE_BLACK_CROWS, IDENTICAL_THREE_CROWS)
    not_matched(three_candle.IDENTICAL_THREE_CROWS, THREE_BLACK_CROWS)


def test_identical_three_crows_uses_the_doji_tolerance_and_not_the_wider_near() -> None:
    """Check that decision C put `Equal` here rather than Morris's "at or near".

    His rule states equality and his commentary allows proximity, so §2.6's
    `Equal` applies: on a range of 22.00 the tolerance is 0.66. An open of
    120.50 is inside it and an open of 122.00 is not — though §2.6's `Near`, at
    2.20, would have admitted both.
    """
    inside_the_tolerance: Shape = (120.5, 121.5, 99.0, 100.0)
    assert matched(
        three_candle.IDENTICAL_THREE_CROWS,
        [
            *background(UPTREND_FILLER),
            IDENTICAL_THREE_CROWS[-3],
            inside_the_tolerance,
            IDENTICAL_THREE_CROWS[-1],
        ],
    )

    outside_the_tolerance: Shape = (122.0, 123.0, 99.0, 100.0)
    not_matched(
        three_candle.IDENTICAL_THREE_CROWS,
        [
            *background(UPTREND_FILLER),
            IDENTICAL_THREE_CROWS[-3],
            outside_the_tolerance,
            IDENTICAL_THREE_CROWS[-1],
        ],
    )


# --- §7.4.12 Advance Block ---------------------------------------------------

ADVANCE_BLOCK: list[Shape] = [
    *background(UPTREND_FILLER),
    (100.0, 130.0, 99.0, 120.0),
    (110.0, 160.0, 109.0, 125.0),
    (120.0, 155.0, 119.0, 130.0),
]
"""Three rising white bars whose last two carry upper shadows of two bodies.

The second bar's body is 15.00 and its upper shadow 35.00, past §2.4's 30.00; the
third's body is 10.00 and its shadow 25.00, past 20.00. The first bar's midpoint
of 114.50 sits above the filler at 110.00.
"""


def test_advance_block_is_the_soldiers_advance_stalling_under_long_tails() -> None:
    """Check §7.4.12, whose rule 2 deliberately measures no body at all.

    That absence is what separates the section from §7.4.9: the same staircase of
    three rising white bars is bullish when the bodies are long and bearish when
    the last two stall under long upper shadows. The second bar here has a body
    of 15.00 in a range of 51.00, which §2.1 will not call long, so the soldiers
    cannot reach these bars.
    """
    values = matched(three_candle.ADVANCE_BLOCK, ADVANCE_BLOCK)
    assert values["pat_advance_block_dir"] == outputs.BEARISH

    not_matched(three_candle.THREE_WHITE_SOLDIERS, ADVANCE_BLOCK)
    not_matched(three_candle.ADVANCE_BLOCK, THREE_WHITE_SOLDIERS)

    # An upper shadow of 19.00 on a body of 10.00 falls short of §2.4's 20.00,
    # and rule 4 wants both of the last two bars to carry one.
    short_upper_shadow: Shape = (120.0, 149.0, 119.0, 130.0)
    not_matched(
        three_candle.ADVANCE_BLOCK,
        [*background(UPTREND_FILLER), *ADVANCE_BLOCK[-3:-1], short_upper_shadow],
    )


# --- §7.4.13 Stalled Pattern -------------------------------------------------

STALLED_PATTERN: list[Shape] = [
    *background(UPTREND_FILLER),
    (100.0, 125.0, 99.0, 120.0),
    (110.0, 135.0, 109.0, 130.0),
    (129.0, 140.0, 128.0, 131.0),
]
"""Two long white bars, the second making a new high, then a small white one.

Bodies of 20.00 in ranges of 26.00 clear §2.1's half; the second bar's high of
135.00 is above the first's 125.00. The third bar's body of 2.00 in a range of
12.00 is short by §2.2, and its open of 129.00 is 1.00 from the second close of
130.00, inside §2.6's `Near` of 1.20. The first midpoint of 112.00 sits above the
filler at 110.00.
"""


def test_stalled_pattern_puts_a_small_bar_alongside_the_second_close() -> None:
    """Check §7.4.13's bearish side, including the two conditions decision C took.

    Nison adds the third bar's colour and the second bar's new high to Morris's
    rules, and both are required here. Rule 4 is §2.6's `Near` rather than
    `Equal`, so the tolerance on a range of 12.00 is 1.20 and not 0.36.
    """
    values = matched(three_candle.STALLED_PATTERN, STALLED_PATTERN)
    assert values["pat_stalled_pattern_dir"] == outputs.BEARISH

    # An open of 128.00 is 2.00 from the second close, past that 1.20.
    opens_too_far_away: Shape = (128.0, 140.0, 127.0, 131.0)
    not_matched(
        three_candle.STALLED_PATTERN,
        [*background(UPTREND_FILLER), *STALLED_PATTERN[-3:-1], opens_too_far_away],
    )

    # A black third bar fails Nison's colour condition on this side.
    black_third: Shape = (131.0, 140.0, 128.0, 129.0)
    not_matched(
        three_candle.STALLED_PATTERN,
        [*background(UPTREND_FILLER), *STALLED_PATTERN[-3:-1], black_third],
    )

    # A second bar whose high of 124.00 fails to clear the first bar's 125.00
    # leaves the pattern without its new extreme.
    no_new_high: Shape = (110.0, 124.0, 109.0, 123.0)
    not_matched(
        three_candle.STALLED_PATTERN,
        [*background(UPTREND_FILLER), STALLED_PATTERN[-3], no_new_high, STALLED_PATTERN[-1]],
    )


def test_the_bullish_stalled_pattern_drops_the_third_bars_colour_and_keeps_the_rest() -> None:
    """Check the one asymmetry §7.4.13 states, and that it is only that one.

    Nison writes no bullish form, so his colour condition is not mirrored and a
    black third bar is admitted there. His new-low condition is mirrored, because
    the section names the colour alone as the thing it does not carry across.

    The bars below invert the bearish case: two long black bodies of 20.00 in
    ranges of 26.00 with the second reaching a new low of 105.00, and a third bar
    whose body of 2.00 in a range of 12.00 opens 1.00 above the second close.
    """
    two_long_black: list[Shape] = [(140.0, 141.0, 115.0, 120.0), (130.0, 131.0, 105.0, 110.0)]
    black_third: Shape = (111.0, 112.0, 100.0, 109.0)
    white_third: Shape = (111.0, 112.0, 100.0, 110.5)

    for third in (black_third, white_third):
        values = matched(
            three_candle.STALLED_PATTERN,
            [*background(DOWNTREND_FILLER), *two_long_black, third],
        )
        assert values["pat_stalled_pattern_dir"] == outputs.BULLISH

    # The mirrored new-low condition is still required: a second bar bottoming at
    # 116.00 does not undercut the first bar's low of 115.00.
    no_new_low: list[Shape] = [(140.0, 141.0, 115.0, 120.0), (130.0, 131.0, 116.0, 118.0)]
    not_matched(
        three_candle.STALLED_PATTERN,
        [*background(DOWNTREND_FILLER), *no_new_low, (119.0, 120.0, 108.0, 118.5)],
    )


# --- §7.4.14 Three Stars in the South ----------------------------------------

THREE_STARS_IN_THE_SOUTH: list[Shape] = [
    *background(DOWNTREND_FILLER),
    (120.0, 122.0, 80.0, 110.0),
    (115.0, 116.0, 90.0, 110.0),
    (110.0, 110.4, 105.6, 106.0),
]
"""Two black bars with long lower shadows, then a small black bar with none.

The first bar's body is 10.00 and its lower shadow 30.00, past §2.4's 20.00; the
second's body is 5.00 and its shadow 20.00, past 10.00, and its low of 90.00 sits
above the first's 80.00. The third bar's shadows are 0.40 each in a range of
4.80, inside §2.5's 0.48, and it opens and closes within the second bar's range.
The first midpoint of 101.00 is below the filler at 130.00.
"""


def test_three_stars_in_the_south_shrinks_the_decline_bar_by_bar() -> None:
    """Check §7.4.14 after the two size scales that admitted no bar were moved.

    Rule 2 asked the first day for a long body *and* a long lower shadow. §2.1
    puts the body past half the range and §2.4 puts the shadow at two bodies, so
    the shadow alone would have to exceed the range — no bar satisfies both.
    Rule 4 asked the third day for a short body with neither shadow, and a body
    under a third of the range with two shadows of at most a tenth each cannot
    add back up to that range.

    The section resolves the two differently. Rule 2 drops `LongBody` outright,
    since keeping "long" would need a range-denominated shadow scale §2 does not
    have. Rule 4 keeps its "small" by moving it onto the body comparison rule 3
    already uses, so the third body must be under the second's.

    The arithmetic above is checked here rather than asserted: the first bar has
    a body of 10.00 in a range of 42.00, so it is *not* long, and it still
    carries the long lower shadow rule 2 wants. The third bar's body of 4.00 is
    not short against its own range of 4.80 either, and qualifies only because it
    is under the second bar's 5.00.
    """
    first, second, third = series(THREE_STARS_IN_THE_SOUTH[-3:])
    assert not scales.long_body(first)
    assert scales.long_lower_shadow(first)
    assert not scales.short_body(third)
    assert primitives.body(third) < primitives.body(second)
    assert scales.no_upper_shadow(third) and scales.no_lower_shadow(third)

    values = matched(three_candle.THREE_STARS_IN_THE_SOUTH, THREE_STARS_IN_THE_SOUTH)
    assert values["pat_three_stars_in_the_south_dir"] == outputs.BULLISH

    # Rule 3's shrinking body: a second body of 12.00 is larger than the first's
    # 10.00, and the section wants it smaller.
    larger_second: Shape = (122.0, 123.0, 90.0, 110.0)
    not_matched(
        three_candle.THREE_STARS_IN_THE_SOUTH,
        [
            *background(DOWNTREND_FILLER),
            THREE_STARS_IN_THE_SOUTH[-3],
            larger_second,
            THREE_STARS_IN_THE_SOUTH[-1],
        ],
    )

    # Rule 4's shrinking body, the condition that replaced `ShortBody`. This bar
    # is black, keeps both shadows at 0.50 inside §2.5's 0.70, and sits within
    # the second bar's range — but its body of 6.00 is above the second's 5.00.
    third_body_not_smaller: Shape = (111.0, 111.5, 104.5, 105.0)
    not_matched(
        three_candle.THREE_STARS_IN_THE_SOUTH,
        [*background(DOWNTREND_FILLER), *THREE_STARS_IN_THE_SOUTH[-3:-1], third_body_not_smaller],
    )

    # Rule 5 keeps the third bar inside the second bar's high-low range, which
    # §7.4.14 chose over the body reading. A high of 117.00 clears the second
    # bar's 116.00.
    reaches_above_the_second: Shape = (116.5, 117.0, 112.0, 112.5)
    not_matched(
        three_candle.THREE_STARS_IN_THE_SOUTH,
        [*background(DOWNTREND_FILLER), *THREE_STARS_IN_THE_SOUTH[-3:-1], reaches_above_the_second],
    )


# --- §7.4.15 Three Inside and §7.4.16 Three Outside --------------------------

HARAMI_SECOND: Shape = (110.0, 136.0, 104.0, 120.0)
"""White, body 10.00 in a range of 32.00 — short by §2.2's 10.67 — inside 100.00 to 140.00."""

THREE_INSIDE_UP: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    HARAMI_SECOND,
    (120.0, 135.0, 119.0, 130.0),
]
"""A bullish harami whose third bar closes at 130.00, above the second's 120.00."""

THREE_INSIDE_DOWN: list[Shape] = [
    *background(UPTREND_FILLER),
    LONG_WHITE_FIRST,
    (120.0, 136.0, 104.0, 110.0),
    (110.0, 111.0, 95.0, 100.0),
]

ENGULFING_SECOND: Shape = (98.0, 145.0, 96.0, 142.0)
"""White, its body from 98.00 to 142.00 around the first body's 100.00 to 140.00."""

THREE_OUTSIDE_UP: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    ENGULFING_SECOND,
    (142.0, 155.0, 141.0, 150.0),
]

THREE_OUTSIDE_DOWN: list[Shape] = [
    *background(UPTREND_FILLER),
    LONG_WHITE_FIRST,
    (142.0, 145.0, 96.0, 98.0),
    (98.0, 99.0, 85.0, 90.0),
]


def test_three_inside_inherits_the_harami_whole_and_adds_a_third_close() -> None:
    """Check §7.4.15's rule 1, which reaches §7.3.2 rather than restating it.

    The first two bars of the case are the harami's own, and the section holds on
    them; the third bar then closes at 130.00, above the second bar's 120.00.
    Moving that close to 120.00 leaves the harami standing and this section not,
    because rule 2 is strict.
    """
    values = matched(three_candle.THREE_INSIDE, THREE_INSIDE_UP)
    assert values["pat_three_inside_dir"] == outputs.BULLISH
    assert values["pat_three_inside_strength"] == outputs.FULL_STRENGTH

    assert matched(two_candle.HARAMI, THREE_INSIDE_UP[:-1])

    level_close: Shape = (118.0, 135.0, 117.0, 120.0)
    shapes = [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, HARAMI_SECOND, level_close]
    not_matched(three_candle.THREE_INSIDE, shapes)
    assert matched(two_candle.HARAMI, shapes[:-1])

    values = matched(three_candle.THREE_INSIDE, THREE_INSIDE_DOWN)
    assert values["pat_three_inside_dir"] == outputs.BEARISH


def test_three_outside_inherits_the_engulfing_whole() -> None:
    """Check §7.4.16's rule 1, and Morris's note that it may not be looser than §7.3.1."""
    values = matched(three_candle.THREE_OUTSIDE, THREE_OUTSIDE_UP)
    assert values["pat_three_outside_dir"] == outputs.BULLISH
    assert matched(two_candle.ENGULFING, THREE_OUTSIDE_UP[:-1])

    values = matched(three_candle.THREE_OUTSIDE, THREE_OUTSIDE_DOWN)
    assert values["pat_three_outside_dir"] == outputs.BEARISH

    # A harami is not an engulfing — §4.1's relation with the bars exchanged —
    # so neither section reaches the other's bars.
    not_matched(three_candle.THREE_OUTSIDE, THREE_INSIDE_UP)
    not_matched(three_candle.THREE_INSIDE, THREE_OUTSIDE_UP)


def test_half_strength_reaches_this_group_only_through_the_two_inherited_sections() -> None:
    """Check §5.6 where §7.4.15 and §7.4.16 say it applies, and where §7.4.17 says it does not.

    A containment or engulfment with exactly one body end coinciding is the one
    boundary the sources distinguish, and these two sections carry the inherited
    match's verdict. The second bar below opens at exactly the first body's
    bottom of 100.00.

    §7.4.17 also uses §4.1's containment and its own output line states a
    strength of 1.0 outright, so the boundary is not split out there. That is
    followed as written, and pinned here so the divergence is visible rather than
    accidental.
    """
    boundary_harami: Shape = (100.0, 136.0, 99.0, 108.0)
    values = matched(
        three_candle.THREE_INSIDE,
        [
            *background(DOWNTREND_FILLER),
            LONG_BLACK_FIRST,
            boundary_harami,
            (108.0, 120.0, 107.0, 115.0),
        ],
    )
    assert values["pat_three_inside_strength"] == outputs.BOUNDARY_STRENGTH

    boundary_engulfing: Shape = (100.0, 145.0, 99.0, 142.0)
    values = matched(
        three_candle.THREE_OUTSIDE,
        [
            *background(DOWNTREND_FILLER),
            LONG_BLACK_FIRST,
            boundary_engulfing,
            (142.0, 155.0, 141.0, 150.0),
        ],
    )
    assert values["pat_three_outside_strength"] == outputs.BOUNDARY_STRENGTH

    boundary_containment: Shape = (140.0, 142.0, 90.0, 110.0)
    values = matched(
        three_candle.UNIQUE_THREE_RIVER,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, boundary_containment, UNIQUE_THIRD],
    )
    assert values["pat_unique_three_river_strength"] == outputs.FULL_STRENGTH


# --- §7.4.17 Unique Three River Bottom ---------------------------------------

UNIQUE_SECOND: Shape = (130.0, 132.0, 90.0, 110.0)
"""Black, its body from 110.00 to 130.00 inside 100.00 to 140.00, its low under 95.00."""

UNIQUE_THIRD: Shape = (100.0, 112.0, 99.0, 104.0)
"""White, body 4.00 in a range of 13.00 — short by §2.2's 4.33 — topping out at 104.00."""

UNIQUE_THREE_RIVER: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    UNIQUE_SECOND,
    UNIQUE_THIRD,
]


def test_unique_three_river_contains_the_body_and_lets_the_tail_out() -> None:
    """Check §7.4.17's rules 3 and 4, which apply to different parts of the same bar.

    §4.1's containment holds between real bodies, so the second bar's body sits
    inside the first while its low of 90.00 runs below the first bar's 95.00.
    Both are required, and a second bar bottoming at 96.00 fails rule 4 while
    still being contained.
    """
    values = matched(three_candle.UNIQUE_THREE_RIVER, UNIQUE_THREE_RIVER)
    assert values["pat_unique_three_river_dir"] == outputs.BULLISH

    no_new_low: Shape = (130.0, 132.0, 96.0, 110.0)
    not_matched(
        three_candle.UNIQUE_THREE_RIVER,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, no_new_low, UNIQUE_THIRD],
    )


def test_unique_three_river_puts_the_whole_third_body_under_the_middle_one() -> None:
    """Check rule 6 under the strongest of the three readings §7.4.17 weighed.

    The third body tops out at 104.00 against the middle body's bottom of 110.00,
    so it lies wholly below. A third bar closing at 115.00 would still close
    below the middle bar's close of 110.00 on the weaker reading — it does not —
    but its body from 108.00 to 115.00 overlaps the middle body, which is what
    the chosen reading excludes.
    """
    overlapping_body: Shape = (108.0, 118.0, 107.0, 115.0)
    not_matched(
        three_candle.UNIQUE_THREE_RIVER,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, UNIQUE_SECOND, overlapping_body],
    )


# --- §7.4.18 Concealing Baby Swallow -----------------------------------------

CONCEALING_BABY_SWALLOW: list[Shape] = [
    *background(DOWNTREND_FILLER),
    (120.0, 121.0, 99.0, 100.0),
    (100.0, 101.0, 79.0, 80.0),
    (75.0, 90.0, 70.0, 72.0),
    (85.0, 92.0, 65.0, 70.0),
]
"""Four bars, which is what puts this section's warm-up at 13 rather than 12.

The first two are black marubozus: bodies of 20.00 in ranges of 22.00 with
shadows of 1.00, inside §2.5's 2.20. The third gaps its body down to 72.00-75.00
under the second body's bottom of 80.00 and then trades back up to 90.00, giving
an upper shadow of 15.00 on a body of 3.00 — past §2.4's 6.00. The fourth covers
the third's whole range, 65.00 to 92.00 against 70.00 to 90.00. The first bar's
midpoint of 110.00 is below the filler at 130.00.
"""


def test_concealing_baby_swallow_spans_four_bars_and_swallows_the_shadows_too() -> None:
    """Check §7.4.18's four rules, and rule 4 as a high-low engulfment.

    The source says "including the shadow", so §4.1's body relation is not what
    rule 4 reads. A fourth bar whose high of 89.00 falls short of the third
    bar's 90.00 therefore fails, even though its body would engulf the third
    body comfortably.
    """
    values = matched(three_candle.CONCEALING_BABY_SWALLOW, CONCEALING_BABY_SWALLOW)
    assert values["pat_concealing_baby_swallow_dir"] == outputs.BULLISH

    misses_the_shadow: Shape = (85.0, 89.0, 65.0, 70.0)
    not_matched(
        three_candle.CONCEALING_BABY_SWALLOW,
        [*background(DOWNTREND_FILLER), *CONCEALING_BABY_SWALLOW[-4:-1], misses_the_shadow],
    )


def test_concealing_baby_swallow_needs_the_third_bar_to_reach_back_into_the_second_body() -> None:
    """Check rule 3, whose three parts describe one movement.

    The body gaps down — §2.8's convention, since the source names no kind — and
    the high then climbs back above the second body's bottom of 80.00, which is
    what leaves the long upper shadow. A third bar peaking at 78.00 gaps and
    keeps a shadow of 3.00 on a body of 3.00, but reaches neither the second body
    nor §2.4's 6.00.
    """
    stays_below_the_second_body: Shape = (75.0, 78.0, 70.0, 72.0)
    not_matched(
        three_candle.CONCEALING_BABY_SWALLOW,
        [
            *background(DOWNTREND_FILLER),
            *CONCEALING_BABY_SWALLOW[-4:-2],
            stays_below_the_second_body,
            (85.0, 92.0, 65.0, 70.0),
        ],
    )

    # And the first two bars have to be marubozus: shadows of 4.00 in a range of
    # 28.00 are past §2.5's 2.80, so §7.2.2's rule is what rejects this one.
    shadowed_second: Shape = (100.0, 104.0, 76.0, 80.0)
    not_matched(
        three_candle.CONCEALING_BABY_SWALLOW,
        [
            *background(DOWNTREND_FILLER),
            CONCEALING_BABY_SWALLOW[-4],
            shadowed_second,
            *CONCEALING_BABY_SWALLOW[-2:],
        ],
    )


# --- the eighteen as a registered catalog ------------------------------------

SECTION_MIN_HISTORY = {
    # Written out from each §7.4 section's own `min_history` line rather than
    # recomputed: seventeen three-bar trend patterns at 12, and Concealing Baby
    # Swallow at 13 because its fourth bar pushes the first day one further back.
    "pat_morning_star": 12,
    "pat_evening_star": 12,
    "pat_morning_doji_star": 12,
    "pat_evening_doji_star": 12,
    "pat_abandoned_baby": 12,
    "pat_tri_star": 12,
    "pat_two_crows": 12,
    "pat_upside_gap_two_crows": 12,
    "pat_three_white_soldiers": 12,
    "pat_three_black_crows": 12,
    "pat_identical_three_crows": 12,
    "pat_advance_block": 12,
    "pat_stalled_pattern": 12,
    "pat_three_stars_in_the_south": 12,
    "pat_three_inside": 12,
    "pat_three_outside": 12,
    "pat_unique_three_river": 12,
    "pat_concealing_baby_swallow": 13,
}

SECTION_RULES: dict[str, PatternRule] = {
    rule.name: rule
    for rule in (
        three_candle.MORNING_STAR,
        three_candle.EVENING_STAR,
        three_candle.MORNING_DOJI_STAR,
        three_candle.EVENING_DOJI_STAR,
        three_candle.ABANDONED_BABY,
        three_candle.TRI_STAR,
        three_candle.TWO_CROWS,
        three_candle.UPSIDE_GAP_TWO_CROWS,
        three_candle.THREE_WHITE_SOLDIERS,
        three_candle.THREE_BLACK_CROWS,
        three_candle.IDENTICAL_THREE_CROWS,
        three_candle.ADVANCE_BLOCK,
        three_candle.STALLED_PATTERN,
        three_candle.THREE_STARS_IN_THE_SOUTH,
        three_candle.THREE_INSIDE,
        three_candle.THREE_OUTSIDE,
        three_candle.UNIQUE_THREE_RIVER,
        three_candle.CONCEALING_BABY_SWALLOW,
    )
}

REGISTERED_SPECS: tuple[PatternSpec, ...] = tuple(
    spec for spec in DEFAULT_PATTERN_REGISTRY.list() if spec.name in SECTION_MIN_HISTORY
)

PATTERNS_REGISTERED_BEFORE = 33
"""§7.1's eleven, §7.2's six, and §7.3's sixteen, the catalogs the earlier files own."""


def test_the_registry_gained_exactly_the_eighteen_sections_of_seven_four() -> None:
    """Check the registered catalog against §8.1's fourth row and the earlier total.

    §8.1 counts one entry per TA-Lib function, so Three Inside and Three Outside
    are one section each rather than two: their Up and Down forms share a name
    and are told apart by the direction key. Splitting them would make this row
    twenty.
    """
    assert len(REGISTERED_SPECS) == 18
    assert {spec.name for spec in REGISTERED_SPECS} == set(SECTION_MIN_HISTORY)
    # No pattern takes a parameter, so an identity is its bare name.
    assert {spec.identifier for spec in REGISTERED_SPECS} == set(SECTION_MIN_HISTORY)

    assert len(DEFAULT_PATTERN_REGISTRY.list()) == PATTERNS_REGISTERED_BEFORE + 18 + 10  # §7.5


def test_each_section_warms_up_where_its_own_line_says() -> None:
    """Check §6's trend formula against the per-section values, not against itself."""
    assert {spec.name: spec.min_history for spec in REGISTERED_SPECS} == SECTION_MIN_HISTORY

    counted = sorted(SECTION_MIN_HISTORY.values())
    assert counted.count(12) == 17
    assert counted.count(13) == 1


def test_the_indicator_tally_is_untouched_by_this_change() -> None:
    """Check that registering eighteen more patterns moved nothing in the other registry."""
    indicator_names = {spec.name for spec in DEFAULT_REGISTRY.list()}
    assert indicator_names.isdisjoint(DEFAULT_PATTERN_REGISTRY.names())
    assert all(not name.startswith(outputs.NAME_PREFIX) for name in indicator_names)


CONFIRMATION_GRADES = {
    # Read off each section's own `확인` header line. `None` is a grade of `No` on
    # both sides, and a direction is a section graded on that side and `No` on
    # the other, which §5.5 says computes a confirmation on the graded side only.
    "pat_morning_star": "both",  # Required, and the section is bullish only
    "pat_evening_star": "both",  # Required, and the section is bearish only
    "pat_morning_doji_star": "both",  # Suggested, bullish only
    "pat_evening_doji_star": "both",  # Required, bearish only
    "pat_abandoned_baby": "both",  # Suggested bullish, Required bearish
    "pat_tri_star": "both",  # Suggested bullish, Required bearish
    "pat_two_crows": "both",  # Required, bearish only
    "pat_upside_gap_two_crows": "both",  # Required, bearish only
    "pat_three_white_soldiers": None,  # No
    "pat_three_black_crows": "both",  # Required, bearish only
    "pat_identical_three_crows": None,  # No, stated in Morris's body text
    "pat_advance_block": "both",  # Required, bearish only
    "pat_stalled_pattern": outputs.BEARISH,  # No bullish, Suggested bearish
    "pat_three_stars_in_the_south": "both",  # Suggested, bullish only
    "pat_three_inside": outputs.BEARISH,  # No up, Required down
    "pat_three_outside": outputs.BEARISH,  # No up, Required down
    "pat_unique_three_river": "both",  # Required, bullish only
    "pat_concealing_baby_swallow": None,  # No
}


def test_confirmation_is_computed_only_where_a_source_graded_it() -> None:
    """Check §5.5's two grade conventions against all eighteen header lines.

    The wiring splits three ways: twelve sections on the general rule, three on
    the bearish side alone, and three on nothing at all.
    """
    assert set(CONFIRMATION_GRADES) == set(SECTION_RULES)
    for name, grade in CONFIRMATION_GRADES.items():
        rule = SECTION_RULES[name]
        if grade is None:
            assert rule.confirm is None, name
        elif grade == "both":
            assert rule.confirm is confirms_by_close_direction, name
        else:
            assert rule.confirm is CONFIRMS_BEARISH_SIDE_ONLY, name

    counted = list(CONFIRMATION_GRADES.values())
    assert counted.count("both") == 12
    assert counted.count(outputs.BEARISH) == 3
    assert counted.count(None) == 3


def test_a_confirmation_lands_on_the_bar_after_the_match() -> None:
    """Check §5.4 on both a bullish and a bearish section of this group.

    The morning star closes at 125.00, so a following close of 130.00 confirms
    it; the evening star closes at 115.00 and a following close of 110.00 does
    the same on the other side. Writing either back onto the pattern bar would
    make the value at index `t` depend on a candle after `t`.
    """
    rising: Shape = (125.0, 132.0, 124.0, 130.0)
    values = run(three_candle.MORNING_STAR, [*MORNING_STAR, rising])
    assert values[-2]["pat_morning_star"] == outputs.MATCHED
    assert values[-2]["pat_morning_star_confirm"] == outputs.NOT_MATCHED
    assert values[-1]["pat_morning_star"] == outputs.NOT_MATCHED
    assert values[-1]["pat_morning_star_confirm"] == outputs.MATCHED

    falling: Shape = (115.0, 116.0, 108.0, 110.0)
    values = run(three_candle.EVENING_STAR, [*EVENING_STAR, falling])
    assert values[-2]["pat_evening_star"] == outputs.MATCHED
    assert values[-1]["pat_evening_star_confirm"] == outputs.MATCHED

    # A close going the other way leaves the key down for the whole deadline.
    values = run(three_candle.EVENING_STAR, [*EVENING_STAR, (115.0, 125.0, 114.0, 120.0)])
    assert values[-1]["pat_evening_star_confirm"] == outputs.NOT_MATCHED


BEARISH_ONLY_CASES: dict[str, tuple[list[Shape], list[Shape]]] = {
    # Each entry is the section's bullish case and its bearish one, in that order.
    "pat_stalled_pattern": (
        [
            *background(DOWNTREND_FILLER),
            (140.0, 141.0, 115.0, 120.0),
            (130.0, 131.0, 105.0, 110.0),
            (111.0, 112.0, 100.0, 110.5),
        ],
        STALLED_PATTERN,
    ),
    "pat_three_inside": (THREE_INSIDE_UP, THREE_INSIDE_DOWN),
    "pat_three_outside": (THREE_OUTSIDE_UP, THREE_OUTSIDE_DOWN),
}


@pytest.mark.parametrize("name", sorted(BEARISH_ONLY_CASES), ids=lambda name: name)
def test_an_ungraded_side_leaves_the_confirmation_key_down(name: str) -> None:
    """Check §5.5's direction convention on live bars for all three asymmetric sections.

    Each is graded `No` on its bullish side, so a following bar that would
    satisfy the general close comparison leaves `_confirm` at 0.0 there while the
    bearish side raises it normally. The following bar is built from the matched
    bar's own close in each case: 5.00 above it on the bullish side and 5.00
    below on the bearish one.
    """
    rule = SECTION_RULES[name]
    bullish_case, bearish_case = BEARISH_ONLY_CASES[name]

    bullish_close = bullish_case[-1][3]
    rising: Shape = (bullish_close, bullish_close + 6.0, bullish_close - 1.0, bullish_close + 5.0)
    values = run(rule, [*bullish_case, rising])
    assert values[-2][name] == outputs.MATCHED
    assert values[-2][f"{name}_dir"] == outputs.BULLISH
    assert values[-1][f"{name}_confirm"] == outputs.NOT_MATCHED

    bearish_close = bearish_case[-1][3]
    falling: Shape = (bearish_close, bearish_close + 1.0, bearish_close - 6.0, bearish_close - 5.0)
    values = run(rule, [*bearish_case, falling])
    assert values[-2][name] == outputs.MATCHED
    assert values[-2][f"{name}_dir"] == outputs.BEARISH
    assert values[-1][f"{name}_confirm"] == outputs.MATCHED


UNGRADED_CASES: dict[str, list[Shape]] = {
    "pat_three_white_soldiers": THREE_WHITE_SOLDIERS,
    "pat_identical_three_crows": IDENTICAL_THREE_CROWS,
    "pat_concealing_baby_swallow": CONCEALING_BABY_SWALLOW,
}


@pytest.mark.parametrize("name", sorted(UNGRADED_CASES), ids=lambda name: name)
def test_the_three_ungraded_sections_never_raise_the_confirmation_key(name: str) -> None:
    """Check §5.5's `No` convention on the bar where a computed one would have fired.

    All three sections match and point somewhere, and the bar after each match
    closes the way the match points, so a confirmation derived from the direction
    alone would raise the key. None of them does, because no source asked for the
    event.
    """
    rule = SECTION_RULES[name]
    case = UNGRADED_CASES[name]
    last_close = case[-1][3]
    direction = outputs.BULLISH if name != "pat_identical_three_crows" else outputs.BEARISH
    moved = last_close + 5.0 if direction == outputs.BULLISH else last_close - 5.0
    following: Shape = (
        last_close,
        max(last_close, moved) + 1.0,
        min(last_close, moved) - 1.0,
        moved,
    )

    values = run(rule, [*case, following])
    assert values[-2][name] == outputs.MATCHED
    assert values[-2][f"{name}_dir"] == direction
    assert values[-2][f"{name}_confirm"] == outputs.NOT_MATCHED
    assert values[-1][f"{name}_confirm"] == outputs.NOT_MATCHED


# --- warm-up, the two paths, and degenerate bars, over every section ----------

MATCHING_CASES: dict[str, list[Shape]] = {
    # One hand-built series per section, each holding on its last bar.
    "pat_morning_star": MORNING_STAR,
    "pat_evening_star": EVENING_STAR,
    "pat_morning_doji_star": MORNING_DOJI_STAR,
    "pat_evening_doji_star": EVENING_DOJI_STAR,
    "pat_abandoned_baby": ABANDONED_BABY,
    "pat_tri_star": TRI_STAR,
    "pat_two_crows": TWO_CROWS,
    "pat_upside_gap_two_crows": UPSIDE_GAP_TWO_CROWS,
    "pat_three_white_soldiers": THREE_WHITE_SOLDIERS,
    "pat_three_black_crows": THREE_BLACK_CROWS,
    "pat_identical_three_crows": IDENTICAL_THREE_CROWS,
    "pat_advance_block": ADVANCE_BLOCK,
    "pat_stalled_pattern": STALLED_PATTERN,
    "pat_three_stars_in_the_south": THREE_STARS_IN_THE_SOUTH,
    "pat_three_inside": THREE_INSIDE_UP,
    "pat_three_outside": THREE_OUTSIDE_UP,
    "pat_unique_three_river": UNIQUE_THREE_RIVER,
    "pat_concealing_baby_swallow": CONCEALING_BABY_SWALLOW,
}

LONG_SERIES: list[Shape] = [
    *[shape for case in MATCHING_CASES.values() for shape in case],
    *ABANDONED_BABY_BEARISH,
    *THREE_INSIDE_DOWN,
    *THREE_OUTSIDE_DOWN,
    *background(150.0, count=12),
]
"""Every hand-built case laid end to end, plus three bearish sides and a quiet tail.

The trend average runs continuously across the whole thing rather than being
restarted per case, so the blocks do not each reproduce the verdict they produce
in isolation. That is the point: this series exists to drive the two execution
paths over a long, varied input, and the per-section claims are made on the cases
themselves.
"""


@pytest.mark.parametrize("name", sorted(MATCHING_CASES), ids=lambda name: name)
def test_every_section_matches_on_its_own_hand_built_case(name: str) -> None:
    """Check that all eighteen are reachable, one hand-built series each.

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


def test_the_four_bar_section_starts_one_bar_after_the_other_seventeen() -> None:
    """Check §6's split inside this group, on one series, index by index.

    Thirteen bars carry both lengths at once. The three-bar sections answer from
    index 11, because their first day needs a ten-period average that first
    exists at index 9 and sits two bars behind the judged bar. Concealing Baby
    Swallow waits one further, to index 12, because its first day is three bars
    behind instead of two.
    """
    candles = series(CONCEALING_BABY_SWALLOW)
    assert len(candles) == 13

    first_finite = {}
    for name, rule in SECTION_RULES.items():
        values = judge_series(rule, candles)
        first_finite[name] = next(
            index for index, value in enumerate(values) if not isnan(value[name])
        )

    assert first_finite["pat_morning_star"] == 11
    assert first_finite["pat_three_inside"] == 11
    assert first_finite["pat_concealing_baby_swallow"] == 12
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


def test_a_degenerate_bar_is_stopped_before_the_scales_are_consulted() -> None:
    """Check §2.7's window gate where a scale would otherwise answer the wrong way.

    A four-price bar has a body of zero, so §7.4.6's rule 2 would read it as a
    doji if the scales were consulted on their own. §2.3 answers False for it and
    §2.7's window gate stops it before that, which is the pair of defences the
    standard asks for.
    """
    four_price_bar: Shape = (110.0, 110.0, 110.0, 110.0)
    candle = series([four_price_bar])[0]
    assert primitives.body(candle) == 0.0
    assert not scales.doji(candle)

    values = not_matched(
        three_candle.TRI_STAR,
        [*background(DOWNTREND_FILLER), TRI_STAR[-3], four_price_bar, TRI_STAR[-1]],
    )
    assert values["pat_tri_star_dir"] == outputs.DIRECTIONLESS


def test_a_degenerate_bar_cannot_confirm_the_match_before_it() -> None:
    """Check §5.5's degenerate-confirmation rule, which sits outside the judgment window.

    The bar after the morning star has all four prices at 130.00, above the
    star's close of 125.00, so the plain close comparison would confirm. §5.5
    refuses it for the reason §2.7 gives: a bar the standard will not judge on is
    not one it will take a confirmation from. Neither of §2.7's two guards
    reaches this bar, because it lies outside the window.
    """
    degenerate: Shape = (130.0, 130.0, 130.0, 130.0)
    values = run(three_candle.MORNING_STAR, [*MORNING_STAR, degenerate])
    assert values[-2]["pat_morning_star"] == outputs.MATCHED
    assert values[-1]["pat_morning_star_confirm"] == outputs.NOT_MATCHED

    barely_alive: Shape = (130.0, 130.01, 130.0, 130.0)
    values = run(three_candle.MORNING_STAR, [*MORNING_STAR, barely_alive])
    assert values[-1]["pat_morning_star_confirm"] == outputs.MATCHED


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
    the bar it confirms, say — would show up here as two different answers for
    the same index.
    """
    candles = series(LONG_SERIES)
    whole = spec.compute_vectorized(candles)
    prefix_length = spec.min_history + 20
    prefix = spec.compute_vectorized(candles[:prefix_length])

    assert_same_series(whole[:prefix_length], prefix)
