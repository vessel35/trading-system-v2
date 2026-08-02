"""Registration list owned by §7.3, the two-bar patterns and what joins them."""

from core_lib.patterns import two_candle
from core_lib.patterns.judgment import spec_for
from core_lib.patterns.registry import PatternSpec

SPECS: tuple[PatternSpec, ...] = tuple(
    spec_for(rule)
    for rule in (
        two_candle.ENGULFING,
        two_candle.HARAMI,
        two_candle.HARAMI_CROSS,
        two_candle.DOJI_STAR,
        two_candle.PIERCING,
        two_candle.DARK_CLOUD_COVER,
        two_candle.COUNTERATTACK,
        two_candle.SEPARATING_LINES,
        two_candle.KICKING,
        two_candle.KICKING_BY_LENGTH,
        two_candle.HOMING_PIGEON,
        two_candle.MATCHING_LOW,
        two_candle.IN_NECK,
        two_candle.ON_NECK,
        two_candle.THRUSTING,
        two_candle.STICK_SANDWICH,
    )
)
