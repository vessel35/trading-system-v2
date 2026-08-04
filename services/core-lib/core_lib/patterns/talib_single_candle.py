"""TA-Lib source ports for the first single-candle ``CDL`` pattern bundle.

The existing pattern modules implement the repository's historical candlestick
standard. This module deliberately does not register into that registry yet. It
ports the TA-Lib C functions as a side-by-side implementation so tests can prove
bar-level parity against captured TA-Lib output before the old implementation is
retired.
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
    real_body_top,
    upper_shadow,
)
from .talib_raw import (
    TALIB_SOURCE_VERSION,
    AverageKey,
    AverageSeries,
    TalibPatternPort,
    _avg,
    sparse_talib_integer_signals,
    talib_integer_from_outputs,
)

_CURRENT: int = 0
_PREVIOUS: int = 1


def _min_open_close(candle: Candle) -> float:
    return real_body_bottom(candle)


def _max_open_close(candle: Candle) -> float:
    return real_body_top(candle)


def _signed_hundred(candle: Candle) -> int:
    return candle_color(candle) * 100


def _lookback(
    setting_types: Sequence[CandleSettingType],
    *,
    extra_bars: int = 0,
) -> int:
    return candle_settings_lookback(setting_types, extra_bars=extra_bars)


def _keys(*setting_types: CandleSettingType, offset: int = _CURRENT) -> tuple[AverageKey, ...]:
    return tuple((setting_type, offset) for setting_type in setting_types)


def _doji(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    candle = candles[index]
    if real_body(candle) <= _avg(averages, CandleSettingType.BODY_DOJI, index):
        return 100
    return 0


def _long_legged_doji(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    candle = candles[index]
    if real_body(candle) <= _avg(
        averages,
        CandleSettingType.BODY_DOJI,
        index,
    ) and (
        lower_shadow(candle) > _avg(averages, CandleSettingType.SHADOW_LONG, index)
        or upper_shadow(candle) > _avg(averages, CandleSettingType.SHADOW_LONG, index)
    ):
        return 100
    return 0


def _rickshaw_man(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    candle = candles[index]
    near = _avg(averages, CandleSettingType.NEAR, index)
    midpoint = candle.low + (candle.high - candle.low) / 2
    if (
        real_body(candle) <= _avg(averages, CandleSettingType.BODY_DOJI, index)
        and lower_shadow(candle) > _avg(averages, CandleSettingType.SHADOW_LONG, index)
        and upper_shadow(candle) > _avg(averages, CandleSettingType.SHADOW_LONG, index)
        and _min_open_close(candle) <= midpoint + near
        and _max_open_close(candle) >= midpoint - near
    ):
        return 100
    return 0


def _dragonfly_doji(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    candle = candles[index]
    shadow_very_short = _avg(averages, CandleSettingType.SHADOW_VERY_SHORT, index)
    if (
        real_body(candle) <= _avg(averages, CandleSettingType.BODY_DOJI, index)
        and upper_shadow(candle) < shadow_very_short
        and lower_shadow(candle) > shadow_very_short
    ):
        return 100
    return 0


def _gravestone_doji(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    candle = candles[index]
    shadow_very_short = _avg(averages, CandleSettingType.SHADOW_VERY_SHORT, index)
    if (
        real_body(candle) <= _avg(averages, CandleSettingType.BODY_DOJI, index)
        and lower_shadow(candle) < shadow_very_short
        and upper_shadow(candle) > shadow_very_short
    ):
        return 100
    return 0


def _takuri(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    candle = candles[index]
    if (
        real_body(candle) <= _avg(averages, CandleSettingType.BODY_DOJI, index)
        and upper_shadow(candle) < _avg(averages, CandleSettingType.SHADOW_VERY_SHORT, index)
        and lower_shadow(candle) > _avg(averages, CandleSettingType.SHADOW_VERY_LONG, index)
    ):
        return 100
    return 0


def _hammer(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    candle = candles[index]
    if (
        real_body(candle) < _avg(averages, CandleSettingType.BODY_SHORT, index)
        and lower_shadow(candle) > _avg(averages, CandleSettingType.SHADOW_LONG, index)
        and upper_shadow(candle) < _avg(averages, CandleSettingType.SHADOW_VERY_SHORT, index)
        and _min_open_close(candle)
        <= candles[index - 1].low + _avg(averages, CandleSettingType.NEAR, index, offset=_PREVIOUS)
    ):
        return 100
    return 0


def _hanging_man(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    candle = candles[index]
    if (
        real_body(candle) < _avg(averages, CandleSettingType.BODY_SHORT, index)
        and lower_shadow(candle) > _avg(averages, CandleSettingType.SHADOW_LONG, index)
        and upper_shadow(candle) < _avg(averages, CandleSettingType.SHADOW_VERY_SHORT, index)
        and _min_open_close(candle)
        >= candles[index - 1].high - _avg(averages, CandleSettingType.NEAR, index, offset=_PREVIOUS)
    ):
        return -100
    return 0


def _inverted_hammer(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    candle = candles[index]
    previous = candles[index - 1]
    if (
        _max_open_close(candle) < _min_open_close(previous)
        and real_body(candle) < _avg(averages, CandleSettingType.BODY_SHORT, index)
        and upper_shadow(candle) > _avg(averages, CandleSettingType.SHADOW_LONG, index)
        and lower_shadow(candle) < _avg(averages, CandleSettingType.SHADOW_VERY_SHORT, index)
    ):
        return 100
    return 0


def _shooting_star(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    candle = candles[index]
    previous = candles[index - 1]
    if (
        _min_open_close(candle) > _max_open_close(previous)
        and real_body(candle) < _avg(averages, CandleSettingType.BODY_SHORT, index)
        and upper_shadow(candle) > _avg(averages, CandleSettingType.SHADOW_LONG, index)
        and lower_shadow(candle) < _avg(averages, CandleSettingType.SHADOW_VERY_SHORT, index)
    ):
        return -100
    return 0


def _spinning_top(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    candle = candles[index]
    body = real_body(candle)
    if (
        upper_shadow(candle) > body
        and lower_shadow(candle) > body
        and body < _avg(averages, CandleSettingType.BODY_SHORT, index)
    ):
        return _signed_hundred(candle)
    return 0


def _high_wave(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    candle = candles[index]
    if (
        real_body(candle) < _avg(averages, CandleSettingType.BODY_SHORT, index)
        and upper_shadow(candle) > _avg(averages, CandleSettingType.SHADOW_VERY_LONG, index)
        and lower_shadow(candle) > _avg(averages, CandleSettingType.SHADOW_VERY_LONG, index)
    ):
        return _signed_hundred(candle)
    return 0


def _marubozu(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    candle = candles[index]
    shadow_very_short = _avg(averages, CandleSettingType.SHADOW_VERY_SHORT, index)
    if (
        real_body(candle) > _avg(averages, CandleSettingType.BODY_LONG, index)
        and upper_shadow(candle) < shadow_very_short
        and lower_shadow(candle) < shadow_very_short
    ):
        return _signed_hundred(candle)
    return 0


def _closing_marubozu(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    candle = candles[index]
    color = candle_color(candle)
    if real_body(candle) <= _avg(averages, CandleSettingType.BODY_LONG, index):
        return 0
    shadow_very_short = _avg(averages, CandleSettingType.SHADOW_VERY_SHORT, index)
    if (
        color == 1
        and upper_shadow(candle) < shadow_very_short
        or color == -1
        and lower_shadow(candle) < shadow_very_short
    ):
        return color * 100
    return 0


def _belt_hold(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    candle = candles[index]
    color = candle_color(candle)
    if real_body(candle) <= _avg(averages, CandleSettingType.BODY_LONG, index):
        return 0
    shadow_very_short = _avg(averages, CandleSettingType.SHADOW_VERY_SHORT, index)
    if (
        color == 1
        and lower_shadow(candle) < shadow_very_short
        or color == -1
        and upper_shadow(candle) < shadow_very_short
    ):
        return color * 100
    return 0


def _long_line(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    candle = candles[index]
    shadow_short = _avg(averages, CandleSettingType.SHADOW_SHORT, index)
    if (
        real_body(candle) > _avg(averages, CandleSettingType.BODY_LONG, index)
        and upper_shadow(candle) < shadow_short
        and lower_shadow(candle) < shadow_short
    ):
        return _signed_hundred(candle)
    return 0


def _short_line(candles: Sequence[Candle], index: int, averages: AverageSeries) -> int:
    candle = candles[index]
    shadow_short = _avg(averages, CandleSettingType.SHADOW_SHORT, index)
    if (
        real_body(candle) < _avg(averages, CandleSettingType.BODY_SHORT, index)
        and upper_shadow(candle) < shadow_short
        and lower_shadow(candle) < shadow_short
    ):
        return _signed_hundred(candle)
    return 0


TALIB_SINGLE_CANDLE_PATTERNS: tuple[TalibPatternPort, ...] = (
    TalibPatternPort(
        "pat_doji",
        "CDLDOJI",
        _lookback((CandleSettingType.BODY_DOJI,)),
        _keys(CandleSettingType.BODY_DOJI),
        _doji,
    ),
    TalibPatternPort(
        "pat_long_legged_doji",
        "CDLLONGLEGGEDDOJI",
        _lookback((CandleSettingType.BODY_DOJI, CandleSettingType.SHADOW_LONG)),
        _keys(CandleSettingType.BODY_DOJI, CandleSettingType.SHADOW_LONG),
        _long_legged_doji,
    ),
    TalibPatternPort(
        "pat_rickshaw_man",
        "CDLRICKSHAWMAN",
        _lookback(
            (
                CandleSettingType.BODY_DOJI,
                CandleSettingType.SHADOW_LONG,
                CandleSettingType.NEAR,
            )
        ),
        _keys(
            CandleSettingType.BODY_DOJI,
            CandleSettingType.SHADOW_LONG,
            CandleSettingType.NEAR,
        ),
        _rickshaw_man,
    ),
    TalibPatternPort(
        "pat_dragonfly_doji",
        "CDLDRAGONFLYDOJI",
        _lookback((CandleSettingType.BODY_DOJI, CandleSettingType.SHADOW_VERY_SHORT)),
        _keys(CandleSettingType.BODY_DOJI, CandleSettingType.SHADOW_VERY_SHORT),
        _dragonfly_doji,
    ),
    TalibPatternPort(
        "pat_gravestone_doji",
        "CDLGRAVESTONEDOJI",
        _lookback((CandleSettingType.BODY_DOJI, CandleSettingType.SHADOW_VERY_SHORT)),
        _keys(CandleSettingType.BODY_DOJI, CandleSettingType.SHADOW_VERY_SHORT),
        _gravestone_doji,
    ),
    TalibPatternPort(
        "pat_takuri",
        "CDLTAKURI",
        _lookback(
            (
                CandleSettingType.BODY_DOJI,
                CandleSettingType.SHADOW_VERY_SHORT,
                CandleSettingType.SHADOW_VERY_LONG,
            )
        ),
        _keys(
            CandleSettingType.BODY_DOJI,
            CandleSettingType.SHADOW_VERY_SHORT,
            CandleSettingType.SHADOW_VERY_LONG,
        ),
        _takuri,
    ),
    TalibPatternPort(
        "pat_hammer",
        "CDLHAMMER",
        _lookback(
            (
                CandleSettingType.BODY_SHORT,
                CandleSettingType.SHADOW_LONG,
                CandleSettingType.SHADOW_VERY_SHORT,
                CandleSettingType.NEAR,
            ),
            extra_bars=1,
        ),
        (
            *_keys(
                CandleSettingType.BODY_SHORT,
                CandleSettingType.SHADOW_LONG,
                CandleSettingType.SHADOW_VERY_SHORT,
            ),
            *_keys(CandleSettingType.NEAR, offset=_PREVIOUS),
        ),
        _hammer,
    ),
    TalibPatternPort(
        "pat_hanging_man",
        "CDLHANGINGMAN",
        _lookback(
            (
                CandleSettingType.BODY_SHORT,
                CandleSettingType.SHADOW_LONG,
                CandleSettingType.SHADOW_VERY_SHORT,
                CandleSettingType.NEAR,
            ),
            extra_bars=1,
        ),
        (
            *_keys(
                CandleSettingType.BODY_SHORT,
                CandleSettingType.SHADOW_LONG,
                CandleSettingType.SHADOW_VERY_SHORT,
            ),
            *_keys(CandleSettingType.NEAR, offset=_PREVIOUS),
        ),
        _hanging_man,
    ),
    TalibPatternPort(
        "pat_inverted_hammer",
        "CDLINVERTEDHAMMER",
        _lookback(
            (
                CandleSettingType.BODY_SHORT,
                CandleSettingType.SHADOW_LONG,
                CandleSettingType.SHADOW_VERY_SHORT,
            ),
            extra_bars=1,
        ),
        _keys(
            CandleSettingType.BODY_SHORT,
            CandleSettingType.SHADOW_LONG,
            CandleSettingType.SHADOW_VERY_SHORT,
        ),
        _inverted_hammer,
    ),
    TalibPatternPort(
        "pat_shooting_star",
        "CDLSHOOTINGSTAR",
        _lookback(
            (
                CandleSettingType.BODY_SHORT,
                CandleSettingType.SHADOW_LONG,
                CandleSettingType.SHADOW_VERY_SHORT,
            ),
            extra_bars=1,
        ),
        _keys(
            CandleSettingType.BODY_SHORT,
            CandleSettingType.SHADOW_LONG,
            CandleSettingType.SHADOW_VERY_SHORT,
        ),
        _shooting_star,
    ),
    TalibPatternPort(
        "pat_spinning_top",
        "CDLSPINNINGTOP",
        _lookback((CandleSettingType.BODY_SHORT,)),
        _keys(CandleSettingType.BODY_SHORT),
        _spinning_top,
    ),
    TalibPatternPort(
        "pat_high_wave",
        "CDLHIGHWAVE",
        _lookback((CandleSettingType.BODY_SHORT, CandleSettingType.SHADOW_VERY_LONG)),
        _keys(CandleSettingType.BODY_SHORT, CandleSettingType.SHADOW_VERY_LONG),
        _high_wave,
    ),
    TalibPatternPort(
        "pat_marubozu",
        "CDLMARUBOZU",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.SHADOW_VERY_SHORT)),
        _keys(CandleSettingType.BODY_LONG, CandleSettingType.SHADOW_VERY_SHORT),
        _marubozu,
    ),
    TalibPatternPort(
        "pat_closing_marubozu",
        "CDLCLOSINGMARUBOZU",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.SHADOW_VERY_SHORT)),
        _keys(CandleSettingType.BODY_LONG, CandleSettingType.SHADOW_VERY_SHORT),
        _closing_marubozu,
    ),
    TalibPatternPort(
        "pat_belt_hold",
        "CDLBELTHOLD",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.SHADOW_VERY_SHORT)),
        _keys(CandleSettingType.BODY_LONG, CandleSettingType.SHADOW_VERY_SHORT),
        _belt_hold,
    ),
    TalibPatternPort(
        "pat_long_line",
        "CDLLONGLINE",
        _lookback((CandleSettingType.BODY_LONG, CandleSettingType.SHADOW_SHORT)),
        _keys(CandleSettingType.BODY_LONG, CandleSettingType.SHADOW_SHORT),
        _long_line,
    ),
    TalibPatternPort(
        "pat_short_line",
        "CDLSHORTLINE",
        _lookback((CandleSettingType.BODY_SHORT, CandleSettingType.SHADOW_SHORT)),
        _keys(CandleSettingType.BODY_SHORT, CandleSettingType.SHADOW_SHORT),
        _short_line,
    ),
)

TALIB_SINGLE_CANDLE_BY_NAME: Mapping[str, TalibPatternPort] = {
    pattern.name: pattern for pattern in TALIB_SINGLE_CANDLE_PATTERNS
}


def compute_talib_single_candle_patterns(
    candles: Sequence[Candle],
) -> dict[str, PatternSeries]:
    """Compute all ported single-candle TA-Lib patterns."""
    return {
        pattern.name: pattern.compute_vectorized(candles)
        for pattern in TALIB_SINGLE_CANDLE_PATTERNS
    }


__all__ = [
    "TALIB_SINGLE_CANDLE_BY_NAME",
    "TALIB_SINGLE_CANDLE_PATTERNS",
    "TALIB_SOURCE_VERSION",
    "TalibPatternPort",
    "compute_talib_single_candle_patterns",
    "sparse_talib_integer_signals",
    "talib_integer_from_outputs",
]
