"""Hold the captured output of TA-Lib's sixty-one `CDL` functions, or say none was captured.

Nothing in this repository imports TA-Lib. The block between the two sentinels below is
produced once, in a throwaway environment, by `scripts/capture_talib_pattern_signals.py`,
which rewrites exactly that block and leaves every word of this file alone. Running the
suite, in continuous integration or anywhere else, needs neither the library nor that
environment.

Whether a capture has happened is stated, not inferred. `_CAPTURED` is a flag the generator
writes, because "captured and TA-Lib matched nothing anywhere" and "nobody has asked
TA-Lib yet" are different facts that produce the same empty tables. The first is a finding
worth investigating; the second is a gap. Tests that need values skip on the flag and never
on a table being empty.

The signals are stored sparsely. A `CDL` function returns an integer per bar and zero on
nearly all of them, so only the non-zero bars are kept and an absent index means zero.
`BAR_COUNT` is recorded beside them, so a capture cut short cannot pass for a series with a
long tail of zeros.

`SERIES_FINGERPRINT` is what makes the values falsifiable. It is `series.series_fingerprint()`
as it stood when the capture ran, so a later edit to `series.py` — another length, another
seed, one changed constant — leaves these signals describing bars that no longer exist, and
the suite rejects them rather than comparing our output against another series' answers.

`FUNCTION_PARAMETERS` records what each `CDL` function was called with, which for seven of
them includes a `penetration` argument carrying a library default. **It is written down,
not adopted.** Our depths come from §7 and the sources behind it; knowing what TA-Lib used
explains a disagreement and never settles one.
"""

from collections.abc import Mapping
from types import MappingProxyType

# --- BEGIN GENERATED CAPTURE (scripts/capture_talib_pattern_signals.py rewrites this block) ---
_CAPTURED: bool = False
_TALIB_VERSION: str | None = None
_TALIB_UNDERLYING_VERSION: str | None = None
_CAPTURED_AT: str | None = None
_SERIES_FINGERPRINT: str | None = None
_BAR_COUNT: int | None = None
_FUNCTION_PARAMETERS: dict[str, dict[str, float]] = {}
_SIGNALS: dict[str, dict[int, int]] = {}
# --- END GENERATED CAPTURE ---

CAPTURED = _CAPTURED
"""Whether the tables below hold a real capture.

The generator sets the flag it derives from. Do not raise it by hand: a true flag with no
values turns every value test from skipped into silently vacuous, which is the single
outcome this module exists to prevent.
"""

TALIB_VERSION = _TALIB_VERSION
"""The `talib.__version__` of the environment the capture ran in."""

TALIB_UNDERLYING_VERSION = _TALIB_UNDERLYING_VERSION
"""The version of the C library under the Python wrapper, where the wrapper exposes it."""

CAPTURED_AT = _CAPTURED_AT
"""The UTC day the capture ran, as an ISO date. No test reads it; it is provenance."""

SERIES_FINGERPRINT = _SERIES_FINGERPRINT
"""`series.series_fingerprint()` at capture time, or `None` before the first capture."""

BAR_COUNT = _BAR_COUNT
"""Bars the capture covered, which has to equal the length of the comparison series."""

FUNCTION_PARAMETERS: Mapping[str, Mapping[str, float]] = MappingProxyType(
    {function: MappingProxyType(dict(values)) for function, values in _FUNCTION_PARAMETERS.items()}
)
"""Per-function arguments as the library reported them, keyed by `CDL` function name.

Only functions that take an argument appear. What is recorded is the library's own
default, read from `talib.abstract`, because the capture passes nothing of its own:
overriding a default would make this a comparison against a tuning we invented rather than
against the library as it ships.
"""

SIGNALS: Mapping[str, Mapping[int, int]] = MappingProxyType(
    {function: MappingProxyType(dict(bars)) for function, bars in _SIGNALS.items()}
)
"""Non-zero bars per `CDL` function: `{function: {bar index: value}}`.

TA-Lib reports a match as a non-zero integer whose sign carries the direction and whose
magnitude is 100, or 200 for the two Hikkake functions on a confirmed instance. **That
magnitude is not our `_strength`.** §5.6 gives half strength to an engulfment with exactly
one coinciding end, which has nothing to do with confirmation, so pairing the two numbers
would compare unrelated quantities and call the result agreement.
"""
