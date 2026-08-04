"""Verify the TA-Lib candlestick calculation foundation."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest
from core_lib.patterns.talib_candles import (
    CANDLE_SETTING_ORDER,
    DEFAULT_CANDLE_SETTINGS,
    CandleAverageState,
    CandleRangeType,
    CandleSettingType,
    candle_average_at,
    candle_average_series,
    candle_gap_down,
    candle_gap_up,
    candle_range,
    candle_settings_lookback,
    candle_settings_min_history,
    real_body_bottom,
    real_body_gap_down,
    real_body_gap_up,
    real_body_top,
)
from core_lib.types import Candle


def make_candle(index: int, open_price: float, high: float, low: float, close: float) -> Candle:
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


def averaging_candles() -> list[Candle]:
    candles: list[Candle] = []
    for index in range(10):
        unit = float(index + 1)
        open_price = 100.0 + index * 10.0
        close = open_price + unit
        high = close + unit
        low = open_price - 2.0 * unit
        candles.append(make_candle(index, open_price, high, low, close))
    candles.append(make_candle(10, 250.0, 260.0, 240.0, 253.0))
    return candles


def varied_candles(count: int) -> list[Candle]:
    candles: list[Candle] = []
    for index in range(count):
        open_price = 100.0 + index * 1.25
        body = float(index % 5 + 1) * 0.2
        close = open_price + body if index % 2 == 0 else open_price - body
        high = max(open_price, close) + 0.4 + float(index % 3) * 0.15
        low = min(open_price, close) - 0.3 - float(index % 4) * 0.1
        candles.append(make_candle(index, open_price, high, low, close))
    return candles


def test_default_candle_settings_match_ta_global_defaults() -> None:
    """Check the eleven ``TA_CandleDefaultSettings`` entries from ``ta_global.c``."""
    expected = {
        CandleSettingType.BODY_LONG: (CandleRangeType.REAL_BODY, 10, 1.0),
        CandleSettingType.BODY_VERY_LONG: (CandleRangeType.REAL_BODY, 10, 3.0),
        CandleSettingType.BODY_SHORT: (CandleRangeType.REAL_BODY, 10, 1.0),
        CandleSettingType.BODY_DOJI: (CandleRangeType.HIGH_LOW, 10, 0.1),
        CandleSettingType.SHADOW_LONG: (CandleRangeType.REAL_BODY, 0, 1.0),
        CandleSettingType.SHADOW_VERY_LONG: (CandleRangeType.REAL_BODY, 0, 2.0),
        CandleSettingType.SHADOW_SHORT: (CandleRangeType.SHADOWS, 10, 1.0),
        CandleSettingType.SHADOW_VERY_SHORT: (CandleRangeType.HIGH_LOW, 10, 0.1),
        CandleSettingType.NEAR: (CandleRangeType.HIGH_LOW, 5, 0.2),
        CandleSettingType.FAR: (CandleRangeType.HIGH_LOW, 5, 0.6),
        CandleSettingType.EQUAL: (CandleRangeType.HIGH_LOW, 5, 0.05),
    }

    assert tuple(DEFAULT_CANDLE_SETTINGS) == CANDLE_SETTING_ORDER
    for setting_type in CANDLE_SETTING_ORDER:
        setting = DEFAULT_CANDLE_SETTINGS[setting_type]
        range_type, avg_period, factor = expected[setting_type]
        assert setting.setting_type == setting_type
        assert setting.range_type == range_type
        assert setting.avg_period == avg_period
        assert setting.factor == factor


def test_candle_range_uses_talib_range_type() -> None:
    candle = make_candle(0, 10.0, 15.0, 8.0, 12.0)

    assert candle_range(CandleSettingType.BODY_LONG, candle) == 2.0
    assert candle_range(CandleSettingType.BODY_DOJI, candle) == 7.0
    assert candle_range(CandleSettingType.SHADOW_SHORT, candle) == 5.0


def test_real_body_bounds_and_gap_helpers_match_talib_macros() -> None:
    first = make_candle(0, 10.0, 12.0, 9.0, 11.0)
    real_body_gap = make_candle(1, 12.5, 13.0, 11.5, 12.8)
    high_low_gap = make_candle(2, 14.0, 15.0, 13.5, 14.5)
    downside_gap = make_candle(3, 7.0, 8.0, 6.5, 6.8)

    assert real_body_bottom(first) == 10.0
    assert real_body_top(first) == 11.0
    assert real_body_gap_up(real_body_gap, first)
    assert not candle_gap_up(real_body_gap, first)
    assert candle_gap_up(high_low_gap, first)
    assert real_body_gap_down(downside_gap, first)
    assert candle_gap_down(downside_gap, first)


def test_candle_average_matches_hand_calculation() -> None:
    candles = averaging_candles()

    assert candle_average_at(CandleSettingType.BODY_LONG, candles, 10) == pytest.approx(5.5)
    assert candle_average_at(CandleSettingType.BODY_DOJI, candles, 10) == pytest.approx(2.2)
    assert candle_average_at(CandleSettingType.SHADOW_SHORT, candles, 10) == pytest.approx(8.25)


def test_zero_average_period_uses_the_target_candle_itself() -> None:
    candles = averaging_candles()

    assert candle_average_at(CandleSettingType.SHADOW_LONG, candles, 10) == 3.0
    assert candle_average_at(CandleSettingType.SHADOW_VERY_LONG, candles, 10) == 6.0


def test_same_setting_average_offsets_are_independent() -> None:
    candles = [
        make_candle(
            index,
            100.0 + index,
            101.0 + index + index * 0.1,
            99.0 + index,
            101.0 + index + index * 0.1,
        )
        for index in range(20)
    ]
    current = candle_average_series(CandleSettingType.BODY_LONG, candles, target_offset=0)
    previous = candle_average_series(CandleSettingType.BODY_LONG, candles, target_offset=1)

    assert current[11] == candle_average_at(CandleSettingType.BODY_LONG, candles, 11)
    assert previous[11] == candle_average_at(CandleSettingType.BODY_LONG, candles, 10)
    assert current[11] != previous[11]


@pytest.mark.parametrize("target_offset", [0, 1, 2])
@pytest.mark.parametrize(
    "setting_type",
    CANDLE_SETTING_ORDER,
    ids=lambda setting_type: setting_type.value,
)
def test_incremental_candle_average_matches_vector_path(
    setting_type: CandleSettingType,
    target_offset: int,
) -> None:
    candles = varied_candles(40)
    vector = candle_average_series(setting_type, candles, target_offset=target_offset)
    state = CandleAverageState(setting_type, target_offset=target_offset)

    incremental = [state.update(candle) for candle in candles]

    assert incremental == vector


def test_lookback_rule_matches_talib_cdl_lookback_shapes() -> None:
    assert candle_settings_lookback((CandleSettingType.BODY_DOJI,)) == 10
    assert candle_settings_min_history((CandleSettingType.BODY_DOJI,)) == 11

    hammer_settings = (
        CandleSettingType.BODY_SHORT,
        CandleSettingType.SHADOW_LONG,
        CandleSettingType.SHADOW_VERY_SHORT,
        CandleSettingType.NEAR,
    )
    assert candle_settings_lookback(hammer_settings, extra_bars=1) == 11
    assert candle_settings_min_history(hammer_settings, extra_bars=1) == 12

    assert candle_settings_lookback((), extra_bars=2) == 2
    assert candle_settings_lookback((CandleSettingType.NEAR,), minimum=1, extra_bars=5) == 10


def assert_series_has_prefix(values: Sequence[float | None], prefix_length: int) -> None:
    assert values[:prefix_length] == [None] * prefix_length
    assert values[prefix_length] is not None


def test_vector_series_marks_unavailable_warmup_slots() -> None:
    candles = varied_candles(20)

    assert_series_has_prefix(candle_average_series(CandleSettingType.BODY_DOJI, candles), 10)
    assert_series_has_prefix(
        candle_average_series(CandleSettingType.BODY_DOJI, candles, target_offset=2),
        12,
    )
    assert_series_has_prefix(candle_average_series(CandleSettingType.SHADOW_LONG, candles), 0)
