"""TA-Lib candlestick settings and candle-average primitives.

This module ports the shared foundation used by TA-Lib's ``TA_CDL*`` functions:

- default candle settings from ``src/ta_common/ta_global.c``
- ``TA_CANDLERANGE`` and ``TA_CANDLEAVERAGE`` from ``src/ta_func/ta_utility.h``
- the common lookback shape used by the candlestick lookback functions

The pattern decisions themselves stay in the existing modules until the TA-Lib
decision code is ported pattern by pattern.
"""

from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from math import fabs
from types import MappingProxyType

from core_lib.types import Candle


class CandleRangeType(StrEnum):
    """TA-Lib ``TA_RangeType`` values used by candle settings."""

    REAL_BODY = "RealBody"
    HIGH_LOW = "HighLow"
    SHADOWS = "Shadows"


class CandleSettingType(StrEnum):
    """The eleven TA-Lib candle setting types used by ``TA_CDL*`` functions."""

    BODY_LONG = "BodyLong"
    BODY_VERY_LONG = "BodyVeryLong"
    BODY_SHORT = "BodyShort"
    BODY_DOJI = "BodyDoji"
    SHADOW_LONG = "ShadowLong"
    SHADOW_VERY_LONG = "ShadowVeryLong"
    SHADOW_SHORT = "ShadowShort"
    SHADOW_VERY_SHORT = "ShadowVeryShort"
    NEAR = "Near"
    FAR = "Far"
    EQUAL = "Equal"


@dataclass(frozen=True, slots=True)
class CandleSetting:
    """One TA-Lib candle setting entry from ``TA_CandleDefaultSettings``."""

    setting_type: CandleSettingType
    range_type: CandleRangeType
    avg_period: int
    factor: float


CandleSettings = Mapping[CandleSettingType, CandleSetting]

CANDLE_SETTING_ORDER: tuple[CandleSettingType, ...] = (
    CandleSettingType.BODY_LONG,
    CandleSettingType.BODY_VERY_LONG,
    CandleSettingType.BODY_SHORT,
    CandleSettingType.BODY_DOJI,
    CandleSettingType.SHADOW_LONG,
    CandleSettingType.SHADOW_VERY_LONG,
    CandleSettingType.SHADOW_SHORT,
    CandleSettingType.SHADOW_VERY_SHORT,
    CandleSettingType.NEAR,
    CandleSettingType.FAR,
    CandleSettingType.EQUAL,
)
"""TA-Lib's default setting order from ``TA_CandleDefaultSettings``."""

_DEFAULT_CANDLE_SETTINGS: dict[CandleSettingType, CandleSetting] = {
    CandleSettingType.BODY_LONG: CandleSetting(
        CandleSettingType.BODY_LONG,
        CandleRangeType.REAL_BODY,
        10,
        1.0,
    ),
    CandleSettingType.BODY_VERY_LONG: CandleSetting(
        CandleSettingType.BODY_VERY_LONG,
        CandleRangeType.REAL_BODY,
        10,
        3.0,
    ),
    CandleSettingType.BODY_SHORT: CandleSetting(
        CandleSettingType.BODY_SHORT,
        CandleRangeType.REAL_BODY,
        10,
        1.0,
    ),
    CandleSettingType.BODY_DOJI: CandleSetting(
        CandleSettingType.BODY_DOJI,
        CandleRangeType.HIGH_LOW,
        10,
        0.1,
    ),
    CandleSettingType.SHADOW_LONG: CandleSetting(
        CandleSettingType.SHADOW_LONG,
        CandleRangeType.REAL_BODY,
        0,
        1.0,
    ),
    CandleSettingType.SHADOW_VERY_LONG: CandleSetting(
        CandleSettingType.SHADOW_VERY_LONG,
        CandleRangeType.REAL_BODY,
        0,
        2.0,
    ),
    CandleSettingType.SHADOW_SHORT: CandleSetting(
        CandleSettingType.SHADOW_SHORT,
        CandleRangeType.SHADOWS,
        10,
        1.0,
    ),
    CandleSettingType.SHADOW_VERY_SHORT: CandleSetting(
        CandleSettingType.SHADOW_VERY_SHORT,
        CandleRangeType.HIGH_LOW,
        10,
        0.1,
    ),
    CandleSettingType.NEAR: CandleSetting(
        CandleSettingType.NEAR,
        CandleRangeType.HIGH_LOW,
        5,
        0.2,
    ),
    CandleSettingType.FAR: CandleSetting(
        CandleSettingType.FAR,
        CandleRangeType.HIGH_LOW,
        5,
        0.6,
    ),
    CandleSettingType.EQUAL: CandleSetting(
        CandleSettingType.EQUAL,
        CandleRangeType.HIGH_LOW,
        5,
        0.05,
    ),
}

