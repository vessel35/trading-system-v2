"""TA-Lib source ports for the first two-candle ``CDL`` pattern bundle.

The functions in this module are direct, unregistered TA-Lib v0.7.1 raw integer
ports. They coexist with the repository's historical ``two_candle.py`` rules
until the later adapter and registry cutover stages.
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


def _lookback(
    setting_types: Sequence[CandleSettingType],
    *,
    extra_bars: int = 1,
) -> int:
    return candle_settings_lookback(setting_types, extra_bars=extra_bars)


def _keys(*setting_types: CandleSettingType, offset: int = _CURRENT) -> tuple[AverageKey, ...]:
    return tuple((setting_type, offset) for setting_type in setting_types)


def _opposite_color(first: Candle, second: Candle) -> bool:
    return candle_color(first) == -candle_color(second)


def _signed_hundred(candle: Candle) -> int:
    return candle_color(candle) * 100


def _is_marubozu(
    candles: Sequence[Candle],
    index: int,
    averages: AverageSeries,
    *,
    offset: int,
) -> bool:
    candle = candles[index - offset]
    shadow_very_short = _avg(
        averages,
        CandleSettingType.SHADOW_VERY_SHORT,
        index,
        offset=offset,
    )
    return (
        real_body(candle) > _avg(averages, CandleSettingType.BODY_LONG, index, offset=offset)
        and upper_shadow(candle) < shadow_very_short
        and lower_shadow(candle) < shadow_very_short
    )


def _kicking_shape(candles: Sequence[Candle], index: int, averages: AverageSeries) -> bool:
    previous = candles[index - 1]
    current = candles[index]
    previous_color = candle_color(previous)
    return (
        _opposite_color(previous, current)
        and _is_marubozu(candles, index, averages, offset=_PREVIOUS)
        and _is_marubozu(candles, index, averages, offset=_CURRENT)
        and (
            previous_color == -1
            and candle_gap_up(current, previous)
            or previous_color == 1
            and candle_gap_down(current, previous)
        )
    )


def _engulfing(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    del averages
    previous = candles[index - 1]
    current = candles[index]
    color = candle_color(current)
    previous_color = candle_color(previous)
    if (
        color == 1
        and previous_color == -1
        and (
            current.close >= previous.open
            and current.open < previous.close
            or current.close > previous.open
            and current.open <= previous.close
        )
        or color == -1
        and previous_color == 1
        and (
            current.open >= previous.close
            and current.close < previous.open
            or current.open > previous.close
            and current.close <= previous.open
        )
    ):
        if current.open != previous.close and current.close != previous.open:
            return color * 100
        return color * 80
    return 0


def _harami(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    previous = candles[index - 1]
    current = candles[index]
    if real_body(previous) <= _avg(
        averages,
        CandleSettingType.BODY_LONG,
        index,
        offset=_PREVIOUS,
    ):
        return 0
    if real_body(current) > _avg(averages, CandleSettingType.BODY_SHORT, index):
        return 0
    if real_body_top(current) < real_body_top(previous) and real_body_bottom(
        current
    ) > real_body_bottom(previous):
        return -candle_color(previous) * 100
    if real_body_top(current) <= real_body_top(previous) and real_body_bottom(
        current
    ) >= real_body_bottom(previous):
        return -candle_color(previous) * 80
    return 0


def _harami_cross(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    previous = candles[index - 1]
    current = candles[index]
    if real_body(previous) <= _avg(
        averages,
        CandleSettingType.BODY_LONG,
        index,
        offset=_PREVIOUS,
    ):
        return 0
    if real_body(current) > _avg(averages, CandleSettingType.BODY_DOJI, index):
        return 0
    if real_body_top(current) < real_body_top(previous) and real_body_bottom(
        current
    ) > real_body_bottom(previous):
        return -candle_color(previous) * 100
    if real_body_top(current) <= real_body_top(previous) and real_body_bottom(
        current
    ) >= real_body_bottom(previous):
        return -candle_color(previous) * 80
    return 0


def _doji_star(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    previous = candles[index - 1]
    current = candles[index]
    previous_color = candle_color(previous)
    if (
        real_body(previous) > _avg(averages, CandleSettingType.BODY_LONG, index, offset=_PREVIOUS)
        and real_body(current) <= _avg(averages, CandleSettingType.BODY_DOJI, index)
        and (
            previous_color == 1
            and real_body_gap_up(current, previous)
            or previous_color == -1
            and real_body_gap_down(current, previous)
        )
    ):
        return -previous_color * 100
    return 0


def _piercing(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    previous = candles[index - 1]
    current = candles[index]
    if (
        candle_color(previous) == -1
        and real_body(previous)
        > _avg(averages, CandleSettingType.BODY_LONG, index, offset=_PREVIOUS)
        and candle_color(current) == 1
        and real_body(current) > _avg(averages, CandleSettingType.BODY_LONG, index)
        and current.open < previous.low
        and current.close < previous.open
        and current.close > previous.close + real_body(previous) * 0.5
    ):
        return 100
    return 0


_DARK_CLOUD_COVER_PENETRATION = resolve_talib_penetration("CDLDARKCLOUDCOVER")


def _dark_cloud_cover(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    previous = candles[index - 1]
    current = candles[index]
    if (
        candle_color(previous) == 1
        and real_body(previous)
        > _avg(averages, CandleSettingType.BODY_LONG, index, offset=_PREVIOUS)
        and candle_color(current) == -1
        and current.open > previous.high
        and current.close > previous.open
        and current.close < previous.close - real_body(previous) * _DARK_CLOUD_COVER_PENETRATION
    ):
        return -100
    return 0


def _counterattack(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    previous = candles[index - 1]
    current = candles[index]
    equal = _avg(averages, CandleSettingType.EQUAL, index, offset=_PREVIOUS)
    if (
        _opposite_color(previous, current)
        and real_body(previous)
        > _avg(averages, CandleSettingType.BODY_LONG, index, offset=_PREVIOUS)
        and real_body(current) > _avg(averages, CandleSettingType.BODY_LONG, index)
        and current.close <= previous.close + equal
        and current.close >= previous.close - equal
    ):
        return _signed_hundred(current)
    return 0


def _separating_lines(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    previous = candles[index - 1]
    current = candles[index]
    current_color = candle_color(current)
    equal = _avg(averages, CandleSettingType.EQUAL, index, offset=_PREVIOUS)
    shadow_very_short = _avg(averages, CandleSettingType.SHADOW_VERY_SHORT, index)
    if (
        _opposite_color(previous, current)
        and current.open <= previous.open + equal
        and current.open >= previous.open - equal
        and real_body(current) > _avg(averages, CandleSettingType.BODY_LONG, index)
        and (
            current_color == 1
            and lower_shadow(current) < shadow_very_short
            or current_color == -1
            and upper_shadow(current) < shadow_very_short
        )
    ):
        return current_color * 100
    return 0


def _kicking(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    if _kicking_shape(candles, index, averages):
        return _signed_hundred(candles[index])
    return 0


def _kicking_by_length(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    if not _kicking_shape(candles, index, averages):
        return 0
    current = candles[index]
    previous = candles[index - 1]
    longer_index = index if real_body(current) > real_body(previous) else index - 1
    return _signed_hundred(candles[longer_index])


def _homing_pigeon(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    previous = candles[index - 1]
    current = candles[index]
    if (
        candle_color(previous) == -1
        and candle_color(current) == -1
        and real_body(previous)
        > _avg(averages, CandleSettingType.BODY_LONG, index, offset=_PREVIOUS)
        and real_body(current) <= _avg(averages, CandleSettingType.BODY_SHORT, index)
        and current.open < previous.open
        and current.close > previous.close
    ):
        return 100
    return 0


def _matching_low(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    previous = candles[index - 1]
    current = candles[index]
    equal = _avg(averages, CandleSettingType.EQUAL, index, offset=_PREVIOUS)
    if (
        candle_color(previous) == -1
        and candle_color(current) == -1
        and current.close <= previous.close + equal
        and current.close >= previous.close - equal
    ):
        return 100
    return 0


def _in_neck(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    previous = candles[index - 1]
    current = candles[index]
    if (
        candle_color(previous) == -1
        and real_body(previous)
        > _avg(averages, CandleSettingType.BODY_LONG, index, offset=_PREVIOUS)
        and candle_color(current) == 1
        and current.open < previous.low
        and current.close
        <= previous.close
        + _avg(
            averages,
            CandleSettingType.EQUAL,
            index,
            offset=_PREVIOUS,
        )
        and current.close >= previous.close
    ):
        return -100
    return 0


def _on_neck(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    previous = candles[index - 1]
    current = candles[index]
    equal = _avg(averages, CandleSettingType.EQUAL, index, offset=_PREVIOUS)
    if (
        candle_color(previous) == -1
        and real_body(previous)
        > _avg(averages, CandleSettingType.BODY_LONG, index, offset=_PREVIOUS)
        and candle_color(current) == 1
        and current.open < previous.low
        and current.close <= previous.low + equal
        and current.close >= previous.low - equal
    ):
        return -100
    return 0


def _thrusting(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    previous = candles[index - 1]
    current = candles[index]
    if (
        candle_color(previous) == -1
        and real_body(previous)
        > _avg(averages, CandleSettingType.BODY_LONG, index, offset=_PREVIOUS)
        and candle_color(current) == 1
        and current.open < previous.low
        and current.close
        > previous.close + _avg(averages, CandleSettingType.EQUAL, index, offset=_PREVIOUS)
        and current.close <= previous.close + real_body(previous) * 0.5
    ):
        return -100
    return 0


TALIB_TWO_CANDLE_PATTERNS: tuple[TalibPatternPort, ...] = (
    TalibPatternPort("pat_engulfing", "CDLENGULFING", 2, (), _engulfing),
    TalibPatternPort(
        "pat_harami",
        "CDLHARAMI",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.BODY_SHORT)),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_PREVIOUS),
            *_keys(CandleSettingType.BODY_SHORT),
        ),
        _harami,
    ),
    TalibPatternPort(
        "pat_harami_cross",
        "CDLHARAMICROSS",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.BODY_DOJI)),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_PREVIOUS),
            *_keys(CandleSettingType.BODY_DOJI),
        ),
        _harami_cross,
    ),
    TalibPatternPort(
        "pat_doji_star",
        "CDLDOJISTAR",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.BODY_DOJI)),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_PREVIOUS),
            *_keys(CandleSettingType.BODY_DOJI),
        ),
        _doji_star,
    ),
    TalibPatternPort(
        "pat_piercing",
        "CDLPIERCING",
        _lookback((CandleSettingType.BODY_LONG,)),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_PREVIOUS),
            *_keys(CandleSettingType.BODY_LONG),
        ),
        _piercing,
    ),
    TalibPatternPort(
        "pat_dark_cloud_cover",
        "CDLDARKCLOUDCOVER",
        _lookback((CandleSettingType.BODY_LONG,)),
        _keys(CandleSettingType.BODY_LONG, offset=_PREVIOUS),
        _dark_cloud_cover,
    ),
    TalibPatternPort(
        "pat_counterattack",
        "CDLCOUNTERATTACK",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.EQUAL)),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_PREVIOUS),
            *_keys(CandleSettingType.BODY_LONG),
            *_keys(CandleSettingType.EQUAL, offset=_PREVIOUS),
        ),
        _counterattack,
    ),
    TalibPatternPort(
        "pat_separating_lines",
        "CDLSEPARATINGLINES",
        _lookback(
            (
                CandleSettingType.BODY_LONG,
                CandleSettingType.EQUAL,
                CandleSettingType.SHADOW_VERY_SHORT,
            )
        ),
        (
            *_keys(CandleSettingType.BODY_LONG),
            *_keys(CandleSettingType.EQUAL, offset=_PREVIOUS),
            *_keys(CandleSettingType.SHADOW_VERY_SHORT),
        ),
        _separating_lines,
    ),
    TalibPatternPort(
        "pat_kicking",
        "CDLKICKING",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.SHADOW_VERY_SHORT)),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_PREVIOUS),
            *_keys(CandleSettingType.BODY_LONG),
            *_keys(CandleSettingType.SHADOW_VERY_SHORT, offset=_PREVIOUS),
            *_keys(CandleSettingType.SHADOW_VERY_SHORT),
        ),
        _kicking,
    ),
    TalibPatternPort(
        "pat_kicking_by_length",
        "CDLKICKINGBYLENGTH",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.SHADOW_VERY_SHORT)),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_PREVIOUS),
            *_keys(CandleSettingType.BODY_LONG),
            *_keys(CandleSettingType.SHADOW_VERY_SHORT, offset=_PREVIOUS),
            *_keys(CandleSettingType.SHADOW_VERY_SHORT),
        ),
        _kicking_by_length,
    ),
    TalibPatternPort(
        "pat_homing_pigeon",
        "CDLHOMINGPIGEON",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.BODY_SHORT)),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_PREVIOUS),
            *_keys(CandleSettingType.BODY_SHORT),
        ),
        _homing_pigeon,
    ),
    TalibPatternPort(
        "pat_matching_low",
        "CDLMATCHINGLOW",
        _lookback((CandleSettingType.EQUAL,)),
        _keys(CandleSettingType.EQUAL, offset=_PREVIOUS),
        _matching_low,
    ),
    TalibPatternPort(
        "pat_in_neck",
        "CDLINNECK",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.EQUAL)),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_PREVIOUS),
            *_keys(CandleSettingType.EQUAL, offset=_PREVIOUS),
        ),
        _in_neck,
    ),
    TalibPatternPort(
        "pat_on_neck",
        "CDLONNECK",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.EQUAL)),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_PREVIOUS),
            *_keys(CandleSettingType.EQUAL, offset=_PREVIOUS),
        ),
        _on_neck,
    ),
    TalibPatternPort(
        "pat_thrusting",
        "CDLTHRUSTING",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.EQUAL)),
        (
            *_keys(CandleSettingType.BODY_LONG, offset=_PREVIOUS),
            *_keys(CandleSettingType.EQUAL, offset=_PREVIOUS),
        ),
        _thrusting,
    ),
)

TALIB_TWO_CANDLE_BY_NAME: Mapping[str, TalibPatternPort] = {
    pattern.name: pattern for pattern in TALIB_TWO_CANDLE_PATTERNS
}
TALIB_TWO_CANDLE_BY_FUNCTION: Mapping[str, TalibPatternPort] = {
    pattern.talib_function: pattern for pattern in TALIB_TWO_CANDLE_PATTERNS
}


def compute_talib_two_candle_patterns(
    candles: Sequence[Candle],
) -> dict[str, PatternSeries]:
    """Compute all ported two-candle TA-Lib patterns in this bundle."""
    return {
        pattern.name: pattern.compute_vectorized(candles) for pattern in TALIB_TWO_CANDLE_PATTERNS
    }


__all__ = [
    "TALIB_TWO_CANDLE_BY_FUNCTION",
    "TALIB_TWO_CANDLE_BY_NAME",
    "TALIB_TWO_CANDLE_PATTERNS",
    "compute_talib_two_candle_patterns",
]
