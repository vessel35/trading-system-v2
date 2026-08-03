"""Check the sixty-one patterns against TA-Lib, and against the table that explains them.

The values, the regimes they were produced from, and the hand-written classification of
every pattern live in the `pattern_reference` package, whose docstring says why an outside
library is a comparison here and never a source. This module states only what has to hold.

Most of the file is dormant until somebody runs the capture. That is deliberate and it is
also the file's main hazard, so the skips name the script that ends it rather than passing
in silence. Four checks run either way: the cause counts have to match the table, the
patterns have to obey §5.3's warm-up contract over every regime, §5.2's shape-only lines
have to claim no direction, and no regime may be described by what it makes match. A fifth
statement — that every registered pattern is classified — is enforced when the package is
imported, so a missing row fails collection instead of any single test.

Everything the capture does decide is decided over the **bundle** rather than over one
regime. A pattern silent on a market with no gaps and matching on a market full of them is
not silent, and a table that recorded it as such would excuse the next real finding on that
row. `series.py` says why one series was not enough.

One thing captured values are deliberately not asserted on is the magnitude of a shared
match. TA-Lib's 80, 100, and 200 answer questions of its own and none of them is §5.6's
`_strength`. The sign is read, and only where both sides claim one: where they claim
opposite signs the bar is counted as a conflict and `Divergence.direction_conflict` has to
explain it.

Section numbers in this file are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

import math
import re
from collections import Counter

import pytest

from pattern_reference import (
    CAPTURE_INSTRUCTIONS,
    CAPTURED,
    CAUSE_COVERAGE,
    DIVERGENCES,
    HIGH_AGREEMENT,
    HIGH_AGREEMENT_FLOOR,
    PENETRATION_FUNCTIONS,
    REGIME_NAMES,
    REGIMES,
    REGIMES_BY_NAME,
    SIGNALS,
    TALIB_FUNCTIONS,
    Cause,
    comparisons,
    fingerprints,
    high_agreement_patterns,
    our_series,
    patterns_matched_by_neither,
    registered_specs,
    talib_signals,
)

_NEEDS_CAPTURE = pytest.mark.skipif(not CAPTURED, reason=CAPTURE_INSTRUCTIONS)


def test_every_cause_covers_the_number_of_patterns_it_claims() -> None:
    """The counts written into the cause docstrings match the table.

    Each `Cause` explains itself in prose that ends with how many patterns carry it. Prose
    and table are two statements of one fact, so this compares them rather than trusting
    that an edit to one reached the other.
    """

    counted = Counter(cause for entry in DIVERGENCES.values() for cause in entry.causes)
    assert dict(counted) == dict(CAUSE_COVERAGE)


@pytest.mark.parametrize("regime", REGIME_NAMES)
def test_every_pattern_is_judged_on_every_bar_after_warm_up(regime: str) -> None:
    """§5.3's contract holds over every regime, not just over a short fixture.

    NaN means the judgment could not run yet and may appear only before `min_history`;
    every later bar carries finite values in all four keys. This runs without TA-Lib
    because it compares the implementation against its own standard, and running it on all
    seven markets exercises far more shapes than the hand-built fixtures elsewhere in the
    suite — including the quiet market, where §2.7's degenerate bar actually occurs.
    """

    produced = our_series(regime)
    bar_count = REGIMES_BY_NAME[regime].bar_count
    for spec in registered_specs():
        values = produced[spec.name]
        assert len(values) == bar_count
        for index, value in enumerate(values):
            warming_up = index < spec.min_history - 1
            for key, number in value.items():
                assert math.isnan(number) == warming_up, f"{key} at index {index}"


def test_no_regime_is_described_by_what_it_makes_match() -> None:
    """A regime's stated character may not name a pattern or a threshold.

    This is the one rule `series.py` cannot be trusted to keep on its own, because breaking
    it is what a well-meaning edit looks like: a market described as "the one that finally
    fires Tri Star" is a market that was built to fire it, and the comparison becomes a
    self-confirmation. Naming a `CDL` function or a §2 section in the description is the
    visible symptom, so it is the thing checked.
    """

    forbidden = re.compile(r"\bCDL[A-Z0-9]*\b|§|\bpat_[a-z_]+\b|\bTA[- ]?Lib\b")
    for regime in REGIMES:
        found = forbidden.findall(regime.character)
        assert not found, f"{regime.name} describes itself with {found}"


def test_no_pattern_claims_a_direction_it_is_not_allowed_to_claim() -> None:
    """§5.2's nine shape-only lines report zero direction on every bar they match.

    This is the half of the direction contract the comparison itself cannot check. TA-Lib
    signs those same nine functions by candle colour, so its sign and our `_dir` are not
    the same quantity and no captured value can settle whether ours is right; what can be
    settled is that we claim nothing, which is what §5.2 requires. It runs without a
    capture for that reason.
    """

    directionless = {
        name for name, entry in DIVERGENCES.items() if Cause.NO_DIRECTION_CLAIMED in entry.causes
    }
    for regime in REGIME_NAMES:
        produced = our_series(regime)
        for name in sorted(directionless):
            for index, value in enumerate(produced[name]):
                if value[name] == 1.0:
                    assert value[f"{name}_dir"] == 0.0, (
                        f"{name} claimed a direction at {regime} index {index}"
                    )


@_NEEDS_CAPTURE
def test_the_capture_describes_these_series() -> None:
    """Captured signals belong to the bars this repository still builds.

    A change to `series.py` leaves the signals answering a question about bars that no
    longer exist. Comparing our output against them would then be comparing two different
    series and reporting the difference as a disagreement about the rules. The check is per
    regime, and it also refuses a capture that covered a different set of regimes than the
    bundle now defines — half a bundle is the failure that would otherwise read as TA-Lib
    matching nothing on the regimes nobody captured.
    """

    assert set(talib_signals.SERIES_FINGERPRINTS) == set(REGIME_NAMES)
    assert set(talib_signals.BAR_COUNTS) == set(REGIME_NAMES)
    assert set(SIGNALS) == set(REGIME_NAMES)
    assert dict(talib_signals.SERIES_FINGERPRINTS) == fingerprints()
    for regime in REGIMES:
        assert talib_signals.BAR_COUNTS[regime.name] == regime.bar_count
    assert talib_signals.TALIB_VERSION, "a capture must record which TA-Lib produced it"


@_NEEDS_CAPTURE
@pytest.mark.parametrize("regime", REGIME_NAMES)
def test_the_capture_covers_every_pattern_in_the_table(regime: str) -> None:
    """Each of the sixty-one functions was called on every regime, silent ones included.

    A function absent from the capture and a function that matched nothing are different
    facts, and only the sparse encoding makes them look alike. The capture writes an entry
    for every function it called, so a missing key means the capture was incomplete.
    """

    assert set(SIGNALS[regime]) == set(TALIB_FUNCTIONS.values())


@_NEEDS_CAPTURE
def test_the_penetration_claim_matches_the_library() -> None:
    """The table's claim about which functions take an argument is the library's own.

    `divergence.py` tags seven patterns with a cause that asserts something about TA-Lib's
    surface. The capture records what the library actually reported, so the assertion is
    checked instead of believed. The values themselves are provenance only: §7 fixes each
    depth from its source and has no setting for a default to be adopted into.
    """

    assert set(talib_signals.FUNCTION_PARAMETERS) == set(PENETRATION_FUNCTIONS)
    for function, parameters in talib_signals.FUNCTION_PARAMETERS.items():
        assert "penetration" in parameters, function


@_NEEDS_CAPTURE
@pytest.mark.parametrize("pattern", sorted(DIVERGENCES))
def test_every_bar_falls_into_exactly_one_of_the_five_outcomes(pattern: str) -> None:
    """The tally accounts for every bar of every regime once.

    Weak on its own and deliberately so: it is the check that the comparison machinery is
    reading both sides over the same bars, which everything below depends on.
    """

    entry = comparisons()[pattern]
    for regime in REGIME_NAMES:
        tally = entry.by_regime[regime]
        assert tally.judged + tally.warming_up == REGIMES_BY_NAME[regime].bar_count


@_NEEDS_CAPTURE
@pytest.mark.parametrize("pattern", sorted(DIVERGENCES))
def test_a_pattern_only_we_never_match_is_explained(pattern: str) -> None:
    """**The finding this package exists to produce.**

    TA-Lib matching a pattern repeatedly while we never match it once is what an
    unreachable rule looks like from outside. Two sections were once written with
    conditions no bar could satisfy; an arithmetic sweep caught those, and it cannot catch
    a rule that is satisfiable in principle but never reached on real-shaped data.

    Divergence itself is expected and is not what fails here — §10.3 says so, and the
    causes in `divergence.py` say which decision each divergence comes from. What fails is
    silence on our side that nobody has looked into. The fix is to investigate the pattern
    and write what was found into `expected_silence`, never to widen a rule until the
    comparison agrees: §10.3 forbids moving an implementation or a threshold toward TA-Lib,
    and doing it here would turn the one check that can find an unreachable rule into a
    check that finds nothing.

    Judged over the bundle, which is what makes the reverse direction bite. A silence
    recorded against one market goes stale the moment another market reaches the rule, and
    a stale entry silently excuses the next real finding on that row.
    """

    entry = DIVERGENCES[pattern]
    result = comparisons()[pattern]
    if entry.expected_silence is None:
        assert not (result.talib_matches > 0 and result.our_matches == 0), (
            f"{entry.talib_function} matched {result.talib_matches} bars across the bundle and "
            f"{pattern} matched none. Investigate why the rule is unreachable on every regime "
            f"and record the finding in divergence.py's expected_silence. Do not relax the rule."
        )
    else:
        assert result.our_matches == 0, (
            f"{pattern} matched {result.our_matches} bars across the bundle, so its recorded "
            f"expected_silence is stale and must be removed"
        )


@_NEEDS_CAPTURE
@pytest.mark.parametrize("pattern", sorted(DIVERGENCES))
def test_a_pattern_neither_side_matches_is_explained(pattern: str) -> None:
    """A row the comparison produced no evidence for has to say why.

    This is the weaker silence and the one the bundle exists to shrink. When TA-Lib is
    silent too, nothing has been learned about the pattern: not that it agrees, not that it
    diverges, only that no market in the bundle reached it. Leaving that unrecorded lets a
    row sit in the catalog looking compared when it never was.

    Checked in both directions, like the silence above. A `mutual_silence` for a pattern
    either side now matches is stale and has to go.
    """

    entry = DIVERGENCES[pattern]
    result = comparisons()[pattern]
    nobody_matched = result.our_matches == 0 and result.talib_matches == 0
    if entry.mutual_silence is None:
        assert not nobody_matched, (
            f"neither {pattern} nor {entry.talib_function} matched a single bar in the bundle, "
            f"so the comparison says nothing about this row. Investigate what no regime reaches "
            f"and record it in divergence.py's mutual_silence."
        )
    else:
        assert nobody_matched, (
            f"{pattern} or {entry.talib_function} now matches, so the recorded mutual_silence "
            f"is stale and must be removed"
        )


@_NEEDS_CAPTURE
@pytest.mark.parametrize("pattern", sorted(DIVERGENCES))
def test_a_direction_conflict_is_explained(pattern: str) -> None:
    """A bar where the two sides claim opposite bearings has to be accounted for.

    The count existed before this check did and nobody read it, which is the failure mode
    a number in a dataclass invites. Reading it here means a systematic sign disagreement —
    a function whose sign is a recognition marker rather than a bearing, say — has to be
    written down as such rather than absorbed into "divergence is expected".

    Both directions again: an explanation for a pattern that no longer conflicts describes
    a comparison that no longer happens.
    """

    entry = DIVERGENCES[pattern]
    result = comparisons()[pattern]
    if entry.direction_conflict is None:
        assert result.both_conflict == 0, (
            f"{pattern} and {entry.talib_function} claimed opposite directions on "
            f"{result.both_conflict} shared bars ({dict(result.conflict_bars_by_regime)}). "
            f"Investigate and record it in divergence.py's direction_conflict."
        )
    else:
        assert result.both_conflict > 0, (
            f"{pattern} no longer conflicts with {entry.talib_function} on any bar, so its "
            f"recorded direction_conflict is stale and must be removed"
        )


@_NEEDS_CAPTURE
def test_the_patterns_that_agree_closely_are_the_recorded_ones() -> None:
    """Agreement is pinned as deliberately as divergence is.

    A file that recorded only where the two sides part company would not notice a pattern
    that used to track its `CDL` function bar for bar drifting away from it, and that
    drift is a change worth explaining. The set is compared in both directions, so a
    pattern joining it fails as loudly as one leaving.
    """

    assert high_agreement_patterns(HIGH_AGREEMENT_FLOOR) == HIGH_AGREEMENT


@_NEEDS_CAPTURE
def test_the_bundle_reaches_more_of_the_catalog_than_one_series_did() -> None:
    """Adding regimes has to buy evidence, and the count is stated rather than assumed.

    The original four thousand bars left eleven patterns neither side matched. If the
    bundle ever regresses past that, a regime has been weakened or removed and the
    comparison covers less of the catalog than the series it replaced — which is the one
    outcome adding markets is supposed to make impossible.
    """

    assert len(patterns_matched_by_neither()) < 11
