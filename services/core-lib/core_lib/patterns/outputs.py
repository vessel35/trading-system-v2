"""Implement §5 of the candlestick pattern standard: the output contract.

A pattern reports four numbers per bar, not one: whether it matched, which way it
points, whether the match was clean or sat exactly on a boundary, and whether the
follow-up bar confirmed it. Decision F keeps all four so nothing is thrown away
that a consumer might later want folded differently.

The distinction between `0.0` and `NaN` is a contract, not a formatting choice.
`0.0` means the judgment ran and the pattern did not hold; `NaN` means the
judgment could not run yet and appears only before `min_history` is reached. A
degenerate bar (§2.7) therefore yields `0.0` — the judgment ran — and never NaN.
Collapsing the two would leave the Evidence completeness check unable to tell
warm-up from a genuine non-match.

Confirmation lands on a different bar from the match. §5.4 forbids writing a
confirmation back onto the pattern bar, because the value at index `t` may only
depend on candles up to `t`. So the four builders below let `confirmed` be set on
a bar that did not itself match: that combination is not a contradiction, it is
the normal shape of a confirmed pattern.
"""

import re

NAME_PREFIX = "pat_"
"""§5.1, from decision G: a pattern name never collides with an indicator name."""

DIRECTION_SUFFIX = "_dir"
STRENGTH_SUFFIX = "_strength"
CONFIRM_SUFFIX = "_confirm"

BULLISH = 1.0
BEARISH = -1.0
DIRECTIONLESS = 0.0
"""§5.2: the nine shape-only candle lines report no direction even when they match.

The sources treat them as names for a shape rather than as directional signals,
and a consumer that wants the bar's colour can read it from the candle.
"""

FULL_STRENGTH = 1.0
BOUNDARY_STRENGTH = 0.5
"""§5.6: half strength marks the one boundary the sources themselves distinguish.

That is an engulfing or containment where exactly one of the two body ends
coincides. §4.1 permits it and separates it from a clean engulfment, so the two
are reported apart.
"""

NOT_MATCHED = 0.0
MATCHED = 1.0

_NAME_PATTERN = re.compile(r"^pat_[a-z0-9]+(?:_[a-z0-9]+)*$")
_RESERVED_SUFFIXES = (DIRECTION_SUFFIX, STRENGTH_SUFFIX, CONFIRM_SUFFIX)
_DIRECTIONS = (BULLISH, BEARISH, DIRECTIONLESS)
_STRENGTHS = (FULL_STRENGTH, BOUNDARY_STRENGTH)


def assert_pattern_name(name: str) -> None:
    """Reject a name that breaks §5.1's naming rule.

    A name ending in one of the three suffixes is rejected as well, because
    `pat_x_dir` would produce the same key as the direction output of `pat_x` and
    the two would silently overwrite each other in one result dictionary.
    """
    if not _NAME_PATTERN.fullmatch(name):
        raise ValueError(
            f"pattern name must be lowercase words joined by underscores "
            f"and start with {NAME_PREFIX!r}: {name!r}"
        )
    for suffix in _RESERVED_SUFFIXES:
        if name.endswith(suffix):
            raise ValueError(f"pattern name must not end with the reserved {suffix!r}: {name!r}")


def output_keys(name: str) -> tuple[str, str, str, str]:
    """Return the match, direction, strength, and confirmation keys for a pattern."""
    assert_pattern_name(name)
    return (
        name,
        f"{name}{DIRECTION_SUFFIX}",
        f"{name}{STRENGTH_SUFFIX}",
        f"{name}{CONFIRM_SUFFIX}",
    )


def _build(name: str, values: tuple[float, float, float, float]) -> dict[str, float]:
    return dict(zip(output_keys(name), values, strict=True))


def undetermined_outputs(name: str) -> dict[str, float]:
    """Return all four keys as NaN, which §5.3 allows only before warm-up ends."""
    undetermined = float("nan")
    return _build(name, (undetermined, undetermined, undetermined, undetermined))


def no_match_outputs(name: str, *, confirmed: bool = False) -> dict[str, float]:
    """Return the outputs of a bar that was judged and did not match.

    `confirmed` stays available because a confirmation belongs to the bar it
    happened on, and that bar is later than — and usually different from — the
    bar that matched.
    """
    return _build(
        name,
        (NOT_MATCHED, DIRECTIONLESS, NOT_MATCHED, MATCHED if confirmed else NOT_MATCHED),
    )


def match_outputs(
    name: str,
    *,
    direction: float,
    strength: float = FULL_STRENGTH,
    confirmed: bool = False,
) -> dict[str, float]:
    """Return the outputs of a bar the pattern matched on.

    Patterns that require confirmation leave `confirmed` false here: the
    confirming bar is a later one, and §5.4 forbids reaching forward to it.
    """
    if direction not in _DIRECTIONS:
        raise ValueError(f"direction must be one of {_DIRECTIONS}: {direction!r}")
    if strength not in _STRENGTHS:
        raise ValueError(f"a matched bar's strength must be one of {_STRENGTHS}: {strength!r}")
    return _build(
        name,
        (MATCHED, direction, strength, MATCHED if confirmed else NOT_MATCHED),
    )
