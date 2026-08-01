"""Implement §6 of the candlestick pattern standard: ``min_history``.

`min_history` is the number of confirmed candles a pattern needs before it can
produce a valid value. It is not the number of candles before some event gets
announced — §5.4's alignment rule handles that, and confirmation delay is
explicitly excluded here.

Two formulas cover all sixty-one patterns, and the reason there are only two is
§2's choice of denominator. Every scale reads its own bar's high-low range and no
earlier bar, so no scale contributes warm-up. What is left is the pattern's own
span and, when it asks for one, the trend average.
"""

from .trend import TREND_EMA_PERIOD


def min_history_for(bar_count: int, *, requires_trend: bool) -> int:
    """Return the confirmed candles a pattern needs before its first valid value.

    Without a trend requirement the answer is the span itself: `bar_count` bars
    all exist first at index `bar_count - 1`.

    With one, the pattern's first day — `bar_count - 1` bars behind the judged
    bar — must already carry a ten-period average. That average first exists at
    index 9, so the judged bar first exists at index `10 + bar_count - 2` and the
    count is one more than that.

    For the patterns whose span is a range rather than a fixed number, pass the
    *shortest* admissible span. That is the first bar where the pattern can be
    judged at all, which is what this number means. Rising/Falling Three Methods
    is the one such pattern, and §7.5.5 states its value as 13, from the shortest
    form of four bars.
    """
    if bar_count <= 0:
        raise ValueError("bar_count must be positive")
    if not requires_trend:
        return bar_count
    return TREND_EMA_PERIOD + bar_count - 1
