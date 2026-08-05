"""TA-Lib source ports for the gap and multi-candle ``CDL`` pattern bundle.

The functions in this module are direct, unregistered TA-Lib v0.7.1 raw integer
ports. They keep TA-Lib's integer output as the source value until the later
adapter and registry cutover stages decide how raw values map to the repository's
older four-key pattern contract.
"""

from collections.abc import Mapping, Sequence

from core_lib.types import Candle

from .registry import PatternSeries
from .talib_candles import (
    CandleSettingType,
    candle_color,
    candle_settings_lookback,
    lower_shadow,
    real_body,
    real_body_bottom,
    real_body_gap_down,
    real_body_gap_up,
    real_body_top,
    upper_shadow,
)
from .talib_raw import (
    AverageKey,
    AverageSeries,
    TalibPatternPort,
    _avg,
    resolve_talib_penetration,
)

_CURRENT: int = 0
_PREVIOUS: int = 1
_TWO_AGO: int = 2
_THREE_AGO: int = 3
_FOUR_AGO: int = 4


def _lookback(
    setting_types: Sequence[CandleSettingType],
    *,
    extra_bars: int,
) -> int:
    return candle_settings_lookback(setting_types, extra_bars=extra_bars)


def _keys(*setting_types: CandleSettingType, offset: int = _CURRENT) -> tuple[AverageKey, ...]:
    return tuple((setting_type, offset) for setting_type in setting_types)


def _long_body(candles: Sequence[Candle], index: int, averages: AverageSeries, offset: int) -> bool:
    candle = candles[index - offset]
    return real_body(candle) > _avg(
        averages,
        CandleSettingType.BODY_LONG,
        index,
        offset=offset,
    )


def _short_body(
    candles: Sequence[Candle], index: int, averages: AverageSeries, offset: int
) -> bool:
    candle = candles[index - offset]
    return real_body(candle) < _avg(
        averages,
        CandleSettingType.BODY_SHORT,
        index,
        offset=offset,
    )


def _three_line_strike(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 3]
    second = candles[index - 2]
    third = candles[index - 1]
    fourth = candles[index]
    third_color = candle_color(third)
    if (
        candle_color(first) == candle_color(second)
        and candle_color(second) == third_color
        and candle_color(fourth) == -third_color
        and second.open
        >= real_body_bottom(first)
        - _avg(averages, CandleSettingType.NEAR, index, offset=_THREE_AGO)
        and second.open
        <= real_body_top(first) + _avg(averages, CandleSettingType.NEAR, index, offset=_THREE_AGO)
        and third.open
        >= real_body_bottom(second) - _avg(averages, CandleSettingType.NEAR, index, offset=_TWO_AGO)
        and third.open
        <= real_body_top(second) + _avg(averages, CandleSettingType.NEAR, index, offset=_TWO_AGO)
        and (
            third_color == 1
            and third.close > second.close
            and second.close > first.close
            and fourth.open > third.close
            and fourth.close < first.open
            or third_color == -1
            and third.close < second.close
            and second.close < first.close
            and fourth.open < third.close
            and fourth.close > first.open
        )
    ):
        return third_color * 100
    return 0


def _breakaway(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 4]
    second = candles[index - 3]
    third = candles[index - 2]
    fourth = candles[index - 1]
    fifth = candles[index]
    first_color = candle_color(first)
    if (
        first_color == candle_color(second)
        and candle_color(second) == candle_color(fourth)
        and candle_color(fourth) == -candle_color(fifth)
        and _long_body(candles, index, averages, _FOUR_AGO)
        and (
            first_color == -1
            and real_body_gap_down(second, first)
            and third.high < second.high
            and third.low < second.low
            and fourth.high < third.high
            and fourth.low < third.low
            and fifth.close > second.open
            and fifth.close < first.close
            or first_color == 1
            and real_body_gap_up(second, first)
            and third.high > second.high
            and third.low > second.low
            and fourth.high > third.high
            and fourth.low > third.low
            and fifth.close < second.open
            and fifth.close > first.close
        )
    ):
        return candle_color(fifth) * 100
    return 0


