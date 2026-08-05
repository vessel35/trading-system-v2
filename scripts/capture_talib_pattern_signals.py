#!/usr/bin/env python3
"""Capture TA-Lib's `CDL` output once and freeze it into the pattern comparison package.

Run this in a throwaway environment that has TA-Lib installed. Nothing else in the
repository imports TA-Lib, and neither the test suite nor continuous integration may start
depending on it: the capture exists so the comparison keeps working long after that
environment is gone.

    python -m venv /tmp/talib-capture
    /tmp/talib-capture/bin/pip install numpy TA-Lib==0.7.1
    /tmp/talib-capture/bin/python scripts/capture_talib_pattern_signals.py

The script needs no other installation. It puts `services/core-lib` and its `tests`
directory on the path itself, so `core_lib` and the `pattern_reference` package import
without the repository being installed into that environment.

Every regime, every function
----------------------------

`pattern_reference.series.REGIMES` is a bundle of markets, not one market, and this script
walks all of them: each of the sixty-one functions is called once per regime, over that
regime's own bars. Capturing one regime and leaving the rest would make the comparison
report the untouched regimes as bars TA-Lib never matched, which is the one wrong answer
this whole package is built to avoid.

What it writes, and what it deliberately does not
-------------------------------------------------

It rewrites one block of
`services/core-lib/tests/pattern_reference/talib_signals.py`, the one between the two
sentinel comments, and leaves the rest of that file — every docstring in it — untouched.
The prose there explains what the numbers mean and is maintained by hand.

It passes **no arguments** to any `CDL` function. Seven of them take a `penetration`
argument with a TA-Lib v0.7.1 library default, and the script records those defaults
because the direct raw port adopts TA-Lib's default call. Passing an explicit value would
make the capture a comparison against a configuration we invented.

It does not touch our implementation, thresholds, standard, or `series.py`: if a regime
produces little, that is a fact about the market to be reported, not a series to be
adjusted until the numbers improve.

Section numbers in this file are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
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

from core_lib.patterns.talib_raw import validate_talib_version_pin  # noqa: E402


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
            "with `pip install numpy TA-Lib==0.7.1` and run this script from it. Do not "
            "add TA-Lib to the repository's dependencies."
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


def _pinned_underlying_version(talib: ModuleType) -> str:
    """Return the underlying version after enforcing the capture/source pin."""
    talib_version = str(getattr(talib, "__version__", ""))
    underlying_version = _underlying_version(talib)
    try:
        validate_talib_version_pin(talib_version, underlying_version)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if underlying_version is None:
        raise AssertionError("validated TA-Lib underlying version cannot be None")
    return underlying_version


def _render_int_map(values: dict[int, int]) -> str:
    """Render one function's non-zero bars as a sorted dict literal on one line."""
    body = ", ".join(f"{index}: {value}" for index, value in sorted(values.items()))
    return "{" + body + "}"


def _render_signals(signals: dict[str, dict[str, dict[int, int]]]) -> str:
    """Render every regime's functions, one function per line.

    One line per function is what the `# fmt: off` around the block buys. Letting the
    formatter expand these produces tens of thousands of lines of bare integers whose diff
    nobody can read.
    """
    lines = ["{"]
    for regime in sorted(signals):
        lines.append(f"    {regime!r}: {{")
        lines.extend(
            f"        {function!r}: {_render_int_map(signals[regime][function])},"
            for function in sorted(signals[regime])
        )
        lines.append("    },")
    lines.append("}")
    return "\n".join(lines)


def _render_str_map(values: dict[str, str]) -> str:
    """Render a name-to-text mapping, one entry per line."""
    lines = [f"    {key!r}: {values[key]!r}," for key in sorted(values)]
    return "{\n" + "\n".join(lines) + "\n}"