DEFAULT_CANDLE_SETTINGS: CandleSettings = MappingProxyType(_DEFAULT_CANDLE_SETTINGS)
"""TA-Lib default candle settings from ``ta_global.c``."""


def default_candle_settings() -> CandleSettings:
    """Return the immutable TA-Lib default candle settings mapping."""
    return DEFAULT_CANDLE_SETTINGS


def real_body(candle: Candle) -> float:
    """Return ``TA_REALBODY(IDX)`` for one candle."""
    return fabs(candle.close - candle.open)


def real_body_bottom(candle: Candle) -> float:
    """Return ``min(inOpen[IDX], inClose[IDX])`` for one candle."""
    return min(candle.open, candle.close)


def real_body_top(candle: Candle) -> float:
    """Return ``max(inOpen[IDX], inClose[IDX])`` for one candle."""
    return max(candle.open, candle.close)


def upper_shadow(candle: Candle) -> float:
    """Return ``TA_UPPERSHADOW(IDX)`` for one candle."""
    body_top = candle.close if candle.close >= candle.open else candle.open
    return candle.high - body_top


def lower_shadow(candle: Candle) -> float:
    """Return ``TA_LOWERSHADOW(IDX)`` for one candle."""
    body_bottom = candle.open if candle.close >= candle.open else candle.close
    return body_bottom - candle.low


def high_low_range(candle: Candle) -> float:
    """Return ``TA_HIGHLOWRANGE(IDX)`` for one candle."""
    return candle.high - candle.low


def candle_color(candle: Candle) -> int:
    """Return ``TA_CANDLECOLOR(IDX)``: ``1`` for close >= open, else ``-1``."""
    return 1 if candle.close >= candle.open else -1


def real_body_gap_up(candle2: Candle, candle1: Candle) -> bool:
    """Return ``TA_REALBODYGAPUP(IDX2, IDX1)``."""
    return real_body_bottom(candle2) > real_body_top(candle1)


def real_body_gap_down(candle2: Candle, candle1: Candle) -> bool:
    """Return ``TA_REALBODYGAPDOWN(IDX2, IDX1)``."""
    return real_body_top(candle2) < real_body_bottom(candle1)


def candle_gap_up(candle2: Candle, candle1: Candle) -> bool:
    """Return ``TA_CANDLEGAPUP(IDX2, IDX1)``."""
    return candle2.low > candle1.high


def candle_gap_down(candle2: Candle, candle1: Candle) -> bool:
    """Return ``TA_CANDLEGAPDOWN(IDX2, IDX1)``."""
    return candle2.high < candle1.low


def candle_range(
    setting_type: CandleSettingType,
    candle: Candle,
    settings: CandleSettings = DEFAULT_CANDLE_SETTINGS,
) -> float:
    """Return ``TA_CANDLERANGE(SET, IDX)``."""
    range_type = settings[setting_type].range_type
    if range_type == CandleRangeType.REAL_BODY:
        return real_body(candle)
    if range_type == CandleRangeType.HIGH_LOW:
        return high_low_range(candle)
    if range_type == CandleRangeType.SHADOWS:
        return upper_shadow(candle) + lower_shadow(candle)


def candle_average(
    setting_type: CandleSettingType,
    period_total: float,
    candle: Candle,
    settings: CandleSettings = DEFAULT_CANDLE_SETTINGS,
) -> float:
    """Return ``TA_CANDLEAVERAGE(SET, SUM, IDX)``."""
    setting = settings[setting_type]
    average = (
        period_total / setting.avg_period
        if setting.avg_period != 0
        else candle_range(setting_type, candle, settings)
    )
    divisor = 2.0 if setting.range_type == CandleRangeType.SHADOWS else 1.0
    return setting.factor * average / divisor


