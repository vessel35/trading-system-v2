"""Registration list owned by §7.5, the long forms and the gap continuations."""

from core_lib.patterns import long_and_gap
from core_lib.patterns.judgment import spec_for
from core_lib.patterns.registry import PatternSpec

SPECS: tuple[PatternSpec, ...] = tuple(
    spec_for(rule)
    for rule in (
        long_and_gap.THREE_LINE_STRIKE,
        long_and_gap.BREAKAWAY,
        long_and_gap.LADDER_BOTTOM,
        long_and_gap.MAT_HOLD,
        long_and_gap.RISE_FALL_THREE_METHODS,
        long_and_gap.GAP_SIDE_BY_SIDE_WHITE,
        long_and_gap.TASUKI_GAP,
        long_and_gap.GAP_THREE_METHODS,
        long_and_gap.HIKKAKE,
        long_and_gap.HIKKAKE_MODIFIED,
    )
)
