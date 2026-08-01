"""Implement §2 of the candlestick pattern standard: the scales.

The sources describe a "long body" or an "almost equal close" in words and give
no numbers, so §2 fixes the numbers. Every threshold below is the standard's,
with the marking §2 gives it — some come straight from Morris or Nison, others
are conventions the standard adopted and justified. None of them is chosen here
and none may be re-chosen by a pattern: §2 says the seven scales are all §7 may
reference, and that a pattern section may not invent an eighth.

One decision runs through the whole module. §2 settled on *that bar's high-low
range* as the denominator, out of the three ways Morris allowed. The consequence
that matters for the code is in §6: a scale reading only its own bar carries no
warm-up, so `min_history` never has a scale term.
"""

from core_lib.types import Candle

from .primitives import (
    body,
    candle_range,
    is_degenerate,
    lower_shadow,
    shadow_reaches_multiple,
    upper_shadow,
)

LONG_BODY_RANGE_FRACTION = 0.50
"""§2.1, from Morris: a long body takes more than 50% of the high-low range."""

SHORT_BODY_RANGE_FRACTION = 1.0 / 3.0
"""§2.2, derived from Morris's spinning top rule: both shadows longer than the body."""

DOJI_RANGE_FRACTION = 0.03
"""§2.3: the upper end of the 1–3% band Morris reports as working well."""

LONG_SHADOW_BODY_MULTIPLE = 2.0
"""§2.4, from Nison and Morris: "at least twice the height of the real body"."""

VERY_SHORT_SHADOW_RANGE_FRACTION = 0.10
"""§2.5, Morris's own worked value: 10% or less of the high-low range."""

EQUAL_RANGE_FRACTION = 0.03
"""§2.6: Morris directs that the doji tolerance also settles "equal" comparisons."""

NEAR_RANGE_FRACTION = 0.10
"""§2.6: "near" shares §2.5's threshold because the sources use them alike."""

SIMILAR_BODY_FRACTION = 0.50
"""§2.6: two bodies are similar when the smaller is at least half the larger."""


def long_body(candle: Candle) -> bool:
    """Return whether the body exceeds half the high-low range (§2.1).

    Strict, because the source reads "more than".
    """
    if is_degenerate(candle):
        return False
    return body(candle) > LONG_BODY_RANGE_FRACTION * candle_range(candle)


def short_body(candle: Candle) -> bool:
    """Return whether the body is under a third of the high-low range (§2.2).

    Strict, because the spinning top rule this is derived from reads "greater
    than". The band between a third and a half is neither long nor short, which
    is what Morris describes when he says many days fall into neither category.
    """
    if is_degenerate(candle):
        return False
    return body(candle) < SHORT_BODY_RANGE_FRACTION * candle_range(candle)


def doji(candle: Candle) -> bool:
    """Return whether the body is at most 3% of the high-low range (§2.3).

    Equality allowed, because the source's form reads "Maximum".
    """
    if is_degenerate(candle):
        return False
    return body(candle) <= DOJI_RANGE_FRACTION * candle_range(candle)


def long_upper_shadow(
    candle: Candle,
    multiple: float = LONG_SHADOW_BODY_MULTIPLE,
) -> bool:
    """Return whether the upper shadow is at least ``multiple`` bodies (§2.4).

    The denominator here is the body, not the range: the sources fixed it that
    way and §2 keeps it rather than forcing its own choice of denominator on the
    one place the sources spoke. Equality allowed, because the sources read
    "at least".

    The multiple is a parameter because §2.4 records three places where the
    sources give a value other than two — Takuri and Shooting Star ask for three.
    Those patterns pass their own number; nothing here invents one.
    """
    return shadow_reaches_multiple(upper_shadow(candle), body(candle), multiple)


def long_lower_shadow(
    candle: Candle,
    multiple: float = LONG_SHADOW_BODY_MULTIPLE,
) -> bool:
    """Return whether the lower shadow is at least ``multiple`` bodies (§2.4)."""
    return shadow_reaches_multiple(lower_shadow(candle), body(candle), multiple)


def no_upper_shadow(candle: Candle) -> bool:
    """Return whether the upper shadow is at most 10% of the range (§2.5).

    "Closes at or near the high" is this same scale. §2.5 says so explicitly so
    that a second threshold is not created for a fact already measured.
    """
    if is_degenerate(candle):
        return False
    return upper_shadow(candle) <= VERY_SHORT_SHADOW_RANGE_FRACTION * candle_range(candle)


def no_lower_shadow(candle: Candle) -> bool:
    """Return whether the lower shadow is at most 10% of the range (§2.5)."""
    if is_degenerate(candle):
        return False
    return lower_shadow(candle) <= VERY_SHORT_SHADOW_RANGE_FRACTION * candle_range(candle)


def equal(first: float, second: float, candle: Candle) -> bool:
    """Return whether two prices count as equal within §2.6's tolerance.

    `candle` is the *later* of the two bars being compared; §2.6 fixes that so
    the tolerance does not depend on which bar the caller happens to pass.

    Exact equality is not usable in practice, which is why the sources' "the
    closes are the same" needs a tolerance at all. Morris directs that the doji
    concept settles these comparisons, so the tolerance is §2.3's.
    """
    if is_degenerate(candle):
        return False
    return abs(first - second) <= EQUAL_RANGE_FRACTION * candle_range(candle)


def near(first: float, second: float, candle: Candle) -> bool:
    """Return whether two prices count as near within §2.6's tolerance.

    "Equal" and "near" are different words in the sources and stay different
    here. `candle` is the later of the two bars, as in `equal`.
    """
    if is_degenerate(candle):
        return False
    return abs(first - second) <= NEAR_RANGE_FRACTION * candle_range(candle)


def similar_body(first: Candle, second: Candle) -> bool:
    """Return whether two real bodies are of similar size (§2.6).

    The smaller body must be at least half the larger, which bounds the ratio of
    the two at 2. This is the one scale with no range denominator, because the
    source phrasing compares the two bodies against each other rather than
    against a bar.
    """
    sizes = (body(first), body(second))
    return min(sizes) >= SIMILAR_BODY_FRACTION * max(sizes)
