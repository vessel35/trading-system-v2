"""Assert the TA-Lib gap and multi-candle pattern ports match captured TA-Lib bars."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from math import isnan

import pytest
from core_lib.patterns.outputs import output_keys
from core_lib.patterns.talib_candles import CandleSettingType, candle_average_series, real_body
from core_lib.patterns.talib_multi_candle import (
    TALIB_MULTI_CANDLE_BY_FUNCTION,
    TALIB_MULTI_CANDLE_BY_NAME,
    TALIB_MULTI_CANDLE_PATTERNS,
    _mat_hold_with_penetration,
)
from core_lib.patterns.talib_raw import (
    AverageSeries,
    TalibPatternPort,
    resolve_talib_penetration,
    sparse_talib_integer_signals,
)
from core_lib.types import Candle

from pattern_reference import (
    CAPTURE_INSTRUCTIONS,
    CAPTURED,
    REGIME_NAMES,
    REGIMES_BY_NAME,
    SIGNALS,
    candles_for,
)

_NEEDS_CAPTURE = pytest.mark.skipif(not CAPTURED, reason=CAPTURE_INSTRUCTIONS)


def _make_candle(index: int, open_price: float, high: float, low: float, close: float) -> Candle:
    open_time = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=index)
    return Candle(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe="1h",
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1000.0,
        quote_volume=None,
        trade_count=None,
    )


def _warmup_candles(count: int = 10, body: float = 1.0) -> list[Candle]:
    candles: list[Candle] = []
    for index in range(count):
        open_price = 80.0 + index * 0.2
        close = open_price + body if index % 2 == 0 else open_price - body
        candles.append(
            _make_candle(
                index,
                open_price=open_price,
                high=max(open_price, close) + 0.5,
                low=min(open_price, close) - 0.5,
                close=close,
            )
        )
    return candles


def _with_replacement(candles: list[Candle], index: int, candle: Candle) -> list[Candle]:
    updated = list(candles)
    updated[index] = candle
    return updated


def _first_mismatch(
    actual: dict[int, int],
    expected: dict[int, int],
    bar_count: int,
) -> tuple[int, int, int] | None:
    for index in range(bar_count):
        actual_value = actual.get(index, 0)
        expected_value = expected.get(index, 0)
        if actual_value != expected_value:
            return index, actual_value, expected_value
    return None


def _captured_total(talib_function: str) -> int:
    return sum(len(SIGNALS[regime][talib_function]) for regime in REGIME_NAMES)


def _captured_values(talib_function: str) -> dict[int, int]:
    values: dict[int, int] = {}
    for regime in REGIME_NAMES:
        for value in SIGNALS[regime][talib_function].values():
            values[value] = values.get(value, 0) + 1
    return values


def _three_line_strike_negative_candles() -> list[Candle]:
    candles = _warmup_candles()
    candles.append(_make_candle(10, 100.0, 100.5, 94.5, 95.0))
    candles.append(_make_candle(11, 97.0, 97.5, 93.5, 94.0))
    candles.append(_make_candle(12, 95.0, 95.5, 92.5, 93.0))
    candles.append(_make_candle(13, 92.0, 101.5, 91.5, 101.0))
    return candles


def _concealing_baby_swallow_candles() -> list[Candle]:
    candles = _warmup_candles()
    candles.append(_make_candle(10, 100.0, 100.05, 94.95, 95.0))
    candles.append(_make_candle(11, 94.0, 94.05, 89.95, 90.0))
    candles.append(_make_candle(12, 89.0, 90.5, 87.8, 88.0))
    candles.append(_make_candle(13, 89.5, 91.0, 87.0, 88.5))
    return candles


def _mat_hold_candles() -> list[Candle]:
    candles = _warmup_candles(body=5.0)
    candles.append(_make_candle(10, 100.0, 106.5, 99.5, 106.0))
    candles.append(_make_candle(11, 107.0, 107.2, 106.4, 106.6))
    candles.append(_make_candle(12, 104.0, 104.7, 103.8, 104.5))
    candles.append(_make_candle(13, 104.2, 104.4, 103.7, 103.9))
    candles.append(_make_candle(14, 104.1, 107.5, 103.9, 107.3))
    return candles


def _rise_fall_three_methods_candles() -> list[Candle]:
    candles = _warmup_candles()
    candles.append(_make_candle(10, 100.0, 106.0, 99.0, 105.0))
    candles.append(_make_candle(11, 104.0, 104.2, 103.3, 103.5))
    candles.append(_make_candle(12, 103.2, 103.4, 102.5, 102.7))
    candles.append(_make_candle(13, 102.5, 102.7, 101.8, 102.0))
    candles.append(_make_candle(14, 102.2, 108.5, 101.9, 108.0))
    return candles


def _breakaway_bearish_candles() -> list[Candle]:
    candles = _warmup_candles()
    candles.append(_make_candle(10, 100.0, 110.5, 99.5, 110.0))
    candles.append(_make_candle(11, 112.0, 113.5, 111.5, 113.0))
    candles.append(_make_candle(12, 114.0, 115.5, 113.5, 115.0))
    candles.append(_make_candle(13, 116.0, 117.5, 115.5, 117.0))
    candles.append(_make_candle(14, 116.5, 117.0, 110.8, 111.0))
    return candles


def _mat_hold_value(candles: list[Candle], penetration: float) -> int:
    pattern = TALIB_MULTI_CANDLE_BY_NAME["pat_mat_hold"]
    averages: AverageSeries = {
        key: candle_average_series(key[0], candles, target_offset=key[1])
        for key in pattern.average_keys
    }
    return _mat_hold_with_penetration(candles, len(candles) - 1, averages, penetration)


@_NEEDS_CAPTURE
@pytest.mark.parametrize(
    "pattern", TALIB_MULTI_CANDLE_PATTERNS, ids=lambda item: item.talib_function
)
@pytest.mark.parametrize("regime", REGIME_NAMES)
def test_talib_multi_candle_port_matches_capture(
    pattern: TalibPatternPort,
    regime: str,
) -> None:
    """Every captured TA-Lib value matches on the same bar with the same sign and size."""
    actual = sparse_talib_integer_signals(
        pattern.name,
        pattern.compute_vectorized(candles_for(regime)),
    )
    expected = dict(SIGNALS[regime][pattern.talib_function])

    mismatch = _first_mismatch(actual, expected, REGIMES_BY_NAME[regime].bar_count)
    assert mismatch is None, (
        f"{pattern.talib_function} diverged on {regime} at bar {mismatch[0]}: "
        f"actual={mismatch[1]}, expected={mismatch[2]}"
    )
    assert actual == expected


def test_talib_multi_candle_outputs_keep_four_key_warmup_contract() -> None:
    candles = candles_for("quiet_small_bodies")
    for pattern in TALIB_MULTI_CANDLE_PATTERNS:
        keys = set(output_keys(pattern.name))
        values = pattern.compute_vectorized(candles)
        assert len(values) == len(candles)
        for index, value in enumerate(values):
            assert set(value) == keys
            if index < pattern.lookback:
                assert all(isnan(number) for number in value.values())
            else:
                assert all(not isnan(number) for number in value.values())


def test_talib_multi_candle_lookbacks_match_source_table() -> None:
    assert {
        talib_function: pattern.lookback
        for talib_function, pattern in TALIB_MULTI_CANDLE_BY_FUNCTION.items()
    } == {
        "CDL3LINESTRIKE": 8,
        "CDLBREAKAWAY": 14,
        "CDLCONCEALBABYSWALL": 13,
        "CDLGAPSIDESIDEWHITE": 7,
        "CDLLADDERBOTTOM": 14,
        "CDLMATHOLD": 14,
        "CDLRISEFALL3METHODS": 14,
        "CDLSTICKSANDWICH": 7,
        "CDLTASUKIGAP": 7,
        "CDLXSIDEGAP3METHODS": 2,
    }


def test_multi_candle_penetration_defaults_stay_pattern_specific() -> None:
    assert resolve_talib_penetration("CDLMATHOLD") == 0.5


@_NEEDS_CAPTURE
def test_multi_candle_capture_sparse_branches_are_explicit() -> None:
    assert _captured_total("CDLCONCEALBABYSWALL") == 0
    assert _captured_total("CDLMATHOLD") == 0

    assert _captured_values("CDL3LINESTRIKE") == {100: 4}
    assert _captured_values("CDLBREAKAWAY") == {-100: 1, 100: 3}
    assert _captured_values("CDLRISEFALL3METHODS") == {-100: 1, 100: 1}
    assert _captured_values("CDLGAPSIDESIDEWHITE") == {-100: 22, 100: 108}
    assert _captured_values("CDLLADDERBOTTOM") == {100: 27}
    assert _captured_values("CDLSTICKSANDWICH") == {100: 29}
    assert _captured_values("CDLTASUKIGAP") == {-100: 73, 100: 84}
    assert _captured_values("CDLXSIDEGAP3METHODS") == {-100: 77, 100: 79}


@pytest.mark.parametrize(
    ("pattern_name", "candles", "expected"),
    (
        ("pat_concealing_baby_swallow", _concealing_baby_swallow_candles(), 100),
        ("pat_mat_hold", _mat_hold_candles(), 100),
        ("pat_three_line_strike", _three_line_strike_negative_candles(), -100),
        ("pat_rise_fall_three_methods", _rise_fall_three_methods_candles(), 100),
        ("pat_breakaway", _breakaway_bearish_candles(), -100),
    ),
)
def test_handmade_multi_candle_inputs_cover_sparse_branches(
    pattern_name: str,
    candles: list[Candle],
    expected: int,
) -> None:
    pattern = TALIB_MULTI_CANDLE_BY_NAME[pattern_name]

    assert len(candles) >= pattern.min_history
    assert pattern.compute_integers(candles)[-1] == expected


def test_three_line_strike_handmade_negative_branch_uses_third_candle_sign() -> None:
    pattern = TALIB_MULTI_CANDLE_BY_NAME["pat_three_line_strike"]
    candles = _three_line_strike_negative_candles()

    assert pattern.compute_integers(candles)[-1] == -100
    assert candles[-1].close >= candles[-1].open


def test_concealing_baby_swallow_handmade_input_uses_shadow_engulfing_only() -> None:
    pattern = TALIB_MULTI_CANDLE_BY_NAME["pat_concealing_baby_swallow"]
    candles = _concealing_baby_swallow_candles()
    fourth = candles[-1]
    broken = _with_replacement(candles, len(candles) - 1, replace(fourth, low=88.0))

    assert pattern.compute_integers(candles)[-1] == 100
    assert pattern.compute_integers(broken)[-1] == 0


def test_mat_hold_handmade_input_exercises_penetration_and_omits_current_body_long() -> None:
    pattern = TALIB_MULTI_CANDLE_BY_NAME["pat_mat_hold"]
    candles = _mat_hold_candles()
    fifth = candles[-1]
    current_body_long = candle_average_series(CandleSettingType.BODY_LONG, candles)[-1]
    current_body_long_would_pass = _with_replacement(
        candles,
        len(candles) - 1,
        replace(fifth, open=103.95, high=108.2, low=103.8, close=108.0),
    )

    assert current_body_long is not None
    assert real_body(fifth) <= current_body_long
    assert pattern.compute_integers(candles)[-1] == 100
    assert _mat_hold_value(candles, 0.5) == 100
    assert _mat_hold_value(candles, 0.2) == 0
    assert pattern.compute_integers(current_body_long_would_pass)[-1] == 100


def test_rise_fall_three_methods_handmade_input_requires_current_body_long() -> None:
    pattern = TALIB_MULTI_CANDLE_BY_NAME["pat_rise_fall_three_methods"]
    candles = _rise_fall_three_methods_candles()
    fifth = candles[-1]
    broken = _with_replacement(candles, len(candles) - 1, replace(fifth, close=103.0, high=103.5))

    assert pattern.compute_integers(candles)[-1] == 100
    assert pattern.compute_integers(broken)[-1] == 0


def test_breakaway_handmade_input_has_no_middle_short_body_requirement() -> None:
    pattern = TALIB_MULTI_CANDLE_BY_NAME["pat_breakaway"]
    candles = _breakaway_bearish_candles()
    third = candles[12]
    long_middle = _with_replacement(candles, 12, replace(third, close=116.5, high=117.0))

    assert pattern.compute_integers(candles)[-1] == -100
    assert pattern.compute_integers(long_middle)[-1] == -100
