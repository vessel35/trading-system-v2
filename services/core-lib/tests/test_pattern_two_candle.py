"""Verify §7.3 of the candlestick pattern standard: the sixteen two-bar sections.

Every expected value here is derived by hand from the standard and the arithmetic
that puts a bar on a threshold is written into the test that uses it, so a rule
and its check cannot drift together. `run` — which nearly every test calls —
judges the batch path and the incremental path and refuses to return until the
two agree bar for bar, so the parity claim is made on each hand-built series
rather than only on a generated one.

Three groups of section are easy to confuse and are separated on purpose. §7.3.1
Engulfing and §7.3.2 Harami are the same containment read in opposite
directions, so neither may hold on the other's bars. §7.3.2 and §7.3.3 differ
only in whether the second bar is a doji. And §7.3.5 Piercing, §7.3.13 In-Neck,
§7.3.14 On-Neck, and §7.3.15 Thrusting differ only in where the second bar
closes, which one test exercises by moving that close and nothing else.

Confirmation is not uniform across the group and §5.5 is why: it computes one
only where a source graded one, and Morris grades some sections differently on
their two sides. Seven sections here take the general rule, seven compute it on
their bearish side alone, and two compute none at all. The three cases are
checked as a table and then exercised on live bars.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from math import isnan

import pytest
from core_lib.indicators.registry import DEFAULT_REGISTRY
from core_lib.patterns import outputs, primitives, scales, two_candle
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
    uptrend, whether the pattern spans two bars or three.
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


# --- the bars most of §7.3 is built on ---------------------------------------
#
# Twelve of the sixteen sections open with a long first day, so two shapes do
# most of the work below. Both have a body of 40.00 in a range of 50.00 — past
# §2.1's half of the range — and a high-low midpoint of 120.00, which is what the
# filler is chosen against.

LONG_BLACK_FIRST: Shape = (140.0, 145.0, 95.0, 100.0)
"""Body 40.00 from 140.00 down to 100.00, range 50.00, midpoint 120.00."""

LONG_WHITE_FIRST: Shape = (100.0, 145.0, 95.0, 140.0)
"""The same bar the other way up: body 40.00 from 100.00 to 140.00."""

DOWNTREND_FILLER = 130.0
"""Above the first day's midpoint of 120.00, so §3 answers `DOWNTREND`."""

UPTREND_FILLER = 110.0
"""Below that midpoint, so §3 answers `UPTREND`."""


# --- §7.3.1 Engulfing --------------------------------------------------------

BULLISH_ENGULFING: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    (98.0, 145.0, 96.0, 142.0),
]
"""A white body from 98.00 to 142.00 around a black one from 100.00 to 140.00."""

BEARISH_ENGULFING: list[Shape] = [
    *background(UPTREND_FILLER),
    LONG_WHITE_FIRST,
    (142.0, 145.0, 96.0, 98.0),
]

BOUNDARY_ENGULFING: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    (100.0, 145.0, 99.0, 142.0),
]
"""The same wrap with the two body bottoms both at 100.00: §5.6's half strength."""


def test_engulfing_wraps_the_first_body_in_the_second() -> None:
    """Check §7.3.1's direction of the wrap, which is what separates it from Harami.

    The second body runs from 98.00 to 142.00 and the first from 100.00 to
    140.00, so the later bar covers the earlier one on both ends and §4.1's
    exclusion — both ends coinciding — does not apply.
    """
    values = matched(two_candle.ENGULFING, BULLISH_ENGULFING)
    assert values["pat_engulfing_dir"] == outputs.BULLISH
    assert values["pat_engulfing_strength"] == outputs.FULL_STRENGTH

    values = matched(two_candle.ENGULFING, BEARISH_ENGULFING)
    assert values["pat_engulfing_dir"] == outputs.BEARISH


def test_engulfing_gives_half_strength_when_one_body_end_coincides() -> None:
    """Check §5.6 through the one relation the sources let it apply to.

    The second body opens at exactly the first body's low of 100.00. §4.1 allows
    that and excludes only both ends coinciding, so the match stands and §5.6
    marks it as sitting on the boundary.
    """
    values = matched(two_candle.ENGULFING, BOUNDARY_ENGULFING)
    assert values["pat_engulfing_strength"] == outputs.BOUNDARY_STRENGTH

    # Both ends together is the excluded case, so the pattern does not hold.
    identical_bodies: Shape = (100.0, 145.0, 96.0, 140.0)
    not_matched(
        two_candle.ENGULFING,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, identical_bodies],
    )


def test_engulfing_needs_the_trend_its_direction_asks_for() -> None:
    """Check that a well-shaped pair under the wrong trend is a non-match, not a flip.

    §7.3.1 puts the bullish side after a decline. The same two bars after a rise
    do not become the bearish side — that side wants the colours the other way
    round — so nothing holds.
    """
    not_matched(
        two_candle.ENGULFING,
        [*background(UPTREND_FILLER), LONG_BLACK_FIRST, (98.0, 145.0, 96.0, 142.0)],
    )


# --- §7.3.2 Harami and §7.3.3 Harami Cross -----------------------------------

HARAMI_SECOND: Shape = (110.0, 136.0, 104.0, 120.0)
"""White, body 10.00 inside the first body, range 32.00.

Short by §2.2, since 10.00 is under a third of 32.00 (10.67), and contained,
since 110.00 and 120.00 both sit inside 100.00 to 140.00.
"""

BULLISH_HARAMI: list[Shape] = [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, HARAMI_SECOND]

COLOURLESS_DOJI_SECOND: Shape = (120.0, 136.0, 104.0, 120.0)
"""Open and close both 120.00: a doji with no body and, by §1.2, no colour."""

BULLISH_HARAMI_CROSS: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    COLOURLESS_DOJI_SECOND,
]


def test_harami_puts_a_short_opposite_coloured_body_inside_a_long_one() -> None:
    """Check §7.3.2's four measured rules and the colour rule that fixes the fifth."""
    values = matched(two_candle.HARAMI, BULLISH_HARAMI)
    assert values["pat_harami_dir"] == outputs.BULLISH
    assert values["pat_harami_strength"] == outputs.FULL_STRENGTH

    # A body of 12.00 in a range of 32.00 is over a third and no longer short.
    not_short: Shape = (110.0, 136.0, 104.0, 122.0)
    not_matched(two_candle.HARAMI, [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, not_short])


def test_harami_shares_engulfings_boundary_rule() -> None:
    """Check §5.6 on the containment, where §4.2 sends the same relation."""
    shared_bottom: Shape = (100.0, 136.0, 99.0, 108.0)
    values = matched(
        two_candle.HARAMI,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, shared_bottom],
    )
    assert values["pat_harami_strength"] == outputs.BOUNDARY_STRENGTH


def test_harami_and_engulfing_never_hold_on_the_same_two_bars() -> None:
    """Check the pair §7.3.1's own note warns about, in both directions.

    Morris's printed Engulfing rule has the two bodies the wrong way round, which
    would turn it into Harami. Reading each section's input through the other
    section is what catches that class of mistake: containment and engulfment are
    the same relation with the bars exchanged, and §4.1 excludes the one case
    where both could hold at once.
    """
    not_matched(two_candle.HARAMI, BULLISH_ENGULFING)
    not_matched(two_candle.ENGULFING, BULLISH_HARAMI)


