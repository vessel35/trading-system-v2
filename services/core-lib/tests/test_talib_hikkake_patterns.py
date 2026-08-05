"""Assert the stateful TA-Lib Hikkake ports match TA-Lib's raw integer contract."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from math import isnan

import pytest
from core_lib.patterns.outputs import output_keys
from core_lib.patterns.talib_candles import CandleSettingType, candle_average_series
from core_lib.patterns.talib_hikkake import (
    TALIB_HIKKAKE_BY_FUNCTION,
    TALIB_HIKKAKE_PATTERNS,
    TalibStatefulPatternPort,
)
from core_lib.patterns.talib_multi_candle import TALIB_MULTI_CANDLE_PATTERNS
from core_lib.patterns.talib_raw import (
    TalibPatternPort,
    sparse_talib_integer_signals,
    talib_integer_from_outputs,
)
from core_lib.patterns.talib_single_candle import TALIB_SINGLE_CANDLE_PATTERNS
from core_lib.patterns.talib_three_candle import TALIB_THREE_CANDLE_PATTERNS
from core_lib.patterns.talib_two_candle import TALIB_TWO_CANDLE_PATTERNS
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

Ohlc = tuple[float, float, float, float]
TalibDirectPort = TalibPatternPort | TalibStatefulPatternPort


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


def _candles(rows: Sequence[Ohlc]) -> list[Candle]:
    return [_make_candle(index, *row) for index, row in enumerate(rows)]


def _warmup_rows(count: int) -> list[Ohlc]:
    return [(100.0 + index, 103.0 + index, 97.0 + index, 101.0 + index) for index in range(count)]


def _sparse(values: Sequence[int]) -> dict[int, int]:
    return {index: value for index, value in enumerate(values) if value != 0}


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


def _hikkake_new_result(candles: Sequence[Candle], index: int) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    if (
        second.high < first.high
        and second.low > first.low
        and (
            third.high < second.high
            and third.low < second.low
            or third.high > second.high
            and third.low > second.low
        )
    ):
        return 100 if third.high < second.high else -100
    return 0


def _hikkakemod_new_result(
    candles: Sequence[Candle],
    index: int,
    near_average: float | None,
) -> int:
    if near_average is None:
        return 0
    first = candles[index - 3]
    second = candles[index - 2]
    third = candles[index - 1]
    fourth = candles[index]
    if (
        second.high < first.high
        and second.low > first.low
        and third.high < second.high
        and third.low > second.low
        and (
            fourth.high < third.high
            and fourth.low < third.low
            and second.close <= second.low + near_average
            or fourth.high > third.high
            and fourth.low > third.low
            and second.close >= second.high - near_average
        )
    ):
        return 100 if fourth.high < third.high else -100
    return 0


def _confirms_previous(
    candles: Sequence[Candle],
    index: int,
    pattern_idx: int,
    pattern_result: int,
) -> bool:
    return index <= pattern_idx + 3 and (
        pattern_result > 0
        and candles[index].close > candles[pattern_idx - 1].high
        or pattern_result < 0
        and candles[index].close < candles[pattern_idx - 1].low
    )


def _basic_hikkake_overwrite_bars(candles: Sequence[Candle]) -> list[int]:
    pattern_idx = 0
    pattern_result = 0
    bars: list[int] = []
    for index in range(5 - 3, len(candles)):
        new_result = _hikkake_new_result(candles, index)
        confirms = _confirms_previous(candles, index, pattern_idx, pattern_result)
        if new_result != 0:
            if index >= 5 and confirms:
                bars.append(index)
            pattern_idx = index
            pattern_result = new_result
        elif confirms:
            pattern_idx = 0
    return bars


def _modified_hikkake_overwrite_bars(candles: Sequence[Candle]) -> list[int]:
    near_averages = candle_average_series(CandleSettingType.NEAR, candles, target_offset=2)
    pattern_idx = 0
    pattern_result = 0
    bars: list[int] = []
    for index in range(10 - 3, len(candles)):
        new_result = _hikkakemod_new_result(candles, index, near_averages[index])
        confirms = _confirms_previous(candles, index, pattern_idx, pattern_result)
        if new_result != 0:
            if index >= 10 and confirms:
                bars.append(index)
            pattern_idx = index
            pattern_result = new_result
        elif confirms:
            pattern_idx = 0
    return bars


def _hikkake_front_loop_candles() -> list[Candle]:
    return _candles(
        (
            (100.0, 120.0, 100.0, 110.0),
            (110.0, 115.0, 105.0, 111.0),
            (106.0, 114.0, 104.0, 107.0),
            (107.0, 113.0, 103.0, 110.0),
            (110.0, 114.0, 104.0, 111.0),
            (111.0, 121.0, 110.0, 121.0),
        )
    )


def _hikkake_deadline_candles() -> list[Candle]:
    return _candles(
        (
            (100.0, 103.0, 97.0, 101.0),
            (101.0, 104.0, 98.0, 102.0),
            (102.0, 105.0, 99.0, 103.0),
            (100.0, 120.0, 100.0, 110.0),
            (110.0, 115.0, 105.0, 111.0),
            (106.0, 114.0, 104.0, 107.0),
            (107.0, 113.0, 103.0, 110.0),
            (108.0, 116.0, 104.0, 111.0),
            (109.0, 117.0, 104.0, 112.0),
            (112.0, 121.0, 111.0, 121.0),
        )
    )


def _hikkakemod_bullish_confirmation_candles() -> list[Candle]:
    return _candles(
        (
            *_warmup_rows(7),
            (110.0, 120.0, 100.0, 112.0),
            (106.0, 115.0, 105.0, 105.8),
            (107.0, 114.0, 106.0, 109.0),
            (105.0, 113.0, 104.0, 108.0),
            (114.0, 116.0, 112.0, 115.0),
        )
    )


def _hikkakemod_bearish_confirmation_candles() -> list[Candle]:
    return _candles(
        (
            *_warmup_rows(7),
            (110.0, 120.0, 100.0, 112.0),
            (114.0, 115.0, 105.0, 114.5),
            (110.0, 114.0, 106.0, 109.0),
            (112.0, 116.0, 107.0, 115.0),
            (105.0, 107.0, 104.0, 105.0),
        )
    )


def _hikkakemod_overwrite_candles() -> list[Candle]:
    return _candles(
        (
            *_warmup_rows(7),
            (110.0, 120.0, 100.0, 112.0),
            (106.0, 115.0, 105.0, 105.8),
            (107.0, 114.0, 106.0, 109.0),
            (105.0, 113.0, 104.0, 108.0),
            (111.0, 112.0, 105.0, 111.8),
            (110.0, 111.0, 106.0, 110.0),
            (114.0, 115.0, 107.0, 115.0),
        )
    )


def _hikkakemod_front_loop_candles() -> list[Candle]:
    return _candles(
        (
            (100.0, 103.0, 97.0, 101.0),
            (101.0, 104.0, 98.0, 102.0),
            (102.0, 105.0, 99.0, 103.0),
            (103.0, 106.0, 100.0, 104.0),
            (110.0, 120.0, 100.0, 112.0),
            (106.0, 115.0, 105.0, 105.8),
            (107.0, 114.0, 106.0, 109.0),
            (105.0, 113.0, 104.0, 108.0),
            (108.0, 116.0, 103.0, 110.0),
            (109.0, 117.0, 102.0, 111.0),
            (114.0, 118.0, 112.0, 115.0),
        )
    )


def _hikkakemod_deadline_candles() -> list[Candle]:
    return _candles(
        (
            *_warmup_rows(7),
            (110.0, 120.0, 100.0, 112.0),
            (106.0, 115.0, 105.0, 105.8),
            (107.0, 114.0, 106.0, 109.0),
            (105.0, 113.0, 104.0, 108.0),
            (113.0, 114.0, 110.0, 113.0),
            (112.0, 113.0, 109.0, 112.0),
            (111.0, 112.0, 108.0, 111.0),
            (114.0, 116.0, 112.0, 115.0),
        )
    )


def _hikkakemod_near_offset_candles() -> list[Candle]:
    return _candles(
        (
            (100.0, 101.0, 100.0, 100.5),
            (101.0, 102.0, 101.0, 101.5),
            (102.0, 103.0, 102.0, 102.5),
            (120.0, 150.0, 100.0, 120.0),
            (103.0, 104.0, 103.0, 103.5),
            (104.0, 105.0, 104.0, 104.5),
            (105.0, 106.0, 105.0, 105.5),
            (110.0, 120.0, 100.0, 112.0),
            (106.0, 115.0, 105.0, 106.5),
            (107.0, 114.0, 106.0, 109.0),
            (105.0, 113.0, 104.0, 108.0),
        )
    )


@_NEEDS_CAPTURE
@pytest.mark.parametrize("pattern", TALIB_HIKKAKE_PATTERNS, ids=lambda item: item.talib_function)
@pytest.mark.parametrize("regime", REGIME_NAMES)
def test_talib_hikkake_ports_match_capture(
    pattern: TalibStatefulPatternPort,
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


def test_talib_hikkake_outputs_keep_four_key_warmup_contract() -> None:
    candles = candles_for("quiet_small_bodies")
    for pattern in TALIB_HIKKAKE_PATTERNS:
        keys = set(output_keys(pattern.name))
        values = pattern.compute_vectorized(candles)
        assert len(values) == len(candles)
        for index, value in enumerate(values):
            assert set(value) == keys
            if index < pattern.lookback:
                assert all(isnan(number) for number in value.values())
            else:
                assert all(not isnan(number) for number in value.values())


def test_talib_hikkake_lookbacks_match_source() -> None:
    assert TALIB_HIKKAKE_BY_FUNCTION["CDLHIKKAKE"].lookback == 5
    assert TALIB_HIKKAKE_BY_FUNCTION["CDLHIKKAKEMOD"].lookback == 10


@_NEEDS_CAPTURE
def test_hikkake_capture_sparse_branches_are_explicit() -> None:
    assert _captured_total("CDLHIKKAKE") == 2181
    assert _captured_values("CDLHIKKAKE") == {100: 895, -100: 929, 200: 173, -200: 184}

    assert _captured_total("CDLHIKKAKEMOD") == 6
    assert _captured_values("CDLHIKKAKEMOD") == {100: 3, -100: 3}


@_NEEDS_CAPTURE
def test_hikkake_capture_covers_basic_overwrite_but_not_modified_overwrite() -> None:
    basic = {
        regime: tuple(_basic_hikkake_overwrite_bars(candles_for(regime))) for regime in REGIME_NAMES
    }
    modified = {
        regime: tuple(_modified_hikkake_overwrite_bars(candles_for(regime)))
        for regime in REGIME_NAMES
    }

    assert sum(len(bars) for bars in basic.values()) == 21
    assert basic == {
        "mixed_hourly": (442, 2055, 2652, 3385, 3570, 3833),
        "strong_uptrend": (711, 1576, 1992, 2522, 2596),
        "strong_downtrend": (101, 2487),
        "choppy_reversals": (453, 798, 1723, 1725, 1802),
        "frequent_gaps": (),
        "quiet_small_bodies": (1511,),
        "wide_swings": (1496, 2054),
    }
    assert sum(len(bars) for bars in modified.values()) == 0


@pytest.mark.parametrize(
    ("talib_function", "candles", "expected"),
    (
        ("CDLHIKKAKE", _hikkake_front_loop_candles(), {5: 200}),
        ("CDLHIKKAKE", _hikkake_deadline_candles(), {5: 100}),
        ("CDLHIKKAKEMOD", _hikkakemod_bullish_confirmation_candles(), {10: 100, 11: 200}),
        ("CDLHIKKAKEMOD", _hikkakemod_bearish_confirmation_candles(), {10: -100, 11: -200}),
        ("CDLHIKKAKEMOD", _hikkakemod_overwrite_candles(), {10: 100, 13: -100}),
        ("CDLHIKKAKEMOD", _hikkakemod_front_loop_candles(), {10: 200}),
        ("CDLHIKKAKEMOD", _hikkakemod_deadline_candles(), {10: 100}),
        ("CDLHIKKAKEMOD", _hikkakemod_near_offset_candles(), {10: 100}),
    ),
    ids=(
        "basic-front-loop-confirmation",
        "basic-three-bar-deadline",
        "modified-bullish-confirmation",
        "modified-bearish-confirmation",
        "modified-overwrite",
        "modified-front-loop-confirmation",
        "modified-three-bar-deadline",
        "modified-near-offset-two",
    ),
)
def test_handmade_inputs_match_talib_c_0_7_1_verified_outputs(
    talib_function: str,
    candles: list[Candle],
    expected: dict[int, int],
) -> None:
    pattern = TALIB_HIKKAKE_BY_FUNCTION[talib_function]

    assert _sparse(pattern.compute_integers(candles)) == expected


@pytest.mark.parametrize(
    ("talib_function", "candles", "confirmation_index", "expected"),
    (
        ("CDLHIKKAKE", _hikkake_front_loop_candles(), 5, 200),
        ("CDLHIKKAKEMOD", _hikkakemod_front_loop_candles(), 10, 200),
    ),
)
def test_hikkake_state_seed_replays_front_loop_transitions(
    talib_function: str,
    candles: list[Candle],
    confirmation_index: int,
    expected: int,
) -> None:
    pattern = TALIB_HIKKAKE_BY_FUNCTION[talib_function]
    state = pattern.make_state()
    state.seed(candles[:confirmation_index])

    value = state.update(candles[confirmation_index])

    assert pattern.compute_integers(candles)[confirmation_index] == expected
    assert talib_integer_from_outputs(pattern.name, value) == expected


def test_hikkakemod_reads_near_average_at_offset_two() -> None:
    candles = _hikkakemod_near_offset_candles()
    near_offset_two = candle_average_series(CandleSettingType.NEAR, candles, target_offset=2)[10]
    near_offset_one = candle_average_series(CandleSettingType.NEAR, candles, target_offset=1)[10]
    second = candles[8]

    assert near_offset_two is not None
    assert near_offset_one is not None
    assert second.close - second.low <= near_offset_two
    assert second.close - second.low > near_offset_one
    assert _sparse(TALIB_HIKKAKE_BY_FUNCTION["CDLHIKKAKEMOD"].compute_integers(candles)) == {
        10: 100
    }


@_NEEDS_CAPTURE
def test_all_sixty_one_direct_talib_ports_match_capture() -> None:
    ports: tuple[TalibDirectPort, ...] = (
        *TALIB_SINGLE_CANDLE_PATTERNS,
        *TALIB_TWO_CANDLE_PATTERNS,
        *TALIB_THREE_CANDLE_PATTERNS,
        *TALIB_MULTI_CANDLE_PATTERNS,
        *TALIB_HIKKAKE_PATTERNS,
    )
    assert (
        len(TALIB_SINGLE_CANDLE_PATTERNS)
        + len(TALIB_TWO_CANDLE_PATTERNS)
        + len(TALIB_THREE_CANDLE_PATTERNS)
        + len(TALIB_MULTI_CANDLE_PATTERNS)
        == 59
    )
    assert len(ports) == 61

    for pattern in ports:
        for regime in REGIME_NAMES:
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
