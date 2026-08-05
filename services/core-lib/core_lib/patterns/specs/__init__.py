"""Gather the group-owned registration lists into one fixed sequence.

`core_lib.indicators.specs` does the same job for the eighty-nine indicators and
this package copies its arrangement deliberately: one module per group of §7, one
calculation module beside it, so adding a pattern touches two files and no one
else's. The groups are §7's own subsections, which is why they are named after
shapes rather than after anything this package invented.

The gathering is a written-out list rather than a directory scan, for the reason
the indicator package gives: a scan lets a module vanish from the build with
nothing failing, while a missing name here is an import error the first time the
registry is used.

Five modules are listed, holding §7.1's eleven patterns, §7.2's six, §7.3's
sixteen, §7.4's eighteen, and §7.5's ten. That is the standard's whole catalog of
sixty-one, and the registry itself did not change as the groups arrived.

The one departure from the indicator package is that the built registry lives
here rather than in `registry.py`. The dependency runs the other way for
patterns: a pattern's spec is assembled from its judgment rule, so the group
modules import `judgment.py`, which imports `registry.py`. Building the default
registry inside `registry.py` would close that into a cycle, and this package is
the first point above the group modules where nothing is left half-imported.

Section numbers in this module are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Final, Protocol, cast

from core_lib.patterns.registry import PatternRegistry, PatternSeries, PatternSpec, PatternState
from core_lib.patterns.talib_hikkake import TALIB_HIKKAKE_PATTERNS
from core_lib.patterns.talib_multi_candle import TALIB_MULTI_CANDLE_PATTERNS
from core_lib.patterns.talib_raw import TALIB_SOURCE_VERSION
from core_lib.patterns.talib_single_candle import TALIB_SINGLE_CANDLE_PATTERNS
from core_lib.patterns.talib_three_candle import TALIB_THREE_CANDLE_PATTERNS
from core_lib.patterns.talib_two_candle import TALIB_TWO_CANDLE_PATTERNS
from core_lib.types import Candle

from . import body_shadow, doji_umbrella, long_and_gap, three_candle, two_candle

TALIB_PATTERN_REGISTRY_VERSION: Final = f"2.0.0+talib.{TALIB_SOURCE_VERSION}"
"""Pattern calculation version for the TA-Lib v0.7.1 registry cutover."""


class _TalibRegistryPort(Protocol):
    name: str
    min_history: int

    def compute_vectorized(self, candles: Sequence[Candle]) -> PatternSeries: ...

    def make_state(self) -> PatternState: ...


GROUP_SPECS: Mapping[str, tuple[PatternSpec, ...]] = MappingProxyType(
    {
        "doji_umbrella": doji_umbrella.SPECS,
        "body_shadow": body_shadow.SPECS,
        "two_candle": two_candle.SPECS,
        "three_candle": three_candle.SPECS,
        "long_and_gap": long_and_gap.SPECS,
    }
)

GROUPS: tuple[str, ...] = tuple(GROUP_SPECS)

TALIB_GROUP_PORTS: Mapping[str, tuple[_TalibRegistryPort, ...]] = MappingProxyType(
    {
        "single_candle": cast(tuple[_TalibRegistryPort, ...], TALIB_SINGLE_CANDLE_PATTERNS),
        "two_candle": cast(tuple[_TalibRegistryPort, ...], TALIB_TWO_CANDLE_PATTERNS),
        "three_candle": cast(tuple[_TalibRegistryPort, ...], TALIB_THREE_CANDLE_PATTERNS),
        "multi_candle": cast(tuple[_TalibRegistryPort, ...], TALIB_MULTI_CANDLE_PATTERNS),
        "hikkake": cast(tuple[_TalibRegistryPort, ...], TALIB_HIKKAKE_PATTERNS),
    }
)
TALIB_GROUPS: tuple[str, ...] = tuple(TALIB_GROUP_PORTS)


def _reject_a_name_claimed_by_two_modules() -> None:
    """Refuse the same pattern registered from two group modules.

    `PatternRegistry.register` already rejects a duplicate identity, so this
    would surface anyway — but as a failure at first use with no indication of
    which two files disagree. Naming them at import is the difference between a
    merge conflict found now and one found later.
    """
    seen: dict[str, str] = {}
    collisions: list[str] = []
    for group, specs in GROUP_SPECS.items():
        for spec in specs:
            owner = seen.setdefault(spec.name, group)
            if owner != group:
                collisions.append(f"{spec.name} is registered from both {owner!r} and {group!r}")
    if collisions:
        raise ValueError("; ".join(collisions))


_reject_a_name_claimed_by_two_modules()


def all_specs() -> tuple[PatternSpec, ...]:
    """Return every registered pattern spec, one group after another in a fixed order."""
    return tuple(spec for specs in GROUP_SPECS.values() for spec in specs)


def _talib_spec_for(port: _TalibRegistryPort) -> PatternSpec:
    """Adapt one TA-Lib port to the shared seven-member consumption contract."""
    return PatternSpec(
        name=port.name,
        params={},
        version=TALIB_PATTERN_REGISTRY_VERSION,
        _vectorized=port.compute_vectorized,
        _state_factory=port.make_state,
        explicit_min_history=port.min_history,
    )


def talib_all_specs() -> tuple[PatternSpec, ...]:
    """Return every TA-Lib registered pattern spec in a fixed group order."""
    return tuple(_talib_spec_for(port) for ports in TALIB_GROUP_PORTS.values() for port in ports)


def build_default_pattern_registry() -> PatternRegistry:
    """Build the registry by gathering every group's registration list.

    Registration is where §6's warm-up length is checked against the state that
    will report itself warmed up, so this loop is not merely bookkeeping: a rule
    whose span and trend requirement disagree with its state fails here, at
    import, rather than at the first bar of a run.
    """
    registry = PatternRegistry()
    for spec in all_specs():
        registry.register(spec)
    return registry


DEFAULT_PATTERN_REGISTRY = build_default_pattern_registry()
"""The registered patterns.

Named apart from the indicators' `DEFAULT_REGISTRY` on purpose. The two are
separate objects holding separate catalogs, and decision G keeps their name sets
disjoint; one shared name for the two registries would invite exactly the
confusion that decision exists to prevent. Nothing here reaches the indicator
registry, so the indicator standard's tally of 89 systems does not move.
"""

LEGACY_PATTERN_REGISTRY = DEFAULT_PATTERN_REGISTRY
"""The legacy pattern-standard registry kept alive until the 5b cleanup."""


def build_talib_pattern_registry() -> PatternRegistry:
    """Build the TA-Lib-backed registry used by runtime consumers."""
    registry = PatternRegistry()
    for spec in talib_all_specs():
        registry.register(spec)
    return registry


TALIB_PATTERN_REGISTRY = build_talib_pattern_registry()
"""The TA-Lib v0.7.1 pattern registry used by the public package default."""