def test_harami_cross_differs_from_harami_only_in_asking_for_a_doji() -> None:
    """Check §7.3.3, whose rule 3 replaces both of §7.3.2's body conditions.

    The second bar here has no body at all in a range of 32.00, so it is a doji
    by §2.3 and colourless by §1.2. That is enough for §7.3.3 and not enough for
    §7.3.2, whose rule 5 wants a colour opposite the first day's.
    """
    values = matched(two_candle.HARAMI_CROSS, BULLISH_HARAMI_CROSS)
    assert values["pat_harami_cross_dir"] == outputs.BULLISH
    not_matched(two_candle.HARAMI, BULLISH_HARAMI_CROSS)

    # And the other way: a short body of 10.00 in a range of 32.00 is far past
    # §2.3's tolerance of 0.96, so Harami's bars are not a Harami Cross.
    not_matched(two_candle.HARAMI_CROSS, BULLISH_HARAMI)


def test_a_faintly_coloured_doji_satisfies_both_harami_sections() -> None:
    """Record the overlap the two sections leave, rather than a rule of either.

    A doji body is at most 3% of the range and a short body is anything under a
    third of it, so every doji is also a short body. When that doji carries a
    faint colour opposite the first day, both sections hold on the same bars.
    The bar below has a body of 1.00 in a range of 36.00 — inside §2.3's
    tolerance of 1.08 — and is white against a black first day.

    Nothing is worked around here: both sections are implemented as written, and
    a consumer telling them apart reads §7.3.3's stricter body, not §7.3.2's
    absence.
    """
    faint_doji: Shape = (120.0, 140.0, 104.0, 121.0)
    shapes = [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, faint_doji]

    assert matched(two_candle.HARAMI_CROSS, shapes)
    assert matched(two_candle.HARAMI, shapes)


# --- §7.3.4 Doji Star --------------------------------------------------------


DOJI_STAR_SECOND: Shape = (80.0, 96.0, 64.0, 80.0)
"""A doji with no body at all, sitting entirely below the first body's low of 100.00."""

BULLISH_DOJI_STAR: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    DOJI_STAR_SECOND,
]

BEARISH_DOJI_STAR: list[Shape] = [
    *background(UPTREND_FILLER),
    LONG_WHITE_FIRST,
    (160.0, 176.0, 144.0, 160.0),
]
"""The mirror: a bodyless doji whose body sits above the first body's top of 140.00."""


def test_doji_star_gaps_its_doji_away_from_the_long_body() -> None:
    """Check §7.3.4's four rules, of which rule 3 is the one doing the separating.

    The star has no body at all in a range of 32.00, which is a doji by §2.3, and
    it sits at 80.00 — below the first body's low of 100.00, so the two real
    bodies gap apart. §1.3's body gap is what Nison's glossary names, not the
    high-low gap: the star's high of 96.00 also clears the first body here, but
    nothing in the section asks it to.
    """
    values = matched(two_candle.DOJI_STAR, BULLISH_DOJI_STAR)
    assert values["pat_doji_star_dir"] == outputs.BULLISH
    assert values["pat_doji_star_strength"] == outputs.FULL_STRENGTH

    values = matched(two_candle.DOJI_STAR, BEARISH_DOJI_STAR)
    assert values["pat_doji_star_dir"] == outputs.BEARISH

    # A doji whose body sits at 105.00 overlaps the first body's 100.00 to
    # 140.00 and removes the gap while staying a doji.
    no_gap: Shape = (105.0, 121.0, 89.0, 105.0)
    not_matched(two_candle.DOJI_STAR, [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, no_gap])


def test_doji_star_keeps_morriss_shadow_sentence_as_a_tendency() -> None:
    """Check that §7.3.4 does not bound the star's shadows, and why it cannot.

    Morris writes that the doji's shadows "should not be excessively long". §7.3.4
    reads that as a tendency, the way §7.1.9 reads Morris's "usually" and §7.3.14
    reads Nison's. The section also records that the alternative is unavailable
    rather than merely unattractive: §2.4 measures a shadow in multiples of the
    body, and rule 4 has already driven that body to almost nothing.

    The star below makes that concrete. Its body is 0.00 and its lower shadow
    16.00, so §1.4's lower-bound convention makes "at least two bodies" true and
    a negated §2.4 would reject it — and by the same arithmetic would reject
    every doji, since a body under 3% of the range leaves the two shadows sharing
    at least 97% of it.
    """
    star = series([DOJI_STAR_SECOND])[0]
    assert scales.doji(star)
    assert primitives.body(star) == 0.0
    assert scales.long_lower_shadow(star)

    assert matched(two_candle.DOJI_STAR, BULLISH_DOJI_STAR)


def test_doji_star_and_harami_cross_are_separated_by_the_gap() -> None:
    """Check the pair §7.3.4 names as the reason it needs no shadow rule.

    Both sections put a doji after a long body, and both are read on the same
    first bar here. §7.3.3 asks for the doji to sit *inside* that body and §7.3.4
    for it to sit *outside* and apart, so neither can reach the other's bars.
    """
    not_matched(two_candle.HARAMI_CROSS, BULLISH_DOJI_STAR)
    not_matched(two_candle.DOJI_STAR, BULLISH_HARAMI_CROSS)


# --- §7.3.5, §7.3.13, §7.3.14, §7.3.15: the four that differ by one price ----
#
# All four take a downtrend, a long black first day, and a white second day
# opening below the first day's low. The first body runs 100.00 to 140.00 with a
# midpoint of 120.00 and a low of 95.00. The second bar opens at 90.00 in a range
# of 42.00, so §2.6's `Equal` tolerance on it is 1.26, and only its close moves.

NECKLINE_SECOND_LOW = 88.0
NECKLINE_SECOND_HIGH = 130.0
NECKLINE_SECOND_OPEN = 90.0


def neckline_case(close: float) -> list[Shape]:
    """Return the shared setup with the second bar closing at `close`."""
    second: Shape = (NECKLINE_SECOND_OPEN, NECKLINE_SECOND_HIGH, NECKLINE_SECOND_LOW, close)
    return [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, second]


ON_NECK_CLOSE = 95.0
"""Exactly the first day's low, which is what §7.3.14's rule 5 names."""

IN_NECK_CLOSE = 101.0
"""Just past the first close of 100.00 and inside §2.6's tolerance of 1.26."""

THRUSTING_CLOSE = 110.0
"""Past that tolerance and still under the first body's midpoint of 120.00."""

PIERCING_CLOSE = 125.0
"""Past the midpoint and still under the first open of 140.00."""


