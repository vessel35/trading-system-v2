"""TA-Lib source ports for the first three-candle ``CDL`` pattern bundle.

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
    candle_gap_down,
    candle_gap_up,
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


def _lookback(
    setting_types: Sequence[CandleSettingType],
    *,
    extra_bars: int = 2,
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
    candles: Sequence[Candle],
    index: int,
    averages: AverageSeries,
    offset: int,
    *,
    inclusive: bool,
) -> bool:
    candle = candles[index - offset]
    average = _avg(averages, CandleSettingType.BODY_SHORT, index, offset=offset)
    if inclusive:
        return real_body(candle) <= average
    return real_body(candle) < average


def _upper_shadow_shorter_than(
    averages: AverageSeries,
    candles: Sequence[Candle],
    index: int,
    setting_type: CandleSettingType,
    offset: int,
) -> bool:
    return upper_shadow(candles[index - offset]) < _avg(
        averages,
        setting_type,
        index,
        offset=offset,
    )


def _upper_shadow_longer_than(
    averages: AverageSeries,
    candles: Sequence[Candle],
    index: int,
    setting_type: CandleSettingType,
    offset: int,
) -> bool:
    return upper_shadow(candles[index - offset]) > _avg(
        averages,
        setting_type,
        index,
        offset=offset,
    )


def _lower_shadow_shorter_than(
    averages: AverageSeries,
    candles: Sequence[Candle],
    index: int,
    setting_type: CandleSettingType,
    offset: int,
) -> bool:
    return lower_shadow(candles[index - offset]) < _avg(
        averages,
        setting_type,
        index,
        offset=offset,
    )


def _two_crows(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    if (
        candle_color(first) == 1
        and _long_body(candles, index, averages, _TWO_AGO)
        and candle_color(second) == -1
        and real_body_gap_up(second, first)
        and candle_color(third) == -1
        and third.open < second.open
        and third.open > second.close
        and third.close > first.open
        and third.close < first.close
    ):
        return -100
    return 0


def _three_black_crows(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    prior = candles[index - 3]
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    if (
        candle_color(prior) == 1
        and candle_color(first) == -1
        and candle_color(second) == -1
        and candle_color(third) == -1
        and second.open < first.open
        and second.open > first.close
        and third.open < second.open
        and third.open > second.close
        and prior.high > first.close
        and first.close > second.close
        and second.close > third.close
        and _lower_shadow_shorter_than(
            averages,
            candles,
            index,
            CandleSettingType.SHADOW_VERY_SHORT,
            _TWO_AGO,
        )
        and _lower_shadow_shorter_than(
            averages,
            candles,
            index,
            CandleSettingType.SHADOW_VERY_SHORT,
            _PREVIOUS,
        )
        and _lower_shadow_shorter_than(
            averages,
            candles,
            index,
            CandleSettingType.SHADOW_VERY_SHORT,
            _CURRENT,
        )
    ):
        return -100
    return 0


def _three_inside(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    first_color = candle_color(first)
    if (
        real_body_top(second) < real_body_top(first)
        and real_body_bottom(second) > real_body_bottom(first)
        and (
            first_color == 1
            and candle_color(third) == -1
            and third.close < first.open
            or first_color == -1
            and candle_color(third) == 1
            and third.close > first.open
        )
        and _long_body(candles, index, averages, _TWO_AGO)
        and _short_body(candles, index, averages, _PREVIOUS, inclusive=True)
    ):
        return -first_color * 100
    return 0


def _three_outside(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    del averages
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    second_color = candle_color(second)
    if (
        second_color == 1
        and candle_color(first) == -1
        and second.close > first.open
        and second.open < first.close
        and third.close > second.close
        or second_color == -1
        and candle_color(first) == 1
        and second.open > first.close
        and second.close < first.open
        and third.close < second.close
    ):
        return second_color * 100
    return 0


def _three_stars_in_the_south(
    candles: Sequence[Candle],
    index: int,
    averages: AverageSeries,
) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    if (
        candle_color(first) == -1
        and candle_color(second) == -1
        and candle_color(third) == -1
        and _long_body(candles, index, averages, _TWO_AGO)
        and lower_shadow(first)
        > _avg(averages, CandleSettingType.SHADOW_LONG, index, offset=_TWO_AGO)
        and real_body(second) < real_body(first)
        and second.open > first.close
        and second.open <= first.high
        and second.low < first.close
        and second.low >= first.low
        and lower_shadow(second)
        > _avg(averages, CandleSettingType.SHADOW_VERY_SHORT, index, offset=_PREVIOUS)
        and _short_body(candles, index, averages, _CURRENT, inclusive=False)
        and lower_shadow(third)
        < _avg(averages, CandleSettingType.SHADOW_VERY_SHORT, index, offset=_CURRENT)
        and upper_shadow(third)
        < _avg(averages, CandleSettingType.SHADOW_VERY_SHORT, index, offset=_CURRENT)
        and third.low > second.low
        and third.high < second.high
    ):
        return 100
    return 0


def _three_white_soldiers(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    if (
        candle_color(first) == 1
        and _upper_shadow_shorter_than(
            averages,
            candles,
            index,
            CandleSettingType.SHADOW_VERY_SHORT,
            _TWO_AGO,
        )
        and candle_color(second) == 1
        and _upper_shadow_shorter_than(
            averages,
            candles,
            index,
            CandleSettingType.SHADOW_VERY_SHORT,
            _PREVIOUS,
        )
        and candle_color(third) == 1
        and _upper_shadow_shorter_than(
            averages,
            candles,
            index,
            CandleSettingType.SHADOW_VERY_SHORT,
            _CURRENT,
        )
        and third.close > second.close
        and second.close > first.close
        and second.open > first.open
        and second.open <= first.close + _avg(averages, CandleSettingType.NEAR, index, offset=2)
        and third.open > second.open
        and third.open <= second.close + _avg(averages, CandleSettingType.NEAR, index, offset=1)
        and real_body(second)
        > real_body(first) - _avg(averages, CandleSettingType.FAR, index, offset=2)
        and real_body(third)
        > real_body(second) - _avg(averages, CandleSettingType.FAR, index, offset=1)
        and real_body(third) > _avg(averages, CandleSettingType.BODY_SHORT, index)
    ):
        return 100
    return 0


_ABANDONED_BABY_PENETRATION = resolve_talib_penetration("CDLABANDONEDBABY")


def _abandoned_baby(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    if (
        _long_body(candles, index, averages, _TWO_AGO)
        and real_body(second)
        <= _avg(averages, CandleSettingType.BODY_DOJI, index, offset=_PREVIOUS)
        and real_body(third) > _avg(averages, CandleSettingType.BODY_SHORT, index)
        and (
            candle_color(first) == 1
            and candle_color(third) == -1
            and third.close < first.close - real_body(first) * _ABANDONED_BABY_PENETRATION
            and candle_gap_up(second, first)
            and candle_gap_down(third, second)
            or candle_color(first) == -1
            and candle_color(third) == 1
            and third.close > first.close + real_body(first) * _ABANDONED_BABY_PENETRATION
            and candle_gap_down(second, first)
            and candle_gap_up(third, second)
        )
    ):
        return candle_color(third) * 100
    return 0


def _advance_block(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    if (
        candle_color(first) == 1
        and candle_color(second) == 1
        and candle_color(third) == 1
        and third.close > second.close
        and second.close > first.close
        and second.open > first.open
        and second.open <= first.close + _avg(averages, CandleSettingType.NEAR, index, offset=2)
        and third.open > second.open
        and third.open <= second.close + _avg(averages, CandleSettingType.NEAR, index, offset=1)
        and _long_body(candles, index, averages, _TWO_AGO)
        and _upper_shadow_shorter_than(
            averages,
            candles,
            index,
            CandleSettingType.SHADOW_SHORT,
            _TWO_AGO,
        )
        and (
            real_body(second)
            < real_body(first) - _avg(averages, CandleSettingType.FAR, index, offset=2)
            and real_body(third)
            < real_body(second) + _avg(averages, CandleSettingType.NEAR, index, offset=1)
            or real_body(third)
            < real_body(second) - _avg(averages, CandleSettingType.FAR, index, offset=1)
            or real_body(third) < real_body(second)
            and real_body(second) < real_body(first)
            and (
                _upper_shadow_longer_than(
                    averages,
                    candles,
                    index,
                    CandleSettingType.SHADOW_SHORT,
                    _CURRENT,
                )
                or _upper_shadow_longer_than(
                    averages,
                    candles,
                    index,
                    CandleSettingType.SHADOW_SHORT,
                    _PREVIOUS,
                )
            )
            or real_body(third) < real_body(second)
            and _upper_shadow_longer_than(
                averages,
                candles,
                index,
                CandleSettingType.SHADOW_LONG,
                _CURRENT,
            )
        )
    ):
        return -100
    return 0


_EVENING_DOJI_STAR_PENETRATION = resolve_talib_penetration("CDLEVENINGDOJISTAR")


def _evening_doji_star(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    if (
        candle_color(first) == 1
        and candle_color(third) == -1
        and real_body_gap_up(second, first)
        and third.close < first.close - real_body(first) * _EVENING_DOJI_STAR_PENETRATION
        and _long_body(candles, index, averages, _TWO_AGO)
        and real_body(second)
        <= _avg(averages, CandleSettingType.BODY_DOJI, index, offset=_PREVIOUS)
        and real_body(third) > _avg(averages, CandleSettingType.BODY_SHORT, index)
    ):
        return -100
    return 0


_EVENING_STAR_PENETRATION = resolve_talib_penetration("CDLEVENINGSTAR")


def _evening_star(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    if (
        candle_color(first) == 1
        and candle_color(third) == -1
        and real_body_gap_up(second, first)
        and third.close < first.close - real_body(first) * _EVENING_STAR_PENETRATION
        and _long_body(candles, index, averages, _TWO_AGO)
        and _short_body(candles, index, averages, _PREVIOUS, inclusive=True)
        and real_body(third) > _avg(averages, CandleSettingType.BODY_SHORT, index)
    ):
        return -100
    return 0


def _identical_three_crows(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    if (
        candle_color(first) == -1
        and _lower_shadow_shorter_than(
            averages,
            candles,
            index,
            CandleSettingType.SHADOW_VERY_SHORT,
            _TWO_AGO,
        )
        and candle_color(second) == -1
        and _lower_shadow_shorter_than(
            averages,
            candles,
            index,
            CandleSettingType.SHADOW_VERY_SHORT,
            _PREVIOUS,
        )
        and candle_color(third) == -1
        and _lower_shadow_shorter_than(
            averages,
            candles,
            index,
            CandleSettingType.SHADOW_VERY_SHORT,
            _CURRENT,
        )
        and first.close > second.close
        and second.close > third.close
        and second.open <= first.close + _avg(averages, CandleSettingType.EQUAL, index, offset=2)
        and second.open >= first.close - _avg(averages, CandleSettingType.EQUAL, index, offset=2)
        and third.open <= second.close + _avg(averages, CandleSettingType.EQUAL, index, offset=1)
        and third.open >= second.close - _avg(averages, CandleSettingType.EQUAL, index, offset=1)
    ):
        return -100
    return 0


_MORNING_DOJI_STAR_PENETRATION = resolve_talib_penetration("CDLMORNINGDOJISTAR")


def _morning_doji_star(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    if (
        candle_color(first) == -1
        and candle_color(third) == 1
        and real_body_gap_down(second, first)
        and third.close > first.close + real_body(first) * _MORNING_DOJI_STAR_PENETRATION
        and _long_body(candles, index, averages, _TWO_AGO)
        and real_body(second)
        <= _avg(averages, CandleSettingType.BODY_DOJI, index, offset=_PREVIOUS)
        and real_body(third) > _avg(averages, CandleSettingType.BODY_SHORT, index)
    ):
        return 100
    return 0


_MORNING_STAR_PENETRATION = resolve_talib_penetration("CDLMORNINGSTAR")


def _morning_star(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    if (
        candle_color(first) == -1
        and candle_color(third) == 1
        and real_body_gap_down(second, first)
        and third.close > first.close + real_body(first) * _MORNING_STAR_PENETRATION
        and _long_body(candles, index, averages, _TWO_AGO)
        and _short_body(candles, index, averages, _PREVIOUS, inclusive=True)
        and real_body(third) > _avg(averages, CandleSettingType.BODY_SHORT, index)
    ):
        return 100
    return 0


def _stalled_pattern(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    if (
        candle_color(first) == 1
        and candle_color(second) == 1
        and candle_color(third) == 1
        and third.close > second.close
        and second.close > first.close
        and _long_body(candles, index, averages, _TWO_AGO)
        and _long_body(candles, index, averages, _PREVIOUS)
        and _upper_shadow_shorter_than(
            averages,
            candles,
            index,
            CandleSettingType.SHADOW_VERY_SHORT,
            _PREVIOUS,
        )
        and second.open > first.open
        and second.open <= first.close + _avg(averages, CandleSettingType.NEAR, index, offset=2)
        and _short_body(candles, index, averages, _CURRENT, inclusive=False)
        and third.open
        >= second.close - real_body(third) - _avg(averages, CandleSettingType.NEAR, index, offset=1)
    ):
        return -100
    return 0


def _tri_star(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    body_doji = _avg(averages, CandleSettingType.BODY_DOJI, index, offset=_TWO_AGO)
    if (
        real_body(first) <= body_doji
        and real_body(second) <= body_doji
        and real_body(third) <= body_doji
    ):
        value = 0
        if real_body_gap_up(second, first) and real_body_top(third) < real_body_top(second):
            value = -100
        if real_body_gap_down(second, first) and real_body_bottom(third) > real_body_bottom(second):
            value = 100
        return value
    return 0


def _unique_three_river(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    if (
        candle_color(first) == -1
        and candle_color(second) == -1
        and candle_color(third) == 1
        and second.close > first.close
        and second.open <= first.open
        and second.low < first.low
        and third.open > second.low
        and _long_body(candles, index, averages, _TWO_AGO)
        and _short_body(candles, index, averages, _CURRENT, inclusive=False)
    ):
        return 100
    return 0


def _upside_gap_two_crows(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]
    if (
        candle_color(first) == 1
        and _long_body(candles, index, averages, _TWO_AGO)
        and candle_color(second) == -1
        and _short_body(candles, index, averages, _PREVIOUS, inclusive=True)
        and real_body_gap_up(second, first)
        and candle_color(third) == -1
        and third.open > second.open
        and third.close < second.close
        and third.close > first.close
    ):
        return -100
    return 0


TALIB_THREE_CANDLE_PATTERNS: tuple[TalibPatternPort, ...] = (
    TalibPatternPort(
        "pat_two_crows",
        "CDL2CROWS",
        _lookback((CandleSettingType.BODY_LONG,)),
        _keys(CandleSettingType.BODY_LONG, offset=_TWO_AGO),
        _two_crows,
    ),
    TalibPatternPort(
        "pat_three_black_crows",
        "CDL3BLACKCROWS",
        _lookback((CandleSettingType.SHADOW_VERY_SHORT,), extra_bars=3),
        (
            *_keys(CandleSettingType.SHADOW_VERY_SHORT, offset=_TWO_AGO),
            *_keys(CandleSettingType.SHADOW_VERY_SHORT, offset=_PREVIOUS),
            *_keys(CandleSettingType.SHADOW_VERY_SHORT),
        ),
        _three_black_crows,
    ),
    TalibPatternPort(
        "pat_three_inside",
        "CDL3INSIDE",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.BODY_SHORT)),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_TWO_AGO),
            *_keys(CandleSettingType.BODY_SHORT, offset=_PREVIOUS),
        ),
        _three_inside,
    ),
    TalibPatternPort("pat_three_outside", "CDL3OUTSIDE", 3, (), _three_outside),
    TalibPatternPort(
        "pat_three_stars_in_the_south",
        "CDL3STARSINSOUTH",
        _lookback(
            (
                CandleSettingType.BODY_LONG,
                CandleSettingType.BODY_SHORT,
                CandleSettingType.SHADOW_LONG,
                CandleSettingType.SHADOW_VERY_SHORT,
            )
        ),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_TWO_AGO),
            *_keys(CandleSettingType.SHADOW_LONG, offset=_TWO_AGO),
            *_keys(CandleSettingType.SHADOW_VERY_SHORT, offset=_PREVIOUS),
            *_keys(CandleSettingType.BODY_SHORT),
            *_keys(CandleSettingType.SHADOW_VERY_SHORT),
        ),
        _three_stars_in_the_south,
    ),
    TalibPatternPort(
        "pat_three_white_soldiers",
        "CDL3WHITESOLDIERS",
        _lookback(
            (
                CandleSettingType.BODY_SHORT,
                CandleSettingType.FAR,
                CandleSettingType.NEAR,
                CandleSettingType.SHADOW_VERY_SHORT,
            )
        ),
        (
            *_keys(CandleSettingType.SHADOW_VERY_SHORT, offset=_TWO_AGO),
            *_keys(CandleSettingType.SHADOW_VERY_SHORT, offset=_PREVIOUS),
            *_keys(CandleSettingType.SHADOW_VERY_SHORT),
            *_keys(CandleSettingType.NEAR, offset=_TWO_AGO),
            *_keys(CandleSettingType.NEAR, offset=_PREVIOUS),
            *_keys(CandleSettingType.FAR, offset=_TWO_AGO),
            *_keys(CandleSettingType.FAR, offset=_PREVIOUS),
            *_keys(CandleSettingType.BODY_SHORT),
        ),
        _three_white_soldiers,
    ),
    TalibPatternPort(
        "pat_abandoned_baby",
        "CDLABANDONEDBABY",
        _lookback(
            (
                CandleSettingType.BODY_DOJI,
                CandleSettingType.BODY_LONG,
                CandleSettingType.BODY_SHORT,
            )
        ),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_TWO_AGO),
            *_keys(CandleSettingType.BODY_DOJI, offset=_PREVIOUS),
            *_keys(CandleSettingType.BODY_SHORT),
        ),
        _abandoned_baby,
    ),
    TalibPatternPort(
        "pat_advance_block",
        "CDLADVANCEBLOCK",
        _lookback(
            (
                CandleSettingType.BODY_LONG,
                CandleSettingType.FAR,
                CandleSettingType.NEAR,
                CandleSettingType.SHADOW_LONG,
                CandleSettingType.SHADOW_SHORT,
            )
        ),
        (
            *_keys(CandleSettingType.SHADOW_SHORT, offset=_TWO_AGO),
            *_keys(CandleSettingType.SHADOW_SHORT, offset=_PREVIOUS),
            *_keys(CandleSettingType.SHADOW_SHORT),
            *_keys(CandleSettingType.SHADOW_LONG, offset=_PREVIOUS),
            *_keys(CandleSettingType.SHADOW_LONG),
            *_keys(CandleSettingType.NEAR, offset=_TWO_AGO),
            *_keys(CandleSettingType.NEAR, offset=_PREVIOUS),
            *_keys(CandleSettingType.FAR, offset=_TWO_AGO),
            *_keys(CandleSettingType.FAR, offset=_PREVIOUS),
            *_keys(CandleSettingType.BODY_LONG, offset=_TWO_AGO),
        ),
        _advance_block,
    ),
    TalibPatternPort(
        "pat_evening_doji_star",
        "CDLEVENINGDOJISTAR",
        _lookback(
            (
                CandleSettingType.BODY_DOJI,
                CandleSettingType.BODY_LONG,
                CandleSettingType.BODY_SHORT,
            )
        ),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_TWO_AGO),
            *_keys(CandleSettingType.BODY_DOJI, offset=_PREVIOUS),
            *_keys(CandleSettingType.BODY_SHORT),
        ),
        _evening_doji_star,
    ),
    TalibPatternPort(
        "pat_evening_star",
        "CDLEVENINGSTAR",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.BODY_SHORT)),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_TWO_AGO),
            *_keys(CandleSettingType.BODY_SHORT, offset=_PREVIOUS),
            *_keys(CandleSettingType.BODY_SHORT),
        ),
        _evening_star,
    ),
    TalibPatternPort(
        "pat_identical_three_crows",
        "CDLIDENTICAL3CROWS",
        _lookback((CandleSettingType.EQUAL, CandleSettingType.SHADOW_VERY_SHORT)),
        (
            *_keys(CandleSettingType.SHADOW_VERY_SHORT, offset=_TWO_AGO),
            *_keys(CandleSettingType.SHADOW_VERY_SHORT, offset=_PREVIOUS),
            *_keys(CandleSettingType.SHADOW_VERY_SHORT),
            *_keys(CandleSettingType.EQUAL, offset=_TWO_AGO),
            *_keys(CandleSettingType.EQUAL, offset=_PREVIOUS),
        ),
        _identical_three_crows,
    ),
    TalibPatternPort(
        "pat_morning_doji_star",
        "CDLMORNINGDOJISTAR",
        _lookback(
            (
                CandleSettingType.BODY_DOJI,
                CandleSettingType.BODY_LONG,
                CandleSettingType.BODY_SHORT,
            )
        ),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_TWO_AGO),
            *_keys(CandleSettingType.BODY_DOJI, offset=_PREVIOUS),
            *_keys(CandleSettingType.BODY_SHORT),
        ),
        _morning_doji_star,
    ),
    TalibPatternPort(
        "pat_morning_star",
        "CDLMORNINGSTAR",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.BODY_SHORT)),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_TWO_AGO),
            *_keys(CandleSettingType.BODY_SHORT, offset=_PREVIOUS),
            *_keys(CandleSettingType.BODY_SHORT),
        ),
        _morning_star,
    ),
    TalibPatternPort(
        "pat_stalled_pattern",
        "CDLSTALLEDPATTERN",
        _lookback(
            (
                CandleSettingType.BODY_LONG,
                CandleSettingType.BODY_SHORT,
                CandleSettingType.NEAR,
                CandleSettingType.SHADOW_VERY_SHORT,
            )
        ),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_TWO_AGO),
            *_keys(CandleSettingType.BODY_LONG, offset=_PREVIOUS),
            *_keys(CandleSettingType.BODY_SHORT),
            *_keys(CandleSettingType.SHADOW_VERY_SHORT, offset=_PREVIOUS),
            *_keys(CandleSettingType.NEAR, offset=_TWO_AGO),
            *_keys(CandleSettingType.NEAR, offset=_PREVIOUS),
        ),
        _stalled_pattern,
    ),
    TalibPatternPort(
        "pat_tri_star",
        "CDLTRISTAR",
        _lookback((CandleSettingType.BODY_DOJI,)),
        _keys(CandleSettingType.BODY_DOJI, offset=_TWO_AGO),
        _tri_star,
    ),
    TalibPatternPort(
        "pat_unique_three_river",
        "CDLUNIQUE3RIVER",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.BODY_SHORT)),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_TWO_AGO),
            *_keys(CandleSettingType.BODY_SHORT),
        ),
        _unique_three_river,
    ),
    TalibPatternPort(
        "pat_upside_gap_two_crows",
        "CDLUPSIDEGAP2CROWS",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.BODY_SHORT)),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_TWO_AGO),
            *_keys(CandleSettingType.BODY_SHORT, offset=_PREVIOUS),
        ),
        _upside_gap_two_crows,
    ),
)

TALIB_THREE_CANDLE_BY_NAME: Mapping[str, TalibPatternPort] = {
    pattern.name: pattern for pattern in TALIB_THREE_CANDLE_PATTERNS
}
TALIB_THREE_CANDLE_BY_FUNCTION: Mapping[str, TalibPatternPort] = {
    pattern.talib_function: pattern for pattern in TALIB_THREE_CANDLE_PATTERNS
}


def compute_talib_three_candle_patterns(
    candles: Sequence[Candle],
) -> dict[str, PatternSeries]:
    """Compute all ported three-candle TA-Lib patterns in this bundle."""
    return {
        pattern.name: pattern.compute_vectorized(candles) for pattern in TALIB_THREE_CANDLE_PATTERNS
    }


__all__ = [
    "TALIB_THREE_CANDLE_BY_FUNCTION",
    "TALIB_THREE_CANDLE_BY_NAME",
    "TALIB_THREE_CANDLE_PATTERNS",
    "compute_talib_three_candle_patterns",
]
