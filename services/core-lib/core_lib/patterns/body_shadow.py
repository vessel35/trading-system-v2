"""Implement §7.2 of the pattern standard: body-and-shadow shapes.

Six sections. Five of them are candle *lines* rather than patterns — Morris gives
them no header fields at all — so they ask for no trend, carry no confirmation
grade, and report no direction. Belt-hold is the exception on every count.

Two boundaries in this group were drawn by the standard rather than by a source,
and both are recorded here because a reader will otherwise look for them in the
sources and not find them. High-Wave and Spinning Top are described identically
in the originals — small body, long shadows — so §7.2.1 separates them by making
High-Wave's shadows reach two bodies while Spinning Top only needs them longer
than the body. And Long Line asks for a long body and nothing else: TA-Lib adds a
shadow requirement to its own function, but Morris's Long Days passage has none,
so §7.2.5 does not add one either.

Section numbers in this module are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

from collections.abc import Sequence

from core_lib.types import Candle

from . import scales
from .judgment import Match, PatternRule, confirms_by_close_direction
from .outputs import BEARISH, BULLISH, DIRECTIONLESS
from .primitives import is_black, is_white
from .trend import DOWNTREND, UPTREND

# --- §7.2.1 High-Wave Candle ------------------------------------------------


def _judge_high_wave(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.2.1: a short body with both shadows at least two bodies long.

    Nison's "very long" shadows become §2.4's multiple of two, one step stronger
    than Spinning Top's "greater than". The two patterns nest by construction:
    anything matching here also matches §7.1.11.
    """
    candle = window[-1]
    if not scales.short_body(candle):
        return None
    if not (scales.long_upper_shadow(candle) and scales.long_lower_shadow(candle)):
        return None
    return Match(DIRECTIONLESS)


HIGH_WAVE = PatternRule(
    name="pat_high_wave",
    bar_count=1,
    requires_trend=False,
    judge=_judge_high_wave,
)
"""§7.2.1 `CDLHIGHWAVE`. No trend, no confirmation grade, no direction (§5.2)."""


# --- §7.2.2 Marubozu --------------------------------------------------------


def _judge_marubozu(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.2.2: a long body with neither shadow.

    "No shadow" is §2.5's very short shadow rather than an exact equality, by
    §4.2: requiring exactly zero would leave this pattern unmatchable in
    practice. The colour is not asked for — a white one is a White Marubozu and a
    black one a Black Marubozu, and §5.2 keeps that out of the direction key.
    """
    candle = window[-1]
    if not scales.long_body(candle):
        return None
    if not (scales.no_upper_shadow(candle) and scales.no_lower_shadow(candle)):
        return None
    return Match(DIRECTIONLESS)


MARUBOZU = PatternRule(
    name="pat_marubozu",
    bar_count=1,
    requires_trend=False,
    judge=_judge_marubozu,
)
"""§7.2.2 `CDLMARUBOZU`. No trend, no confirmation grade, no direction."""


# --- §7.2.3 Closing Marubozu ------------------------------------------------


def _judge_closing_marubozu(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.2.3: a long body with no shadow at the closing end.

    Which end that is depends on the colour, so this is the one section in §7.2
    that reads the colour to decide *which* condition applies rather than as a
    condition itself. The opposite shadow may be anything. A colourless bar has
    no closing end to speak of, and cannot reach here anyway: a body of zero is
    never a long body outside the degenerate bar §2.7 already excludes.
    """
    candle = window[-1]
    if not scales.long_body(candle):
        return None
    if is_white(candle):
        closing_end_is_bare = scales.no_upper_shadow(candle)
    elif is_black(candle):
        closing_end_is_bare = scales.no_lower_shadow(candle)
    else:
        return None
    if not closing_end_is_bare:
        return None
    return Match(DIRECTIONLESS)


CLOSING_MARUBOZU = PatternRule(
    name="pat_closing_marubozu",
    bar_count=1,
    requires_trend=False,
    judge=_judge_closing_marubozu,
)
"""§7.2.3 `CDLCLOSINGMARUBOZU`. No trend, no confirmation grade, no direction."""


# --- §7.2.4 Belt-hold -------------------------------------------------------


def _judge_belt_hold(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.2.4: a long body opening at the extreme of its own range.

    The two sides are deliberately not mirror images, and §7.2.4 says so. The
    bullish side asks for a bare lower shadow *and* a bare upper one, because
    Nison has it closing at or near the session high. The bearish side asks only
    for the bare upper shadow, because Nison says only that it continues lower
    through the session and never fixes where it closes. Symmetrising the two
    would add a condition the sources do not have.
    """
    candle = window[-1]
    if not scales.long_body(candle):
        return None
    if trend == DOWNTREND and is_white(candle):
        if scales.no_lower_shadow(candle) and scales.no_upper_shadow(candle):
            return Match(BULLISH)
        return None
    if trend == UPTREND and is_black(candle):
        if scales.no_upper_shadow(candle):
            return Match(BEARISH)
        return None
    return None


BELT_HOLD = PatternRule(
    name="pat_belt_hold",
    bar_count=1,
    requires_trend=True,
    judge=_judge_belt_hold,
    confirm=confirms_by_close_direction,
)
"""§7.2.4 `CDLBELTHOLD`. Trend required, directional, min_history 10.

Confirmation is graded `Suggested` on the bullish side and `Required` on the
bearish one; neither source says what it is, so §5.5's general rule applies and
one key carries both sides.
"""


# --- §7.2.5 Long Line Candle ------------------------------------------------


def _judge_long_line(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.2.5: a long body. The section's rule list is that one line."""
    if not scales.long_body(window[-1]):
        return None
    return Match(DIRECTIONLESS)


LONG_LINE = PatternRule(
    name="pat_long_line",
    bar_count=1,
    requires_trend=False,
    judge=_judge_long_line,
)
"""§7.2.5 `CDLLONGLINE`. No trend, no confirmation grade, no direction."""


# --- §7.2.6 Short Line Candle -----------------------------------------------


def _judge_short_line(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.2.6: a short body, the same section read with a maximum instead."""
    if not scales.short_body(window[-1]):
        return None
    return Match(DIRECTIONLESS)


SHORT_LINE = PatternRule(
    name="pat_short_line",
    bar_count=1,
    requires_trend=False,
    judge=_judge_short_line,
)
"""§7.2.6 `CDLSHORTLINE`. No trend, no confirmation grade, no direction."""
