"""Registration list owned by §7.1, the doji family and the umbrella lines."""

from core_lib.patterns import doji_umbrella
from core_lib.patterns.judgment import spec_for
from core_lib.patterns.registry import PatternSpec

SPECS: tuple[PatternSpec, ...] = tuple(
    spec_for(rule)
    for rule in (
        doji_umbrella.DOJI,
        doji_umbrella.LONG_LEGGED_DOJI,
        doji_umbrella.RICKSHAW_MAN,
        doji_umbrella.DRAGONFLY_DOJI,
        doji_umbrella.GRAVESTONE_DOJI,
        doji_umbrella.TAKURI,
        doji_umbrella.HAMMER,
        doji_umbrella.HANGING_MAN,
        doji_umbrella.INVERTED_HAMMER,
        doji_umbrella.SHOOTING_STAR,
        doji_umbrella.SPINNING_TOP,
    )
)
