"""Registration list owned by §7.2, the body-and-shadow shapes."""

from core_lib.patterns import body_shadow
from core_lib.patterns.judgment import spec_for
from core_lib.patterns.registry import PatternSpec

SPECS: tuple[PatternSpec, ...] = tuple(
    spec_for(rule)
    for rule in (
        body_shadow.HIGH_WAVE,
        body_shadow.MARUBOZU,
        body_shadow.CLOSING_MARUBOZU,
        body_shadow.BELT_HOLD,
        body_shadow.LONG_LINE,
        body_shadow.SHORT_LINE,
    )
)
