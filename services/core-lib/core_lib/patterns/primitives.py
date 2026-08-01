"""Implement §1 of the candlestick pattern standard: shared candle primitives.

Every pattern in §7 reaches its bars through this module. It holds the derived
quantities of §1.1, the colour definitions of §1.2, the six gaps of §1.3, and the
division convention of §1.4.

The standard is `docs/references/candlestick_pattern_calc_spec.md`. It stands
beside the technical-indicator standard rather than inside it, so nothing here
adds to that document's count of 89 systems.
"""

from collections.abc import Sequence

from core_lib.types import Candle

# --- §1.1 derived quantities ------------------------------------------------


def body(candle: Candle) -> float:
    """Return the real body size ``abs(C - O)``."""
    return abs(candle.close - candle.open)


def body_top(candle: Candle) -> float:
    """Return the upper end of the real body, ``max(O, C)``."""
    return max(candle.open, candle.close)


def body_bottom(candle: Candle) -> float:
    """Return the lower end of the real body, ``min(O, C)``."""
    return min(candle.open, candle.close)


def body_mid(candle: Candle) -> float:
    """Return the real body midpoint, ``(O + C) / 2``."""
    return (candle.open + candle.close) / 2.0


def upper_shadow(candle: Candle) -> float:
    """Return the upper shadow, ``H - BodyTop``."""
    return candle.high - body_top(candle)


def lower_shadow(candle: Candle) -> float:
    """Return the lower shadow, ``BodyBot - L``."""
    return body_bottom(candle) - candle.low


def candle_range(candle: Candle) -> float:
    """Return the high-low range, ``H - L``.

    Named with the `candle_` prefix because `range` is a builtin. Every scale in
    §2 divides by this quantity, which is why §2.7 has to say what happens when
    it is zero.
    """
    return candle.high - candle.low


def range_mid(candle: Candle) -> float:
    """Return the high-low midpoint, ``(H + L) / 2``.

    This is what §3 feeds to the trend average — not the close. Missing that
    substitution changes every trend judgment silently.
    """
    return (candle.high + candle.low) / 2.0


# --- §1.2 colour ------------------------------------------------------------


def is_white(candle: Candle) -> bool:
    """Return whether the candle closed above its open."""
    return candle.close > candle.open


def is_black(candle: Candle) -> bool:
    """Return whether the candle closed below its open."""
    return candle.close < candle.open


def is_colorless(candle: Candle) -> bool:
    """Return whether ``C == O``, which is neither white nor black (§1.2).

    A rule that demands a colour fails on such a bar. A rule that demands only a
    doji still holds, because those rules do not ask for a colour.
    """
    return candle.close == candle.open


# --- §1.3 gaps --------------------------------------------------------------
#
# The three kinds are different measurements and decision D keeps them apart. A
# pattern's own section in §7 states which kind it reads, with the source quote
# that fixes it. §2.8 covers the five patterns whose source text does not say.


def gap_up_body(previous: Candle, current: Candle) -> bool:
    """Return whether the current real body sits entirely above the previous one."""
    return body_bottom(current) > body_top(previous)


def gap_down_body(previous: Candle, current: Candle) -> bool:
    """Return whether the current real body sits entirely below the previous one."""
    return body_top(current) < body_bottom(previous)


def gap_up_range(previous: Candle, current: Candle) -> bool:
    """Return whether the current low is above the previous high."""
    return current.low > previous.high


def gap_down_range(previous: Candle, current: Candle) -> bool:
    """Return whether the current high is below the previous low."""
    return current.high < previous.low


def gap_up_open(previous: Candle, current: Candle) -> bool:
    """Return whether the current open is above the previous close."""
    return current.open > previous.close


def gap_down_open(previous: Candle, current: Candle) -> bool:
    """Return whether the current open is below the previous close."""
    return current.open < previous.close


# --- §1.4 the division convention -------------------------------------------
#
# §1.4 closes every place a pattern would divide by zero, and closes it here so
# no pattern section reopens it. Two bars are undefined in two different ways.
#
# A `Range == 0` bar leaves every range-denominated scale undefined. §2.7 rules
# that a pattern touching such a bar is *not matched* (0.0), never NaN: the
# judgment ran and failed, which is a different statement from "cannot judge
# yet". `any_degenerate` is the gate a pattern calls before evaluating, and each
# scale in §2 also answers False on its own so a negated scale cannot smuggle a
# degenerate bar into a match.
#
# A `Body == 0` bar leaves the shadow multiples of §2.4 undefined instead, and
# §1.4 answers that case by the direction of the comparison. A lower bound holds
# when the shadow is positive: without that a dragonfly doji would fail the shape
# requirement of Takuri, and Morris defines Takuri as a kind of dragonfly doji.
# An upper bound fails there instead: without that a gravestone doji would pass
# Inverted Hammer's shape requirement and collide with its own pattern. The two
# halves are `shadow_reaches_multiple` and `shadow_within_multiple`.
#
# Neither convention needs an actual division. The standard writes every scale
# in multiplied form (`Body > 0.50 * Range`, not `Body / Range > 0.50`), so the
# implementation multiplies too and no quotient is ever formed.


def is_degenerate(candle: Candle) -> bool:
    """Return whether all four prices are equal, leaving §2's scales undefined."""
    return candle_range(candle) == 0.0


def any_degenerate(candles: Sequence[Candle]) -> bool:
    """Return whether any bar in a pattern window is degenerate (§2.7).

    A pattern evaluates this over the bars it spans and reports not-matched when
    it answers True.
    """
    return any(is_degenerate(candle) for candle in candles)


def shadow_reaches_multiple(shadow: float, body_size: float, multiple: float) -> bool:
    """Return ``shadow >= multiple * body`` under §1.4's zero-body rule.

    With a zero body the product is zero and the plain comparison would call any
    shadow — including no shadow at all — long enough. §1.4 rules instead that
    the comparison holds when the shadow is positive and fails when the shadow is
    also zero, which is what this returns.

    This is the lower-bound half of §1.4's `ShadowRatio` extension, the half §2.4
    defines. `shadow_within_multiple` is the upper-bound half and answers the
    zero-body case the other way; §1.4 says in so many words that the two
    directions must not be unified.
    """
    if body_size == 0.0:
        return shadow > 0.0
    return shadow >= multiple * body_size


def shadow_within_multiple(shadow: float, body_size: float, multiple: float) -> bool:
    """Return ``shadow <= multiple * body`` under §1.4's zero-body rule.

    The upper-bound half of §1.4's `ShadowRatio` extension. A zero body sends the
    ratio to infinity when the shadow is positive, so the comparison is **false**
    there, and §1.4 makes it false for a zero shadow as well.

    Carrying the lower bound's answer over to here would break the standard, and
    §1.4 names the pattern it breaks. §7.1.9 Inverted Hammer asks for
    `US <= 2.0 * Body`; if a zero body satisfied that, a gravestone doji with an
    arbitrarily long upper shadow would pass Inverted Hammer's shape requirement,
    which contradicts §7.1.5 Gravestone Doji existing as its own pattern.
    """
    if body_size == 0.0:
        return False
    return shadow <= multiple * body_size
