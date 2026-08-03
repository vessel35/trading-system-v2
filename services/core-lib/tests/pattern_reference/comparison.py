"""Put our judgment and TA-Lib's side by side and count what happens on each bar.

The comparison is a tally, not an assertion. §10.3 says divergence is the expected
outcome, so what is worth producing is a shape of disagreement specific enough to be
attributed to a decision: how often both sides matched and pointed the same way, how often
both matched and contradicted each other, and how often exactly one of them spoke.

Two things are deliberately not compared.

The magnitude of TA-Lib's value is ignored. It reports 100 on a match and 200 on the
confirmed instance of the two Hikkake functions, while our `_strength` is 0.5 only for the
§5.6 boundary case of an engulfment with one coinciding end. The two numbers answer
unrelated questions, and pairing them would manufacture agreement or disagreement out of
nothing.

Bars still warming up are dropped rather than counted. §5.3 makes NaN mean "cannot judge
yet" and it appears only before `min_history`; a bar we have not judged cannot belong in
any of the five outcomes, and folding it into "neither matched" would credit us with
agreeing on bars we never looked at.

Section numbers in this file are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from core_lib.patterns import DEFAULT_PATTERN_REGISTRY
from core_lib.patterns.registry import PatternSpec

from .series import reference_candles


@dataclass(frozen=True, slots=True)
class Tally:
    """The five outcomes of one pattern against its `CDL` function, over judged bars."""

    both_agree: int
    """Both matched and their directions do not contradict each other."""

    both_conflict: int
    """Both matched and each claimed the opposite direction."""

    ours_only: int
    """We matched and TA-Lib reported zero."""

    talib_only: int
    """TA-Lib reported non-zero and we did not match."""

    neither: int
    """Neither matched."""

    warming_up: int
    """Bars dropped before counting, where §5.3 says our output is NaN.

    Not a sixth outcome. It is recorded so the five can be checked to account for every
    remaining bar, which is what catches a series and a capture of different lengths.
    """

    @property
    def judged(self) -> int:
        """Return the bars the five outcomes were counted over."""
        return (
            self.both_agree + self.both_conflict + self.ours_only + self.talib_only + self.neither
        )

    @property
    def our_matches(self) -> int:
        """Return how many bars we matched on."""
        return self.both_agree + self.both_conflict + self.ours_only

    @property
    def talib_matches(self) -> int:
        """Return how many bars TA-Lib reported non-zero on."""
        return self.both_agree + self.both_conflict + self.talib_only


def _directions_contradict(ours: float, theirs: int) -> bool:
    """Return whether the two sides claim opposite directions.

    A contradiction needs both sides to make a claim. §5.2's nine shape-only lines report
    `_dir` of zero, which is the absence of a claim rather than a third direction, so the
    sign TA-Lib puts on those functions — the bar's colour — is not something our zero can
    contradict. Counting those as conflicts would report nine patterns as disagreeing about
    a question only one of them is answering.
    """
    if ours == 0.0 or theirs == 0:
        return False
    return (ours > 0.0) != (theirs > 0)


def tally_one(
    ours: Sequence[Mapping[str, float]],
    theirs: Mapping[int, int],
    *,
    name: str,
) -> Tally:
    """Count the five outcomes for one pattern over one series.

    `theirs` is sparse in the sense `talib_signals.SIGNALS` is: a bar not present in it
    carried a zero. `ours` is the full series our vectorized path produced.
    """
    outcomes = {"both_agree": 0, "both_conflict": 0, "ours_only": 0, "talib_only": 0, "neither": 0}
    warming_up = 0
    for index, value in enumerate(ours):
        matched = value[name]
        if math.isnan(matched):
            warming_up += 1
            continue
        their_value = theirs.get(index, 0)
        if matched and their_value:
            contradicted = _directions_contradict(value[f"{name}_dir"], their_value)
            key = "both_conflict" if contradicted else "both_agree"
        elif matched:
            key = "ours_only"
        elif their_value:
            key = "talib_only"
        else:
            key = "neither"
        outcomes[key] += 1
    return Tally(**outcomes, warming_up=warming_up)


def our_series() -> dict[str, list[dict[str, float]]]:
    """Return every registered pattern's output over the comparison series.

    Computed once and reused, because sixty-one patterns over four thousand bars is the
    most expensive thing in this package and every test in the file wants the same answer.
    """
    if not _CACHE:
        candles = reference_candles()
        for spec in DEFAULT_PATTERN_REGISTRY.list():
            _CACHE[spec.name] = [dict(value) for value in spec.compute_vectorized(candles)]
    return _CACHE


_CACHE: dict[str, list[dict[str, float]]] = {}


def registered_specs() -> list[PatternSpec]:
    """Return the registered patterns in a deterministic order."""
    return DEFAULT_PATTERN_REGISTRY.list()