def candle_period_total_at(
    setting_type: CandleSettingType,
    candles: Sequence[Candle],
    target_index: int,
    settings: CandleSettings = DEFAULT_CANDLE_SETTINGS,
) -> float:
    """Return the previous-period range total used for one target candle."""
    if target_index < 0 or target_index >= len(candles):
        raise IndexError("target_index is outside candles")

    avg_period = settings[setting_type].avg_period
    if avg_period == 0:
        return 0.0
    if target_index < avg_period:
        raise ValueError("not enough candles before target_index")

    period_total = 0.0
    trailing_index = target_index - avg_period
    index = trailing_index
    while index < target_index:
        period_total += candle_range(setting_type, candles[index], settings)
        index += 1
    return period_total


def candle_average_at(
    setting_type: CandleSettingType,
    candles: Sequence[Candle],
    target_index: int,
    settings: CandleSettings = DEFAULT_CANDLE_SETTINGS,
) -> float:
    """Return ``TA_CANDLEAVERAGE`` for one target candle."""
    period_total = candle_period_total_at(setting_type, candles, target_index, settings)
    return candle_average(setting_type, period_total, candles[target_index], settings)


def candle_average_series(
    setting_type: CandleSettingType,
    candles: Sequence[Candle],
    *,
    target_offset: int = 0,
    settings: CandleSettings = DEFAULT_CANDLE_SETTINGS,
) -> list[float | None]:
    """Return TA-Lib candle averages aligned to each current candle.

    ``target_offset`` is the distance from the current pattern candle to the
    candle whose average is requested. For example, TA-Lib calls
    ``TA_CANDLEAVERAGE(Near, NearPeriodTotal, i - 1)`` with ``target_offset=1``.
    Entries that TA-Lib could not evaluate yet are ``None``.
    """
    if target_offset < 0:
        raise ValueError("target_offset must not be negative")

    values: list[float | None] = [None] * len(candles)
    avg_period = settings[setting_type].avg_period
    first_current_index = avg_period + target_offset
    if first_current_index >= len(candles):
        return values

    if avg_period == 0:
        for current_index in range(target_offset, len(candles)):
            target_index = current_index - target_offset
            values[current_index] = candle_average(
                setting_type,
                0.0,
                candles[target_index],
                settings,
            )
        return values

    period_total = 0.0
    target_index = first_current_index - target_offset
    trailing_index = target_index - avg_period
    index = trailing_index
    while index < target_index:
        period_total += candle_range(setting_type, candles[index], settings)
        index += 1

    for current_index in range(first_current_index, len(candles)):
        target_index = current_index - target_offset
        values[current_index] = candle_average(
            setting_type,
            period_total,
            candles[target_index],
            settings,
        )
        period_total += candle_range(setting_type, candles[target_index], settings) - candle_range(
            setting_type,
            candles[trailing_index],
            settings,
        )
        trailing_index += 1
    return values


def candle_settings_lookback(
    setting_types: Iterable[CandleSettingType],
    *,
    extra_bars: int = 0,
    minimum: int = 0,
    settings: CandleSettings = DEFAULT_CANDLE_SETTINGS,
) -> int:
    """Return the TA-Lib ``TA_CDL*_Lookback`` value for candle settings.

    TA-Lib lookbacks take the maximum average period among the settings used by
    a pattern, then add the number of extra prior bars the pattern reads. Some
    patterns with no settings are pure constants, and ``minimum`` covers the
    ``max(1, Near_avgPeriod)`` form used by ``CDLHIKKAKEMOD``.
    """
    if extra_bars < 0:
        raise ValueError("extra_bars must not be negative")
    if minimum < 0:
        raise ValueError("minimum must not be negative")

    avg_periods = [settings[setting_type].avg_period for setting_type in setting_types]
    return max([minimum, *avg_periods]) + extra_bars


def candle_settings_min_history(
    setting_types: Iterable[CandleSettingType],
    *,
    extra_bars: int = 0,
    minimum: int = 0,
    settings: CandleSettings = DEFAULT_CANDLE_SETTINGS,
) -> int:
    """Return candle count required before the first finite output."""
    return (
        candle_settings_lookback(
            setting_types,
            extra_bars=extra_bars,
            minimum=minimum,
            settings=settings,
        )
        + 1
    )


