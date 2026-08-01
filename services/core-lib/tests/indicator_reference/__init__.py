"""What the tests expect of each indicator category, one module per category.

Two kinds of statement live here, and both are written by hand rather than read back
from the code they check.

The first is what a category registers: its combination identifiers, its indicator
names, how many of the standard's 89 systems those registrations account for, and any
output the standard itself leaves undefined. A pin that derived those from the registry
would agree with any registry, so `test_indicator_registry.py` compares the merged
hand-written statement against the live registry and fails on a silent addition or
removal either way.

The second is what an outside implementation produces. The parity tests prove our two
execution paths agree, and the relation tests prove each indicator satisfies a property
its standard section states separately. Neither can catch a formula we transcribed
wrongly in both paths. The calculation standard carries no worked numbers of its own
(its §12 defers them), so the values here come from **TA-Lib 0.7.1**, which §13 of the
standard names as a cross-check target, with Tulip Indicators 0.4.0 and ta 0.11.0
filling in what TA-Lib does not implement. Every entry that is not TA-Lib says so in a
comment beside it.

Those numbers were produced once, offline, in a throwaway environment and frozen here.
Nothing in this repository depends on TA-Lib at run time or in continuous integration;
regenerating them needs that environment again, and the generator is described in
`docs/roadmap-stage-3-0-plan.md`.

TA-Lib is a comparison, never a source. Where a value disagrees, the standard decides
who is wrong, and the documented disagreements are seed-window conventions the standard
itself describes rather than errors in either implementation.

Each category owns one module here, so two people adding indicators to different
categories never edit the same file. This module merges the six and is the only place
that names them. Leaving a category out of the merge takes both of its statements with
it, and the tests refuse to pass on the shorter list: the registry comparison sees a
registered combination nobody expected, and the outside comparison sees a registered
output nobody covered.
"""

from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import NamedTuple, Protocol

from . import momentum, strength, systems, trend, volatility, volume
from .series import CONVERGENCE_NOISE_FLOOR, SAMPLE_INDICES, reference_candles

__all__ = [
    "CATEGORY_DATA",
    "CONVERGENCE_NOISE_FLOOR",
    "CONVERGING",
    "COVERED_CATEGORIES",
    "REFERENCE",
    "REGISTERED_IDENTIFIERS",
    "REGISTERED_NAMES",
    "REGISTERED_STANDARD_SYSTEMS",
    "SAMPLE_INDICES",
    "UNCOMPARED",
    "UNDEFINED_OUTPUTS",
    "reference_candles",
]

ReferenceValues = dict[str, dict[int, float]]
ConvergingValues = dict[str, tuple[dict[int, float], dict[int, float]]]
UncomparedReasons = dict[str, str]
UndefinedOutputs = dict[str, tuple[str, ...]]


class CategoryModule(Protocol):
    """Everything one category's module has to declare for the merge to work.

    Owners read this as the checklist for their own file. A module missing any of
    these names fails to satisfy the protocol, which mypy reports against the table
    below rather than leaving it to be discovered as a missing attribute at run time.
    """

    IDENTIFIERS: frozenset[str]
    NAMES: frozenset[str]
    STANDARD_SYSTEMS: int
    UNDEFINED_OUTPUTS: UndefinedOutputs
    REFERENCE: ReferenceValues
    CONVERGING: ConvergingValues
    UNCOMPARED: UncomparedReasons


class CategoryData(NamedTuple):
    """One category's statements, exactly as its module declares them."""

    identifiers: frozenset[str]
    names: frozenset[str]
    standard_systems: int
    undefined_outputs: UndefinedOutputs
    reference: ReferenceValues
    converging: ConvergingValues
    uncompared: UncomparedReasons


def _declared_by(module: CategoryModule) -> CategoryData:
    """Read one category module's declarations into the shape the merge uses."""
    return CategoryData(
        identifiers=module.IDENTIFIERS,
        names=module.NAMES,
        standard_systems=module.STANDARD_SYSTEMS,
        undefined_outputs=module.UNDEFINED_OUTPUTS,
        reference=module.REFERENCE,
        converging=module.CONVERGING,
        uncompared=module.UNCOMPARED,
    )


CATEGORY_DATA: Mapping[str, CategoryData] = MappingProxyType(
    {
        "trend": _declared_by(trend),
        "momentum": _declared_by(momentum),
        "volatility": _declared_by(volatility),
        "volume": _declared_by(volume),
        "strength": _declared_by(strength),
        "systems": _declared_by(systems),
    }
)

COVERED_CATEGORIES = frozenset(CATEGORY_DATA)


def _merge[Value](parts: Iterable[tuple[str, Mapping[str, Value]]]) -> dict[str, Value]:
    """Merge one table across categories, refusing an output claimed twice."""
    merged: dict[str, Value] = {}
    claimed_by: dict[str, str] = {}
    for category, part in parts:
        for output, value in part.items():
            if output in claimed_by:
                raise ValueError(f"{output} is claimed by both {claimed_by[output]} and {category}")
            claimed_by[output] = category
            merged[output] = value
    return merged


def _merge_disjoint(label: str, parts: Iterable[tuple[str, frozenset[str]]]) -> frozenset[str]:
    """Union one hand-written set across categories, refusing an entry claimed twice.

    An indicator belongs to exactly one category, so the same entry appearing in two
    modules means one of the two owners copied the other's line. Without this the
    union would absorb the duplicate and the registry comparison would still pass.
    """
    merged: set[str] = set()
    claimed_by: dict[str, str] = {}
    for category, part in parts:
        for entry in part:
            if entry in claimed_by:
                raise ValueError(
                    f"{label} {entry} is claimed by both {claimed_by[entry]} and {category}"
                )
            claimed_by[entry] = category
            merged.add(entry)
    return frozenset(merged)


REGISTERED_IDENTIFIERS = _merge_disjoint(
    "identifier",
    ((category, data.identifiers) for category, data in CATEGORY_DATA.items()),
)
REGISTERED_NAMES = _merge_disjoint(
    "name",
    ((category, data.names) for category, data in CATEGORY_DATA.items()),
)
REGISTERED_STANDARD_SYSTEMS = sum(data.standard_systems for data in CATEGORY_DATA.values())
UNDEFINED_OUTPUTS: UndefinedOutputs = _merge(
    (category, data.undefined_outputs) for category, data in CATEGORY_DATA.items()
)
REFERENCE: ReferenceValues = _merge(
    (category, data.reference) for category, data in CATEGORY_DATA.items()
)
CONVERGING: ConvergingValues = _merge(
    (category, data.converging) for category, data in CATEGORY_DATA.items()
)
UNCOMPARED: UncomparedReasons = _merge(
    (category, data.uncompared) for category, data in CATEGORY_DATA.items()
)


def _reject_outputs_in_two_tables() -> None:
    """Refuse an output that is compared and excused at the same time.

    The three comparison tables answer the same question in incompatible ways:
    matched exactly, converging from a different seed, or not compared at all. An
    output in two of them would make the suite report both answers and notice neither.
    """
    tables: tuple[tuple[str, frozenset[str]], ...] = (
        ("REFERENCE", frozenset(REFERENCE)),
        ("CONVERGING", frozenset(CONVERGING)),
        ("UNCOMPARED", frozenset(UNCOMPARED)),
    )
    overlaps = [
        f"{name} and {other_name} both hold {sorted(outputs & other_outputs)}"
        for index, (name, outputs) in enumerate(tables)
        for other_name, other_outputs in tables[index + 1 :]
        if outputs & other_outputs
    ]
    if overlaps:
        raise ValueError("; ".join(overlaps))


_reject_outputs_in_two_tables()
