"""Implement §4.1 of the candlestick pattern standard: engulfment and containment.

§4 is about where an inequality is strict and where it is not. Nearly all of it
is convention the standard had to settle itself, and §4.2 routes those cases into
the scales of §2 — "equal" to §2.6, "no tail" to §2.5, a size comparison to a
strict inequality. Only one place in the whole standard has the sources speaking
directly about strictness, and that place is here.

Morris states it twice, once under Engulfing and once under Harami: either the
tops or the bottoms of the two bodies may be equal, but not both at once. So the
two comparisons below are non-strict and a single exclusion removes the one case
that would otherwise let a body engulf or contain a body identical to it. §5.6
then reads a match where exactly one end coincides as a boundary match and gives
it half strength, which is why the standard bothered to admit that case rather
than requiring both ends to be strict.

Nothing here reads a scale or the high-low range. The relation is between two
real bodies and the sources fixed it exactly, which is why §7.3.1 Engulfing is
one of the few sections whose "what we chose" note says: nothing.

Section numbers in this module are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

from core_lib.types import Candle

from .primitives import body_bottom, body_top


def engulf(previous: Candle, current: Candle) -> bool:
    """Return whether the current real body engulfs the previous one (§4.1).

    Both comparisons are non-strict, and the two ends coinciding at once is the
    only excluded case.
    """
    return _wraps(inner=previous, outer=current)


def contain(previous: Candle, current: Candle) -> bool:
    """Return whether the current real body sits inside the previous one (§4.1).

    The same relation as `engulf` with the two bars exchanged, which is how §4.1
    writes it: Harami is the inclusion Engulfing is, read the other way round.
    """
    return _wraps(inner=current, outer=previous)


def _wraps(*, inner: Candle, outer: Candle) -> bool:
    """Return whether `outer`'s real body covers `inner`'s without matching it exactly."""
    inner_bottom, inner_top = body_bottom(inner), body_top(inner)
    outer_bottom, outer_top = body_bottom(outer), body_top(outer)
    if outer_bottom > inner_bottom or outer_top < inner_top:
        return False
    return not (outer_bottom == inner_bottom and outer_top == inner_top)
