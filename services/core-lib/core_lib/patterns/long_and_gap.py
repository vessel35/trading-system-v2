"""Implement §7.5 of the pattern standard: the long forms and the gap continuations.

Ten sections, and the group is named for both halves of §7.5's own title. Five
span four bars or more — §7.5.1 through §7.5.5 — and four of the remaining five
span three, held here rather than in §7.4 because their subject is a gap that the
market then trades back into. §7.5.9 Hikkake belongs to neither half and to this
group only because §7.5 is where the standard put it: it is not a Japanese
candlestick pattern at all, and its source ignores the real body entirely.

Four things separate this group from the three before it.

**The span is not always a fixed number.** §7.5.5 Rising/Falling Three Methods
admits two to five small candles between its two long ones, so its window runs
from four bars to seven. `judgment.py` offers a rule its admissible spans
shortest first and takes the first that holds, which is §7.5.5's own convention
for the case where several would: the smallest `n` is adopted so that one bar
never reports the pattern twice. §6 takes the shortest form for the warm-up as
well, which is why `min_history` is 13 and not 16 — the section states outright
that the number means something slightly different here, since index 12 can only
be asked about `n = 2` and index 15 is the first bar where all five forms are
judged.

**Two sections carry a three-bar confirmation deadline.** §5.5 leaves the general
deadline at one bar and names Chesler's three for the two Hikkake sections alone.
Those two also carry their own confirmation *content*: the price moving past the
inside bar's high or low, which is not the closing comparison every other section
takes from §5.5.

**Warm-up splits four ways here** where the earlier groups split two. Eight
sections require §3's prior trend and land at 12, 13, or 14 by their span. The
two Hikkake sections require none, so §6's other formula applies and their
warm-up is the span itself — 3 and 4. Nothing below declares any of those
numbers; §6 derives each from the span and the trend flag.

**Confirmation.** §5.5 computes one only where a source graded one, so this group
splits the same three ways the earlier ones did. Four sections take the general
rule outright, four are graded on their bearish side and `No` on their bullish
one, §7.5.3 Ladder Bottom is graded `No` and computes nothing, and the two
Hikkake sections replace the general rule with the one their source states.

The four keys, the degenerate gate, warm-up, the span loop, and the placement of
confirmations are not here. `judgment.py` holds them once for all sixty-one
patterns.

Section numbers in this module are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

from collections.abc import Callable, Sequence

from core_lib.types import Candle

from . import scales
from .judgment import (
    CONFIRMS_BEARISH_SIDE_ONLY,
    Match,
    PatternRule,
    confirms_by_close_direction,
)
from .outputs import BEARISH, BULLISH
from .primitives import (
    body_bottom,
    body_top,
    candle_range,
    gap_down_body,
    gap_up_body,
    is_black,
    is_white,
)
from .trend import DOWNTREND, UPTREND

ColourTest = Callable[[Candle], bool]
"""§1.2's two colour predicates, held in a variable where a rule picks between them."""


def _opens_inside_the_body(body_bar: Candle, opening_bar: Candle) -> bool:
    """Return whether a bar opened strictly within another bar's real body.

    §7.5.7 and §7.5.8 both ask their third bar to open inside the second body,
    and §4.2 makes the two comparisons strict: "inside" is a size comparison, and
    the one place the sources fixed an equality — §4.1's engulfment and
    containment — is a different relation with its own rule.
    """
    return body_bottom(body_bar) < opening_bar.open < body_top(body_bar)


# --- §7.5.1 Three-Line Strike -----------------------------------------------


