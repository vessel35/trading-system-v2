"""Check the sixty-one patterns against TA-Lib, and against the table that explains them.

The values, the series they were produced from, and the hand-written classification of
every pattern live in the `pattern_reference` package, whose docstring says why an outside
library is a comparison here and never a source. This module states only what has to hold.

Most of the file is dormant until somebody runs the capture. That is deliberate and it is
also the file's main hazard, so the skips name the script that ends it rather than passing
in silence. Three checks run either way: the cause counts have to match the table, the
patterns have to obey §5.3's warm-up contract over a series far longer than the ones the
other pattern tests use, and §5.2's shape-only lines have to claim no direction. A fourth
statement — that every registered pattern is classified — is enforced when the package is
imported, so a missing row fails collection instead of any single test.

One thing captured values are deliberately not asserted on is the direction of a shared
match. TA-Lib's sign means the candle's colour on some functions and the pattern's bearing
on others, so an assertion either way would encode a belief about the comparison target
rather than a claim of the standard. The count is kept instead: `Tally.both_conflict` is
what to read when investigating whether the two sides disagree about a pattern's bearing.

Section numbers in this file are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

import math
from collections import Counter

import pytest

from pattern_reference import (
    BAR_COUNT,
    CAPTURE_INSTRUCTIONS,
    CAPTURED,
    CAUSE_COVERAGE,
    DIVERGENCES,
    PENETRATION_FUNCTIONS,
    SIGNALS,
    TALIB_FUNCTIONS,
    Cause,
    our_series,
    registered_specs,
    series_fingerprint,
    talib_signals,
    tally_one,
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


def test_every_pattern_is_judged_on_every_bar_after_warm_up() -> None:
    """§5.3's contract holds over four thousand bars, not just over a short fixture.

    NaN means the judgment could not run yet and may appear only before `min_history`;
    every later bar carries finite values in all four keys. This runs without TA-Lib
    because it compares the implementation against its own standard, and the long series
    exercises far more shapes than the hand-built fixtures elsewhere in the suite.
    """

    produced = our_series()
    for spec in registered_specs():
        values = produced[spec.name]
        assert len(values) == BAR_COUNT
        for index, value in enumerate(values):
            warming_up = index < spec.min_history - 1
            for key, number in value.items():
                assert math.isnan(number) == warming_up, f"{key} at index {index}"


@_NEEDS_CAPTURE
def test_the_capture_describes_this_series() -> None:
    """Captured signals belong to the bars this repository still builds.

    A change to `series.py` leaves the signals answering a question about bars that no
    longer exist. Comparing our output against them would then be comparing two different
    series and reporting the difference as a disagreement about the rules.
    """

    assert talib_signals.SERIES_FINGERPRINT == series_fingerprint()
    assert talib_signals.BAR_COUNT == BAR_COUNT
    assert talib_signals.TALIB_VERSION, "a capture must record which TA-Lib produced it"


@_NEEDS_CAPTURE
def test_the_capture_covers_every_pattern_in_the_table() -> None:
    """Each of the sixty-one functions was called, including ones that never matched.

    A function absent from the capture and a function that matched nothing are different
    facts, and only the sparse encoding makes them look alike. The capture writes an entry
    for every function it called, so a missing key means the capture was incomplete.
    """

    assert set(SIGNALS) == set(TALIB_FUNCTIONS.values())


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
    """The tally accounts for every bar of the series once.

    Weak on its own and deliberately so: it is the check that the comparison machinery is
    reading both sides over the same bars, which everything below depends on.
    """

    tally = tally_one(
        our_series()[pattern],
        SIGNALS[TALIB_FUNCTIONS[pattern]],
        name=pattern,
    )
    assert tally.judged + tally.warming_up == BAR_COUNT


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

    The reverse is checked too. A recorded silence for a pattern that does match is stale,
    and a stale entry silently excuses the next real finding on that row.
    """

    entry = DIVERGENCES[pattern]
    tally = tally_one(
        our_series()[pattern],
        SIGNALS[entry.talib_function],
        name=pattern,
    )
    if entry.expected_silence is None:
        assert not (tally.talib_matches > 0 and tally.our_matches == 0), (
            f"{entry.talib_function} matched {tally.talib_matches} bars and {pattern} matched "
            f"none. Investigate why the rule is unreachable on this series and record the "
            f"finding in divergence.py's expected_silence. Do not relax the rule."
        )
    else:
        assert tally.our_matches == 0, (
            f"{pattern} matched {tally.our_matches} bars, so its recorded expected_silence is "
            f"stale and must be removed"
        )


def test_no_pattern_claims_a_direction_it_is_not_allowed_to_claim() -> None:
    """§5.2's nine shape-only lines report zero direction on every bar they match.

    This is the half of the direction contract the comparison itself cannot check. TA-Lib
    signs those same nine functions by candle colour, so its sign and our `_dir` are not
    the same quantity and no captured value can settle whether ours is right; what can be
    settled is that we claim nothing, which is what §5.2 requires. It runs without a
    capture for that reason.
    """

    produced = our_series()
    directionless = {
        name for name, entry in DIVERGENCES.items() if Cause.NO_DIRECTION_CLAIMED in entry.causes
    }
    for name in sorted(directionless):
        for index, value in enumerate(produced[name]):
            if value[name] == 1.0:
                assert value[f"{name}_dir"] == 0.0, f"{name} claimed a direction at index {index}"
