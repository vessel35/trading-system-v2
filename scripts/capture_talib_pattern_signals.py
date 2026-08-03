#!/usr/bin/env python3
"""Capture TA-Lib's `CDL` output once and freeze it into the pattern comparison package.

Run this in a throwaway environment that has TA-Lib installed. Nothing else in the
repository imports TA-Lib, and neither the test suite nor continuous integration may start
depending on it: the capture exists so the comparison keeps working long after that
environment is gone.

    python -m venv /tmp/talib-capture
    /tmp/talib-capture/bin/pip install numpy TA-Lib
    /tmp/talib-capture/bin/python scripts/capture_talib_pattern_signals.py

The script needs no other installation. It puts `services/core-lib` and its `tests`
directory on the path itself, so `core_lib` and the `pattern_reference` package import
without the repository being installed into that environment.

What it writes, and what it deliberately does not
-------------------------------------------------

It rewrites one block of
`services/core-lib/tests/pattern_reference/talib_signals.py`, the one between the two
sentinel comments, and leaves the rest of that file — every docstring in it — untouched.
The prose there explains what the numbers mean and is maintained by hand.

It passes **no arguments** to any `CDL` function. Seven of them take a `penetration`
argument with a library default, and the script records those defaults as provenance
rather than choosing values. §7 of the pattern standard fixes each depth from its source,
so there is nothing of ours for a default to be tuned against, and passing one would make
the comparison a comparison against a configuration we invented.

It does not touch our implementation, our thresholds, or the standard. §10.3 is explicit
that a disagreement is resolved by re-reading the standard, never by moving toward the
library.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CORE_LIB = REPOSITORY_ROOT / "services" / "core-lib"
TARGET = CORE_LIB / "tests" / "pattern_reference" / "talib_signals.py"

BEGIN = "# --- BEGIN GENERATED CAPTURE"
END = "# --- END GENERATED CAPTURE ---"

for path in (CORE_LIB, CORE_LIB / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _require_talib() -> ModuleType:
    """Import TA-Lib, or explain what is missing and stop.

    A bare ImportError here reads as a broken repository. It is not: the repository is
    supposed to lack TA-Lib, and this script is the one place that is supposed to have it.
    """
    try:
        import talib
    except ImportError as error:  # pragma: no cover - the repository never has TA-Lib
        raise SystemExit(
            "TA-Lib is not installed in this interpreter, which is expected everywhere "
            "except the throwaway environment this script is meant to run in. Create one "
            "with `pip install numpy TA-Lib` and run this script from it. Do not add TA-Lib "
            "to the repository's dependencies."
        ) from error
    return talib


def _underlying_version(talib: ModuleType) -> str | None:
    """Return the C library's version if the wrapper exposes one.

    Older wrappers report it as bytes and some do not report it at all, so a missing
    version is recorded as absent rather than guessed at from the wrapper's own version.
    """
    reported = getattr(talib, "__ta_version__", None)
    if isinstance(reported, bytes):
        return reported.decode(errors="replace").strip() or None
    if isinstance(reported, str):
        return reported.strip() or None
    return None


def _render_int_map(values: dict[int, int]) -> str:
    """Render one function's non-zero bars as a sorted dict literal."""
    body = ", ".join(f"{index}: {value}" for index, value in sorted(values.items()))
    return "{" + body + "}"


def _render_signals(signals: dict[str, dict[int, int]]) -> str:
    """Render every function's non-zero bars, one function per line."""
    lines = [
        f"    {function!r}: {_render_int_map(signals[function])},"
        for function in sorted(signals)
    ]
    return "{\n" + "\n".join(lines) + "\n}"


def _render_parameters(parameters: dict[str, dict[str, float]]) -> str:
    """Render the per-function arguments the library reported."""
    if not parameters:
        return "{}"
    lines = [
        f"    {function!r}: {dict(parameters[function])!r},"
        for function in sorted(parameters)
    ]
    return "{\n" + "\n".join(lines) + "\n}"


def _generated_block(
    *,
    talib_version: str,
    underlying_version: str | None,
    fingerprint: str,
    bar_count: int,
    parameters: dict[str, dict[str, float]],
    signals: dict[str, dict[int, int]],
) -> str:
    """Build the replacement for the block between the sentinels."""
    captured_at = datetime.now(UTC).date().isoformat()
    return "\n".join(
        (
            "_CAPTURED: bool = True",
            f"_TALIB_VERSION: str | None = {talib_version!r}",
            f"_TALIB_UNDERLYING_VERSION: str | None = {underlying_version!r}",
            f"_CAPTURED_AT: str | None = {captured_at!r}",
            f"_SERIES_FINGERPRINT: str | None = {fingerprint!r}",
            f"_BAR_COUNT: int | None = {bar_count}",
            "_FUNCTION_PARAMETERS: dict[str, dict[str, float]] = "
            + _render_parameters(parameters),
            "_SIGNALS: dict[str, dict[int, int]] = " + _render_signals(signals),
        )
    )


def _replace_block(text: str, block: str) -> str:
    """Put the new block between the sentinels, leaving everything else as it is."""
    begin = text.index(BEGIN)
    begin_end = text.index("\n", begin) + 1
    end = text.index(END)
    return text[:begin_end] + block + "\n" + text[end:]


def main() -> None:
    """Read the comparison series, call every `CDL` function, and write the capture."""
    talib = _require_talib()
    import numpy
    from talib import abstract

    from pattern_reference.divergence import TALIB_FUNCTIONS
    from pattern_reference.series import reference_candles, series_fingerprint

    candles = reference_candles()
    arrays = {
        name: numpy.array([getattr(candle, name) for candle in candles], dtype=float)
        for name in ("open", "high", "low", "close")
    }

    signals: dict[str, dict[int, int]] = {}
    parameters: dict[str, dict[str, float]] = {}
    for function_name in sorted(set(TALIB_FUNCTIONS.values())):
        function = getattr(talib, function_name)
        produced = function(
            arrays["open"], arrays["high"], arrays["low"], arrays["close"]
        )
        # Every called function gets an entry, empty included: a function absent from the
        # capture and a function that matched nothing are different facts, and the sparse
        # encoding is the only thing that makes them look alike.
        signals[function_name] = {
            index: int(value) for index, value in enumerate(produced) if int(value) != 0
        }
        declared = abstract.Function(function_name).parameters
        if declared:
            parameters[function_name] = {
                key: float(value) for key, value in declared.items()
            }

    block = _generated_block(
        talib_version=str(talib.__version__),
        underlying_version=_underlying_version(talib),
        fingerprint=series_fingerprint(candles),
        bar_count=len(candles),
        parameters=parameters,
        signals=signals,
    )
    TARGET.write_text(
        _replace_block(TARGET.read_text(encoding="utf-8"), block), encoding="utf-8"
    )

    matched = sum(len(bars) for bars in signals.values())
    silent = sorted(name for name, bars in signals.items() if not bars)
    print(f"wrote {TARGET.relative_to(REPOSITORY_ROOT)}")
    print(
        f"  TA-Lib {talib.__version__}, {len(candles)} bars, {len(signals)} functions"
    )
    print(
        f"  {matched} non-zero bars in total; {len(silent)} functions matched nothing: {silent}"
    )
    print("  run `ruff format` on the rewritten file, then run the suite")


if __name__ == "__main__":
    main()
