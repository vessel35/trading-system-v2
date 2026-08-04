"""Put legacy four-key judgment and TA-Lib raw integers side by side.

The comparison is a migration tally, not the target contract. TA-Lib v0.7.1 is the source
for the direct raw integer ports, while the registered implementation still exposes the
repository's older four-key shape until the adapter and registry cutover are complete.

Counting matches on each side is not enough for that. Two sides that each match forty bars
of a series have said nothing to each other unless those are the same forty bars, so every
outcome here is decided per bar and the two questions are kept apart:

`bar_agreement` asks whether the two sides fire on the same bars — of every bar either side
matched, the fraction both matched. `direction_agreement` asks, of those shared bars, the
fraction where the two did not claim opposite directions. A pattern can score high on the
first and low on the second, and that combination is a different finding from either side
being silent.

Both are reported per regime and over the bundle. Where a pattern goes wrong is often a
property of the market rather than of the rule — a gap pattern that agrees on a gappy
market and diverges on a market with no gaps is telling you about §1.3, not about §7 — and
a single pooled number hides that.

Two things are still deliberately separated.

TA-Lib magnitudes are compared to four-key strength only where their meaning is verified.
Engulfing's ±80 and ±100 map to the legacy 0.5 and 1.0 strength split. Other non-±100
values remain raw event-shape facts for the adapter stage, especially Hikkake's ±200
confirmation markers.

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
from dataclasses import dataclass, field
from types import MappingProxyType

from core_lib.patterns import DEFAULT_PATTERN_REGISTRY
from core_lib.patterns.outputs import BOUNDARY_STRENGTH, FULL_STRENGTH
from core_lib.patterns.registry import PatternSpec
from core_lib.patterns.talib_raw import (
    TALIB_RAW_BOUNDARY_MAGNITUDE,
    TALIB_RAW_MATCH_MAGNITUDE,
)

from .divergence import TALIB_FUNCTIONS
from .series import REGIME_NAMES, candles_for
from .talib_signals import SIGNALS

TALIB_BASE_MATCH_MAGNITUDE = TALIB_RAW_MATCH_MAGNITUDE
"""TA-Lib's ordinary match magnitude, distinct from confirmation or other event markers."""

TALIB_STRENGTH_MAGNITUDES_BY_PATTERN: Mapping[str, Mapping[float, int]] = MappingProxyType(
    {
        "pat_engulfing": MappingProxyType(
            {
                BOUNDARY_STRENGTH: TALIB_RAW_BOUNDARY_MAGNITUDE,
                FULL_STRENGTH: TALIB_RAW_MATCH_MAGNITUDE,
            }
        )
    }
)
"""Verified legacy strength-to-TA-Lib magnitude mappings."""


@dataclass(frozen=True, slots=True)
class Tally:
    """The counted outcomes of one pattern against its `CDL` function, over one regime."""

    both_agree: int
    """Both matched the same event on the same bar and their directions do not contradict."""

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

    conflict_bars: tuple[int, ...] = field(default=())
    """The bars where both matched the same event and claimed the opposite direction.

    The indices are kept rather than only their count. A conflict is the one outcome that
    cannot be explained without looking at the bar it happened on, and a number nobody can
    trace back to a bar is a number nobody investigates.
    """

    same_bar_different_event_bars: tuple[int, ...] = field(default=())
    """The bars where both arrays are non-zero but the raw integer maps to another event.

    Hikkake confirmation is the known example: TA-Lib reports ±200 in the same integer
    series, while the legacy shape has a separate confirmation key.
    """

    @property
    def both_conflict(self) -> int:
        """Return how many same-event bars both matched on with opposite directions."""
        return len(self.conflict_bars)

    @property
    def same_bar_different_event(self) -> int:
        """Return how many same-bar non-zero pairs were not the same event."""
        return len(self.same_bar_different_event_bars)

    @property
    def judged(self) -> int:
        """Return the bars the counted outcomes were counted over."""
        return (
            self.both_agree
            + self.both_conflict
            + self.same_bar_different_event
            + self.ours_only
            + self.talib_only
            + self.neither
        )

    @property
    def both_matched(self) -> int:
        """Return how many bars both sides matched the same event on."""
        return self.both_agree + self.both_conflict

    @property
    def our_matches(self) -> int:
        """Return how many bars we matched on."""
        return self.both_matched + self.same_bar_different_event + self.ours_only

    @property
    def talib_matches(self) -> int:
        """Return how many bars TA-Lib reported non-zero on."""
        return self.both_matched + self.same_bar_different_event + self.talib_only

    @property
    def matched_by_either(self) -> int:
        """Return bars at least one side matched."""
        return self.both_matched + self.same_bar_different_event + self.ours_only + self.talib_only

    @property
    def overlap_expectation(self) -> float | None:
        """Return `ours * talib / judged`, used as a visibility measure for sparse rows."""
        if self.our_matches == 0 or self.talib_matches == 0 or self.judged == 0:
            return None
        return self.our_matches * self.talib_matches / self.judged

    @property
    def overlap_rate(self) -> float | None:
        """Return observed same-event overlap as a fraction of the maximum possible overlap."""
        possible = min(self.our_matches, self.talib_matches)
        if possible == 0:
            return None
        return self.both_matched / possible

    @property
    def bundle_zero_overlap(self) -> bool:
        """Return whether both sides matched but never on the same event bar."""
        return self.our_matches > 0 and self.talib_matches > 0 and self.both_matched == 0

    @property
    def regime_zero_overlap(self) -> bool:
        """Return whether local zero overlap is visible enough to need investigation."""
        expectation = self.overlap_expectation
        return self.bundle_zero_overlap and expectation is not None and expectation >= 1.0

    @property
    def material_overlap_deficit(self) -> bool:
        """Return whether observed overlap falls below expectation by more than sqrt(E)."""
        expectation = self.overlap_expectation
        return (
            expectation is not None
            and expectation >= 1.0
            and expectation - self.both_matched > math.sqrt(expectation)
        )


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


