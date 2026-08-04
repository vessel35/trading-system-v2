"""Implement §7.4 of the pattern standard: the three-bar patterns.

Eighteen sections. Seventeen span three bars; §7.4.18 Concealing Baby Swallow
spans four and is filed here anyway, the way §7.3 keeps the three-bar Stick
Sandwich among its two-bar patterns.

Five things recur across the group, and stating them once keeps them out of
eighteen rule bodies.

**Span and warm-up.** Every section here requires §3's prior trend, so §6 puts
`min_history` at 12 for the seventeen three-bar sections and at 13 for the
four-bar one. Nothing below declares those numbers: §6 derives each from the span
and the trend flag, and `PatternRegistry.register` checks the derivation against
the state that will call itself warmed up.

**Which side matched.** Twelve sections are one-sided — Morris and Nison describe
them as a bullish or a bearish formation and not as a shape that could be either
— so their rule reads one trend and reports one direction. Six admit both sides:
§7.4.5 Abandoned Baby, §7.4.6 Tri Star, §7.4.13 Stalled Pattern, §7.4.15 Three
Inside, §7.4.16 Three Outside, and their direction follows the trend the way it
does throughout §7.3.

**Two sections are built on §7.3 rather than beside it.** §7.4.15 and §7.4.16
inherit Harami and Engulfing in full and add a third bar closing past the second.
They reach those sections through their registered rules rather than restating
them, so neither can drift away from the section it cites, and they carry the
inherited match's strength — which is the only way §5.6's half strength reaches
this group at all.

**Gaps.** Four kinds of source text appear here and §1.3 keeps them apart. The
star sections and the two crows sections gap between real bodies because their
sources say so in as many words. §7.4.5 Abandoned Baby gaps across the whole
high-low range, including shadows, because both of its sources state that
explicitly and §7.4.5 is the one section in the standard that reads a range gap.
§7.4.6 Tri Star and §7.4.18 Concealing Baby Swallow have sources that never say
which kind, so §2.8's convention applies and both read the body gap.

**Confirmation.** §5.5 computes a confirmation only where a source graded one, so
this group splits three ways exactly as §7.3 did. Twelve sections take the
general rule outright — the next bar closes the way the match points, deadline
one bar. Three are graded on their bearish side and `No` on their bullish one, so
a bullish match leaves `_confirm` at 0.0. The last three are graded `No` outright
and compute nothing at all.

The four keys, the degenerate gate, warm-up, and the placement of confirmations
are not here. `judgment.py` holds them once for all sixty-one patterns.

Section numbers in this module are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

from collections.abc import Sequence

from core_lib.indicators.primitives import NAN
from core_lib.types import Candle

from . import body_shadow, scales, two_candle
from .inequalities import contain
from .judgment import (
    CONFIRMS_BEARISH_SIDE_ONLY,
    Match,
    PatternRule,
    confirms_by_close_direction,
)
from .outputs import BEARISH, BULLISH
from .primitives import (
    body,
    body_bottom,
    body_mid,
    body_top,
    gap_down_body,
    gap_down_range,
    gap_up_body,
    gap_up_range,
    is_black,
    is_white,
)
from .trend import DOWNTREND, UPTREND


def _opens_inside_the_previous_body(previous: Candle, current: Candle) -> bool:
    """Return whether a bar opened strictly within the preceding real body.

    §7.4.9 writes this condition out and §7.4.10 and §7.4.12 both refer back to
    it, so it is one function rather than three copies. §4.2 makes the two
    comparisons strict: "inside" is a size comparison, and the one place the
    sources fixed an equality — §4.1's engulfment and containment — is a
    different relation with its own rule.
    """
    return body_bottom(previous) < current.open < body_top(previous)


def _is_black_marubozu(candle: Candle) -> bool:
    """Return whether a bar is a black marubozu, which §7.4.18 asks for by reference.

    Reached through §7.2.2's own rule with §1.2's colour added, rather than
    restated, so this section cannot drift away from the one it cites. The trend
    argument is the NaN `judgment.py` hands every trendless rule and §7.2.2 does
    not read it.
    """
    return is_black(candle) and body_shadow.MARUBOZU.judge((candle,), NAN) is not None


# --- §7.4.1 Morning Star ----------------------------------------------------


def _judge_morning_star(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.4.1: a small body gapping below a long black one, then a recovery.

    Five rules, and the fifth is the one the two sources disagree about. Morris
    lists four and never asks the third day to penetrate the first body; Nison
    writes that it "closes well into the first session's black real body".
    Decision C takes the reading with more conditions, so the penetration is
    required here.

    Its depth is the standard's own. Nison gives a number for Piercing and Dark
    Cloud Cover and none for the star family, so §7.4.1 carries the neighbouring
    50 percent across and says plainly that the figure is not the author's for
    this pattern. TA-Lib's default of 0.3 is not used: decision A forbids
    inheriting its table, and no source for that number was found.

    Rule 3 does not ask the star's colour. That is deliberate in the sources —
    the gap is what makes it a star — and it is why a colourless middle bar is
    admitted here while §1.2 keeps it out of any rule that names a colour.
    """
    first, star, last = window
    if trend != DOWNTREND:
        return None
    if not (is_black(first) and scales.long_body(first)):
        return None
    if not (scales.short_body(star) and gap_down_body(first, star)):
        return None
    if not is_white(last):
        return None
    if not last.close > body_mid(first):
        return None
    return Match(BULLISH)


