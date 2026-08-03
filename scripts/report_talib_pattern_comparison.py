#!/usr/bin/env python3
"""Print the candlestick comparison in full: per pattern, per regime, bar by bar.

This reads the values already captured into
`services/core-lib/tests/pattern_reference/talib_signals.py` and needs no TA-Lib. Only
`scripts/capture_talib_pattern_signals.py` needs the library, and only when the regimes
change.

The suite asserts the findings that have to hold — an unexplained silence, an unexplained
direction conflict, a pattern that dropped out of the close-agreement set. This prints
everything else beside them: how many bars each side matched in each market, how many were
the same bar, and which bars the two disagreed about the direction of. That is what an
investigation reads before writing a `Divergence` note, and it is deliberately not asserted
on, because a number that has to stay put is a number nobody may learn anything new from.

    .venv/bin/python scripts/report_talib_pattern_comparison.py

Section numbers in this file are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CORE_LIB = REPOSITORY_ROOT / "services" / "core-lib"

for path in (CORE_LIB, CORE_LIB / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def main() -> None:
    """Render the report, or explain that there is nothing to render yet."""
    from pattern_reference import CAPTURE_INSTRUCTIONS, CAPTURED, render_report

    if not CAPTURED:
        raise SystemExit(CAPTURE_INSTRUCTIONS)
    print(render_report())


if __name__ == "__main__":
    main()