def _is_same_event_magnitude(name: str, ours: Mapping[str, float], theirs: int) -> bool:
    """Return whether a TA-Lib raw magnitude maps to the legacy matched event."""
    magnitude = abs(theirs)
    strength_mapping = TALIB_STRENGTH_MAGNITUDES_BY_PATTERN.get(name)
    if strength_mapping is None:
        return magnitude == TALIB_BASE_MATCH_MAGNITUDE
    strength = ours[f"{name}_strength"]
    return strength_mapping.get(strength) == magnitude


def tally_one(
    ours: Sequence[Mapping[str, float]],
    theirs: Mapping[int, int],
    *,
    name: str,
) -> Tally:
    """Count the five outcomes for one pattern over one regime.

    `theirs` is sparse in the sense `talib_signals.SIGNALS` is: a bar not present in it
    carried a zero. `ours` is the full series our vectorized path produced.
    """
    outcomes = {"both_agree": 0, "ours_only": 0, "talib_only": 0, "neither": 0}
    conflicts: list[int] = []
    different_events: list[int] = []
    warming_up = 0
    for index, value in enumerate(ours):
        matched = value[name]
        if math.isnan(matched):
            warming_up += 1
            continue
        their_value = theirs.get(index, 0)
        if matched and their_value:
            if not _is_same_event_magnitude(name, value, their_value):
                different_events.append(index)
                continue
            if _directions_contradict(value[f"{name}_dir"], their_value):
                conflicts.append(index)
                continue
            key = "both_agree"
        elif matched:
            key = "ours_only"
        elif their_value:
            key = "talib_only"
        else:
            key = "neither"
        outcomes[key] += 1
    return Tally(
        **outcomes,
        warming_up=warming_up,
        conflict_bars=tuple(conflicts),
        same_bar_different_event_bars=tuple(different_events),
    )


