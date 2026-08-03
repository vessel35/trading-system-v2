"""Compare the sixty-one candlestick patterns against TA-Lib's `CDL` functions.

What this package is for, and what it is not for
------------------------------------------------

`tests/indicator_reference/` is the model for the arrangement here — values captured once
from an outside library, frozen, and never depended on at run time — but the question is a
different one. There, an outside library computes the same formula from the same standard,
so a mismatch means somebody transcribed something wrongly. Here, §10.3 of the pattern
standard states that mismatches are expected, and the two structural reasons are decisions
the standard took on purpose: decision A refused TA-Lib's `TA_SetCandleSettings` table and
§2 put every scale over the judged bar's own high-low range, while decision B made §3's
prior trend part of the pattern where TA-Lib mostly judges shape alone.

**TA-Lib is the comparison, never the source.** Where the two disagree the standard is
right and TA-Lib is different. Nothing here may be used to argue an implementation or a
threshold should move, and `divergence.py` records why each pattern diverges precisely so
that the reason stays attached to a decision instead of drifting into "we matched the
library".

The output worth having
-----------------------

A pattern TA-Lib matches repeatedly while we never match it once. Two sections were once
written with conditions no bar could satisfy at all, and an arithmetic sweep found those; a
rule that is satisfiable in principle but unreachable on real-shaped data survives that
sweep untouched. This comparison is the only axis that can see it, so
`test_pattern_reference_values.py` fails on any such pattern that has no investigated
explanation recorded beside it.

The four parts
--------------

`series.py` builds the four thousand bars both sides are run over and fingerprints them.
`talib_signals.py` holds the captured `CDL` output, or declares that none has been
captured. `divergence.py` is the hand-written table of expected relations and their causes.
`comparison.py` counts the five per-bar outcomes. This module merges them and refuses a
registered pattern that nobody classified.

Capturing the values
--------------------

`scripts/capture_talib_pattern_signals.py`, run once in a throwaway environment that has
TA-Lib installed, rewrites `talib_signals.py` in place. Neither the suite nor continuous
integration imports TA-Lib, and no test requires the environment to exist; the ones that
need values skip while `CAPTURED` is false and say in the skip message how to produce them.
`docs/roadmap-stage-3-0-plan.md` carries the same instructions.

Section numbers in this file are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

from core_lib.patterns import DEFAULT_PATTERN_REGISTRY

from . import talib_signals
from .comparison import Tally, our_series, registered_specs, tally_one
from .divergence import (
    CAUSE_COVERAGE,
    DIVERGENCES,
    PENETRATION_FUNCTIONS,
    TALIB_FUNCTIONS,
    Cause,
    Divergence,
)
from .series import BAR_COUNT, reference_candles, series_fingerprint
from .talib_signals import CAPTURED, SIGNALS

__all__ = [
    "BAR_COUNT",
    "CAPTURED",
    "CAPTURE_INSTRUCTIONS",
    "CAUSE_COVERAGE",
    "DIVERGENCES",
    "PENETRATION_FUNCTIONS",
    "SIGNALS",
    "TALIB_FUNCTIONS",
    "Cause",
    "Divergence",
    "Tally",
    "our_series",
    "reference_candles",
    "registered_specs",
    "series_fingerprint",
    "talib_signals",
    "tally_one",
]

CAPTURE_INSTRUCTIONS = (
    "TA-Lib signals have not been captured. In a throwaway environment with TA-Lib "
    "installed, run scripts/capture_talib_pattern_signals.py, which rewrites "
    "services/core-lib/tests/pattern_reference/talib_signals.py in place. Neither this "
    "repository nor continuous integration depends on TA-Lib at any other time."
)
"""What a skipped test says instead of passing quietly.

A skip with no instructions is indistinguishable from a test nobody meant to run, and this
package spends most of its life in the skipped state.
"""


def _reject_a_pattern_nobody_classified() -> None:
    """Refuse a registered pattern with no row in the divergence table, and the reverse.

    Enforced here, at import, rather than in a test. A pattern registered without a row
    would otherwise be compared against nothing and reported as agreeing by omission, and
    the unexplained-silence check — the one finding this package exists to produce — would
    never look at it. Failing at import means the file cannot be half-updated.

    The reverse direction matters as much. A row naming a pattern that no longer exists is
    a classification of nothing, and it would keep a retired pattern's reasoning alive in a
    table that reads as current.
    """
    registered = {spec.name for spec in DEFAULT_PATTERN_REGISTRY.list()}
    classified = set(DIVERGENCES)
    unclassified = sorted(registered - classified)
    orphaned = sorted(classified - registered)
    problems = []
    if unclassified:
        problems.append(f"registered but absent from the divergence table: {unclassified}")
    if orphaned:
        problems.append(f"in the divergence table but not registered: {orphaned}")
    if problems:
        raise ValueError("; ".join(problems))


def _reject_a_trend_claim_the_registry_contradicts() -> None:
    """Refuse a row whose prior-trend cause disagrees with the registered spec.

    `PatternSpec.requires_trend` is what actually decides whether §3 runs, and the table
    claims the same thing in prose. Two statements of one fact drift, and this one can be
    checked for free and without TA-Lib, so it is checked rather than trusted.
    """
    disagreements = []
    for spec in DEFAULT_PATTERN_REGISTRY.list():
        claimed = Cause.PRIOR_TREND in DIVERGENCES[spec.name].causes
        if claimed != spec.requires_trend:
            disagreements.append(
                f"{spec.name} is registered with requires_trend={spec.requires_trend} "
                f"but the divergence table {'claims' if claimed else 'omits'} the prior-trend cause"
            )
    if disagreements:
        raise ValueError("; ".join(disagreements))


_reject_a_pattern_nobody_classified()
_reject_a_trend_claim_the_registry_contradicts()