def test_the_four_neckline_sections_are_told_apart_by_the_closing_price_alone() -> None:
    """Check §7.3.5, §7.3.13, §7.3.14, and §7.3.15 against one shared setup.

    Everything but the second bar's close is held fixed, so each section's
    boundaries are read off one axis. Moving up that axis: a close at the first
    day's low of 95.00 is On-Neck; a close of 101.00 is inside §2.6's tolerance
    of 1.26 around the first close of 100.00 and is In-Neck; a close of 110.00 is
    past that tolerance and not yet at the midpoint of 120.00 and is Thrusting; a
    close of 125.00 is past the midpoint and inside the body and is Piercing.

    Each row asserts one match and three non-matches, which is what makes the
    four exclusive rather than merely distinguishable. §7.3.15 designed the
    In-Neck boundary for exactly this: `Equal` on one side of it and `¬Equal` on
    the other leaves neither an overlap nor a gap.
    """
    sections = {
        "pat_on_neck": two_candle.ON_NECK,
        "pat_in_neck": two_candle.IN_NECK,
        "pat_thrusting": two_candle.THRUSTING,
        "pat_piercing": two_candle.PIERCING,
    }
    expected = {
        ON_NECK_CLOSE: "pat_on_neck",
        IN_NECK_CLOSE: "pat_in_neck",
        THRUSTING_CLOSE: "pat_thrusting",
        PIERCING_CLOSE: "pat_piercing",
    }

    for close, holder in expected.items():
        shapes = neckline_case(close)
        for name, rule in sections.items():
            if name == holder:
                assert matched(rule, shapes), f"close {close} should be {name}"
            else:
                not_matched(rule, shapes)


def test_piercing_closes_past_the_midpoint_and_stays_inside_the_body() -> None:
    """Check §7.3.5's two-sided rule 5 and the strict open comparison of rule 4."""
    values = matched(two_candle.PIERCING, neckline_case(PIERCING_CLOSE))
    assert values["pat_piercing_dir"] == outputs.BULLISH

    # A close at 141.00 is above the first open of 140.00 and no longer inside
    # the body, so the penetration rule rejects it from the top. The high moves
    # with it, because `Candle` refuses a close above its own high.
    closing_over_the_body: Shape = (90.0, 145.0, 88.0, 141.0)
    not_matched(
        two_candle.PIERCING,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, closing_over_the_body],
    )

    # Rule 4 compares the open with the previous *low* of 95.00, strictly, which
    # Morris marks in brackets as "that's low, not close". Opening at exactly the
    # low is not below it.
    opening_at_the_low: Shape = (95.0, 130.0, 88.0, PIERCING_CLOSE)
    not_matched(
        two_candle.PIERCING,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, opening_at_the_low],
    )


def test_the_midpoint_itself_belongs_to_thrusting() -> None:
    """Check §4.3's boundary, which the standard resolved by reading the sources.

    Piercing is written "more than halfway" and Thrusting "does not close above
    the middle", so a close exactly on the first body's midpoint of 120.00 falls
    to Thrusting. Nothing was invented for the tie; the two inequalities meet
    there on their own.
    """
    assert matched(two_candle.THRUSTING, neckline_case(120.0))
    not_matched(two_candle.PIERCING, neckline_case(120.0))


def test_in_neck_wants_a_small_second_candle_and_on_neck_does_not() -> None:
    """Check the one measured difference between §7.3.13 and §7.3.14.

    Nison writes that In-Neck's white candle "should also be a small white
    candle" and that On-Neck's is "(usually a small one)". §7.3.13 takes the
    first as a requirement and §7.3.14 reads the second as a tendency and leaves
    it out, so a large second bar is fatal to one section and irrelevant to the
    other.

    The bar below opens at 90.00 and closes at 101.00 in a range of 12.00, so its
    body of 11.00 is well over a third of the range and no longer short. It still
    sits inside §2.6's tolerance of 0.36 around the first close of 100.00.
    """
    large_bodied: Shape = (90.0, 102.0, 90.0, 101.0)
    not_matched(
        two_candle.IN_NECK,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, large_bodied],
    )

    # On-Neck's second bar carries no size condition at all: this one has a body
    # of 5.00 in a range of 6.00, far past long, and the section still holds
    # because its close sits on the first day's low of 95.00.
    long_bodied_on_the_neckline: Shape = (90.0, 96.0, 90.0, 95.0)
    assert matched(
        two_candle.ON_NECK,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, long_bodied_on_the_neckline],
    )


def test_in_neck_and_on_neck_overlap_when_the_first_day_has_no_lower_shadow() -> None:
    """Record where the four-way split above stops being a split.

    §7.3.13 measures the second close against the first *close* and §7.3.14
    against the first *low*, and those are two different prices only when the
    first bar has a lower shadow. A black closing marubozu has none, so the two
    conditions collapse onto the same price and both sections hold at once.

    The first bar below closes at 100.00 with its low also at 100.00 and a body
    of 40.00 in a range of 45.00, so it is long. The second opens at 95.00, below
    that low, and closes at 100.50 in a range of 17.00 — inside §2.6's tolerance
    of 0.51 of both reference prices — with a body of 5.50, under a third of its
    range and therefore short enough for In-Neck's extra condition.

    Nothing here is worked around: both sections are implemented as written, and
    the overlap follows from §2.6 being the tolerance in both places. It is
    recorded so that a consumer reading the two as mutually exclusive learns
    otherwise here, and so that the four-way test above is understood as holding
    for a first bar that has a lower shadow rather than for every first bar.
    """
    no_lower_shadow_first: Shape = (140.0, 145.0, 100.0, 100.0)
    just_above_both: Shape = (95.0, 110.0, 93.0, 100.5)
    shapes = [*background(DOWNTREND_FILLER), no_lower_shadow_first, just_above_both]

    assert matched(two_candle.IN_NECK, shapes)
    assert matched(two_candle.ON_NECK, shapes)
    # The other two still stay out: Thrusting needs the closes *not* equal and
    # Piercing needs a close past the midpoint of 120.00.
    not_matched(two_candle.THRUSTING, shapes)
    not_matched(two_candle.PIERCING, shapes)


def test_the_bullish_sides_of_the_three_continuation_sections() -> None:
    """Check the mirrored forms, including where the mirror is deliberately partial.

    All three run after an uptrend behind a long white first day whose body is
    100.00 to 140.00, high 145.00 and midpoint 120.00, and all three take a black
    second bar opening above that high. In-Neck closes at 139.00 — inside §2.6's
    tolerance of 1.26 below the first close of 140.00 — with a body of 11.00 in a
    range of 42.00, which is short. On-Neck closes at the first day's *high* of
    145.00 rather than its low. Thrusting closes at 130.00, past the tolerance
    and not below the midpoint of 120.00.
    """
    in_neck: Shape = (150.0, 152.0, 110.0, 139.0)
    values = matched(
        two_candle.IN_NECK,
        [*background(UPTREND_FILLER), LONG_WHITE_FIRST, in_neck],
    )
    assert values["pat_in_neck_dir"] == outputs.BULLISH

    on_neck: Shape = (150.0, 152.0, 143.0, 145.0)
    values = matched(
        two_candle.ON_NECK,
        [*background(UPTREND_FILLER), LONG_WHITE_FIRST, on_neck],
    )
    assert values["pat_on_neck_dir"] == outputs.BULLISH

    thrusting: Shape = (150.0, 152.0, 125.0, 130.0)
    values = matched(
        two_candle.THRUSTING,
        [*background(UPTREND_FILLER), LONG_WHITE_FIRST, thrusting],
    )
    assert values["pat_thrusting_dir"] == outputs.BULLISH


