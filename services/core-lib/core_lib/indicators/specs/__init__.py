"""Gather the six category-owned registration lists into one fixed sequence.

Every category owns exactly one module in this package and one calculation module
beside `registry.py`, so adding an indicator touches those two files and nothing
else. This package is the only place that names the six categories; `registry.py`
gathers whatever they hold without knowing what is in them, which is what keeps the
registry itself unchanged as the catalog grows.

The gathering is deliberately a written-out list rather than a directory scan. A
scan would let a module disappear from the build without anything failing, while a
missing name here is an import error at the first use of the registry.
"""

from collections.abc import Mapping
from types import MappingProxyType

from core_lib.indicators.registry import IndicatorSpec

from . import momentum, strength, systems, trend, volatility, volume

CATEGORY_SPECS: Mapping[str, tuple[IndicatorSpec, ...]] = MappingProxyType(
    {
        "trend": trend.SPECS,
        "momentum": momentum.SPECS,
        "volatility": volatility.SPECS,
        "volume": volume.SPECS,
        "strength": strength.SPECS,
        "systems": systems.SPECS,
    }
)

CATEGORIES: tuple[str, ...] = tuple(CATEGORY_SPECS)


def _reject_misfiled_specs() -> None:
    """Refuse a spec registered from a module that does not own its category.

    File ownership is the whole point of the split, and a spec whose `category`
    disagrees with the module holding it silently hands one person's indicator to
    another person's file. Checking at import makes that a startup failure rather
    than a merge conflict discovered later.
    """
    misfiled = [
        f"{spec.identifier} declares {spec.category!r} but lives in {category!r}"
        for category, specs in CATEGORY_SPECS.items()
        for spec in specs
        if spec.category != category
    ]
    if misfiled:
        raise ValueError("; ".join(misfiled))


_reject_misfiled_specs()


def all_specs() -> tuple[IndicatorSpec, ...]:
    """Return every registered spec, one category after another in a fixed order."""
    return tuple(spec for specs in CATEGORY_SPECS.values() for spec in specs)
