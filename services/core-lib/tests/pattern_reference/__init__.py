"""Expose the frozen TA-Lib capture and the regime series it belongs to.

`series.py` builds the seven market regimes and their 22,000 candles.
`talib_signals.py` holds the captured TA-Lib v0.7.1 raw `CDL` integers for those
exact bars. The legacy comparison, divergence table, and report helpers were
retired after the public pattern registry moved to the TA-Lib ports.
"""

from core_lib.patterns.specs import TALIB_FUNCTIONS

from . import talib_signals
from .series import (
    REGIME_NAMES,
    REGIMES,
    REGIMES_BY_NAME,
    TOTAL_BAR_COUNT,
    Regime,
    candles_for,
    fingerprints,
    series_fingerprint,
)
from .talib_signals import CAPTURED, SIGNALS

CAPTURE_INSTRUCTIONS = (
    "TA-Lib signals have not been captured. In a throwaway environment with TA-Lib "
    "installed, run scripts/capture_talib_pattern_signals.py, which rewrites "
    "services/core-lib/tests/pattern_reference/talib_signals.py in place. Neither this "
    "repository nor continuous integration depends on TA-Lib at any other time."
)
"""What skipped capture-backed tests say when the frozen TA-Lib values are absent."""

__all__ = [
    "CAPTURED",
    "CAPTURE_INSTRUCTIONS",
    "REGIMES",
    "REGIMES_BY_NAME",
    "REGIME_NAMES",
    "SIGNALS",
    "TALIB_FUNCTIONS",
    "TOTAL_BAR_COUNT",
    "Regime",
    "candles_for",
    "fingerprints",
    "series_fingerprint",
    "talib_signals",
]