def test_the_long_first_day_is_asked_for_on_one_side_only() -> None:
    """Check the asymmetry §7.3.13 and §7.3.15 both inherit from Morris.

    On the bearish side neither section measures the first day, so a first bar
    with a body of 12.00 in a range of 50.00 — well under §2.1's half — still
    carries both. On the bullish side both ask for a long white day, and the same
    body size rejects them.

    Shortening the first body moves its midpoint with it, from 120.00 to 106.00,
    and Thrusting's ceiling follows: its second bar closes at 105.00 here rather
    than at the 110.00 the long-bodied case uses.
    """
    short_black_first: Shape = (112.0, 145.0, 95.0, 100.0)
    assert matched(
        two_candle.IN_NECK,
        [*background(DOWNTREND_FILLER), short_black_first, (90.0, 130.0, 88.0, 101.0)],
    )
    assert matched(
        two_candle.THRUSTING,
        [*background(DOWNTREND_FILLER), short_black_first, (90.0, 130.0, 88.0, 105.0)],
    )

    short_white_first: Shape = (100.0, 145.0, 95.0, 112.0)
    not_matched(
        two_candle.IN_NECK,
        [*background(UPTREND_FILLER), short_white_first, (150.0, 152.0, 110.0, 111.0)],
    )
    not_matched(
        two_candle.THRUSTING,
        [*background(UPTREND_FILLER), short_white_first, (150.0, 152.0, 105.0, 107.0)],
    )


# --- §7.3.6 Dark Cloud Cover -------------------------------------------------

DARK_CLOUD_COVER_CASE: list[Shape] = [
    *background(UPTREND_FILLER),
    LONG_WHITE_FIRST,
    (150.0, 152.0, 105.0, 110.0),
]
"""Opening at 150.00 above the first high of 145.00 and closing at 110.00.

That close sits under the first body's midpoint of 120.00 and above its open of
100.00, which is §4.3's penetration read the bearish way.
"""


def test_dark_cloud_cover_opens_above_the_previous_high() -> None:
    """Check §7.3.6's rule 4, where decision C chose between the two sources.

    Morris measures against the previous high and Nison would also accept the
    previous close. The narrower reading is the rule, so an open at 142.00 — above
    the close of 140.00 but below the high of 145.00 — is not enough.
    """
    values = matched(two_candle.DARK_CLOUD_COVER, DARK_CLOUD_COVER_CASE)
    assert values["pat_dark_cloud_cover_dir"] == outputs.BEARISH

    opening_above_the_close_only: Shape = (142.0, 143.0, 105.0, 110.0)
    not_matched(
        two_candle.DARK_CLOUD_COVER,
        [*background(UPTREND_FILLER), LONG_WHITE_FIRST, opening_above_the_close_only],
    )


def test_a_close_on_the_midpoint_leaves_dark_cloud_cover_for_thrusting() -> None:
    """Check §4.3's tie on the bearish side too, where the same pair of rules meet.

    A close of exactly 120.00 fails Dark Cloud Cover's strict "below the
    midpoint" and satisfies Thrusting's bullish rule 6, which is non-strict. The
    two sections divide the axis at the midpoint without leaving a gap, the same
    way Piercing and Thrusting do on the other side.
    """
    on_the_midpoint: Shape = (150.0, 152.0, 105.0, 120.0)
    shapes = [*background(UPTREND_FILLER), LONG_WHITE_FIRST, on_the_midpoint]

    not_matched(two_candle.DARK_CLOUD_COVER, shapes)
    assert matched(two_candle.THRUSTING, shapes)


# --- §7.3.7 Counterattack ----------------------------------------------------

COUNTERATTACK_CASE: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    (90.0, 101.0, 89.0, 100.0),
]
"""A long white bar opening at 90.00 — below the first low of 95.00 — and closing
at 100.00, exactly the first close. Its body of 10.00 fills a range of 12.00, so
it clears §2.1's half of the range and the two closes meet §2.6 exactly."""


def test_counterattack_needs_two_long_bodies_meeting_at_the_close() -> None:
    """Check §7.3.7's rules 3 to 5, the two that no neighbouring section shares."""
    values = matched(two_candle.COUNTERATTACK, COUNTERATTACK_CASE)
    assert values["pat_counterattack_dir"] == outputs.BULLISH

    # A close of 104.00 in a range of 16.00 is 4.00 away from the first close,
    # past §2.6's tolerance of 0.48.
    closes_apart: Shape = (90.0, 105.0, 89.0, 104.0)
    not_matched(
        two_candle.COUNTERATTACK,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, closes_apart],
    )

    # A second body of 10.00 in a range of 30.00 meets the close condition and
    # fails rule 3, which asks for both days to be long.
    second_not_long: Shape = (90.0, 110.0, 80.0, 100.0)
    not_matched(
        two_candle.COUNTERATTACK,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, second_not_long],
    )


def test_counterattack_carries_nisons_open_condition_to_the_bullish_side() -> None:
    """Check the symmetry §7.3.7 marks as the standard's own.

    Nison writes only the bearish form's open — above the prior day's high — and
    §7.3.7 mirrors it rather than inventing a threshold for "sharply lower". So
    an open of 96.00, below the first close of 100.00 but above the first low of
    95.00, is not enough.
    """
    opening_inside_the_range: Shape = (96.0, 101.0, 95.5, 100.0)
    not_matched(
        two_candle.COUNTERATTACK,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, opening_inside_the_range],
    )


# --- §7.3.8 Separating Lines -------------------------------------------------

SEPARATING_FIRST: Shape = (120.0, 125.0, 95.0, 100.0)
"""Black, opening at 120.00, midpoint 110.00 — above the filler, so an uptrend."""

SEPARATING_LINES_CASE: list[Shape] = [
    *background(100.0),
    SEPARATING_FIRST,
    (120.0, 137.0, 118.0, 135.0),
]


def test_separating_lines_meet_at_the_open_and_carry_the_trend() -> None:
    """Check §7.3.8, whose direction runs with the trend because it continues it.

    The two opens are both 120.00, well inside §2.6's tolerance of 0.57 on a
    range of 19.00. The bullish side follows an *uptrend* here, which is the
    opposite of every reversal section in this group.
    """
    values = matched(two_candle.SEPARATING_LINES, SEPARATING_LINES_CASE)
    assert values["pat_separating_lines_dir"] == outputs.BULLISH

    # Opens 5.00 apart in a range of 14.00, past the tolerance of 0.42.
    opens_apart: Shape = (125.0, 137.0, 123.0, 135.0)
    not_matched(
        two_candle.SEPARATING_LINES,
        [*background(100.0), SEPARATING_FIRST, opens_apart],
    )


def test_separating_lines_ask_for_no_length_at_all() -> None:
    """Check that no long-body condition crept in from the neighbouring sections.

    Morris's rules carry none, and §7.3.8 says so. Both bars below have bodies of
    2.00 in ranges of 30.00 and 21.00, far under §2.1, and the section still
    holds because the two opens meet.
    """
    tiny_first: Shape = (120.0, 125.0, 95.0, 118.0)
    tiny_second: Shape = (120.0, 137.0, 116.0, 122.0)
    assert matched(
        two_candle.SEPARATING_LINES,
        [*background(100.0), tiny_first, tiny_second],
    )