def _judge_three_line_strike(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.5.1: three bars extending the trend, then one bar undoing them all.

    Morris's rule section says only "three days resembling Three White Soldiers",
    and the passage before it is specific, so decision C adopts the passage: three
    white days with consecutively higher highs, then a long black day that opens
    at a new high and falls below the first white day's low.

    The bearish side is not the exact mirror and §7.5.1 says to leave it that way.
    Where the bullish side asks the fourth day to close under the first day's
    *open*, Morris writes the bearish side as closing "above the high of the first
    black day", so this one comparison reads the high on that side.

    The pattern is a continuation, so the direction follows the trend rather than
    the fourth bar's colour: three white bars and a long black one after an
    advance are a bullish sign here, which is the reading that surprises.
    """
    first, second, third, last = window
    if trend == UPTREND:
        direction = BULLISH
        three_extend_the_trend: ColourTest = is_white
        stepped_further = second.high > first.high and third.high > second.high
        last_has_the_opposite_colour = is_black(last)
        opened_beyond_the_third = last.open > third.high
        reached_past_the_first = last.low < first.low and last.close < first.open
    elif trend == DOWNTREND:
        direction = BEARISH
        three_extend_the_trend = is_black
        stepped_further = second.low < first.low and third.low < second.low
        last_has_the_opposite_colour = is_white(last)
        opened_beyond_the_third = last.open < third.low
        reached_past_the_first = last.high > first.high and last.close > first.high
    else:
        return None
    if not all(three_extend_the_trend(candle) for candle in (first, second, third)):
        return None
    if not stepped_further:
        return None
    if not (last_has_the_opposite_colour and scales.long_body(last)):
        return None
    if not opened_beyond_the_third:
        return None
    if not reached_past_the_first:
        return None
    return Match(direction)


THREE_LINE_STRIKE = PatternRule(
    name="pat_three_line_strike",
    bar_count=4,
    requires_trend=True,
    judge=_judge_three_line_strike,
    confirm=CONFIRMS_BEARISH_SIDE_ONLY,
)
"""§7.5.1 `CDL3LINESTRIKE`. Trend required, directional, min_history 13.

Graded `No` on the bullish side and `Suggested` on the bearish one, so §5.5
computes a confirmation only for a bearish match.
"""


# --- §7.5.2 Breakaway --------------------------------------------------------


def _judge_breakaway(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.5.2: a gap opening a five-bar run that a reversal closes back into.

    The bearish side is Morris's own invention and he says so — the Japanese
    literature has no bearish Breakaway — but it is his rule section all the same,
    so both sides are carried.

    Rule 4 asks the third and fourth bars for falling closes and not for a colour.
    Morris writes that condition with "It is better if", which is a recommendation
    rather than a requirement, and decision C keeps a recommendation out of the
    rules.

    The span is fixed at five bars. Morris's flexibility section allows more or
    fewer days after the gap, and §7.5.2 leaves that as commentary because his
    rule section is the norm; fixing it is also what settles the warm-up and the
    state's bound.
    """
    first, second, third, fourth, last = window
    if trend == DOWNTREND:
        direction = BULLISH
        two_have_the_trend_colour = is_black(first) and is_black(second)
        gapped_with_the_trend = gap_down_body(first, second)
        the_middle_carried_on = third.close < second.close and fourth.close < third.close
        last_has_the_opposite_colour = is_white(last)
        closes_inside_the_gap = body_top(second) < last.close < body_bottom(first)
    elif trend == UPTREND:
        direction = BEARISH
        two_have_the_trend_colour = is_white(first) and is_white(second)
        gapped_with_the_trend = gap_up_body(first, second)
        the_middle_carried_on = third.close > second.close and fourth.close > third.close
        last_has_the_opposite_colour = is_black(last)
        closes_inside_the_gap = body_bottom(second) > last.close > body_top(first)
    else:
        return None
    if not (two_have_the_trend_colour and scales.long_body(first)):
        return None
    if not gapped_with_the_trend:
        return None
    if not the_middle_carried_on:
        return None
    if not (last_has_the_opposite_colour and scales.long_body(last)):
        return None
    if not closes_inside_the_gap:
        return None
    return Match(direction)


BREAKAWAY = PatternRule(
    name="pat_breakaway",
    bar_count=5,
    requires_trend=True,
    judge=_judge_breakaway,
    confirm=confirms_by_close_direction,
)
"""§7.5.2 `CDLBREAKAWAY`. Trend required, directional, min_history 14.

Graded `Suggested` on both sides, so one key serves them both.
"""


# --- §7.5.3 Ladder Bottom ----------------------------------------------------


def _judge_ladder_bottom(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.5.3: a decline of long black bars that grows a tail and then turns.

    Morris alone describes it; Nison's second edition has no entry. Rule 3 is the
    one place in the whole standard where a scale is read *negatively*: the fourth
    bar must have an upper shadow, which §7.5.3 renders as the negation of §2.5.
    That is why §2.7 puts its degenerate gate on the window before any rule is
    looked at — a four-price bar makes §2.5 answer False, and a negated False
    would count as a satisfied condition. The gate is in `judgment.py` and this
    rule does not re-check the window.

    §2.5's threshold is what "has an upper shadow" means here: more than a tenth
    of the range. Morris gives no size, and reading it as `US > 0` would let
    floating-point noise through.
    """
    first, second, third, fourth, last = window
    if trend != DOWNTREND:
        return None
    if not all(is_black(candle) and scales.long_body(candle) for candle in (first, second, third)):
        return None
    if not (second.open < first.open and third.open < second.open):
        return None
    if not (second.close < first.close and third.close < second.close):
        return None
    if not (is_black(fourth) and not scales.no_upper_shadow(fourth)):
        return None
    if not (is_white(last) and last.open > body_top(fourth)):
        return None
    return Match(BULLISH)


LADDER_BOTTOM = PatternRule(
    name="pat_ladder_bottom",
    bar_count=5,
    requires_trend=True,
    judge=_judge_ladder_bottom,
)
"""§7.5.3 `CDLLADDERBOTTOM`. Downtrend, bullish, min_history 14.

Graded `No`, so §5.5 computes no confirmation at all and `_confirm` stays at 0.0
for the whole series.
"""


# --- §7.5.4 Mat Hold ---------------------------------------------------------


def _judge_mat_hold(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.5.4: a long bar, three small ones drifting back, then a break out.

    Morris's rule section describes the bullish side qualitatively — "almost a
    starlike day" — and his commentary is specific, so decision C adopts the
    commentary. The bearish side is already specific in the rule section and is
    used as it stands, mirrored.

    Rule 6 is where the two readings differ and §7.5.4 chose the narrower one.
    The rule section asks the fifth day for a new closing high; the commentary
    asks it to close above the highest high of the three black days, which is
    harder to reach.

    TA-Lib's `penetration` parameter of 0.5 has no source behind it and is not
    used. §7.5.4 says so outright, and decision A forbids inheriting that table.
    """
    first, second, third, fourth, last = window
    if trend == UPTREND:
        direction = BULLISH
        first_has_the_trend_colour = is_white(first)
        gapped_with_the_trend = gap_up_body(first, second)
        three_oppose_the_trend: ColourTest = is_black
        the_fourth_went_further = fourth.close < third.close
        stayed_inside_the_first_range = fourth.low >= first.low
        last_has_the_trend_colour = is_white(last)
        broke_past_the_three = last.close > max(second.high, third.high, fourth.high)
    elif trend == DOWNTREND:
        direction = BEARISH
        first_has_the_trend_colour = is_black(first)
        gapped_with_the_trend = gap_down_body(first, second)
        three_oppose_the_trend = is_white
        the_fourth_went_further = fourth.close > third.close
        stayed_inside_the_first_range = fourth.high <= first.high
        last_has_the_trend_colour = is_black(last)
        broke_past_the_three = last.close < min(second.low, third.low, fourth.low)
    else:
        return None
    if not (first_has_the_trend_colour and scales.long_body(first)):
        return None
    if not (three_oppose_the_trend(second) and gapped_with_the_trend):
        return None
    # The third bar digs into the first body, which is the same relation on both
    # sides: strictly between the two body ends, by §4.2.
    if not (three_oppose_the_trend(third) and body_bottom(first) < third.close < body_top(first)):
        return None
    if not (three_oppose_the_trend(fourth) and scales.short_body(fourth)):
        return None
    if not (the_fourth_went_further and stayed_inside_the_first_range):
        return None
    if not (last_has_the_trend_colour and broke_past_the_three):
        return None
    return Match(direction)


MAT_HOLD = PatternRule(
    name="pat_mat_hold",
    bar_count=5,
    requires_trend=True,
    judge=_judge_mat_hold,
    confirm=CONFIRMS_BEARISH_SIDE_ONLY,
)
"""§7.5.4 `CDLMATHOLD`. Trend required, directional, min_history 14.

Graded `No` bullish and `Suggested` bearish, so only a bearish match computes one.
"""


# --- §7.5.5 Rising / Falling Three Methods -----------------------------------


def _judge_rise_fall_three_methods(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.5.5: a long bar, `n` small ones held inside it, then a longer one.

    The only section whose window is not a fixed length. Nison closes the count
    himself — "two and up to five small real bodies work fine" — so `n` runs from
    two to five and the window from four bars to seven. `judgment.py` calls this
    rule once per admissible span, shortest first, and stops at the first match;
    the window it hands over is exactly the span being asked about, so `n` here is
    `len(window) - 2` and never has to be passed separately.

    Rule 3 asks the middle bars for no colour. Morris writes "It is best if they
    are opposite in color", which is a recommendation, and decision C keeps
    recommendations out of the rules. Rule 4 is the condition that makes them a
    pause rather than a reversal: each stays inside the first bar's high-low
    range, which Morris fixes in as many words.

    "A strong day" in rule 5 is §2.1's long body. The sources give no number for
    it, and §7.5.5 records taking the nearest scale the standard already had
    rather than inventing an eighth.
    """
    first, last = window[0], window[-1]
    middles = window[1:-1]
    if trend == UPTREND:
        direction = BULLISH
        has_the_trend_colour: ColourTest = is_white
        carried_the_trend_on = last.close > first.close
    elif trend == DOWNTREND:
        direction = BEARISH
        has_the_trend_colour = is_black
        carried_the_trend_on = last.close < first.close
    else:
        return None
    if not (has_the_trend_colour(first) and scales.long_body(first)):
        return None
    if not all(scales.short_body(candle) for candle in middles):
        return None
    if not all(candle.high <= first.high and candle.low >= first.low for candle in middles):
        return None
    if not (has_the_trend_colour(last) and scales.long_body(last)):
        return None
    if not carried_the_trend_on:
        return None
    return Match(direction)


RISE_FALL_THREE_METHODS = PatternRule(
    name="pat_rise_fall_three_methods",
    bar_count=4,
    requires_trend=True,
    judge=_judge_rise_fall_three_methods,
    confirm=CONFIRMS_BEARISH_SIDE_ONLY,
    longest_bar_count=7,
)
"""§7.5.5 `CDLRISEFALL3METHODS`. Trend required, directional, min_history 13.

The one section admitting a range of spans: four bars at `n = 2` and seven at
`n = 5`. §6 takes the shortest for the warm-up on purpose — §7.5.5 states that
warming up at 16 instead would discard the `n = 2` forms that do hold at indexes
12 through 15, and that losing those is worse than a warm-up whose meaning is
uniform.

Graded `No` on the Rising side and `Suggested` on the Falling one, so only a
bearish match computes a confirmation.
"""


# --- §7.5.6 Up/Down-gap Side-by-side White Lines -----------------------------


def _judge_gap_side_by_side_white(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.5.6: two white bars opening level with each other after a gap.

    The two sources give the opening condition different widths — Nison writes
    "the same open" and Morris "at about the same price" — and decision C takes
    the narrower, so §2.6's `Equal` applies rather than its wider `Near`.

    Both bars stay white on the down-gap side. That is Nison's own point: side by
    side white lines in a downtrend are read as bearish in spite of their colour,
    so the mirror turns the gap and the trend over and leaves the colours alone.

    The gap is the one between real bodies. No source says which kind, so §2.8's
    convention applies, and this section is one of the five that convention was
    written for.
    """
    first, second, last = window
    if trend == UPTREND:
        direction = BULLISH
        gapped_with_the_trend = gap_up_body(first, second)
    elif trend == DOWNTREND:
        direction = BEARISH
        gapped_with_the_trend = gap_down_body(first, second)
    else:
        return None
    if not gapped_with_the_trend:
        return None
    if not (is_white(second) and is_white(last)):
        return None
    if not scales.equal(last.open, second.open, last):
        return None
    if not scales.similar_body(second, last):
        return None
    return Match(direction)


GAP_SIDE_BY_SIDE_WHITE = PatternRule(
    name="pat_gap_side_by_side_white",
    bar_count=3,
    requires_trend=True,
    judge=_judge_gap_side_by_side_white,
    confirm=confirms_by_close_direction,
)
"""§7.5.6 `CDLGAPSIDESIDEWHITE`. Trend required, directional, min_history 12.

Graded `Suggested` on the up-gap side and `Required` on the down-gap one. Both
sides carry a grade, so §5.5's general rule applies to each.
"""


# --- §7.5.7 Tasuki Gap -------------------------------------------------------


def _judge_tasuki_gap(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.5.7: a gap, then an opposite bar that reaches into it without closing it.

    Nison adds two conditions to Morris's rules and decision C takes both. The
    two candles of the tasuki are of about the same size, which is §2.6's
    `SimilarBody`; and the third bar's close is "the fight point", so a close past
    the far side of the window voids the pattern rather than deepening it. Rule 5
    is that pair of bounds: the close comes back into the gap and stops there.

    The gap is between real bodies, which the sources state, so §2.8 is not
    reached here.
    """
    first, second, last = window
    if trend == UPTREND:
        direction = BULLISH
        two_have_the_trend_colour = is_white(first) and is_white(second)
        gapped_with_the_trend = gap_up_body(first, second)
        last_has_the_opposite_colour = is_black(last)
        closed_back_into_the_gap = body_top(first) < last.close < body_bottom(second)
    elif trend == DOWNTREND:
        direction = BEARISH
        two_have_the_trend_colour = is_black(first) and is_black(second)
        gapped_with_the_trend = gap_down_body(first, second)
        last_has_the_opposite_colour = is_white(last)
        closed_back_into_the_gap = body_top(second) < last.close < body_bottom(first)
    else:
        return None
    if not (two_have_the_trend_colour and gapped_with_the_trend):
        return None
    if not scales.similar_body(first, second):
        return None
    if not (last_has_the_opposite_colour and _opens_inside_the_body(second, last)):
        return None
    if not closed_back_into_the_gap:
        return None
    return Match(direction)


TASUKI_GAP = PatternRule(
    name="pat_tasuki_gap",
    bar_count=3,
    requires_trend=True,
    judge=_judge_tasuki_gap,
    confirm=confirms_by_close_direction,
)
"""§7.5.7 `CDLTASUKIGAP`. Trend required, directional, min_history 12.

Graded `Suggested` on the upward side and `Required` on the downward one, so both
sides compute a confirmation.
"""


# --- §7.5.8 Upside / Downside Gap Three Methods ------------------------------


def _judge_gap_three_methods(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.5.8: the same gap as §7.5.7, filled by the third bar instead.

    Morris's commentary is what fixes the third day, so decision C adopts it: the
    bar opens inside the second body and closes inside the first, bridging the
    two, which is what makes it the opposite colour of both.

    That last condition is what separates this section from §7.5.7 and the two
    exclude each other. A tasuki close stops inside the window — above the first
    body's top on the upward side — and this section's close goes past it, into
    the first body. No bar can do both.
    """
    first, second, last = window
    if trend == UPTREND:
        direction = BULLISH
        two_have_the_trend_colour = is_white(first) and is_white(second)
        gapped_with_the_trend = gap_up_body(first, second)
        last_has_the_opposite_colour = is_black(last)
    elif trend == DOWNTREND:
        direction = BEARISH
        two_have_the_trend_colour = is_black(first) and is_black(second)
        gapped_with_the_trend = gap_down_body(first, second)
        last_has_the_opposite_colour = is_white(last)
    else:
        return None
    if not (two_have_the_trend_colour and scales.long_body(first) and scales.long_body(second)):
        return None
    if not gapped_with_the_trend:
        return None
    if not (last_has_the_opposite_colour and _opens_inside_the_body(second, last)):
        return None
    if not body_bottom(first) < last.close < body_top(first):
        return None
    return Match(direction)


GAP_THREE_METHODS = PatternRule(
    name="pat_gap_three_methods",
    bar_count=3,
    requires_trend=True,
    judge=_judge_gap_three_methods,
    confirm=CONFIRMS_BEARISH_SIDE_ONLY,
)
"""§7.5.8 `CDLXSIDEGAP3METHODS`. Trend required, directional, min_history 12.

Graded `No` on the Upside form and `Required` on the Downside one, so §5.5
computes a confirmation only for a bearish match.
"""


# --- §7.5.9 Hikkake and §7.5.10 Modified Hikkake -----------------------------


def _confirms_hikkake(window: Sequence[Candle], direction: float, following: Candle) -> bool:
    """Apply the confirmation Chesler states for both Hikkake sections (§5.5).

    Not §5.5's general close comparison. The source names the event itself: on a
    bullish setup the price moves above the inside bar's high, and on a bearish
    one below its low. It is the bar's own extreme that is compared, because the
    condition is about the price trading through a level rather than about where
    the bar settles, and §5.5 lists this among the four places a source gave both
    the content and the deadline.

    The inside bar is the second-to-last bar of either window: `t - 1` in the
    basic section's three and in the modified section's four alike. §4.2 makes the
    comparison strict, as a size comparison.
    """
    inside = window[-2]
    if direction == BULLISH:
        return following.high > inside.high
    if direction == BEARISH:
        return following.low < inside.low
    return False


CONFIRM_WITHIN_THREE_BARS = 3
"""§5.5, from Chesler: the two Hikkake sections confirm within three bars or not at all."""


def _judge_hikkake(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.5.9: an inside bar, then a break out of it that goes nowhere.

    Chesler's pattern is a western one — he calls "inside day false breakout" the
    correct name for it — and it reads only the highs and the lows. The open and
    the close are not used anywhere in this section, which is why no scale of §2
    appears in it and why §7.5.9's "what we chose" note reads: nothing.

    Rule 2's polarity is the thing to get wrong. The *bullish* setup is the one
    whose third bar breaks *below* the inside bar, because the pattern trades the
    failure of that break. A bar clearing the inside bar upward is the bearish
    setup.

    Both comparisons on each side must hold: rule 1 asks for an inside bar by two
    strict inequalities, and rule 2 asks the third bar for a lower high *and* a
    lower low. A third bar engulfing the inside bar's range answers neither side
    and is no match.
    """
    context, inside, setup = window
    if not (inside.high < context.high and inside.low > context.low):
        return None
    if setup.high < inside.high and setup.low < inside.low:
        return Match(BULLISH)
    if setup.high > inside.high and setup.low > inside.low:
        return Match(BEARISH)
    return None


HIKKAKE = PatternRule(
    name="pat_hikkake",
    bar_count=3,
    requires_trend=False,
    judge=_judge_hikkake,
    confirm=_confirms_hikkake,
    confirm_within_bars=CONFIRM_WITHIN_THREE_BARS,
)
"""§7.5.9 `CDLHIKKAKE`. No trend, directional, min_history 3.

Confirmation is required and its deadline is three bars, both from Chesler. §6
keeps the deadline out of the warm-up: the setup is judged on its own three bars
and the confirmation is a later event on a later bar.
"""


def _judge_hikkake_modified(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.5.10: §7.5.9 with two demands added to the bar before the inside bar.

    Rule 1 inherits the basic section whole and reaches it through the registered
    rule rather than restating it, the way §7.4.15 and §7.4.16 reach the harami
    and the engulfing. The window handed over is the last three bars, so the
    inside bar and the setup bar are the same two the basic section reads.

    Rule 2 is an exact equality and stays one. Chesler writes that the bar "must
    close at the top of its range", and §7.5.10 refuses to soften that into §4.2's
    "no tail" convention even though the consequence is a pattern that almost
    never fires — the source predicts the rarity itself, and widening a stated
    equality would be changing the source rather than reading it.
    """
    earlier, context = window[0], window[1]
    basic = HIKKAKE.judge(window[1:], trend)
    if basic is None:
        return None
    if basic.direction == BULLISH:
        closed_at_the_end_of_its_range = context.close == context.low
    else:
        closed_at_the_end_of_its_range = context.close == context.high
    if not closed_at_the_end_of_its_range:
        return None
    if not candle_range(context) < candle_range(earlier):
        return None
    return Match(basic.direction)


HIKKAKE_MODIFIED = PatternRule(
    name="pat_hikkake_modified",
    bar_count=4,
    requires_trend=False,
    judge=_judge_hikkake_modified,
    confirm=_confirms_hikkake,
    confirm_within_bars=CONFIRM_WITHIN_THREE_BARS,
)
"""§7.5.10 `CDLHIKKAKEMOD`. No trend, directional, min_history 4.

The same confirmation as §7.5.9 in content and in deadline, and the same inside
bar to measure it against — which is why one function serves both sections.
"""
