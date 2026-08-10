#!/usr/bin/env python3
"""Capture TA-Lib 0.7.1 BETA/CORREL outputs for four paired random streams.

Run this only in a throwaway environment against an explicitly supplied TA-Lib
0.7.1 shared library. The generated values are frozen into the test package, so
neither the test suite nor continuous integration loads TA-Lib.

    .venv/bin/python scripts/capture_talib_paired_statistics.py \
        --library /private/tmp/ta-lib-build/libta-lib.dylib
"""

from __future__ import annotations

import argparse
import sys
from ctypes import CDLL, POINTER, byref, c_char_p, c_double, c_int
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CORE_LIB = REPOSITORY_ROOT / "services" / "core-lib"
TARGET = CORE_LIB / "tests" / "indicator_reference" / "statistics_talib.py"

BEGIN = "# --- BEGIN GENERATED CAPTURE"
END = "# --- END GENERATED CAPTURE ---"

for path in (CORE_LIB, CORE_LIB / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _capture(
    library: CDLL,
    function_name: str,
    first: list[float],
    second: list[float],
    period: int,
) -> tuple[int, tuple[float, ...]]:
    count = len(first)
    if len(second) != count:
        raise ValueError("paired capture inputs must have equal length")
    array_type = c_double * count
    output = array_type()
    beginning = c_int()
    output_count = c_int()
    function = getattr(library, f"TA_{function_name}")
    function.argtypes = [
        c_int,
        c_int,
        POINTER(c_double),
        POINTER(c_double),
        c_int,
        POINTER(c_int),
        POINTER(c_int),
        POINTER(c_double),
    ]
    function.restype = c_int
    return_code = function(
        0,
        count - 1,
        array_type(*first),
        array_type(*second),
        period,
        byref(beginning),
        byref(output_count),
        output,
    )
    if return_code != 0:
        raise RuntimeError(f"TA_{function_name} returned {return_code}")
    return beginning.value, tuple(output[: output_count.value])


def _render_outputs(outputs: dict[str, dict[int, tuple[float, ...]]]) -> str:
    lines = ["{"]
    for name in sorted(outputs):
        lines.append(f"    {name!r}: {{")
        for seed in sorted(outputs[name]):
            values = ", ".join(repr(value) for value in outputs[name][seed])
            lines.append(f"        {seed}: ({values},),")
        lines.append("    },")
    lines.append("}")
    return "\n".join(lines)


def _generated_block(
    version: str,
    bar_count: int,
    lookbacks: dict[str, int],
    outputs: dict[str, dict[int, tuple[float, ...]]],
) -> str:
    return "\n".join(
        (
            "# fmt: off",
            f"TA_LIB_VERSION = {version!r}",
            f"BAR_COUNT = {bar_count}",
            f"LOOKBACKS = {lookbacks!r}",
            "OUTPUTS: dict[str, dict[int, tuple[float, ...]]] = "
            + _render_outputs(outputs),
            "# fmt: on",
        )
    )


def _replace_block(text: str, block: str) -> str:
    begin = text.index(BEGIN)
    begin_end = text.index("\n", begin) + 1
    end = text.index(END)
    return text[:begin_end] + block + "\n" + text[end:]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=Path, required=True)
    args = parser.parse_args()

    from indicator_reference import (
        RANDOM_BAR_COUNT,
        RANDOM_SEEDS,
        paired_random_candles,
    )

    library = CDLL(str(args.library))
    version_function = library.TA_GetVersionString
    version_function.restype = c_char_p
    version = version_function().decode()
    if not version.startswith("0.7.1 "):
        raise SystemExit(f"expected TA-Lib 0.7.1, got {version!r}")
    if library.TA_Initialize() != 0:
        raise RuntimeError("TA_Initialize failed")

    periods = {"BETA": 5, "CORREL": 30}
    outputs: dict[str, dict[int, tuple[float, ...]]] = {name: {} for name in periods}
    lookbacks: dict[str, int] = {}
    try:
        for seed in RANDOM_SEEDS:
            primary, reference = paired_random_candles(seed)
            first = [candle.close for candle in reference]
            second = [candle.close for candle in primary]
            for name, period in periods.items():
                lookback, values = _capture(library, name, first, second, period)
                previous = lookbacks.setdefault(name, lookback)
                if previous != lookback:
                    raise AssertionError(f"{name} lookback changed across captures")
                outputs[name][seed] = values
    finally:
        if library.TA_Shutdown() != 0:
            raise RuntimeError("TA_Shutdown failed")

    block = _generated_block(version, RANDOM_BAR_COUNT, lookbacks, outputs)
    TARGET.write_text(_replace_block(TARGET.read_text(), block))
    for name in sorted(outputs):
        print(
            f"{name}: {len(outputs[name])} seeds, "
            f"{len(next(iter(outputs[name].values())))} values per seed"
        )


if __name__ == "__main__":
    main()