# --- §7.3.9 Kicking and §7.3.10 Kicking by Length ----------------------------
#
# The two sections Morris marks `Trend Required: No`, so their series carry no
# filler at all and their first valid bar is index 1.

BLACK_MARUBOZU_20: Shape = (120.0, 121.0, 99.0, 100.0)
"""Body 20.00 in a range of 22.00 with shadows of 1.00, inside §2.5's 2.20."""

WHITE_MARUBOZU_20: Shape = (130.0, 151.0, 129.0, 150.0)
"""The same measurements the other way up, its body starting above 120.00."""

WHITE_MARUBOZU_30: Shape = (130.0, 161.0, 129.0, 160.0)
"""Body 30.00 in a range of 32.00: longer than the black bar it follows."""

BLACK_MARUBOZU_40: Shape = (140.0, 141.0, 99.0, 100.0)
"""Body 40.00 in a range of 42.00: longer than the white bar that follows it."""

WHITE_MARUBOZU_20_HIGH: Shape = (150.0, 171.0, 149.0, 170.0)
"""Body 20.00 opening above 140.00, so the bodies still gap apart."""

KICKING_CASE: list[Shape] = [BLACK_MARUBOZU_20, WHITE_MARUBOZU_20]


def test_kicking_reads_no_trend_and_needs_a_gap_between_the_bodies() -> None:
    """Check §7.3.9 with no filler in front of it at all.

    Two bars are the whole series, which only works because Morris marks this
    section `Trend Required: No` and §6 then puts warm-up at the span itself. The
    gap is §2.8's body gap: the white body starts at 130.00, above the black
    body's top of 120.00.
    """
    values = matched(two_candle.KICKING, KICKING_CASE)
    assert values["pat_kicking_dir"] == outputs.BULLISH

    # A white marubozu opening at 115.00 overlaps the black body and removes the
    # gap while leaving both bars marubozus.
    overlapping: Shape = (115.0, 136.0, 114.0, 135.0)
    not_matched(two_candle.KICKING, [BLACK_MARUBOZU_20, overlapping])

    # A second bar with shadows of 6.00 in a range of 32.00 is past §2.5's 3.20
    # and is no longer a marubozu, so §7.2.2's rule is what rejects it.
    shadowed: Shape = (130.0, 156.0, 124.0, 150.0)
    not_matched(two_candle.KICKING, [BLACK_MARUBOZU_20, shadowed])


def test_kicking_by_length_points_at_the_longer_body_and_not_at_the_gap() -> None:
    """Check §7.3.10's rule 2, the one direction rule in §7.3 that ignores the trend.

    Both series below are the *bullish* Kicking arrangement — black, then white,
    gapping up. When the white body is the longer one at 30.00 against 20.00 the
    two sections agree; when the black body is longer at 40.00 against 20.00 they
    disagree, and §7.3.10 reports bearish. That disagreement is the section's
    whole reason for existing.
    """
    values = matched(two_candle.KICKING_BY_LENGTH, [BLACK_MARUBOZU_20, WHITE_MARUBOZU_30])
    assert values["pat_kicking_by_length_dir"] == outputs.BULLISH

    black_is_longer = [BLACK_MARUBOZU_40, WHITE_MARUBOZU_20_HIGH]
    values = matched(two_candle.KICKING_BY_LENGTH, black_is_longer)
    assert values["pat_kicking_by_length_dir"] == outputs.BEARISH
    assert matched(two_candle.KICKING, black_is_longer)["pat_kicking_dir"] == outputs.BULLISH


def test_two_bodies_of_the_same_length_leave_kicking_by_length_undecided() -> None:
    """Check §7.3.10's rule 3, which the standard added rather than found.

    Both bodies are 20.00, so no side is longer and no direction can be read. The
    standard reports not-matched rather than picking a side, while §7.3.9 — which
    never asks — still holds on the same two bars.
    """
    not_matched(two_candle.KICKING_BY_LENGTH, KICKING_CASE)
    assert matched(two_candle.KICKING, KICKING_CASE)


def test_kicking_by_length_holds_only_where_kicking_already_does() -> None:
    """Record the containment §7.3.10 creates by building on §7.3.9's rules.

    Its rule 1 is §7.3.9 in full and its rule 3 only removes the tie, so the
    later section can never reach a bar the earlier one refused. The two can
    still disagree about *direction*, which is the whole point of §7.3.10, and
    the test above pins that case.
    """
    candles = series(LONG_SERIES)
    kicking = judge_series(two_candle.KICKING, candles)
    by_length = judge_series(two_candle.KICKING_BY_LENGTH, candles)

    for index, (short_form, long_form) in enumerate(zip(kicking, by_length, strict=True)):
        if long_form["pat_kicking_by_length"] == outputs.MATCHED:
            assert short_form["pat_kicking"] == outputs.MATCHED, f"index {index}"


# --- §7.3.11 Homing Pigeon and §7.3.12 Matching Low --------------------------

HOMING_PIGEON_SECOND: Shape = (120.0, 136.0, 104.0, 110.0)
"""Black, body 10.00 in a range of 32.00, contained inside 100.00 to 140.00."""

HOMING_PIGEON_CASE: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    HOMING_PIGEON_SECOND,
]

MATCHING_LOW_CASE: list[Shape] = [
    *background(DOWNTREND_FILLER),
    LONG_BLACK_FIRST,
    (115.0, 117.0, 98.0, 100.0),
]
"""A second black bar closing at exactly the first close of 100.00."""


def test_homing_pigeon_is_harami_with_the_two_days_sharing_a_colour() -> None:
    """Check §7.3.11 against §7.3.2, which it differs from in one rule.

    Both sections want a long first day, a short contained second, and a
    downtrend. Harami's rule 5 wants the second day to be the opposite colour and
    this section wants it black like the first, so the two can never hold on the
    same bars — reading either section's input through the other is what pins
    that.
    """
    values = matched(two_candle.HOMING_PIGEON, HOMING_PIGEON_CASE)
    assert values["pat_homing_pigeon_dir"] == outputs.BULLISH
    assert values["pat_homing_pigeon_strength"] == outputs.FULL_STRENGTH

    not_matched(two_candle.HARAMI, HOMING_PIGEON_CASE)
    not_matched(two_candle.HOMING_PIGEON, BULLISH_HARAMI)


def test_homing_pigeon_carries_the_boundary_strength_of_its_containment() -> None:
    """Check §4.2's extension: §4.1's relation reaches a section the sources left open.

    Morris never fixed the equality handling here, so §4.2 routes it to the one
    place the sources did speak. The second body's top sits at exactly the first
    body's top of 140.00, which §4.1 admits and §5.6 marks as a boundary match.
    """
    shared_top: Shape = (140.0, 145.0, 104.0, 132.0)
    values = matched(
        two_candle.HOMING_PIGEON,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, shared_top],
    )
    assert values["pat_homing_pigeon_strength"] == outputs.BOUNDARY_STRENGTH


