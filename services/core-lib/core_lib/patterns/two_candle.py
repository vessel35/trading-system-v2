"""Implement §7.3 of the pattern standard: the two-bar patterns and what joins them.

Sixteen sections. Fifteen span two bars; Stick Sandwich spans three and is filed
here anyway, which is why §7.3 is titled for two candles *and what amounts to
them* rather than for two candles alone.

Four things recur across the group, and stating them once keeps them out of
sixteen rule bodies.

**Span and warm-up.** Fourteen sections require §3's prior trend, so `min_history`
is 11 for the two-bar ones and 12 for Stick Sandwich, whose extra bar pushes the
first day one further back. Kicking and Kicking by Length are the two entries
Morris marks `Trend Required: No` — the only two in his 89 — and they warm up at
2. Nothing here declares those numbers: §6 derives each from the span and the
trend flag, and `PatternRegistry.register` checks the derivation against the
state that will call itself warmed up.

**Which side matched.** For every section but one the trend decides the side, and
the colours then follow it rather than the other way round: a downtrend admits
the bullish reading and an uptrend the bearish one, so a bar pair that is shaped
right but sits under the wrong trend is not the other side of the pattern, it is
no match. Kicking by Length is the exception and says so in its own section — it
reads no trend at all and takes its direction from the longer of the two bodies.

**The two asymmetries.** In-Neck and Thrusting ask for a long first day on one
side and not on the other. That is Morris's asymmetry, not a simplification here,
and §7.3.13 and §7.3.15 both say to leave it standing. Stick Sandwich is
asymmetric in a larger way — its two sides do not share a rule between them — and
§7.3.16 states that this too is Morris's text rather than anything introduced by
the standard.

**Confirmation.** §5.5 computes a confirmation only where a source graded one,
and Morris grades some sections differently on their two sides, so this group
splits three ways. Seven sections take §5.5's general rule outright — the next
bar closes the way the match points, deadline one bar. Seven more are graded on
their bearish side and `No` on their bullish one, so the rule runs only when the
match came out bearish and a bullish match leaves `_confirm` at 0.0. The last
two, §7.3.11 Homing Pigeon and §7.3.12 Matching Low, are graded `No` outright
and compute nothing at all.

None of that is a property of the direction as such. A grade records that a
source asked for confirmation, and the standard declines to manufacture the
event where no source asked for it, which is the same reason `_confirm` stays
down for the twelve candle lines of §7.1 and §7.2.

The four keys, the degenerate gate, warm-up, and the placement of confirmations
are not here. `judgment.py` holds them once for all sixty-one patterns.

Section numbers in this module are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

from collections.abc import Sequence

from core_lib.indicators.primitives import NAN
from core_lib.types import Candle

from . import body_shadow, scales
from .inequalities import contain, engulf
from .judgment import (
    CONFIRMS_BEARISH_SIDE_ONLY,
    Match,
    PatternRule,
    confirms_by_close_direction,
)
from .outputs import BEARISH, BOUNDARY_STRENGTH, BULLISH, FULL_STRENGTH
from .primitives import (
    body,
    body_bottom,
    body_mid,
    body_top,
    gap_down_body,
    gap_up_body,
    is_black,
    is_white,
)
from .trend import DOWNTREND, UPTREND


def _wrap_strength(first: Candle, second: Candle) -> float:
    """Return §5.6's strength for an engulfment or containment that already holds.

    §5.6 puts half strength on exactly one situation in the whole standard: the
    two real bodies share one end. §4.1 has already excluded their sharing both,
    so a relation that holds and has one end coinciding is the boundary case and
    everything else is a full match.
    """
    ends_coincide = body_bottom(first) == body_bottom(second) or body_top(first) == body_top(second)
    return BOUNDARY_STRENGTH if ends_coincide else FULL_STRENGTH


def _is_marubozu(candle: Candle) -> bool:
    """Return whether a bar satisfies §7.2.2, which §7.3.9 asks for by reference.

    Reached through §7.2.2's own rule rather than restated, so Kicking cannot
    drift away from the section it cites. The trend argument is the NaN
    `judgment.py` hands every trendless rule and §7.2.2 does not read it.
    """
    return body_shadow.MARUBOZU.judge((candle,), NAN) is not None


# --- §7.3.1 Engulfing -------------------------------------------------------


def _judge_engulfing(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.3.1: the second body wraps the first, after the opposite trend.

    The direction of the wrap is what separates this section from §7.3.2, and
    §7.3.1 records that Morris's printed rule 2 has the two bodies the wrong way
    round. The standard follows his flexibility passage, his scenario passage,
    and Nison — all three of which put the *second* body around the first — so
    `engulf(previous, current)` is the relation and not `contain`.

    Nothing asks for a long body or for the shadows to be covered. §7.3.1's own
    note keeps Morris's "engulfing the tails too is stronger" as commentary, and
    §5.6's half strength is reserved for the one boundary §4.1 admits.
    """
    previous, current = window[0], window[1]
    if trend == DOWNTREND and is_black(previous) and is_white(current):
        direction = BULLISH
    elif trend == UPTREND and is_white(previous) and is_black(current):
        direction = BEARISH
    else:
        return None
    if not engulf(previous, current):
        return None
    return Match(direction, _wrap_strength(previous, current))


