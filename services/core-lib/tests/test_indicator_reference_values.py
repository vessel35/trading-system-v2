"""Check indicator values against an outside implementation, not against ourselves.

The values themselves live in the `indicator_reference` package, one module per
indicator category, and that package's docstring explains where they came from and
why an outside library is a comparison rather than a source. This module only states
what has to hold of them.
"""

import math

import pytest
from core_lib.indicators.registry import DEFAULT_REGISTRY, IndicatorSeries

from indicator_reference import (
    CONVERGENCE_NOISE_FLOOR,
    CONVERGING,
    COVERED_CATEGORIES,
    REFERENCE,
    SAMPLE_INDICES,
    UNCOMPARED,
    paired_reference_candles,
    reference_candles,
)


def _computed_series() -> dict[str, list[float]]:
    """Return every registered series, flattening dict outputs to `name.key`."""

    candles = reference_candles()
    reference = paired_reference_candles()
    flattened: dict[str, list[float]] = {}
    for spec in DEFAULT_REGISTRY.list():
        series: IndicatorSeries
        if spec.needs_reference_series:
            state = spec.make_paired_state()
            series = [
                state.update(candle, reference_candle)
                for candle, reference_candle in zip(candles, reference, strict=True)
            ]
        else:
            series = spec.compute_vectorized(candles)
        if series and isinstance(series[0], dict):
            for key in series[0]:
                flattened[f"{spec.identifier}.{key}"] = [
                    float(value[key])  # type: ignore[index]
                    for value in series
                ]
        else:
            flattened[spec.identifier] = [float(value) for value in series]  # type: ignore[arg-type]
    return flattened


@pytest.mark.parametrize("name", sorted(REFERENCE))
def test_values_match_an_outside_implementation(name: str) -> None:
    """Our value equals TA-Lib's at every sampled point."""

    produced = _computed_series()[name]
    for index, expected in REFERENCE[name].items():
        if name == "HT_TRENDMODE":
            assert produced[index] == expected, f"{name} at index {index}"
        else:
            assert produced[index] == pytest.approx(expected, rel=1e-9, abs=1e-9), (
                f"{name} at index {index}"
            )


@pytest.mark.parametrize("name", sorted(CONVERGING))
def test_seed_window_differences_converge_to_the_outside_implementation(name: str) -> None:
    """A different seed window may differ early, but the gap must close.

    A persistent gap would mean the formulas themselves disagree, which is what
    this shape of assertion separates from a seed that is merely forgotten at a
    geometric rate.
    """

    values, tolerance = CONVERGING[name]
    produced = _computed_series()[name]
    previous_gap = math.inf
    for index in SAMPLE_INDICES:
        gap = abs(produced[index] - values[index])
        assert gap <= tolerance[index], f"{name} at index {index} gap {gap}"
        if previous_gap > CONVERGENCE_NOISE_FLOOR:
            assert gap <= previous_gap, f"{name} gap grew at index {index}"
        previous_gap = gap


def test_every_registered_output_is_covered_by_the_outside_comparison() -> None:
    """No registered output may sit outside the comparison unnoticed.

    A new indicator that nobody compared would otherwise pass the suite on parity
    alone, which is the exact gap this file exists to close. Splitting the values
    across category modules does not weaken it: dropping a module from the merge
    removes its entries from `compared` and leaves its outputs in `produced`, so a
    forgotten category fails here rather than passing on a shorter table.
    """

    compared = set(REFERENCE) | set(CONVERGING) | set(UNCOMPARED)
    produced = set(_computed_series())
    assert produced - compared == set()
    assert set(UNCOMPARED) <= produced, "an uncompared entry no longer exists"


def test_every_registered_category_owns_a_reference_module() -> None:
    """A registered category with no data module of its own must not stay silent.

    The check above catches a dropped module through the outputs it stops covering.
    This one names the category directly, so a new category arriving without its
    comparison table fails with the category name rather than with a list of
    uncovered output keys.
    """

    registered = {spec.category for spec in DEFAULT_REGISTRY.list()}
    assert registered <= COVERED_CATEGORIES, (
        f"no reference module for {registered - COVERED_CATEGORIES}"
    )