def test_matching_low_needs_two_black_closes_within_the_doji_tolerance() -> None:
    """Check §7.3.12, and that Morris's narrower thousandth rule was not adopted.

    The second bar's range is 19.00, so §2.6 allows 0.57 between the two closes.
    A close of 100.50 is inside that and matches; 102.00 is outside and does not.
    Morris's alternative — within a thousandth of the first close, or 0.10 here —
    would reject the first of those, and §2.6 records why the standard uses the
    doji concept he himself directs it to.
    """
    values = matched(two_candle.MATCHING_LOW, MATCHING_LOW_CASE)
    assert values["pat_matching_low_dir"] == outputs.BULLISH

    inside_the_tolerance: Shape = (115.0, 117.0, 98.0, 100.5)
    assert matched(
        two_candle.MATCHING_LOW,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, inside_the_tolerance],
    )

    outside_the_tolerance: Shape = (115.0, 117.0, 98.0, 102.0)
    not_matched(
        two_candle.MATCHING_LOW,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, outside_the_tolerance],
    )


# --- §7.3.16 Stick Sandwich --------------------------------------------------

SANDWICH_BULLISH: list[Shape] = [
    *background(120.0),
    (120.0, 125.0, 95.0, 100.0),
    (106.0, 120.0, 105.0, 118.0),
    (115.0, 117.0, 98.0, 100.0),
]
"""Black closing at 100.00, white trading entirely above it, black closing there again.

The first bar's midpoint is 110.00 against filler at 120.00, so the trend is
down. The middle bar's low of 105.00 is above the first close. The third bar's
range is 19.00, so §2.6 allows 0.57 between the two closes and they are equal.
"""

SANDWICH_BEARISH: list[Shape] = [
    *background(100.0),
    (100.0, 125.0, 95.0, 120.0),
    (118.0, 119.0, 90.0, 95.0),
    (94.0, 122.0, 93.0, 120.0),
]
"""White, then a black bar opening at 118.00 under the first close of 120.00 and
closing at 95.00 under the first open of 100.00, then a white bar whose body from
94.00 to 120.00 engulfs the middle body from 95.00 to 118.00."""


def test_stick_sandwich_spans_three_bars_and_reads_the_trend_on_the_first() -> None:
    """Check §7.3.16's bullish side, whose span is what puts warm-up at 12."""
    values = matched(two_candle.STICK_SANDWICH, SANDWICH_BULLISH)
    assert values["pat_stick_sandwich_dir"] == outputs.BULLISH
    assert values["pat_stick_sandwich_strength"] == outputs.FULL_STRENGTH

    # The middle bar's low at 99.00 is below the first close of 100.00, which is
    # the one thing rule 3 measures.
    trades_below: list[Shape] = [
        *background(120.0),
        (120.0, 125.0, 95.0, 100.0),
        (106.0, 120.0, 99.0, 118.0),
        (115.0, 117.0, 98.0, 100.0),
    ]
    not_matched(two_candle.STICK_SANDWICH, trades_below)


def test_the_two_sides_of_stick_sandwich_share_no_rule() -> None:
    """Check §7.3.16's asymmetry, which the section attributes to Morris's text.

    The bearish side asks for an engulfment where the bullish side asks for two
    equal closes, and it never mentions matching closes at all. Because of that,
    §5.6's half strength can only ever appear on the bearish side.
    """
    values = matched(two_candle.STICK_SANDWICH, SANDWICH_BEARISH)
    assert values["pat_stick_sandwich_dir"] == outputs.BEARISH
    assert values["pat_stick_sandwich_strength"] == outputs.FULL_STRENGTH

    shared_bottom: list[Shape] = [*SANDWICH_BEARISH[:-1], (95.0, 122.0, 93.0, 120.0)]
    values = matched(two_candle.STICK_SANDWICH, shared_bottom)
    assert values["pat_stick_sandwich_strength"] == outputs.BOUNDARY_STRENGTH

    # The third body from 96.00 to 117.00 sits inside the middle body instead of
    # around it, so the bearish side's rule 4 fails.
    contained_instead: list[Shape] = [*SANDWICH_BEARISH[:-1], (96.0, 122.0, 93.0, 117.0)]
    not_matched(two_candle.STICK_SANDWICH, contained_instead)


# --- the sixteen as a registered catalog -------------------------------------

SECTION_MIN_HISTORY = {
    # Written out from each §7.3 section's own `min_history` line rather than
    # recomputed: thirteen two-bar trend patterns at 11, Stick Sandwich at 12 for
    # its third bar, and the two Kicking sections at 2 because they read no trend.
    "pat_engulfing": 11,
    "pat_harami": 11,
    "pat_harami_cross": 11,
    "pat_doji_star": 11,
    "pat_piercing": 11,
    "pat_dark_cloud_cover": 11,
    "pat_counterattack": 11,
    "pat_separating_lines": 11,
    "pat_kicking": 2,
    "pat_kicking_by_length": 2,
    "pat_homing_pigeon": 11,
    "pat_matching_low": 11,
    "pat_in_neck": 11,
    "pat_on_neck": 11,
    "pat_thrusting": 11,
    "pat_stick_sandwich": 12,
}

SECTION_RULES: dict[str, PatternRule] = {
    rule.name: rule
    for rule in (
        two_candle.ENGULFING,
        two_candle.HARAMI,
        two_candle.HARAMI_CROSS,
        two_candle.DOJI_STAR,
        two_candle.PIERCING,
        two_candle.DARK_CLOUD_COVER,
        two_candle.COUNTERATTACK,
        two_candle.SEPARATING_LINES,
        two_candle.KICKING,
        two_candle.KICKING_BY_LENGTH,
        two_candle.HOMING_PIGEON,
        two_candle.MATCHING_LOW,
        two_candle.IN_NECK,
        two_candle.ON_NECK,
        two_candle.THRUSTING,
        two_candle.STICK_SANDWICH,
    )
}

REGISTERED_SPECS: tuple[PatternSpec, ...] = tuple(
    spec for spec in DEFAULT_PATTERN_REGISTRY.list() if spec.name in SECTION_MIN_HISTORY
)

PATTERNS_REGISTERED_BEFORE = 17
"""§7.1's eleven and §7.2's six, the catalog `test_pattern_single_candle.py` owns."""


def test_the_registry_gained_exactly_the_sixteen_sections_of_seven_three() -> None:
    """Check the registered catalog against §8.1's third row and the earlier total."""
    assert len(REGISTERED_SPECS) == 16
    assert {spec.name for spec in REGISTERED_SPECS} == set(SECTION_MIN_HISTORY)
    # No pattern takes a parameter, so an identity is its bare name.
    assert {spec.identifier for spec in REGISTERED_SPECS} == set(SECTION_MIN_HISTORY)

    assert len(DEFAULT_PATTERN_REGISTRY.list()) == PATTERNS_REGISTERED_BEFORE + 16 + 18  # §7.4
    assert DEFAULT_PATTERN_REGISTRY.names() >= set(SECTION_MIN_HISTORY)


