"""Verify the TA-Lib raw integer candlestick contract."""

import pytest
from core_lib.patterns.talib_raw import (
    TALIB_CDL_PATTERN_COUNT,
    TALIB_DBL_MAX,
    TALIB_PENETRATION_DEFAULTS,
    TALIB_RAW_ALLOWED_VALUES,
    TALIB_SOURCE_VERSION,
    TalibRawPatternSpec,
    resolve_talib_penetration,
    talib_penetration_lookback,
    validate_talib_raw_integer_series,
    validate_talib_version_pin,
)

from pattern_reference import CAPTURE_INSTRUCTIONS, CAPTURED, REGIME_NAMES, SIGNALS, talib_signals

_NEEDS_CAPTURE = pytest.mark.skipif(not CAPTURED, reason=CAPTURE_INSTRUCTIONS)


def test_raw_pattern_spec_uses_lookback_plus_one_min_history() -> None:
    spec = TalibRawPatternSpec("pat_example", "CDLEXAMPLE", 3)

    assert spec.first_output_index == 3
    assert spec.min_history == 4
    assert [spec.is_warmup_index(index) for index in range(5)] == [
        True,
        True,
        True,
        False,
        False,
    ]


def test_raw_integer_series_uses_zero_for_warmup_prefix() -> None:
    spec = TalibRawPatternSpec("pat_example", "CDLEXAMPLE", 2)

    validate_talib_raw_integer_series(spec, [0, 0, 100, -80, 200], candle_count=5)


def test_raw_integer_series_rejects_nonzero_warmup_prefix() -> None:
    spec = TalibRawPatternSpec("pat_example", "CDLEXAMPLE", 2)

    with pytest.raises(ValueError, match="warm-up index 1"):
        validate_talib_raw_integer_series(spec, [0, 100, 0], candle_count=3)


def test_raw_integer_series_rejects_unexpected_shape() -> None:
    spec = TalibRawPatternSpec("pat_example", "CDLEXAMPLE", 0)

    with pytest.raises(ValueError, match="produced 1 values for 2 candles"):
        validate_talib_raw_integer_series(spec, [0], candle_count=2)
    with pytest.raises(TypeError, match="must be int"):
        validate_talib_raw_integer_series(spec, [False], candle_count=1)
    with pytest.raises(ValueError, match="raw integer"):
        validate_talib_raw_integer_series(spec, [300], candle_count=1)


def test_penetration_defaults_and_lookback_error_path_match_talib_0_7_1() -> None:
    assert TALIB_PENETRATION_DEFAULTS == {
        "CDLABANDONEDBABY": 0.3,
        "CDLDARKCLOUDCOVER": 0.5,
        "CDLEVENINGDOJISTAR": 0.3,
        "CDLEVENINGSTAR": 0.3,
        "CDLMATHOLD": 0.5,
        "CDLMORNINGDOJISTAR": 0.3,
        "CDLMORNINGSTAR": 0.3,
    }
    assert resolve_talib_penetration("CDLDARKCLOUDCOVER") == 0.5
    assert talib_penetration_lookback("CDLDARKCLOUDCOVER", 11) == 11
    assert talib_penetration_lookback("CDLDARKCLOUDCOVER", 11, 0.0) == 11
    assert talib_penetration_lookback("CDLDARKCLOUDCOVER", 11, TALIB_DBL_MAX) == 11
    assert talib_penetration_lookback("CDLDARKCLOUDCOVER", 11, -0.1) == -1
    assert talib_penetration_lookback("CDLDARKCLOUDCOVER", 11, float("inf")) == -1

    with pytest.raises(ValueError, match="outside TA-Lib bounds"):
        resolve_talib_penetration("CDLDARKCLOUDCOVER", -0.1)


@_NEEDS_CAPTURE
def test_captured_talib_version_matches_raw_port_source_pin() -> None:
    validate_talib_version_pin(
        talib_signals.TALIB_VERSION,
        talib_signals.TALIB_UNDERLYING_VERSION,
    )
    assert talib_signals.TALIB_VERSION == TALIB_SOURCE_VERSION


@_NEEDS_CAPTURE
def test_capture_contains_sixty_one_raw_integer_functions_on_each_regime() -> None:
    for regime in REGIME_NAMES:
        assert len(SIGNALS[regime]) == TALIB_CDL_PATTERN_COUNT
        for values in SIGNALS[regime].values():
            assert set(values.values()) <= TALIB_RAW_ALLOWED_VALUES


@_NEEDS_CAPTURE
def test_capture_records_dark_cloud_cover_default_penetration() -> None:
    assert talib_signals.FUNCTION_PARAMETERS["CDLDARKCLOUDCOVER"] == {"penetration": 0.5}