def _render_int_by_name(values: dict[str, int]) -> str:
    """Render a name-to-count mapping, one entry per line."""
    lines = [f"    {key!r}: {values[key]!r}," for key in sorted(values)]
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
    fingerprints: dict[str, str],
    bar_counts: dict[str, int],
    parameters: dict[str, dict[str, float]],
    signals: dict[str, dict[str, dict[int, int]]],
) -> str:
    """Build the replacement for the block between the sentinels."""
    captured_at = datetime.now(UTC).date().isoformat()
    return "\n".join(
        (
            "_CAPTURED: bool = True",
            f"_TALIB_VERSION: str | None = {talib_version!r}",
            f"_TALIB_UNDERLYING_VERSION: str | None = {underlying_version!r}",
            f"_CAPTURED_AT: str | None = {captured_at!r}",
            "_SERIES_FINGERPRINTS: dict[str, str] = " + _render_str_map(fingerprints),
            "_BAR_COUNTS: dict[str, int] = " + _render_int_by_name(bar_counts),
            "_FUNCTION_PARAMETERS: dict[str, dict[str, float]] = "
            + _render_parameters(parameters),
            "# fmt: off",
            "_SIGNALS: dict[str, dict[str, dict[int, int]]] = "
            + _render_signals(signals),
            "# fmt: on",
        )
    )


def _replace_block(text: str, block: str) -> str:
    """Put the new block between the sentinels, leaving everything else as it is."""
    begin = text.index(BEGIN)
    begin_end = text.index("\n", begin) + 1
    end = text.index(END)
    return text[:begin_end] + block + "\n" + text[end:]


def main() -> None:
    """Read every regime, call every `CDL` function on each, and write the capture."""
    talib = _require_talib()
    underlying_version = _pinned_underlying_version(talib)
    import numpy
    from talib import abstract

    from core_lib.patterns.specs import TALIB_FUNCTIONS
    from pattern_reference.series import REGIMES, candles_for, series_fingerprint

    function_names = sorted(set(TALIB_FUNCTIONS.values()))
    signals: dict[str, dict[str, dict[int, int]]] = {}
    fingerprints: dict[str, str] = {}
    bar_counts: dict[str, int] = {}
    parameters: dict[str, dict[str, float]] = {}

    for regime in REGIMES:
        candles = candles_for(regime.name)
        arrays = {
            name: numpy.array(
                [getattr(candle, name) for candle in candles], dtype=float
            )
            for name in ("open", "high", "low", "close")
        }
        fingerprints[regime.name] = series_fingerprint(candles)
        bar_counts[regime.name] = len(candles)
        per_function: dict[str, dict[int, int]] = {}
        for function_name in function_names:
            function = getattr(talib, function_name)
            produced = function(
                arrays["open"], arrays["high"], arrays["low"], arrays["close"]
            )
            # Every called function gets an entry, empty included: a function absent from
            # the capture and a function that matched nothing are different facts, and the
            # sparse encoding is the only thing that makes them look alike.
            per_function[function_name] = {
                index: int(value)
                for index, value in enumerate(produced)
                if int(value) != 0
            }
        signals[regime.name] = per_function
        matched = sum(len(bars) for bars in per_function.values())
        silent = sum(1 for bars in per_function.values() if not bars)
        print(
            f"  {regime.name}: {len(candles)} bars, {matched} non-zero, {silent} functions silent"
        )

    for function_name in function_names:
        declared = abstract.Function(function_name).parameters
        if declared:
            parameters[function_name] = {
                key: float(value) for key, value in declared.items()
            }

    block = _generated_block(
        talib_version=str(talib.__version__),
        underlying_version=underlying_version,
        fingerprints=fingerprints,
        bar_counts=bar_counts,
        parameters=parameters,
        signals=signals,
    )
    TARGET.write_text(
        _replace_block(TARGET.read_text(encoding="utf-8"), block), encoding="utf-8"
    )

    everywhere_silent = sorted(
        function
        for function in function_names
        if not any(signals[regime][function] for regime in signals)
    )
    print(f"wrote {TARGET.relative_to(REPOSITORY_ROOT)}")
    print(
        f"  TA-Lib {talib.__version__}, {len(signals)} regimes, "
        f"{sum(bar_counts.values())} bars, {len(function_names)} functions"
    )
    print(
        f"  {len(everywhere_silent)} functions matched nothing anywhere: {everywhere_silent}"
    )
    print("  run `ruff format` on the rewritten file, then run the suite")


if __name__ == "__main__":
    main()
