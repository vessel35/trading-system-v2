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

Four modules are listed today, holding §7.1's eleven patterns, §7.2's six,
§7.3's sixteen, and §7.4's eighteen. §7.5 adds one more module and ten more
patterns; the registry itself does not change when they arrive.

The one departure from the indicator package is that the built registry lives
here rather than in `registry.py`. The dependency runs the other way for
patterns: a pattern's spec is assembled from its judgment rule, so the group
modules import `judgment.py`, which imports `registry.py`. Building the default
registry inside `registry.py` would close that into a cycle, and this package is
the first point above the group modules where nothing is left half-imported.
"""

from collections.abc import Mapping
from types import MappingProxyType

from core_lib.patterns.registry import PatternRegistry, PatternSpec

from . import body_shadow, doji_umbrella, three_candle, two_candle

GROUP_SPECS: Mapping[str, tuple[PatternSpec, ...]] = MappingProxyType(
    {
        "doji_umbrella": doji_umbrella.SPECS,
        "body_shadow": body_shadow.SPECS,
        "two_candle": two_candle.SPECS,
        "three_candle": three_candle.SPECS,
    }
)

GROUPS: tuple[str, ...] = tuple(GROUP_SPECS)


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
