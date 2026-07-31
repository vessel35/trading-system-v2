"""Prove no volatility value at bar t is built from a candle after t.

The incremental path cannot look ahead by construction, because it is handed one
candle at a time. The batch path can: it receives the whole series and any accidental
use of a later element would still produce a plausible-looking number, and the parity
tests would not notice, because they compare the two paths on the same complete series
rather than on a growing one.

So this cuts the series short at several lengths and requires the last value of each
truncated run to equal the value the full run produced at that same index. A calculation
that reached forward would change when the future was removed. §0.11 states the rule
this stands on: a recursive indicator may use only confirmed earlier values.

SuperTrend is the reason this file exists in the volatility category. Its bands are
recursive and its trend state persists between bars, so it is the one indicator here
where a shift in the wrong direction would be easy to write and hard to see.
"""

from math import isnan

import pytest
from core_lib.indicators.registry import DEFAULT_REGISTRY, IndicatorSpec, IndicatorValue

from indicator_reference.series import reference_candles

VOLATILITY_SPECS = [spec for spec in DEFAULT_REGISTRY.list() if spec.category == "volatility"]


def same_value(expected: IndicatorValue, actual: IndicatorValue) -> bool:
    """Compare two indicator values exactly, treating NaN as equal to NaN."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        return all(same_value(expected[key], actual[key]) for key in expected)
    assert isinstance(actual, float)
    return (isnan(expected) and isnan(actual)) or expected == actual


@pytest.mark.parametrize("spec", VOLATILITY_SPECS, ids=lambda spec: spec.identifier)
def test_truncating_the_future_does_not_change_the_present(spec: IndicatorSpec) -> None:
    """The value at bar t is the same whether or not later candles exist."""

    candles = reference_candles()
    full = spec.compute_vectorized(candles)
    for length in (spec.min_history, spec.min_history + 1, 60, 150, 250, len(candles)):
        if length > len(candles):
            continue
        truncated = spec.compute_vectorized(candles[:length])
        assert len(truncated) == length
        assert same_value(full[length - 1], truncated[-1]), (
            f"{spec.identifier} changed at index {length - 1} when the future was removed"
        )