def _concealing_baby_swallow(
    candles: Sequence[Candle],
    index: int,
    averages: AverageSeries,
) -> int:
    first = candles[index - 3]
    second = candles[index - 2]
    third = candles[index - 1]
    fourth = candles[index]
    shadow_first = _avg(
        averages,
        CandleSettingType.SHADOW_VERY_SHORT,
        index,
        offset=_THREE_AGO,
    )
    shadow_second = _avg(
        averages,
        CandleSettingType.SHADOW_VERY_SHORT,
        index,
        offset=_TWO_AGO,
    )
    if (
        candle_color(first) == -1
        and candle_color(second) == -1
        and candle_color(third) == -1
        and candle_color(fourth) == -1
        and lower_shadow(first) < shadow_first
        and upper_shadow(first) < shadow_first
        and lower_shadow(second) < shadow_second
        and upper_shadow(second) < shadow_second
        and real_body_gap_down(third, second)
        and upper_shadow(third)
        > _avg(averages, CandleSettingType.SHADOW_VERY_SHORT, index, offset=_PREVIOUS)
        and third.high > second.close
        and fourth.high > third.high
        and fourth.low < third.low
    ):
        return 100
    return 0


def _gap_side_by_side_white(
    candles: Sequence[Candle],
    index: int,
    averages: AverageSeries,
) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    upside_gap = real_body_bottom(second) > real_body_top(first) and real_body_bottom(
        third
    ) > real_body_top(first)
    downside_gap = real_body_top(second) < real_body_bottom(first) and real_body_top(
        third
    ) < real_body_bottom(first)
    near = _avg(averages, CandleSettingType.NEAR, index, offset=_PREVIOUS)
    equal = _avg(averages, CandleSettingType.EQUAL, index, offset=_PREVIOUS)
    if (
        (upside_gap or downside_gap)
        and candle_color(second) == 1
        and candle_color(third) == 1
        and real_body(third) >= real_body(second) - near
        and real_body(third) <= real_body(second) + near
        and third.open >= second.open - equal
        and third.open <= second.open + equal
    ):
        return 100 if upside_gap else -100
    return 0


def _ladder_bottom(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 4]
    second = candles[index - 3]
    third = candles[index - 2]
    fourth = candles[index - 1]
    fifth = candles[index]
    if (
        candle_color(first) == -1
        and candle_color(second) == -1
        and candle_color(third) == -1
        and first.open > second.open
        and second.open > third.open
        and first.close > second.close
        and second.close > third.close
        and candle_color(fourth) == -1
        and upper_shadow(fourth)
        > _avg(averages, CandleSettingType.SHADOW_VERY_SHORT, index, offset=_PREVIOUS)
        and candle_color(fifth) == 1
        and fifth.open > fourth.open
        and fifth.close > fourth.high
    ):
        return 100
    return 0


_MAT_HOLD_PENETRATION = resolve_talib_penetration("CDLMATHOLD")


def _mat_hold_with_penetration(
    candles: Sequence[Candle],
    index: int,
    averages: AverageSeries,
    penetration: float,
) -> int:
    first = candles[index - 4]
    second = candles[index - 3]
    third = candles[index - 2]
    fourth = candles[index - 1]
    fifth = candles[index]
    penetration_floor = first.close - real_body(first) * penetration
    if (
        candle_color(first) == 1
        and candle_color(second) == -1
        and candle_color(fifth) == 1
        and real_body_gap_up(second, first)
        and real_body_bottom(third) < first.close
        and real_body_bottom(fourth) < first.close
        and real_body_bottom(third) > penetration_floor
        and real_body_bottom(fourth) > penetration_floor
        and real_body_top(third) < second.open
        and real_body_top(fourth) < real_body_top(third)
        and fifth.open > fourth.close
        and fifth.close > max(max(second.high, third.high), fourth.high)
        and _long_body(candles, index, averages, _FOUR_AGO)
        and _short_body(candles, index, averages, _THREE_AGO)
        and _short_body(candles, index, averages, _TWO_AGO)
        and _short_body(candles, index, averages, _PREVIOUS)
    ):
        return 100
    return 0


