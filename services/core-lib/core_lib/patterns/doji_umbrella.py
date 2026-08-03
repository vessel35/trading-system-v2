"""Implement §7.1 of the pattern standard: the doji family and the umbrella lines.

Eleven sections, and each rule below is that section's numbered list and nothing
else. Where a section defers to a scale it calls the scale; where it writes an
inequality out — Takuri's three bodies, Inverted Hammer's two — it uses the
number that section states, because §2.4 records those multiples as the sources'
own and refuses to re-fix them centrally.

Two of the eleven turn on §1.4's zero-body rule pointing in opposite directions,
and the standard says so at length. A dragonfly doji has no body, so the lower
bound in Takuri's and Hammer's shape requirement holds for it — Morris defines
Takuri as a kind of dragonfly doji, so it has to. A gravestone doji has no body
either, and the upper bound in Inverted Hammer's rule 3 fails for it — otherwise
any gravestone doji would satisfy Inverted Hammer's shape and §7.1.5 would have
nothing left to name.

The four keys, the degenerate gate, warm-up, and the placement of confirmations
are not here. `judgment.py` holds them once for all sixty-one patterns.

Section numbers in this module are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

from collections.abc import Sequence

from core_lib.types import Candle

from . import scales
from .judgment import Match, PatternRule, confirms_by_close_direction
from .outputs import BEARISH, BULLISH, DIRECTIONLESS
from .primitives import (
    body,
    body_bottom,
    body_mid,
    body_top,
    gap_up_open,
    lower_shadow,
    range_mid,
    upper_shadow,
)
from .trend import DOWNTREND, UPTREND

TAKURI_SHADOW_MULTIPLE = 3.0
"""§7.1.6, from Morris: "a lower shadow at least three times the length of the body"."""

SHOOTING_STAR_SHADOW_MULTIPLE = 3.0
"""§7.1.10, from Morris: "at least three times as long as the body"."""

# --- §7.1.1 Doji ------------------------------------------------------------


def _judge_doji(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.1.1: the body is at most §2.3's fraction of the high-low range."""
    if not scales.doji(window[-1]):
        return None
    return Match(DIRECTIONLESS)


DOJI = PatternRule(
    name="pat_doji",
    bar_count=1,
    requires_trend=False,
    judge=_judge_doji,
)
"""§7.1.1 `CDLDOJI`. No trend, no confirmation grade, no direction (§5.2)."""


# --- §7.1.2 Long-Legged Doji ------------------------------------------------