@dataclass(frozen=True, slots=True)
class Comparison:
    """One pattern against its `CDL` function across the whole bundle of regimes."""

    pattern: str
    talib_function: str
    by_regime: Mapping[str, Tally]

    def _total(self, attribute: str) -> int:
        return sum(int(getattr(tally, attribute)) for tally in self.by_regime.values())

    @property
    def both_agree(self) -> int:
        """Return shared bars with no direction contradiction, over the bundle."""
        return self._total("both_agree")

    @property
    def both_conflict(self) -> int:
        """Return shared bars where the two claimed opposite directions, over the bundle."""
        return self._total("both_conflict")

    @property
    def same_bar_different_event(self) -> int:
        """Return same-bar non-zero pairs that were not the same event, over the bundle."""
        return self._total("same_bar_different_event")

    @property
    def both_matched(self) -> int:
        """Return shared bars, over the bundle."""
        return self._total("both_matched")

    @property
    def ours_only(self) -> int:
        """Return bars only we matched, over the bundle."""
        return self._total("ours_only")

    @property
    def talib_only(self) -> int:
        """Return bars only TA-Lib matched, over the bundle."""
        return self._total("talib_only")

    @property
    def neither(self) -> int:
        """Return bars neither matched, over the bundle."""
        return self._total("neither")

    @property
    def judged(self) -> int:
        """Return the bars the outcomes were counted over, across every regime."""
        return self._total("judged")

    @property
    def our_matches(self) -> int:
        """Return how many bars we matched, across every regime."""
        return self._total("our_matches")

    @property
    def talib_matches(self) -> int:
        """Return how many bars TA-Lib matched, across every regime."""
        return self._total("talib_matches")

    @property
    def matched_by_either(self) -> int:
        """Return bars at least one side matched, across every regime."""
        return self.both_matched + self.same_bar_different_event + self.ours_only + self.talib_only

    @property
    def overlap_expectation(self) -> float | None:
        """Return `ours * talib / judged`, used as a visibility measure for sparse rows."""
        if self.our_matches == 0 or self.talib_matches == 0 or self.judged == 0:
            return None
        return self.our_matches * self.talib_matches / self.judged

    @property
    def overlap_rate(self) -> float | None:
        """Return observed same-event overlap as a fraction of the maximum possible overlap."""
        possible = min(self.our_matches, self.talib_matches)
        if possible == 0:
            return None
        return self.both_matched / possible

    @property
    def bundle_zero_overlap(self) -> bool:
        """Return whether both sides matched somewhere but never on the same event bar."""
        return self.our_matches > 0 and self.talib_matches > 0 and self.both_matched == 0

    @property
    def regime_zero_overlap(self) -> bool:
        """Return whether zero overlap is visible enough to need investigation."""
        expectation = self.overlap_expectation
        return self.bundle_zero_overlap and expectation is not None and expectation >= 1.0

    @property
    def material_overlap_deficit(self) -> bool:
        """Return whether observed overlap falls below expectation by more than sqrt(E)."""
        expectation = self.overlap_expectation
        return (
            expectation is not None
            and expectation >= 1.0
            and expectation - self.both_matched > math.sqrt(expectation)
        )

    @property
    def bar_agreement(self) -> float | None:
        """Return the fraction of matched bars that both sides matched.

        `None` when neither side matched anywhere, because a ratio out of no bars is not a
        zero — it is the absence of evidence, and the two must not be reported alike.
        """
        if self.matched_by_either == 0:
            return None
        return self.both_matched / self.matched_by_either

    @property
    def direction_agreement(self) -> float | None:
        """Return the fraction of shared bars where the directions did not contradict.

        `None` when the two never matched the same bar, for the same reason as above.
        """
        if self.both_matched == 0:
            return None
        return self.both_agree / self.both_matched

    @property
    def conflict_bars_by_regime(self) -> Mapping[str, tuple[int, ...]]:
        """Return the conflicting bars of each regime that has any."""
        return MappingProxyType(
            {
                regime: tally.conflict_bars
                for regime, tally in self.by_regime.items()
                if tally.conflict_bars
            }
        )

    @property
    def same_bar_different_event_bars_by_regime(self) -> Mapping[str, tuple[int, ...]]:
        """Return same-bar different-event bars of each regime that has any."""
        return MappingProxyType(
            {
                regime: tally.same_bar_different_event_bars
                for regime, tally in self.by_regime.items()
                if tally.same_bar_different_event_bars
            }
        )


def our_series(regime_name: str) -> Mapping[str, list[dict[str, float]]]:
    """Return every registered pattern's output over one regime.

    Computed once per regime and reused, because sixty-one patterns over the bundle is the
    most expensive thing in this package and every caller wants the same answer.
    """
    if regime_name not in _OUR_CACHE:
        candles = candles_for(regime_name)
        _OUR_CACHE[regime_name] = {
            spec.name: [dict(value) for value in spec.compute_vectorized(candles)]
            for spec in DEFAULT_PATTERN_REGISTRY.list()
        }
    return _OUR_CACHE[regime_name]


_OUR_CACHE: dict[str, dict[str, list[dict[str, float]]]] = {}


def compare_one(pattern: str) -> Comparison:
    """Return one pattern's comparison across every regime."""
    function = TALIB_FUNCTIONS[pattern]
    return Comparison(
        pattern=pattern,
        talib_function=function,
        by_regime=MappingProxyType(
            {
                regime: tally_one(
                    our_series(regime)[pattern],
                    SIGNALS[regime][function],
                    name=pattern,
                )
                for regime in REGIME_NAMES
            }
        ),
    )


def comparisons() -> Mapping[str, Comparison]:
    """Return every registered pattern's comparison, built once and reused."""
    if not _COMPARISON_CACHE:
        for spec in DEFAULT_PATTERN_REGISTRY.list():
            _COMPARISON_CACHE[spec.name] = compare_one(spec.name)
    return MappingProxyType(_COMPARISON_CACHE)


_COMPARISON_CACHE: dict[str, Comparison] = {}


def registered_specs() -> list[PatternSpec]:
    """Return the registered patterns in a deterministic order."""
    return DEFAULT_PATTERN_REGISTRY.list()