@dataclass(slots=True)
class CandleAverageState:
    """Incrementally maintain one TA-Lib candle-average moving total."""

    setting_type: CandleSettingType
    target_offset: int = 0
    settings: CandleSettings = field(default_factory=default_candle_settings)
    _seen: int = field(init=False, default=0, repr=False)
    _period_total: float = field(init=False, default=0.0, repr=False)
    _current: float | None = field(init=False, default=None, repr=False)
    _range_buffer: deque[float] = field(init=False, repr=False)
    _candle_buffer: deque[Candle] = field(init=False, repr=False)
    _first_range_index: int = field(init=False, default=0, repr=False)
    _first_candle_index: int = field(init=False, default=0, repr=False)
    _max_range_buffer_length: int = field(init=False, repr=False)
    _max_candle_buffer_length: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.target_offset < 0:
            raise ValueError("target_offset must not be negative")
        avg_period = self.settings[self.setting_type].avg_period
        self._max_range_buffer_length = max(1, avg_period + self.target_offset + 2)
        self._max_candle_buffer_length = self.target_offset + 1
        self._range_buffer = deque()
        self._candle_buffer = deque()

    @property
    def warmed_up(self) -> bool:
        """Return whether the current candle can produce an average."""
        target_index = self._seen - 1 - self.target_offset
        return target_index >= self.settings[self.setting_type].avg_period

    @property
    def period_total(self) -> float:
        """Return the moving sum currently feeding ``TA_CANDLEAVERAGE``."""
        return self._period_total

    def reset(self) -> None:
        """Clear the moving total and buffered candle ranges."""
        self._seen = 0
        self._period_total = 0.0
        self._current = None
        self._range_buffer.clear()
        self._candle_buffer.clear()
        self._first_range_index = 0
        self._first_candle_index = 0

    def seed(self, candles: Sequence[Candle]) -> None:
        """Reset and replay existing candles in order."""
        self.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> float | None:
        """Advance by one confirmed candle and return the aligned average."""
        candle_index = self._seen
        self._seen += 1
        self._append_range(candle_index, candle_range(self.setting_type, candle, self.settings))
        self._append_candle(candle_index, candle)

        avg_period = self.settings[self.setting_type].avg_period
        target_index = candle_index - self.target_offset
        if avg_period == 0:
            if target_index < 0:
                self._current = None
                return self._current
            self._current = candle_average(
                self.setting_type,
                0.0,
                self._candle_at(target_index),
                self.settings,
            )
            return self._current

        add_index = target_index - 1
        subtract_index = target_index - avg_period - 1
        if add_index >= 0:
            added = self._range_at(add_index)
            if subtract_index >= 0:
                self._period_total += added - self._range_at(subtract_index)
            else:
                self._period_total += added

        if target_index < avg_period:
            self._current = None
            return self._current

        self._current = candle_average(
            self.setting_type,
            self._period_total,
            self._candle_at(target_index),
            self.settings,
        )
        return self._current

    def current(self) -> float | None:
        """Return the most recently produced aligned average."""
        return self._current

    def _append_range(self, index: int, value: float) -> None:
        self._range_buffer.append(value)
        if len(self._range_buffer) > self._max_range_buffer_length:
            self._range_buffer.popleft()
            self._first_range_index += 1

    def _append_candle(self, index: int, candle: Candle) -> None:
        self._candle_buffer.append(candle)
        if len(self._candle_buffer) > self._max_candle_buffer_length:
            self._candle_buffer.popleft()
            self._first_candle_index += 1

    def _range_at(self, index: int) -> float:
        position = index - self._first_range_index
        if position < 0 or position >= len(self._range_buffer):
            raise IndexError("range buffer does not hold requested index")
        return self._range_buffer[position]

    def _candle_at(self, index: int) -> Candle:
        position = index - self._first_candle_index
        if position < 0 or position >= len(self._candle_buffer):
            raise IndexError("candle buffer does not hold requested index")
        return self._candle_buffer[position]


__all__ = [
    "CANDLE_SETTING_ORDER",
    "DEFAULT_CANDLE_SETTINGS",
    "CandleAverageState",
    "CandleRangeType",
    "CandleSetting",
    "CandleSettingType",
    "CandleSettings",
    "candle_average",
    "candle_average_at",
    "candle_average_series",
    "candle_color",
    "candle_gap_down",
    "candle_gap_up",
    "candle_period_total_at",
    "candle_range",
    "candle_settings_lookback",
    "candle_settings_min_history",
    "default_candle_settings",
    "high_low_range",
    "lower_shadow",
    "real_body",
    "real_body_bottom",
    "real_body_gap_down",
    "real_body_gap_up",
    "real_body_top",
    "upper_shadow",
]