def test_each_section_warms_up_where_its_own_line_says() -> None:
    """Check §6's two formulas against the per-section values, not against itself.

    The interesting split is §8.3's: thirteen two-bar trend sections at 11, Stick
    Sandwich at 12, and the two Kicking sections at 2. Those last two are the
    only entries in Morris's 89 headers marked `Trend Required: No` outside the
    candle lines, and §6's trendless formula is what turns that into a warm-up of
    the span alone.
    """
    assert {spec.name: spec.min_history for spec in REGISTERED_SPECS} == SECTION_MIN_HISTORY

    counted = sorted(SECTION_MIN_HISTORY.values())
    assert counted.count(2) == 2
    assert counted.count(11) == 13
    assert counted.count(12) == 1


def test_the_indicator_tally_is_untouched_by_this_change() -> None:
    """Check that registering sixteen more patterns moved nothing in the other registry."""
    indicator_names = {spec.name for spec in DEFAULT_REGISTRY.list()}
    assert indicator_names.isdisjoint(DEFAULT_PATTERN_REGISTRY.names())
    assert all(not name.startswith(outputs.NAME_PREFIX) for name in indicator_names)


CONFIRMATION_GRADES = {
    # Read off each section's own `확인` header line. `None` is a grade of `No` on
    # both sides, and a direction is a section graded on that side and `No` on
    # the other, which §5.5 says computes a confirmation on the graded side only.
    "pat_engulfing": "both",  # Suggested bullish, Required bearish
    "pat_harami": outputs.BEARISH,  # No bullish, Required bearish
    "pat_harami_cross": outputs.BEARISH,  # No bullish, Required bearish
    "pat_doji_star": outputs.BEARISH,  # No bullish, Suggested bearish
    "pat_piercing": "both",  # Suggested, and the section is bullish only
    "pat_dark_cloud_cover": "both",  # Required, and the section is bearish only
    "pat_counterattack": "both",  # Suggested bullish, Required bearish
    "pat_separating_lines": outputs.BEARISH,  # No bullish, Required bearish
    "pat_kicking": "both",  # Required, ungraded by direction
    "pat_kicking_by_length": "both",  # Required, ungraded by direction
    "pat_homing_pigeon": None,  # No
    "pat_matching_low": None,  # No
    "pat_in_neck": "both",  # Required on both sides
    "pat_on_neck": outputs.BEARISH,  # Required bearish, No bullish
    "pat_thrusting": outputs.BEARISH,  # Suggested bearish, No bullish
    "pat_stick_sandwich": outputs.BEARISH,  # No bullish, Suggested bearish
}


def test_confirmation_is_computed_only_where_a_source_graded_it() -> None:
    """Check §5.5's two grade conventions against all sixteen header lines.

    §5.5 rules that a grade of `No` means no confirmation is computed rather than
    one computed and ignored, and that a section graded differently on its two
    sides computes one on the graded side alone. So the wiring splits three ways
    and this table is the whole of it: seven sections on the general rule, seven
    on the bearish side only, and two on nothing.
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
    assert counted.count("both") == 7
    assert counted.count(outputs.BEARISH) == 7
    assert counted.count(None) == 2


def test_an_ungraded_side_leaves_the_confirmation_key_down() -> None:
    """Check §5.5's direction convention on live bars rather than on the wiring.

    §7.3.2 Harami is graded `No` bullish and `Required` bearish. The bullish
    match below closes at 120.00 and the bar after it closes at 130.00, which
    would satisfy the general close comparison; the key stays at 0.0 anyway,
    because no source asked for a confirmation on that side. The bearish match
    then shows the other half of the same rule working normally.
    """
    rising: Shape = (120.0, 132.0, 119.0, 130.0)
    values = run(two_candle.HARAMI, [*BULLISH_HARAMI, rising])
    assert values[-2]["pat_harami"] == outputs.MATCHED
    assert values[-2]["pat_harami_dir"] == outputs.BULLISH
    assert values[-1]["pat_harami_confirm"] == outputs.NOT_MATCHED

    bearish_harami: list[Shape] = [
        *background(UPTREND_FILLER),
        LONG_WHITE_FIRST,
        (120.0, 136.0, 104.0, 110.0),
    ]
    falling: Shape = (110.0, 111.0, 98.0, 100.0)
    values = run(two_candle.HARAMI, [*bearish_harami, falling])
    assert values[-2]["pat_harami"] == outputs.MATCHED
    assert values[-2]["pat_harami_dir"] == outputs.BEARISH
    assert values[-1]["pat_harami_confirm"] == outputs.MATCHED


def test_the_bullish_doji_star_is_not_confirmed_and_the_bearish_one_is() -> None:
    """Check the same convention on §7.3.4, whose two sides are graded apart.

    Graded `No` bullish and `Suggested` bearish. The bullish star closes at 80.00
    and a following close of 95.00 leaves the key down; the bearish star closes
    at 160.00 and a following close of 150.00 raises it.
    """
    rising: Shape = (80.0, 96.0, 79.0, 95.0)
    values = run(two_candle.DOJI_STAR, [*BULLISH_DOJI_STAR, rising])
    assert values[-2]["pat_doji_star_dir"] == outputs.BULLISH
    assert values[-1]["pat_doji_star_confirm"] == outputs.NOT_MATCHED

    falling: Shape = (160.0, 161.0, 148.0, 150.0)
    values = run(two_candle.DOJI_STAR, [*BEARISH_DOJI_STAR, falling])
    assert values[-2]["pat_doji_star_dir"] == outputs.BEARISH
    assert values[-1]["pat_doji_star_confirm"] == outputs.MATCHED


def test_the_two_ungraded_sections_never_raise_the_confirmation_key() -> None:
    """Check §5.5's `No` convention over a whole series, not just one bar pair.

    §7.3.11 and §7.3.12 both match in the long series and both point bullish, so
    a confirmation computed from the direction alone would fire somewhere in it.
    Neither key ever leaves 0.0.
    """
    candles = series(LONG_SERIES)
    for name in ("pat_homing_pigeon", "pat_matching_low"):
        rule = SECTION_RULES[name]
        values = judge_series(rule, candles)[rule.min_history - 1 :]
        assert any(value[name] == outputs.MATCHED for value in values), name
        assert all(value[f"{name}_confirm"] == outputs.NOT_MATCHED for value in values), name


# --- warm-up, the two paths, and degenerate bars, over every section ----------

MATCHING_CASES: dict[str, list[Shape]] = {
    # One hand-built series per section, each holding on its last bar.
    "pat_engulfing": BULLISH_ENGULFING,
    "pat_harami": BULLISH_HARAMI,
    "pat_harami_cross": BULLISH_HARAMI_CROSS,
    "pat_doji_star": BULLISH_DOJI_STAR,
    "pat_piercing": neckline_case(PIERCING_CLOSE),
    "pat_dark_cloud_cover": DARK_CLOUD_COVER_CASE,
    "pat_counterattack": COUNTERATTACK_CASE,
    "pat_separating_lines": SEPARATING_LINES_CASE,
    "pat_kicking": KICKING_CASE,
    "pat_kicking_by_length": [BLACK_MARUBOZU_20, WHITE_MARUBOZU_30],
    "pat_homing_pigeon": HOMING_PIGEON_CASE,
    "pat_matching_low": MATCHING_LOW_CASE,
    "pat_in_neck": neckline_case(IN_NECK_CLOSE),
    "pat_on_neck": neckline_case(ON_NECK_CLOSE),
    "pat_thrusting": neckline_case(THRUSTING_CLOSE),
    "pat_stick_sandwich": SANDWICH_BULLISH,
}

LONG_SERIES: list[Shape] = [
    *[shape for case in MATCHING_CASES.values() for shape in case],
    *BEARISH_ENGULFING,
    *BEARISH_DOJI_STAR,
    *SANDWICH_BEARISH,
    *background(150.0, count=12),
]
"""Every hand-built case laid end to end, plus two bearish sides and a quiet tail.