MORNING_STAR = PatternRule(
    name="pat_morning_star",
    bar_count=3,
    requires_trend=True,
    judge=_judge_morning_star,
    confirm=confirms_by_close_direction,
)
"""§7.4.1 `CDLMORNINGSTAR`. Downtrend, bullish, `Required` confirmation, min_history 12."""


# --- §7.4.2 Evening Star ----------------------------------------------------


def _judge_evening_star(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.4.2: §7.4.1 turned over, with the same penetration convention."""
    first, star, last = window
    if trend != UPTREND:
        return None
    if not (is_white(first) and scales.long_body(first)):
        return None
    if not (scales.short_body(star) and gap_up_body(first, star)):
        return None
    if not is_black(last):
        return None
    if not last.close < body_mid(first):
        return None
    return Match(BEARISH)


EVENING_STAR = PatternRule(
    name="pat_evening_star",
    bar_count=3,
    requires_trend=True,
    judge=_judge_evening_star,
    confirm=confirms_by_close_direction,
)
"""§7.4.2 `CDLEVENINGSTAR`. Uptrend, bearish, `Required` confirmation, min_history 12."""


# --- §7.4.3 Morning Doji Star -----------------------------------------------


def _judge_morning_doji_star(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.4.3: §7.4.1 with a doji in place of the small body.

    That single substitution is the whole difference between the two sections,
    and it makes this one strictly narrower: §2.3's doji body is at most 3
    percent of the range while §2.2's short body is anything under a third of it,
    so every bar reaching here would also reach §7.4.1.

    Rule 3 carries a third clause asking the doji's shadows not to be excessively
    long, by reference to §7.3.4's rule 5. That rule no longer exists. §7.3.4 was
    corrected to four rules and states in its own text why: §2.4 measures a
    shadow in multiples of the body, rule 3 here has already driven that body to
    almost nothing, and negating §2.4 would ask for `Range < 5 * Body` while the
    doji asks for `Range >= 33.3 * Body`. No bar satisfies both, so keeping the
    clause would empty this section and §7.4.4 with it. The clause is therefore
    read the way §7.3.4 reads the sentence it came from — as a tendency — and is
    not a condition here.
    """
    first, star, last = window
    if trend != DOWNTREND:
        return None
    if not (is_black(first) and scales.long_body(first)):
        return None
    if not (scales.doji(star) and gap_down_body(first, star)):
        return None
    if not is_white(last):
        return None
    if not last.close > body_mid(first):
        return None
    return Match(BULLISH)


MORNING_DOJI_STAR = PatternRule(
    name="pat_morning_doji_star",
    bar_count=3,
    requires_trend=True,
    judge=_judge_morning_doji_star,
    confirm=confirms_by_close_direction,
)
"""§7.4.3 `CDLMORNINGDOJISTAR`. Downtrend, bullish, `Suggested` confirmation, min_history 12."""


# --- §7.4.4 Evening Doji Star -----------------------------------------------


def _judge_evening_doji_star(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.4.4: §7.4.3 turned over, and likewise narrower than §7.4.2."""
    first, star, last = window
    if trend != UPTREND:
        return None
    if not (is_white(first) and scales.long_body(first)):
        return None
    if not (scales.doji(star) and gap_up_body(first, star)):
        return None
    if not is_black(last):
        return None
    if not last.close < body_mid(first):
        return None
    return Match(BEARISH)


EVENING_DOJI_STAR = PatternRule(
    name="pat_evening_doji_star",
    bar_count=3,
    requires_trend=True,
    judge=_judge_evening_doji_star,
    confirm=confirms_by_close_direction,
)
"""§7.4.4 `CDLEVENINGDOJISTAR`. Uptrend, bearish, `Required` confirmation, min_history 12."""


# --- §7.4.5 Abandoned Baby --------------------------------------------------


def _judge_abandoned_baby(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.4.5: a doji isolated on both sides by a gap across the whole range.

    The one section in the standard whose gap includes the shadows. Both sources
    fix it: Morris writes of a doji "whose shadow gaps above or below the
    previous day's upper or lower shadow" and then of a third day gapping back
    "with no shadows overlapping", and Nison's glossary says "gaps away
    (including shadows)". So §1.3's range gap is read here and the body gap the
    star sections use is not.

    Nothing asks the first day for a long body and nothing asks the third day to
    penetrate it. §7.4.5 records both absences as deliberate: the sources give
    this pattern its isolation as the whole of its content, and adding the star
    family's conditions would make it unreachable in a market whose two gaps are
    already rare.
    """
    first, baby, last = window
    if trend == DOWNTREND:
        direction = BULLISH
        first_has_the_trend_colour = is_black(first)
        gapped_away = gap_down_range(first, baby)
        last_has_the_opposite_colour = is_white(last)
        gapped_back = gap_up_range(baby, last)
    elif trend == UPTREND:
        direction = BEARISH
        first_has_the_trend_colour = is_white(first)
        gapped_away = gap_up_range(first, baby)
        last_has_the_opposite_colour = is_black(last)
        gapped_back = gap_down_range(baby, last)
    else:
        return None
    if not first_has_the_trend_colour:
        return None
    if not (scales.doji(baby) and gapped_away):
        return None
    if not last_has_the_opposite_colour:
        return None
    if not gapped_back:
        return None
    return Match(direction)


ABANDONED_BABY = PatternRule(
    name="pat_abandoned_baby",
    bar_count=3,
    requires_trend=True,
    judge=_judge_abandoned_baby,
    confirm=confirms_by_close_direction,
)
"""§7.4.5 `CDLABANDONEDBABY`. Trend required, directional, min_history 12.

Graded `Suggested` on the bullish side and `Required` on the bearish one. Both
sides carry a grade, so §5.5's general rule applies to each and one key serves
them both.
"""


# --- §7.4.6 Tri Star --------------------------------------------------------


def _judge_tri_star(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.4.6: three dojis arranged the way a morning or evening star is.

    Nison calls it extraordinarily rare and describes it by that arrangement
    alone, so the rules are three dojis and a middle bar gapping away from both
    neighbours. No source says which kind of gap, so §2.8's convention makes it
    the body gap.

    §7.4.6 flags that this choice matters more here than anywhere else §2.8
    reaches. Three dojis have almost no body between them, so a body gap is a
    very small distance to clear and a range gap would be a very large one — the
    section says so rather than letting the reader assume the two readings are
    close.
    """
    first, middle, last = window
    if trend == DOWNTREND:
        direction = BULLISH
        arranged = gap_down_body(first, middle) and gap_up_body(middle, last)
    elif trend == UPTREND:
        direction = BEARISH
        arranged = gap_up_body(first, middle) and gap_down_body(middle, last)
    else:
        return None
    if not all(scales.doji(candle) for candle in window):
        return None
    if not arranged:
        return None
    return Match(direction)


TRI_STAR = PatternRule(
    name="pat_tri_star",
    bar_count=3,
    requires_trend=True,
    judge=_judge_tri_star,
    confirm=confirms_by_close_direction,
)
"""§7.4.6 `CDLTRISTAR`. Trend required, directional, min_history 12.

Graded `Suggested` bullish and `Required` bearish, so both sides compute one.
"""


# --- §7.4.7 Two Crows -------------------------------------------------------


def _judge_two_crows(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.4.7: an upside gap filled by the third day closing back inside.

    Morris's rules are terse and the passage before them is what fixes the
    section, so decision C adopts the passage: the second day gaps much higher
    and closes near its low but still above the first body, and the third opens
    inside that second body and sells off into the first, closing the gap.

    Rules 4 and 5 read "inside" as two strict inequalities, by §4.2. That is the
    standard's own reading and §7.4.7 marks it as such.

    Rule 3's closing condition is entailed by its gap: a black body's close is
    its bottom, and the body gap already puts that bottom above the first body's
    top. It is written out anyway because the section writes it, and a condition
    that follows from its neighbours is not a condition to drop.
    """
    first, second, third = window
    if trend != UPTREND:
        return None
    if not (is_white(first) and scales.long_body(first)):
        return None
    if not (is_black(second) and gap_up_body(first, second)):
        return None
    if not second.close > body_top(first):
        return None
    if not (is_black(third) and _opens_inside_the_previous_body(second, third)):
        return None
    if not body_bottom(first) < third.close < body_top(first):
        return None
    return Match(BEARISH)


TWO_CROWS = PatternRule(
    name="pat_two_crows",
    bar_count=3,
    requires_trend=True,
    judge=_judge_two_crows,
    confirm=confirms_by_close_direction,
)
"""§7.4.7 `CDL2CROWS`. Uptrend, bearish, `Required` confirmation, min_history 12."""


# --- §7.4.8 Upside Gap Two Crows --------------------------------------------


def _judge_upside_gap_two_crows(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.4.8: the same gap as §7.4.7, left open instead of filled.

    Rule 5 is the whole difference between the two sections and §7.4.8 says so:
    the third close stays above the first day's close here, where §7.4.7 requires
    it back inside the first body. The two therefore exclude each other whenever
    the first body is white, which rule 2 requires — a close above the first
    close cannot also be under the first body's top.

    Nison fixes both remaining rules. He names the gap as the one between real
    bodies, and he describes the third bar as opening above the second black
    body's open and closing under its close, which is an engulfment stated in
    prices rather than through §4.1's relation. It is written as Nison writes it,
    with two strict comparisons, because §4.1's relation admits a boundary case
    the section does not mention.
    """
    first, second, third = window
    if trend != UPTREND:
        return None
    if not (is_white(first) and scales.long_body(first)):
        return None
    if not (is_black(second) and gap_up_body(first, second)):
        return None
    if not (is_black(third) and third.open > second.open and third.close < second.close):
        return None
    if not third.close > first.close:
        return None
    return Match(BEARISH)


UPSIDE_GAP_TWO_CROWS = PatternRule(
    name="pat_upside_gap_two_crows",
    bar_count=3,
    requires_trend=True,
    judge=_judge_upside_gap_two_crows,
    confirm=confirms_by_close_direction,
)
"""§7.4.8 `CDLUPSIDEGAP2CROWS`. Uptrend, bearish, `Required` confirmation, min_history 12."""


# --- §7.4.9 Three Advancing White Soldiers ----------------------------------


def _judge_three_white_soldiers(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.4.9: three long white bars stepping up, each closing at its high.

    Rule 5 is where the standard translated rather than transcribed. The sources
    ask each day to close "at or near its high", and §2.5 states that this is the
    same fact as a very short upper shadow and that no second threshold is to be
    created for it.

    Rule 4 asks each open to sit inside the previous body, which is what makes
    the three bars a staircase rather than three unrelated long days.
    """
    first, second, third = window
    if trend != DOWNTREND:
        return None
    if not all(is_white(candle) and scales.long_body(candle) for candle in window):
        return None
    if not (second.close > first.close and third.close > second.close):
        return None
    if not (
        _opens_inside_the_previous_body(first, second)
        and _opens_inside_the_previous_body(second, third)
    ):
        return None
    if not all(scales.no_upper_shadow(candle) for candle in window):
        return None
    return Match(BULLISH)


THREE_WHITE_SOLDIERS = PatternRule(
    name="pat_three_white_soldiers",
    bar_count=3,
    requires_trend=True,
    judge=_judge_three_white_soldiers,
)
"""§7.4.9 `CDL3WHITESOLDIERS`. Downtrend, bullish, min_history 12.

One of the three sections here graded `No`, so §5.5 computes no confirmation at
all and `_confirm` stays at 0.0 for the whole series.
"""


# --- §7.4.10 Three Black Crows ----------------------------------------------


def _judge_three_black_crows(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.4.10: §7.4.9 upside down, plus the rule the sources add to this side.

    The two sections are not mirror images and §7.4.10 says so. Morris gives the
    crows a rule the soldiers do not have — each day closes at a new low — which
    is rule 3 here. The soldiers' rising closes are the same shape of condition
    but the sources state them as an advance rather than as new extremes.
    """
    first, second, third = window
    if trend != UPTREND:
        return None
    if not all(is_black(candle) and scales.long_body(candle) for candle in window):
        return None
    if not (second.close < first.close and third.close < second.close):
        return None
    if not (
        _opens_inside_the_previous_body(first, second)
        and _opens_inside_the_previous_body(second, third)
    ):
        return None
    if not all(scales.no_lower_shadow(candle) for candle in window):
        return None
    return Match(BEARISH)


THREE_BLACK_CROWS = PatternRule(
    name="pat_three_black_crows",
    bar_count=3,
    requires_trend=True,
    judge=_judge_three_black_crows,
    confirm=confirms_by_close_direction,
)
"""§7.4.10 `CDL3BLACKCROWS`. Uptrend, bearish, `Required` confirmation, min_history 12."""


# --- §7.4.11 Identical Three Crows ------------------------------------------


def _judge_identical_three_crows(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.4.11: three long black bars each opening where the last one closed.

    Rule 3 is what the name points at and what separates this section from
    §7.4.10. There the opens sit strictly inside the previous body; here they sit
    on the previous close, within §2.6's tolerance. The two are not exclusive —
    §2.6 allows an open a little above the previous close, which is also inside
    the previous body — but §7.4.10 additionally asks each bar to close at its
    low, and this section asks nothing about the shadows at all.

    Morris's commentary allows an open "at or near the previous day's close"
    while his rule states equality. Decision C makes the rule the norm, so §2.6's
    `Equal` is used rather than §2.6's wider `Near`. The section notes that the
    two readings differ little in practice because `Equal` already carries a
    tolerance.
    """
    first, second, third = window
    if trend != UPTREND:
        return None
    if not all(is_black(candle) and scales.long_body(candle) for candle in window):
        return None
    if not (second.close < first.close and third.close < second.close):
        return None
    if not scales.equal(second.open, first.close, second):
        return None
    if not scales.equal(third.open, second.close, third):
        return None
    return Match(BEARISH)


IDENTICAL_THREE_CROWS = PatternRule(
    name="pat_identical_three_crows",
    bar_count=3,
    requires_trend=True,
    judge=_judge_identical_three_crows,
)
"""§7.4.11 `CDLIDENTICAL3CROWS`. Uptrend, bearish, min_history 12.

Graded `No`, and here the grade is not read off a header field: Morris's entry
for this pattern is laid out differently from the rest and says in the body that
no confirmation is required.
"""


# --- §7.4.12 Advance Block --------------------------------------------------


def _judge_advance_block(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.4.12: three rising white bars whose last two stall under long tails.

    Rule 2 asks for no length at all, which is exactly what separates this
    section from §7.4.9: the same staircase of three white bars is a bullish
    advance when the bodies are long and a bearish stall when the last two carry
    long upper shadows instead.

    Nison offers two ways the weakening can show — tall upper shadows or
    progressively smaller bodies — and Morris's rule names only the shadows.
    Decision C makes the rule the norm, so the shrinking bodies stay commentary.
    The shadows are §2.4's, measured against the body.
    """
    first, second, third = window
    if trend != UPTREND:
        return None
    if not all(is_white(candle) for candle in window):
        return None
    if not (second.close > first.close and third.close > second.close):
        return None
    if not (
        _opens_inside_the_previous_body(first, second)
        and _opens_inside_the_previous_body(second, third)
    ):
        return None
    if not (scales.long_upper_shadow(second) and scales.long_upper_shadow(third)):
        return None
    return Match(BEARISH)


ADVANCE_BLOCK = PatternRule(
    name="pat_advance_block",
    bar_count=3,
    requires_trend=True,
    judge=_judge_advance_block,
    confirm=confirms_by_close_direction,
)
"""§7.4.12 `CDLADVANCEBLOCK`. Uptrend, bearish, `Required` confirmation, min_history 12."""


# --- §7.4.13 Stalled Pattern (Deliberation) ---------------------------------


def _judge_stalled_pattern(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.4.13: two long bars extending the trend, then a small one alongside.

    The bearish side is the one both sources describe, and Nison adds two
    conditions to Morris's: the third bar must be white, and the second must make
    a new high. Decision C adopts both.

    The bullish side is the mirror with one omission the section states outright.
    Nison never writes a bullish form, so his colour condition is not carried
    across and the third bar is asked only to be short. His new-high condition is
    mirrored, because the section excludes the colour condition alone.

    No gap is required on either side. Nison offers one as an alternative to the
    close proximity of rule 4, and an alternative is not a requirement, so §7.4.13
    leaves it out.
    """
    first, second, third = window
    if trend == UPTREND:
        direction = BEARISH
        two_bars_extend_the_trend = is_white(first) and is_white(second)
        second_reaches_a_new_extreme = second.high > first.high
        third_has_the_colour_the_sources_ask_for = is_white(third)
    elif trend == DOWNTREND:
        direction = BULLISH
        two_bars_extend_the_trend = is_black(first) and is_black(second)
        second_reaches_a_new_extreme = second.low < first.low
        third_has_the_colour_the_sources_ask_for = True
    else:
        return None
    if not two_bars_extend_the_trend:
        return None
    if not (scales.long_body(first) and scales.long_body(second)):
        return None
    if not second_reaches_a_new_extreme:
        return None
    if not (third_has_the_colour_the_sources_ask_for and scales.short_body(third)):
        return None
    if not scales.near(third.open, second.close, third):
        return None
    return Match(direction)


STALLED_PATTERN = PatternRule(
    name="pat_stalled_pattern",
    bar_count=3,
    requires_trend=True,
    judge=_judge_stalled_pattern,
    confirm=CONFIRMS_BEARISH_SIDE_ONLY,
)
"""§7.4.13 `CDLSTALLEDPATTERN`. Trend required, directional, min_history 12.

Graded `No` on the bullish side and `Suggested` on the bearish one, so §5.5
computes a confirmation only for a bearish match.
"""


# --- §7.4.14 Three Stars in the South ---------------------------------------


def _judge_three_stars_in_the_south(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.4.14: three shrinking black bars, the decline losing its reach.

    Morris alone describes this pattern; Nison's second edition has no entry for
    it. The first two days are black with long lower shadows and the second is
    the smaller of them, opening the decline's grip; the third is a small black
    bar with no tails, contained in the second day's range.

    Two of the section's conditions cannot be implemented as printed, and the
    reason is the same in both places. Rule 2 asks the first day for `LongBody`
    and `LongLowerShadow` at once: §2.1 makes the body more than half the range
    and §2.4 makes the lower shadow at least two bodies, so the shadow alone
    would have to exceed the whole range. Rule 4 asks the third day for
    `ShortBody` with neither shadow: a body under a third of the range and two
    shadows of at most a tenth each cannot add up to the range they are measured
    against. Both collapses come from §2 having put every scale over the bar's
    own high-low range, where Morris measures "long" and "short" against an
    average of recent bodies and has no contradiction.

    The section resolves the two places differently. Rule 2 simply drops
    `LongBody`, because keeping "long" would need a range-denominated shadow
    scale that §2 does not have and §0 forbids inventing. Rule 4 keeps its
    "small" by moving it onto the comparison rule 3 already uses, so the third
    body must be smaller than the second — which is Morris's own descending-body
    reading and adds no new number.

    Rule 5's "range" is the high-low range. §7.4.14 chose that reading because
    rule 3 of the same section speaks of lows, and Morris writes "body range"
    where he means the body; the section records that the other reading is
    available and that the choice can be revisited.
    """
    first, second, third = window
    if trend != DOWNTREND:
        return None
    if not (is_black(first) and scales.long_lower_shadow(first)):
        return None
    if not (is_black(second) and scales.long_lower_shadow(second)):
        return None
    if not (body(second) < body(first) and second.low > first.low):
        return None
    if not (is_black(third) and body(third) < body(second)):
        return None
    if not (scales.no_upper_shadow(third) and scales.no_lower_shadow(third)):
        return None
    if not (second.low <= third.low and third.high <= second.high):
        return None
    return Match(BULLISH)


THREE_STARS_IN_THE_SOUTH = PatternRule(
    name="pat_three_stars_in_the_south",
    bar_count=3,
    requires_trend=True,
    judge=_judge_three_stars_in_the_south,
    confirm=confirms_by_close_direction,
)
"""§7.4.14 `CDL3STARSINSOUTH`. Downtrend, bullish, `Suggested` confirmation, min_history 12."""


# --- §7.4.15 Three Inside Up / Down -----------------------------------------


def _judge_three_inside(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.4.15: a harami whose third bar closes past the second.

    Morris invented this pattern and says so, to improve on the harami's results
    rather than to describe something the Japanese literature holds. Rule 1
    inherits §7.3.2 in full, trend and all, and it is reached through the
    registered harami rule so that the inheritance cannot go stale. The trend
    this rule receives is judged on bar `t - 2`, which is the harami's own first
    day, so passing it straight through is exact rather than approximate.

    The section is one pattern with two sides rather than two patterns, which is
    how §8.1 counts it, so Up and Down share the name `pat_three_inside` and are
    told apart by the direction key.

    Rule 2 compares against the second day's close. Morris's commentary describes
    a third day that closes higher than the harami, and §7.4.15 marks the choice
    of the second close as the standard's own reading of that sentence.
    """
    second, third = window[1], window[2]
    harami = two_candle.HARAMI.judge(window[:2], trend)
    if harami is None:
        return None
    if harami.direction == BULLISH:
        carried_on = third.close > second.close
    else:
        carried_on = third.close < second.close
    if not carried_on:
        return None
    return Match(harami.direction, harami.strength)


THREE_INSIDE = PatternRule(
    name="pat_three_inside",
    bar_count=3,
    requires_trend=True,
    judge=_judge_three_inside,
    confirm=CONFIRMS_BEARISH_SIDE_ONLY,
)
"""§7.4.15 `CDL3INSIDE`. Trend required, directional, min_history 12.

Graded `No` on the Up side and `Required` on the Down side, so §5.5 computes a
confirmation only for a bearish match.

Half strength reaches this section through the harami it inherits: §5.6 puts it
on a containment with exactly one body end coinciding, and the inherited match
already carries that verdict.
"""


# --- §7.4.16 Three Outside Up / Down ----------------------------------------


def _judge_three_outside(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.4.16: §7.4.15 built on the engulfing instead of the harami.

    Morris invented this one too, on the same reasoning and for the engulfing
    pattern. His note that "confirmation patterns do not have any more
    flexibility than the underlying pattern" is what rule 1 means by inheriting
    §7.3.1 in full, and reaching the registered engulfing rule is how that is
    kept true.

    §7.4.16 is the second section in the whole standard whose "what we chose"
    note reads: nothing. The engulfing uses no scale, the sources fixed its
    equality handling themselves, and Morris's commentary supplies rule 2's
    comparison, so only §3's trend judgment comes from a convention.
    """
    second, third = window[1], window[2]
    engulfing = two_candle.ENGULFING.judge(window[:2], trend)
    if engulfing is None:
        return None
    if engulfing.direction == BULLISH:
        carried_on = third.close > second.close
    else:
        carried_on = third.close < second.close
    if not carried_on:
        return None
    return Match(engulfing.direction, engulfing.strength)


THREE_OUTSIDE = PatternRule(
    name="pat_three_outside",
    bar_count=3,
    requires_trend=True,
    judge=_judge_three_outside,
    confirm=CONFIRMS_BEARISH_SIDE_ONLY,
)
"""§7.4.16 `CDL3OUTSIDE`. Trend required, directional, min_history 12.

Graded like §7.4.15: `No` on the Up side, `Required` on the Down side.
"""


# --- §7.4.17 Unique Three River Bottom --------------------------------------


def _judge_unique_three_river(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.4.17: a harami in black whose tail makes a new low, then a small rise.

    Morris alone describes it. Rule 3 is a containment of two black bodies rather
    than the harami's opposite colours, and rule 4 then sends the second day's
    *shadow* below the first day's low — which §4.1's relation permits, because
    it holds between real bodies and says nothing about the tails.

    Rule 6 is the section's own reading of "a short white day that is below the
    middle day". The words leave three possibilities: the whole third body below
    the middle body, the two closes compared, or the two lows compared. §7.4.17
    took the strongest, because "below the middle day" names the bar rather than
    one of its prices and because comparing closes would admit two bodies that
    overlap. The section records that the choice can be revisited.

    Strength is full even where the containment sits on a boundary. §5.6's half
    strength is written for the sections that report it, and this section's
    output line states 1.0 outright, so the boundary is not split out here.
    """
    first, second, third = window
    if trend != DOWNTREND:
        return None
    if not (is_black(first) and scales.long_body(first)):
        return None
    if not (is_black(second) and contain(first, second)):
        return None
    if not second.low < first.low:
        return None
    if not (is_white(third) and scales.short_body(third)):
        return None
    if not body_top(third) < body_bottom(second):
        return None
    return Match(BULLISH)


UNIQUE_THREE_RIVER = PatternRule(
    name="pat_unique_three_river",
    bar_count=3,
    requires_trend=True,
    judge=_judge_unique_three_river,
    confirm=confirms_by_close_direction,
)
"""§7.4.17 `CDLUNIQUE3RIVER`. Downtrend, bullish, `Required` confirmation, min_history 12."""


# --- §7.4.18 Concealing Baby Swallow ----------------------------------------


def _judge_concealing_baby_swallow(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.4.18: four black bars, the last swallowing the one before it whole.

    The only four-bar pattern filed in §7.4, which is why its warm-up is 13 where
    the rest of the group warms up at 12: its first day sits three bars behind the
    bar being judged rather than two, and §3 reads the trend on that first day.

    Rule 4 is a high-low engulfment and not §4.1's. The source says "including the
    shadow" in as many words, so the fourth bar has to cover the third bar's whole
    range, and the comparison is non-strict on both ends the way §4.1's is.

    Rule 3's gap has no kind named in the source — it says only "a down gap open"
    — so §2.8's convention makes it the body gap. The same rule then asks the
    third bar's high to reach back into the second body, which is what gives it
    the long upper shadow §2.4 measures.
    """
    first, second, third, fourth = window
    if trend != DOWNTREND:
        return None
    if not (_is_black_marubozu(first) and _is_black_marubozu(second)):
        return None
    if not (is_black(third) and gap_down_body(second, third)):
        return None
    if not (third.high > body_bottom(second) and scales.long_upper_shadow(third)):
        return None
    if not (is_black(fourth) and fourth.high >= third.high and fourth.low <= third.low):
        return None
    return Match(BULLISH)


CONCEALING_BABY_SWALLOW = PatternRule(
    name="pat_concealing_baby_swallow",
    bar_count=4,
    requires_trend=True,
    judge=_judge_concealing_baby_swallow,
)
"""§7.4.18 `CDLCONCEALBABYSWALL`. Downtrend, bullish, min_history 13.

The third section here graded `No`, so no confirmation is computed. Morris marks
it so and the standard declines to manufacture the event where no source asked
for it.
"""
