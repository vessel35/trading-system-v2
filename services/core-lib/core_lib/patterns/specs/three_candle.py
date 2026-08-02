"""Registration list owned by §7.4, the three-bar patterns."""

from core_lib.patterns import three_candle
from core_lib.patterns.judgment import spec_for
from core_lib.patterns.registry import PatternSpec

SPECS: tuple[PatternSpec, ...] = tuple(
    spec_for(rule)
    for rule in (
        three_candle.MORNING_STAR,
        three_candle.EVENING_STAR,
        three_candle.MORNING_DOJI_STAR,
        three_candle.EVENING_DOJI_STAR,
        three_candle.ABANDONED_BABY,
        three_candle.TRI_STAR,
        three_candle.TWO_CROWS,
        three_candle.UPSIDE_GAP_TWO_CROWS,
        three_candle.THREE_WHITE_SOLDIERS,
        three_candle.THREE_BLACK_CROWS,
        three_candle.IDENTICAL_THREE_CROWS,
        three_candle.ADVANCE_BLOCK,
        three_candle.STALLED_PATTERN,
        three_candle.THREE_STARS_IN_THE_SOUTH,
        three_candle.THREE_INSIDE,
        three_candle.THREE_OUTSIDE,
        three_candle.UNIQUE_THREE_RIVER,
        three_candle.CONCEALING_BABY_SWALLOW,
    )
)