The trend average runs continuously across the whole thing rather than being
restarted per case, so the blocks do not each reproduce the verdict they produce
in isolation. That is the point: this series exists to drive the two execution
paths over a long, varied input, and the per-section claims are made on the cases
themselves.
"""


@pytest.mark.parametrize("name", sorted(MATCHING_CASES), ids=lambda name: name)
def test_every_section_matches_on_its_own_hand_built_case(name: str) -> None:
    """Check that all sixteen are reachable, one hand-built series each.

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
    """Check §5.3: NaN before `min_history - 1`, a finite number from there on.

    The boundary index is the interesting one, and an off-by-one in either
    direction is the failure §6's derivation exists to prevent.
    """
    candles = series(LONG_SERIES)
    values = spec.compute_vectorized(candles)
    boundary = spec.min_history - 1

    for index in range(boundary):
        assert all(isnan(value) for value in values[index].values()), f"index {index}"
    assert all(not isnan(value) for later in values[boundary:] for value in later.values())


def test_the_two_trendless_sections_start_ten_bars_before_the_others() -> None:
    """Check the warm-up split §8.3 draws, on one series, index by index.

    Twelve bars carry all three lengths at once. Kicking and Kicking by Length
    answer from index 1, because §6 gives a trendless pattern its span and
    nothing more. The two-bar trend sections stay NaN until index 10, because
    their first day needs a ten-period average that first exists at index 9.
    Stick Sandwich waits one further, to index 11, because its first day is two
    bars behind the bar being judged rather than one.
    """
    candles = series([*background(130.0), LONG_BLACK_FIRST, HARAMI_SECOND, HOMING_PIGEON_SECOND])
    assert len(candles) == 12

    first_finite = {}
    for name, rule in SECTION_RULES.items():
        values = judge_series(rule, candles)
        first_finite[name] = next(
            index for index, value in enumerate(values) if not isnan(value[name])
        )

    assert first_finite["pat_kicking"] == 1
    assert first_finite["pat_kicking_by_length"] == 1
    assert first_finite["pat_engulfing"] == 10
    assert first_finite["pat_harami"] == 10
    assert first_finite["pat_stick_sandwich"] == 11
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

    A four-price bar is a doji by arithmetic — its body is zero — and §7.3.4's
    remaining rules would let it through as the star. §2.7 keeps such a bar out
    of every judgment, and the scales themselves answer False on it as well, so
    both of the standard's two defences are in play here.
    """
    four_price_bar: Shape = (80.0, 80.0, 80.0, 80.0)
    candle = series([four_price_bar])[0]
    assert primitives.body(candle) == 0.0
    assert not scales.doji(candle)

    values = not_matched(
        two_candle.DOJI_STAR,
        [*background(DOWNTREND_FILLER), LONG_BLACK_FIRST, four_price_bar],
    )
    assert values["pat_doji_star_dir"] == outputs.DIRECTIONLESS


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


# --- §5.4 and §5.5: where a confirmation is written --------------------------


def test_a_confirmation_lands_on_the_bar_after_the_match() -> None:
    """Check §5.4 on a bullish section: the key rises on the later bar, not the match.

    The engulfing bar closes at 142.00, so a following close of 150.00 confirms
    it. Writing that back onto the engulfing bar would make the value at index
    `t` depend on a candle after `t`.
    """
    following: Shape = (142.0, 152.0, 141.0, 150.0)
    values = run(two_candle.ENGULFING, [*BULLISH_ENGULFING, following])

    assert values[-2]["pat_engulfing"] == outputs.MATCHED
    assert values[-2]["pat_engulfing_confirm"] == outputs.NOT_MATCHED
    assert values[-1]["pat_engulfing"] == outputs.NOT_MATCHED
    assert values[-1]["pat_engulfing_confirm"] == outputs.MATCHED


def test_a_confirmation_has_to_run_the_way_the_match_pointed() -> None:
    """Check §5.5's general rule on a `Required` bearish section.

    Dark Cloud Cover closes at 110.00 and points down, so only a lower close
    confirms it. A higher one leaves the key at 0.0 for the whole one-bar
    deadline, which is what §5.5 means by the deadline closing.
    """
    lower: Shape = (110.0, 111.0, 98.0, 100.0)
    values = run(two_candle.DARK_CLOUD_COVER, [*DARK_CLOUD_COVER_CASE, lower])
    assert values[-2]["pat_dark_cloud_cover_dir"] == outputs.BEARISH
    assert values[-1]["pat_dark_cloud_cover_confirm"] == outputs.MATCHED

    higher: Shape = (110.0, 125.0, 109.0, 120.0)
    values = run(two_candle.DARK_CLOUD_COVER, [*DARK_CLOUD_COVER_CASE, higher])
    assert values[-1]["pat_dark_cloud_cover_confirm"] == outputs.NOT_MATCHED


def test_a_confirmation_is_not_retroactive_past_its_one_bar_deadline() -> None:
    """Check §5.5's deadline: a move on the second bar after the match is too late."""
    flat: Shape = (142.0, 143.0, 138.0, 140.0)
    much_higher: Shape = (140.0, 200.0, 139.0, 190.0)
    values = run(two_candle.ENGULFING, [*BULLISH_ENGULFING, flat, much_higher])

    assert values[-3]["pat_engulfing"] == outputs.MATCHED
    assert values[-2]["pat_engulfing_confirm"] == outputs.NOT_MATCHED
    assert values[-1]["pat_engulfing_confirm"] == outputs.NOT_MATCHED


def test_a_degenerate_bar_cannot_confirm_the_match_before_it() -> None:
    """Check §5.5's degenerate-confirmation rule on a trendless section.

    The bar after the kicking pair has all four prices at 160.00, above the white
    marubozu's close of 150.00, so the plain close comparison would confirm.
    §5.5 refuses it for the reason §2.7 gives: a bar the standard will not judge
    on is not one it will take a confirmation from. Neither of §2.7's two guards
    reaches this bar, because it sits outside the judgment window.
    """
    degenerate: Shape = (160.0, 160.0, 160.0, 160.0)
    values = run(two_candle.KICKING, [*KICKING_CASE, degenerate])
    assert values[-2]["pat_kicking"] == outputs.MATCHED
    assert values[-1]["pat_kicking_confirm"] == outputs.NOT_MATCHED

    barely_alive: Shape = (160.0, 160.01, 160.0, 160.0)
    values = run(two_candle.KICKING, [*KICKING_CASE, barely_alive])
    assert values[-1]["pat_kicking_confirm"] == outputs.MATCHED
