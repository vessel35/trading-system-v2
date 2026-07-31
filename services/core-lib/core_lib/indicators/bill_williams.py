"""Track Bill Williams indicators awaiting later registration.

The four this catalog carried — Alligator, Fractals, Gator Oscillator, and the
Market Facilitation Index — are registered now, and their calculations live in
`systems.py` beside the other rule-based systems that share its two conventions.
The module stays because the follow-up catalog is assembled from a fixed list of
category tuples, and an empty tuple states that this category has nothing left
outstanding where a missing module would state nothing at all.
"""

FOLLOW_UP_INDICATORS: tuple[str, ...] = ()