ENGULFING = PatternRule(
    name="pat_engulfing",
    bar_count=2,
    requires_trend=True,
    judge=_judge_engulfing,
    confirm=confirms_by_close_direction,
)
"""§7.3.1 `CDLENGULFING`. Trend required, directional, min_history 11.

The one section in the whole standard whose "what we chose" note reads: nothing.
Its inequalities are the ones the sources fixed themselves (§4.1) and it reaches
no scale at all, so only the trend judgment of §3 comes from a convention.
"""


# --- §7.3.2 Harami ----------------------------------------------------------


def _judge_harami(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.3.2: a long day swallowed by a short one of the opposite colour.

    Rule 5 asks for the opposite colour and rule 2 for a long first day, but
    §7.3.2 does not ask for the first day's *own* colour: Morris grades that a
    preference rather than a requirement. Requiring the second day to be white on
    the bullish side already fixes the first day as black through rule 5, which
    is the section's own reading, and a colourless bar satisfies neither side
    because §1.2 gives it no colour to be the opposite of.
    """
    previous, current = window[0], window[1]
    if trend == DOWNTREND and is_black(previous) and is_white(current):
        direction = BULLISH
    elif trend == UPTREND and is_white(previous) and is_black(current):
        direction = BEARISH
    else:
        return None
    if not (scales.long_body(previous) and scales.short_body(current)):
        return None
    if not contain(previous, current):
        return None
    return Match(direction, _wrap_strength(previous, current))


HARAMI = PatternRule(
    name="pat_harami",
    bar_count=2,
    requires_trend=True,
    judge=_judge_harami,
    confirm=CONFIRMS_BEARISH_SIDE_ONLY,
)
"""§7.3.2 `CDLHARAMI`. Trend required, directional, min_history 11.

Graded `No` on the bullish side and `Required` on the bearish one. Morris's
scenario passage supplies the bearish condition — "confirmation on the third day
would be a lower close" — which is the same close comparison §5.5 generalised.
"""


# --- §7.3.3 Harami Cross ----------------------------------------------------


def _judge_harami_cross(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.3.3: a harami whose second session is a doji.

    Four rules, and the colour requirement of §7.3.2 is not among them — a doji
    is asked for instead, and §2.3's doji says nothing about colour. So this
    section admits pairs §7.3.2 rejects, and where the doji does carry a faint
    colour opposite the first day both sections hold at once.

    Rule 4 reads Morris's bare "within the range of the previous long day" as the
    *body* range. §7.3.3 marks that as the standard's own choice and gives the
    reason: Nison's glossary defines this pattern as a harami with a doji in
    place of the small body, which only holds if the containment is inherited
    unchanged. The section also records that the high-low reading is defensible
    and that the choice can be revisited.
    """
    previous, current = window[0], window[1]
    if trend == DOWNTREND:
        direction = BULLISH
    elif trend == UPTREND:
        direction = BEARISH
    else:
        return None
    if not (scales.long_body(previous) and scales.doji(current)):
        return None
    if not contain(previous, current):
        return None
    return Match(direction, _wrap_strength(previous, current))


HARAMI_CROSS = PatternRule(
    name="pat_harami_cross",
    bar_count=2,
    requires_trend=True,
    judge=_judge_harami_cross,
    confirm=CONFIRMS_BEARISH_SIDE_ONLY,
)
"""§7.3.3 `CDLHARAMICROSS`. Trend required, directional, min_history 11.

Graded like §7.3.2: `No` bullish, `Required` bearish.
"""


# --- §7.3.4 Doji Star -------------------------------------------------------


def _judge_doji_star(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.3.4: a doji gapping away from a long real body.

    Four rules. Rule 3 reads the gap between the two *real bodies* rather than
    their ranges, which Nison's glossary fixes in so many words, and that gap is
    also what keeps this section apart from §7.3.3 Harami Cross — the other
    section pairing a long body with a doji, which asks for containment and no
    gap at all.

    Morris adds that the doji's shadows "should not be excessively long,
    especially in the bullish case". §7.3.4 keeps that as a tendency and not a
    rule, on the same reading it gives Morris's "usually" in §7.1.9 and Nison's
    in §7.3.14. It also records why the alternative fails outright: §2.4 measures
    a shadow in multiples of the body, and rule 4 has already made that body
    almost nothing, so negating §2.4 here would ask for `Range < 5 * Body` while
    rule 4 asks for `Range >= 33.3 * Body` and no bar could satisfy both. A
    body-relative scale combined *negatively* with a small-body requirement
    always collapses that way; every other section in §7 combines the two
    positively and none has the problem.
    """
    previous, current = window[0], window[1]
    if trend == DOWNTREND:
        direction = BULLISH
        gapped = gap_down_body(previous, current)
    elif trend == UPTREND:
        direction = BEARISH
        gapped = gap_up_body(previous, current)
    else:
        return None
    if not scales.long_body(previous):
        return None
    if not gapped:
        return None
    if not scales.doji(current):
        return None
    return Match(direction)


DOJI_STAR = PatternRule(
    name="pat_doji_star",
    bar_count=2,
    requires_trend=True,
    judge=_judge_doji_star,
    confirm=CONFIRMS_BEARISH_SIDE_ONLY,
)
"""§7.3.4 `CDLDOJISTAR`. Trend required, directional, min_history 11.

Graded `No` on the bullish side and `Suggested` on the bearish one, so §5.5
computes a confirmation only for a bearish match.
"""


# --- §7.3.5 Piercing Line ---------------------------------------------------


def _judge_piercing(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.3.5: a white day opening under the low and closing past the midpoint.

    Rule 4 is a price comparison and not a gap: Morris writes "that's low, not
    close" in brackets, so the second open is measured against the previous
    *low*, strictly. Rule 5 is §4.3's penetration, whose depth the sources gave —
    more than halfway into the prior body, and still inside it.
    """
    previous, current = window[0], window[1]
    if trend != DOWNTREND:
        return None
    if not (is_black(previous) and scales.long_body(previous)):
        return None
    if not is_white(current):
        return None
    if not current.open < previous.low:
        return None
    if not (current.close > body_mid(previous) and current.close < previous.open):
        return None
    return Match(BULLISH)


PIERCING = PatternRule(
    name="pat_piercing",
    bar_count=2,
    requires_trend=True,
    judge=_judge_piercing,
    confirm=confirms_by_close_direction,
)
"""§7.3.5 `CDLPIERCING`. Downtrend, bullish, min_history 11."""


# --- §7.3.6 Dark Cloud Cover ------------------------------------------------


def _judge_dark_cloud_cover(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.3.6: §7.3.5 upside down, with the stricter of the two source opens.

    Morris measures the second open against the previous *high* and Nison allows
    the previous close as well. Decision C takes the narrower reading, so rule 4
    compares against the high and is strict.
    """
    previous, current = window[0], window[1]
    if trend != UPTREND:
        return None
    if not (is_white(previous) and scales.long_body(previous)):
        return None
    if not is_black(current):
        return None
    if not current.open > previous.high:
        return None
    if not (current.close < body_mid(previous) and current.close > previous.open):
        return None
    return Match(BEARISH)


DARK_CLOUD_COVER = PatternRule(
    name="pat_dark_cloud_cover",
    bar_count=2,
    requires_trend=True,
    judge=_judge_dark_cloud_cover,
    confirm=confirms_by_close_direction,
)
"""§7.3.6 `CDLDARKCLOUDCOVER`. Uptrend, bearish, `Required` confirmation, min_history 11."""


# --- §7.3.7 Counterattack (Meeting Lines) -----------------------------------


def _judge_counterattack(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.3.7: two long days of opposite colour meeting at the same close.

    Rule 4 carries Nison's "sharply lower" and "robustly higher" without inventing
    a threshold for either: he writes out what he means for the bearish side —
    opening above the prior day's high — and §7.3.7 applies that same form to the
    bullish side, which is the one convention this section takes.
    """
    previous, current = window[0], window[1]
    if trend == DOWNTREND and is_black(previous) and is_white(current):
        direction = BULLISH
        opened_beyond = current.open < previous.low
    elif trend == UPTREND and is_white(previous) and is_black(current):
        direction = BEARISH
        opened_beyond = current.open > previous.high
    else:
        return None
    if not (scales.long_body(previous) and scales.long_body(current)):
        return None
    if not opened_beyond:
        return None
    if not scales.equal(current.close, previous.close, current):
        return None
    return Match(direction)


COUNTERATTACK = PatternRule(
    name="pat_counterattack",
    bar_count=2,
    requires_trend=True,
    judge=_judge_counterattack,
    confirm=confirms_by_close_direction,
)
"""§7.3.7 `CDLCOUNTERATTACK`. Trend required, directional, min_history 11."""


# --- §7.3.8 Separating Lines ------------------------------------------------


def _judge_separating_lines(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.3.8: two opposite-coloured bodies meeting at the same open.

    A continuation, so the trend and the direction agree rather than oppose: the
    bullish side follows an uptrend and its first day is the one bar running
    against it. Morris's rules carry no length requirement and none is added,
    which is what separates this from every other section in the group where two
    bodies meet.
    """
    previous, current = window[0], window[1]
    if trend == UPTREND and is_black(previous) and is_white(current):
        direction = BULLISH
    elif trend == DOWNTREND and is_white(previous) and is_black(current):
        direction = BEARISH
    else:
        return None
    if not scales.equal(current.open, previous.open, current):
        return None
    return Match(direction)


SEPARATING_LINES = PatternRule(
    name="pat_separating_lines",
    bar_count=2,
    requires_trend=True,
    judge=_judge_separating_lines,
    confirm=CONFIRMS_BEARISH_SIDE_ONLY,
)
"""§7.3.8 `CDLSEPARATINGLINES`. Trend required, continuation, min_history 11.

Graded `No` bullish and `Required` bearish, so only a bearish match is confirmed.
"""


# --- §7.3.9 Kicking ---------------------------------------------------------


def _kicking_shape(window: Sequence[Candle]) -> float | None:
    """Return the direction of §7.3.9's arrangement, or None when it is not there.

    Two marubozus of opposite colour with a gap between their bodies. §7.3.9
    writes the bullish side — black then white, gapping up — and the bearish side
    is its mirror. The gap is the one between real bodies: Morris writes only
    that "a gap must occur between the two lines", so §2.8's convention applies,
    and both bars being marubozus leaves body and range nearly the same anyway.

    Split out because §7.3.10 asks for this same arrangement by reference and
    then decides direction differently.
    """
    previous, current = window[0], window[1]
    if not (_is_marubozu(previous) and _is_marubozu(current)):
        return None
    if is_black(previous) and is_white(current) and gap_up_body(previous, current):
        return BULLISH
    if is_white(previous) and is_black(current) and gap_down_body(previous, current):
        return BEARISH
    return None


def _judge_kicking(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.3.9: the arrangement alone, with the direction the gap points.

    One of the two sections in the standard that read no trend. Morris marks it
    `Trend Required: No` and writes that market direction matters less here than
    in most candle patterns, so the trend argument is the NaN a trendless rule
    receives and is not looked at.
    """
    direction = _kicking_shape(window)
    if direction is None:
        return None
    return Match(direction)


KICKING = PatternRule(
    name="pat_kicking",
    bar_count=2,
    requires_trend=False,
    judge=_judge_kicking,
    confirm=confirms_by_close_direction,
)
"""§7.3.9 `CDLKICKING`. No trend, `Required` confirmation, directional, min_history 2.

The 2 is the whole of §6's trendless formula: two bars exist first at index 1, no
scale here reaches back past its own bar, and there is no average to warm up.
"""


# --- §7.3.10 Kicking by Length ----------------------------------------------


def _judge_kicking_by_length(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.3.10: §7.3.9's shape, pointed by the longer body instead of the gap.

    The one section whose direction disagrees with its own arrangement: a bullish
    kicking whose black body is the longer of the two reports bearish, because
    the Japanese theory Morris relays puts future movement on the side of the
    longer candle regardless of price trend.

    Three things here are the standard's own. "The longer side" is read as body
    length, because a marubozu is defined by its body and §2.5's tolerance lets
    body and range disagree slightly. A tie reports no match, since inventing a
    side would state a direction the sources do not have. And the pattern exists
    as a separate section only because TA-Lib made it one.

    The longer bar is always coloured: §2.1's long body cannot be zero once §2.7
    has excluded the degenerate bar, so the white test decides the direction.
    """
    if _kicking_shape(window) is None:
        return None
    previous, current = window[0], window[1]
    if body(previous) == body(current):
        return None
    longer = previous if body(previous) > body(current) else current
    return Match(BULLISH if is_white(longer) else BEARISH)


KICKING_BY_LENGTH = PatternRule(
    name="pat_kicking_by_length",
    bar_count=2,
    requires_trend=False,
    judge=_judge_kicking_by_length,
    confirm=confirms_by_close_direction,
)
"""§7.3.10 `CDLKICKINGBYLENGTH`. No trend, `Required` confirmation, min_history 2."""


# --- §7.3.11 Homing Pigeon --------------------------------------------------


def _judge_homing_pigeon(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.3.11: a harami whose two days share a colour instead of opposing.

    That single difference is the whole of it, and it is why the same pair of
    bars can never satisfy this section and §7.3.2 at once.
    """
    previous, current = window[0], window[1]
    if trend != DOWNTREND:
        return None
    if not (is_black(previous) and scales.long_body(previous)):
        return None
    if not (is_black(current) and scales.short_body(current)):
        return None
    if not contain(previous, current):
        return None
    return Match(BULLISH, _wrap_strength(previous, current))


HOMING_PIGEON = PatternRule(
    name="pat_homing_pigeon",
    bar_count=2,
    requires_trend=True,
    judge=_judge_homing_pigeon,
)
"""§7.3.11 `CDLHOMINGPIGEON`. Downtrend, bullish, min_history 11.

One of the two sections here graded `No`, so §5.5 computes no confirmation at all
and `_confirm` stays at 0.0 for the whole series.

The containment is §4.1's relation extended to a section that never fixed its own
equality handling, which §4.2 routes here deliberately, so §5.6's half strength
applies the same way it does to Harami.
"""


# --- §7.3.12 Matching Low ---------------------------------------------------


def _judge_matching_low(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.3.12: two black days closing at the same price after a decline.

    "The same price" is §2.6's `Equal`, measured against the later bar's range.
    §7.3.12 records that Morris's much narrower alternative for the mirrored
    Matching High — within a thousandth — is not adopted, because it would leave
    this section and three others effectively unmatchable.
    """
    previous, current = window[0], window[1]
    if trend != DOWNTREND:
        return None
    if not (is_black(previous) and scales.long_body(previous)):
        return None
    if not is_black(current):
        return None
    if not scales.equal(current.close, previous.close, current):
        return None
    return Match(BULLISH)


MATCHING_LOW = PatternRule(
    name="pat_matching_low",
    bar_count=2,
    requires_trend=True,
    judge=_judge_matching_low,
)
"""§7.3.12 `CDLMATCHINGLOW`. Downtrend, bullish, min_history 11.

Graded `No`, so like §7.3.11 it computes no confirmation.
"""


# --- §7.3.13 In-Neck Line ---------------------------------------------------


def _judge_in_neck(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.3.13: a small counter-coloured day closing barely into the body.

    A continuation, so the direction runs with the trend. Rule 5 asks the close
    to enter the previous body and to stay §2.6-equal to the previous close,
    which is how §7.3.13 renders "slightly into" — Morris says of the two closes
    that for all practical purposes they are equal, so no separate penetration
    ceiling is invented.

    The long first day is asked for on the bullish side only. §7.3.13 leaves that
    asymmetry standing because Morris writes "long white day" there and nothing
    of the kind on the bearish side.
    """
    previous, current = window[0], window[1]
    if trend == DOWNTREND and is_black(previous) and is_white(current):
        direction = BEARISH
        first_day_must_be_long = False
        opened_beyond = current.open < previous.low
        closed_into_the_body = current.close > previous.close
    elif trend == UPTREND and is_white(previous) and is_black(current):
        direction = BULLISH
        first_day_must_be_long = True
        opened_beyond = current.open > previous.high
        closed_into_the_body = current.close < previous.close
    else:
        return None
    if first_day_must_be_long and not scales.long_body(previous):
        return None
    if not scales.short_body(current):
        return None
    if not opened_beyond:
        return None
    if not closed_into_the_body:
        return None
    if not scales.equal(current.close, previous.close, current):
        return None
    return Match(direction)


IN_NECK = PatternRule(
    name="pat_in_neck",
    bar_count=2,
    requires_trend=True,
    judge=_judge_in_neck,
    confirm=confirms_by_close_direction,
)
"""§7.3.13 `CDLINNECK`. Trend required, continuation, `Required` confirmation, min_history 11.

The small second candle comes from Nison — "it should also be a small white
candle" — and decision C adopts it. §7.3.14 shows the contrast: there Nison's
"(usually a small one)" is a tendency and no size requirement follows.
"""


# --- §7.3.14 On-Neck Line ---------------------------------------------------


def _judge_on_neck(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.3.14: the counter-coloured day closing at the first day's extreme.

    Rule 3 has no length requirement of any kind. Morris rules one out in so many
    words — "this day does not need to be a long day" — and Nison's "(usually a
    small one)" is a tendency, so §7.3.14 keeps the second bar unmeasured. That is
    the single difference from §7.3.13, whose second bar must be short.

    Rule 5 is what names the pattern: the close sits on the first day's low on the
    bearish side and on its high on the bullish one, within §2.6's tolerance.
    """
    previous, current = window[0], window[1]
    if trend == DOWNTREND and is_black(previous) and is_white(current):
        direction = BEARISH
        opened_beyond = current.open < previous.low
        neckline = previous.low
    elif trend == UPTREND and is_white(previous) and is_black(current):
        direction = BULLISH
        opened_beyond = current.open > previous.high
        neckline = previous.high
    else:
        return None
    if not scales.long_body(previous):
        return None
    if not opened_beyond:
        return None
    if not scales.equal(current.close, neckline, current):
        return None
    return Match(direction)


ON_NECK = PatternRule(
    name="pat_on_neck",
    bar_count=2,
    requires_trend=True,
    judge=_judge_on_neck,
    confirm=CONFIRMS_BEARISH_SIDE_ONLY,
)
"""§7.3.14 `CDLONNECK`. Trend required, continuation, min_history 11.

Graded `Required` bearish and `No` bullish, the reverse order of §7.3.2's line
and the same effect.
"""


# --- §7.3.15 Thrusting Line -------------------------------------------------


def _judge_thrusting(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.3.15: deeper into the body than In-Neck, not past the midpoint.

    Rules 5 and 6 are a floor and a ceiling and they are where this section meets
    its neighbours. The floor is §7.3.13's `Equal` negated, which §7.3.15 chose so
    that In-Neck and Thrusting neither overlap nor leave a gap between them. The
    ceiling is §4.3's midpoint, non-strict: a close exactly on the midpoint is
    Thrusting rather than Piercing, because the sources write Piercing as "more
    than halfway" and Thrusting as "does not close above the middle".

    Rule 2 asks for no length on the bearish side and §7.3.15's bullish sentence
    adds a long first day, the same asymmetry §7.3.13 carries.
    """
    previous, current = window[0], window[1]
    if trend == DOWNTREND and is_black(previous) and is_white(current):
        direction = BEARISH
        first_day_must_be_long = False
        opened_beyond = current.open < previous.low
        closed_into_the_body = current.close > previous.close
        stayed_below_the_midpoint = current.close <= body_mid(previous)
    elif trend == UPTREND and is_white(previous) and is_black(current):
        direction = BULLISH
        first_day_must_be_long = True
        opened_beyond = current.open > previous.high
        closed_into_the_body = current.close < previous.close
        stayed_below_the_midpoint = current.close >= body_mid(previous)
    else:
        return None
    if first_day_must_be_long and not scales.long_body(previous):
        return None
    if not opened_beyond:
        return None
    if not closed_into_the_body:
        return None
    if scales.equal(current.close, previous.close, current):
        return None
    if not stayed_below_the_midpoint:
        return None
    return Match(direction)


THRUSTING = PatternRule(
    name="pat_thrusting",
    bar_count=2,
    requires_trend=True,
    judge=_judge_thrusting,
    confirm=CONFIRMS_BEARISH_SIDE_ONLY,
)
"""§7.3.15 `CDLTHRUSTING`. Trend required, continuation, min_history 11.

Graded `Suggested` bearish and `No` bullish, so only a bearish match is confirmed.


§7.3.15 also declines to put a threshold on Nison's "considerably lower" open:
rule 4 already requires the open below the previous low and rule 5 requires a
close well inside the body, so the two together carry what the phrase meant.
"""


# --- §7.3.16 Stick Sandwich -------------------------------------------------


def _judge_stick_sandwich(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.3.16: three bars whose two sides share no rule.

    The bullish side is the pattern the name describes — a white day filling the
    space between two black ones that close at the same price. The bearish side
    is not its mirror: it asks for the middle body to sit under the first close
    and end under the first open, and for the third body to engulf the middle
    one, and it never mentions two closes matching. §7.3.16 states plainly that
    the asymmetry is Morris's text rather than a shortcut taken here.

    Three bars, so §3 reads the trend on bar `t - 2` and §6 puts warm-up at 12.
    """
    first, second, third = window[0], window[1], window[2]
    if trend == DOWNTREND:
        if not is_black(first):
            return None
        if not (is_white(second) and second.low > first.close):
            return None
        if not (is_black(third) and scales.equal(third.close, first.close, third)):
            return None
        return Match(BULLISH)
    if trend == UPTREND:
        if not is_white(first):
            return None
        if not (is_black(second) and second.open < first.close and second.close < first.open):
            return None
        if not (is_white(third) and engulf(second, third)):
            return None
        return Match(BEARISH, _wrap_strength(second, third))
    return None


STICK_SANDWICH = PatternRule(
    name="pat_stick_sandwich",
    bar_count=3,
    requires_trend=True,
    judge=_judge_stick_sandwich,
    confirm=CONFIRMS_BEARISH_SIDE_ONLY,
)
"""§7.3.16 `CDLSTICKSANDWICH`. Trend required, directional, min_history 12.

Half strength reaches only the bearish side, because §5.6's boundary is an
engulfment or a containment sharing one end and the bullish side has neither.
Confirmation lands on the same side and for an unrelated reason: the section is
graded `No` bullish and `Suggested` bearish.
"""
