"""Verify the TA-Lib-backed candlestick pattern registry cutover."""

from collections.abc import Mapping, Sequence
from math import isnan

import pytest
from core_lib.indicators import DEFAULT_REGISTRY
from core_lib.patterns import (
    DEFAULT_PATTERN_REGISTRY,
    TALIB_CDL_PATTERN_COUNT,
    TALIB_PATTERN_REGISTRY_VERSION,
)
from core_lib.patterns.registry import PatternValue
from core_lib.patterns.specs import TALIB_FUNCTIONS
from core_lib.patterns.talib_hikkake import TALIB_HIKKAKE_PATTERNS, TalibStatefulPatternPort
from core_lib.patterns.talib_multi_candle import TALIB_MULTI_CANDLE_PATTERNS
from core_lib.patterns.talib_raw import TalibPatternPort, sparse_talib_integer_signals
from core_lib.patterns.talib_single_candle import TALIB_SINGLE_CANDLE_PATTERNS
from core_lib.patterns.talib_three_candle import TALIB_THREE_CANDLE_PATTERNS
from core_lib.patterns.talib_two_candle import TALIB_TWO_CANDLE_PATTERNS

from pattern_reference import (
    CAPTURE_INSTRUCTIONS,
    CAPTURED,
    REGIME_NAMES,
    REGIMES_BY_NAME,
    SIGNALS,
    TOTAL_BAR_COUNT,
    candles_for,
)

_NEEDS_CAPTURE = pytest.mark.skipif(not CAPTURED, reason=CAPTURE_INSTRUCTIONS)

TalibDirectPort = TalibPatternPort | TalibStatefulPatternPort

_STATELESS_TALIB_PORTS: tuple[TalibPatternPort, ...] = (
    *TALIB_SINGLE_CANDLE_PATTERNS,
    *TALIB_TWO_CANDLE_PATTERNS,
    *TALIB_THREE_CANDLE_PATTERNS,
    *TALIB_MULTI_CANDLE_PATTERNS,
)

_ALL_TALIB_PORTS: tuple[TalibDirectPort, ...] = (
    *_STATELESS_TALIB_PORTS,
    *TALIB_HIKKAKE_PATTERNS,
)


def _assert_same_series(
    name: str,
    left: Sequence[PatternValue],
    right: Sequence[PatternValue],
) -> None:
    assert len(left) == len(right)
    for index, (left_value, right_value) in enumerate(zip(left, right, strict=True)):
        assert left_value.keys() == right_value.keys(), f"{name} index {index}"
        for key in left_value:
            left_number = left_value[key]
            right_number = right_value[key]
            if isnan(left_number):
                assert isnan(right_number), f"{name} index {index} key {key}"
            else:
                assert left_number == right_number, f"{name} index {index} key {key}"


def _first_mismatch(
    actual: Mapping[int, int],
    expected: Mapping[int, int],
    bar_count: int,
) -> tuple[int, int, int] | None:
    for index in range(bar_count):
        actual_value = actual.get(index, 0)
        expected_value = expected.get(index, 0)
        if actual_value != expected_value:
            return index, actual_value, expected_value
    return None


def test_public_default_pattern_registry_is_talib_cutover() -> None:
    specs = DEFAULT_PATTERN_REGISTRY.list()
    history = {spec.name: spec.min_history for spec in specs}
    port_history = {port.name: port.min_history for port in _ALL_TALIB_PORTS}

    assert len(_STATELESS_TALIB_PORTS) == 59
    assert len(_ALL_TALIB_PORTS) == TALIB_CDL_PATTERN_COUNT == 61
    assert len(specs) == TALIB_CDL_PATTERN_COUNT
    assert {spec.name for spec in specs} == set(TALIB_FUNCTIONS)
    assert all(spec.version == TALIB_PATTERN_REGISTRY_VERSION for spec in specs)
    assert TALIB_PATTERN_REGISTRY_VERSION == "2.0.0+talib.0.7.1"

    assert all(not spec.params for spec in specs)
    assert all(spec.explicit_min_history > 0 for spec in specs)
    assert all(not hasattr(spec, "bar_count") for spec in specs)
    assert all(not hasattr(spec, "requires_trend") for spec in specs)
    assert history == port_history
    assert max(history.values()) == 15
    assert history["pat_doji"] == 11


def test_public_pattern_names_stay_disjoint_from_indicators_and_indicator_tally_stays_put() -> None:
    indicator_names = {spec.name for spec in DEFAULT_REGISTRY.list()}
    pattern_names = DEFAULT_PATTERN_REGISTRY.names()

    assert len(DEFAULT_REGISTRY.list()) == 84
    assert len(pattern_names) == TALIB_CDL_PATTERN_COUNT
    assert indicator_names.isdisjoint(pattern_names)


def test_all_sixty_one_talib_ports_incremental_paths_match_vectorized() -> None:
    checked = 0
    compared_bars = 0

    for port in _ALL_TALIB_PORTS:
        for regime in REGIME_NAMES:
            candles = candles_for(regime)
            state = port.make_state()
            incremental = [state.update(candle) for candle in candles]

            assert state.min_history == port.min_history
            _assert_same_series(port.name, port.compute_vectorized(candles), incremental)
            checked += 1
            compared_bars += REGIMES_BY_NAME[regime].bar_count

    assert checked == TALIB_CDL_PATTERN_COUNT * len(REGIME_NAMES) == 427
    assert compared_bars == TALIB_CDL_PATTERN_COUNT * TOTAL_BAR_COUNT == 1_342_000


@_NEEDS_CAPTURE
def test_registered_talib_pattern_specs_match_capture() -> None:
    checked = 0
    compared_bars = 0

    for spec in DEFAULT_PATTERN_REGISTRY.list():
        talib_function = TALIB_FUNCTIONS[spec.name]
        for regime in REGIME_NAMES:
            candles = candles_for(regime)
            actual = sparse_talib_integer_signals(
                spec.name,
                spec.compute_vectorized(candles),
            )
            expected = dict(SIGNALS[regime][talib_function])
            mismatch = _first_mismatch(actual, expected, REGIMES_BY_NAME[regime].bar_count)
            if mismatch is not None:
                pytest.fail(
                    f"{spec.name}/{talib_function} diverged on {regime} at bar "
                    f"{mismatch[0]}: actual={mismatch[1]}, expected={mismatch[2]}"
                )
            assert actual == expected
            checked += 1
            compared_bars += REGIMES_BY_NAME[regime].bar_count

    assert checked == TALIB_CDL_PATTERN_COUNT * len(REGIME_NAMES) == 427
    assert compared_bars == TALIB_CDL_PATTERN_COUNT * TOTAL_BAR_COUNT == 1_342_000