def _judge_long_legged_doji(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.1.2: a doji whose two shadows are both long (§2.4)."""
    candle = window[-1]
    if not scales.doji(candle):
        return None
    if not (scales.long_upper_shadow(candle) and scales.long_lower_shadow(candle)):
        return None
    return Match(DIRECTIONLESS)


LONG_LEGGED_DOJI = PatternRule(
    name="pat_long_legged_doji",
    bar_count=1,
    requires_trend=False,
    judge=_judge_long_legged_doji,
)
"""§7.1.2 `CDLLONGLEGGEDDOJI`. No trend, no confirmation grade, no direction."""


# --- §7.1.3 Rickshaw Man ----------------------------------------------------


def _judge_rickshaw_man(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.1.3: a long-legged doji whose body sits in the middle of the range.

    Rule 1 is §7.1.2 in full, which is how the section writes it. Rule 2 renders
    Nison's "in the middle of the session's range" as §2.6's `Near`; the sources
    give no number for that phrase.
    """
    if _judge_long_legged_doji(window, trend) is None:
        return None
    candle = window[-1]
    if not scales.near(body_mid(candle), range_mid(candle), candle):
        return None
    return Match(DIRECTIONLESS)


RICKSHAW_MAN = PatternRule(
    name="pat_rickshaw_man",
    bar_count=1,
    requires_trend=False,
    judge=_judge_rickshaw_man,
)
"""§7.1.3 `CDLRICKSHAWMAN`. No trend, no confirmation grade, no direction."""


# --- §7.1.4 Dragonfly Doji --------------------------------------------------


def _judge_dragonfly_doji(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.1.4: a doji opening, closing, and peaking at the session high.

    Nison asks for the open, high, and close together, which is the narrower of
    the two source readings and the one decision C takes. "At the high" becomes
    §2.5's very short upper shadow rather than an exact equality, because §4.2
    routes "closes at the high" there and an exact equality would leave this
    pattern effectively unmatchable.
    """
    candle = window[-1]
    if not scales.doji(candle):
        return None
    if not scales.no_upper_shadow(candle):
        return None
    if not scales.long_lower_shadow(candle):
        return None
    return Match(BULLISH)


DRAGONFLY_DOJI = PatternRule(
    name="pat_dragonfly_doji",
    bar_count=1,
    requires_trend=False,
    judge=_judge_dragonfly_doji,
)
"""§7.1.4 `CDLDRAGONFLYDOJI`. No trend, no confirmation grade, bullish (§5.2)."""


# --- §7.1.5 Gravestone Doji -------------------------------------------------


def _judge_gravestone_doji(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.1.5: a doji opening and closing at the session low, with a long top."""
    candle = window[-1]
    if not scales.doji(candle):
        return None
    if not scales.no_lower_shadow(candle):
        return None
    if not scales.long_upper_shadow(candle):
        return None
    return Match(BEARISH)


GRAVESTONE_DOJI = PatternRule(
    name="pat_gravestone_doji",
    bar_count=1,
    requires_trend=False,
    judge=_judge_gravestone_doji,
)
"""§7.1.5 `CDLGRAVESTONEDOJI`. No trend, no confirmation grade, bearish."""


# --- §7.1.6 Takuri ----------------------------------------------------------


def _judge_takuri(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.1.6: a dragonfly doji whose lower shadow reaches three bodies.

    Rule 1 is §7.1.4's rules 1 and 2 — doji and no upper shadow — and rule 2
    replaces §7.1.4's rule 3 with the larger multiple Morris states for Takuri.
    """
    candle = window[-1]
    if not scales.doji(candle):
        return None
    if not scales.no_upper_shadow(candle):
        return None
    if not scales.long_lower_shadow(candle, multiple=TAKURI_SHADOW_MULTIPLE):
        return None
    return Match(BULLISH)


TAKURI = PatternRule(
    name="pat_takuri",
    bar_count=1,
    requires_trend=False,
    judge=_judge_takuri,
)
"""§7.1.6 `CDLTAKURI`. No trend, no confirmation grade, bullish."""


# --- §7.1.7 Hammer ----------------------------------------------------------


def _has_hammer_shape(candle: Candle) -> bool:
    """Return §7.1.7's rules 2 to 4, the shape Hanging Man shares verbatim.

    A short body with no upper shadow and a lower shadow of at least two bodies.
    The colour is not asked for; §7.1.7 says so and §7.1.8 inherits the rules
    unchanged, so the two sections differ only in the trend and what they mean.
    """
    if not scales.short_body(candle):
        return False
    if not scales.no_upper_shadow(candle):
        return False
    return scales.long_lower_shadow(candle)


def _judge_hammer(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.1.7: the umbrella shape after a downtrend."""
    if trend != DOWNTREND:
        return None
    if not _has_hammer_shape(window[-1]):
        return None
    return Match(BULLISH)


HAMMER = PatternRule(
    name="pat_hammer",
    bar_count=1,
    requires_trend=True,
    judge=_judge_hammer,
    confirm=confirms_by_close_direction,
)
"""§7.1.7 `CDLHAMMER`. Downtrend, `Required` confirmation, bullish, min_history 10.

Morris grades confirmation `Required` and gives no condition for it, so §5.5's
general rule applies: the next bar closes above this one.
"""


# --- §7.1.8 Hanging Man -----------------------------------------------------


def _judge_hanging_man(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.1.8: the same shape as Hammer, after an uptrend instead."""
    if trend != UPTREND:
        return None
    if not _has_hammer_shape(window[-1]):
        return None
    return Match(BEARISH)


def _confirms_hanging_man(
    window: Sequence[Candle],
    direction: float,
    following: Candle,
) -> bool:
    """Apply §7.1.8's own confirmation: the next close falls below the body.

    Nison names this one rather than leaving it to §5.5's general rule, and he
    gives both a minimum requirement (the next bar *opens* below the body) and a
    recommended one (it *closes* below). §5.5 takes the recommended reading.
    """
    return following.close < body_bottom(window[-1])


HANGING_MAN = PatternRule(
    name="pat_hanging_man",
    bar_count=1,
    requires_trend=True,
    judge=_judge_hanging_man,
    confirm=_confirms_hanging_man,
)
"""§7.1.8 `CDLHANGINGMAN`. Uptrend, confirmation required, bearish, min_history 10.

The two sources disagree on the grade — Morris writes `No`, Nison writes that a
hanging man should be confirmed — and decision C takes the stricter side.
"""


# --- §7.1.9 Inverted Hammer -------------------------------------------------


def _judge_inverted_hammer(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.1.9: a short body low in the range after a decline.

    Morris also writes that the upper shadow is "usually no more than two times"
    the body, but §7.1.9 reads that "usually" as a tendency rather than a
    requirement and leaves it out, the same way §7.3.14 reads Nison's "(usually a
    small one)". Two things follow from the section and are worth restating here.
    A long upper shadow is implied rather than asked for: the two rules below
    leave the upper shadow at least 56.7% of the range. And a gravestone doji in
    a downtrend does match, because a doji body is a short body; §7.1.9 records
    that this agrees with Nison, who separates the inverted hammer from the
    shooting star by preceding trend alone.

    Rule 4 of the section requires nothing: Morris states in so many words that
    no gap down is needed, so there is no condition to write.
    """
    if trend != DOWNTREND:
        return None
    candle = window[-1]
    if not scales.short_body(candle):
        return None
    if not scales.no_lower_shadow(candle):
        return None
    return Match(BULLISH)


def _confirms_inverted_hammer(
    window: Sequence[Candle],
    direction: float,
    following: Candle,
) -> bool:
    """Apply §7.1.9's own confirmation: the next close rises above the body."""
    return following.close > body_top(window[-1])


INVERTED_HAMMER = PatternRule(
    name="pat_inverted_hammer",
    bar_count=1,
    requires_trend=True,
    judge=_judge_inverted_hammer,
    confirm=_confirms_inverted_hammer,
)
"""§7.1.9 `CDLINVERTEDHAMMER`. Downtrend, confirmation required, bullish, min_history 10."""


# --- §7.1.10 Shooting Star --------------------------------------------------


def _judge_shooting_star(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.1.10: a gap-opened short body with a very long upper shadow.

    Two bars, not one. Morris requires prices to gap open after an uptrend and a
    gap needs a bar to measure against, so the span is two and the trend is read
    on the earlier of them. The gap is the plain open-against-previous-close kind
    of §1.3, because Morris writes only "Prices gap open" without saying whether
    he means bodies or ranges.
    """
    if trend != UPTREND:
        return None
    previous, candle = window[0], window[1]
    if not gap_up_open(previous, candle):
        return None
    if not scales.short_body(candle):
        return None
    if not scales.no_lower_shadow(candle):
        return None
    if not scales.long_upper_shadow(candle, multiple=SHOOTING_STAR_SHADOW_MULTIPLE):
        return None
    return Match(BEARISH)


SHOOTING_STAR = PatternRule(
    name="pat_shooting_star",
    bar_count=2,
    requires_trend=True,
    judge=_judge_shooting_star,
    confirm=confirms_by_close_direction,
)
"""§7.1.10 `CDLSHOOTINGSTAR`. Uptrend, `Required` confirmation, bearish, min_history 11.

The eleven is the only value in §7.1 that is neither 1 nor 10, and the gap
requirement is why: a two-bar span puts the first day one bar further back, so
the trend average has to exist one bar earlier.
"""


# --- §7.1.11 Spinning Top ---------------------------------------------------


def _judge_spinning_top(window: Sequence[Candle], trend: float) -> Match | None:
    """Judge §7.1.11: both shadows strictly longer than the body.

    Written out rather than routed through a scale, and §2.2 is the reason: the
    short-body threshold was *derived* from this rule, so asking for both would
    apply the same condition twice. Morris says as much — the small body relative
    to the shadows is what makes the spinning top.

    The comparison is arithmetic and strict, which handles the no-body case the
    way §2.7 asks: a bar with no body matches when both shadows are positive.
    """
    candle = window[-1]
    size = body(candle)
    if not (upper_shadow(candle) > size and lower_shadow(candle) > size):
        return None
    return Match(DIRECTIONLESS)


SPINNING_TOP = PatternRule(
    name="pat_spinning_top",
    bar_count=1,
    requires_trend=False,
    judge=_judge_spinning_top,
)
"""§7.1.11 `CDLSPINNINGTOP`. No trend, no confirmation grade, no direction."""