def _mat_hold(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    return _mat_hold_with_penetration(candles, index, averages, _MAT_HOLD_PENETRATION)


def _rise_fall_three_methods(
    candles: Sequence[Candle],
    index: int,
    averages: AverageSeries,
) -> int:
    first = candles[index - 4]
    second = candles[index - 3]
    third = candles[index - 2]
    fourth = candles[index - 1]
    fifth = candles[index]
    first_color = candle_color(first)
    if (
        first_color == -candle_color(second)
        and candle_color(second) == candle_color(third)
        and candle_color(third) == candle_color(fourth)
        and candle_color(fourth) == -candle_color(fifth)
        and real_body_bottom(second) < first.high
        and real_body_top(second) > first.low
        and real_body_bottom(third) < first.high
        and real_body_top(third) > first.low
        and real_body_bottom(fourth) < first.high
        and real_body_top(fourth) > first.low
        and third.close * first_color < second.close * first_color
        and fourth.close * first_color < third.close * first_color
        and fifth.open * first_color > fourth.close * first_color
        and fifth.close * first_color > first.close * first_color
        and _long_body(candles, index, averages, _FOUR_AGO)
        and _short_body(candles, index, averages, _THREE_AGO)
        and _short_body(candles, index, averages, _TWO_AGO)
        and _short_body(candles, index, averages, _PREVIOUS)
        and _long_body(candles, index, averages, _CURRENT)
    ):
        return 100 * first_color
    return 0


def _stick_sandwich(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    equal = _avg(averages, CandleSettingType.EQUAL, index, offset=_TWO_AGO)
    if (
        candle_color(first) == -1
        and candle_color(second) == 1
        and candle_color(third) == -1
        and second.low > first.close
        and third.close <= first.close + equal
        and third.close >= first.close - equal
    ):
        return 100
    return 0


def _tasuki_gap(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    similar_size = abs(real_body(second) - real_body(third)) < _avg(
        averages,
        CandleSettingType.NEAR,
        index,
        offset=_PREVIOUS,
    )
    if (
        real_body_gap_up(second, first)
        and candle_color(second) == 1
        and candle_color(third) == -1
        and third.open < second.close
        and third.open > second.open
        and third.close < second.open
        and third.close > real_body_top(first)
        and similar_size
        or real_body_gap_down(second, first)
        and candle_color(second) == -1
        and candle_color(third) == 1
        and third.open < second.open
        and third.open > second.close
        and third.close > second.open
        and third.close < real_body_bottom(first)
        and similar_size
    ):
        return candle_color(second) * 100
    return 0


def _xside_gap_three_methods(
    candles: Sequence[Candle],
    index: int,
    averages: AverageSeries,
) -> int:
    del averages
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    first_color = candle_color(first)
    if (
        first_color == candle_color(second)
        and candle_color(second) == -candle_color(third)
        and third.open < real_body_top(second)
        and third.open > real_body_bottom(second)
        and third.close < real_body_top(first)
        and third.close > real_body_bottom(first)
        and (
            first_color == 1
            and real_body_gap_up(second, first)
            or first_color == -1
            and real_body_gap_down(second, first)
        )
    ):
        return first_color * 100
    return 0


TALIB_MULTI_CANDLE_PATTERNS: tuple[TalibPatternPort, ...] = (
    TalibPatternPort(
        "pat_three_line_strike",
        "CDL3LINESTRIKE",
        _lookback((CandleSettingType.NEAR,), extra_bars=3),
        (
            *_keys(CandleSettingType.NEAR, offset=_THREE_AGO),
            *_keys(CandleSettingType.NEAR, offset=_TWO_AGO),
        ),
        _three_line_strike,
    ),
    TalibPatternPort(
        "pat_breakaway",
        "CDLBREAKAWAY",
        _lookback((CandleSettingType.BODY_LONG,), extra_bars=4),
        _keys(CandleSettingType.BODY_LONG, offset=_FOUR_AGO),
        _breakaway,
    ),
    TalibPatternPort(
        "pat_concealing_baby_swallow",
        "CDLCONCEALBABYSWALL",
        _lookback((CandleSettingType.SHADOW_VERY_SHORT,), extra_bars=3),
        (
            *_keys(CandleSettingType.SHADOW_VERY_SHORT, offset=_THREE_AGO),
            *_keys(CandleSettingType.SHADOW_VERY_SHORT, offset=_TWO_AGO),
            *_keys(CandleSettingType.SHADOW_VERY_SHORT, offset=_PREVIOUS),
        ),
        _concealing_baby_swallow,
    ),
    TalibPatternPort(
        "pat_gap_side_by_side_white",
        "CDLGAPSIDESIDEWHITE",
        _lookback((CandleSettingType.NEAR, CandleSettingType.EQUAL), extra_bars=2),
        (
            *_keys(CandleSettingType.NEAR, offset=_PREVIOUS),
            *_keys(CandleSettingType.EQUAL, offset=_PREVIOUS),
        ),
        _gap_side_by_side_white,
    ),
    TalibPatternPort(
        "pat_ladder_bottom",
        "CDLLADDERBOTTOM",
        _lookback((CandleSettingType.SHADOW_VERY_SHORT,), extra_bars=4),
        _keys(CandleSettingType.SHADOW_VERY_SHORT, offset=_PREVIOUS),
        _ladder_bottom,
    ),
    TalibPatternPort(
        "pat_mat_hold",
        "CDLMATHOLD",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.BODY_SHORT), extra_bars=4),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_FOUR_AGO),
            *_keys(CandleSettingType.BODY_SHORT, offset=_THREE_AGO),
            *_keys(CandleSettingType.BODY_SHORT, offset=_TWO_AGO),
            *_keys(CandleSettingType.BODY_SHORT, offset=_PREVIOUS),
        ),
        _mat_hold,
    ),
    TalibPatternPort(
        "pat_rise_fall_three_methods",
        "CDLRISEFALL3METHODS",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.BODY_SHORT), extra_bars=4),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_FOUR_AGO),
            *_keys(CandleSettingType.BODY_LONG),
            *_keys(CandleSettingType.BODY_SHORT, offset=_THREE_AGO),
            *_keys(CandleSettingType.BODY_SHORT, offset=_TWO_AGO),
            *_keys(CandleSettingType.BODY_SHORT, offset=_PREVIOUS),
        ),
        _rise_fall_three_methods,
    ),
    TalibPatternPort(
        "pat_stick_sandwich",
        "CDLSTICKSANDWICH",
        _lookback((CandleSettingType.EQUAL,), extra_bars=2),
        _keys(CandleSettingType.EQUAL, offset=_TWO_AGO),
        _stick_sandwich,
    ),
    TalibPatternPort(
        "pat_tasuki_gap",
        "CDLTASUKIGAP",
        _lookback((CandleSettingType.NEAR,), extra_bars=2),
        _keys(CandleSettingType.NEAR, offset=_PREVIOUS),
        _tasuki_gap,
    ),
    TalibPatternPort(
        "pat_gap_three_methods",
        "CDLXSIDEGAP3METHODS",
        2,
        (),
        _xside_gap_three_methods,
    ),
)

TALIB_MULTI_CANDLE_BY_NAME: Mapping[str, TalibPatternPort] = {
    pattern.name: pattern for pattern in TALIB_MULTI_CANDLE_PATTERNS
}
TALIB_MULTI_CANDLE_BY_FUNCTION: Mapping[str, TalibPatternPort] = {
    pattern.talib_function: pattern for pattern in TALIB_MULTI_CANDLE_PATTERNS
}


def compute_talib_multi_candle_patterns(
    candles: Sequence[Candle],
) -> dict[str, PatternSeries]:
    """Compute all ported multi-candle TA-Lib patterns in this bundle."""
    return {
        pattern.name: pattern.compute_vectorized(candles) for pattern in TALIB_MULTI_CANDLE_PATTERNS
    }


__all__ = [
    "TALIB_MULTI_CANDLE_BY_FUNCTION",
    "TALIB_MULTI_CANDLE_BY_NAME",
    "TALIB_MULTI_CANDLE_PATTERNS",
    "compute_talib_multi_candle_patterns",
]
