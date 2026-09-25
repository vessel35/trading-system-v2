"""Keep the capability list free of inventory, and pin where deployment looks.

``core_lib.capabilities`` records what the platform can express, never what is
deployed right now. Writing an inventory into it would mean that adding a policy
file - which the authoring contract says must be a file plus a registration row -
also required editing ``core_lib`` to keep its tests green.
"""

from __future__ import annotations

from core_lib.capabilities import PLATFORM_CAPABILITIES, capability
from core_lib.indicators.registry import build_default_registry
from core_lib.patterns import TALIB_PATTERN_REGISTRY
from trading_plugins import discovery
from trading_plugins.discovery import registered_money_management


def _strings_in(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (tuple, list, set, frozenset)):
        return [text for item in value for text in _strings_in(item)]
    if isinstance(value, dict):
        return [text for item in value.items() for text in _strings_in(item)]
    return []


def test_no_capability_value_records_inventory() -> None:
    """Fail if a deployed name is written into the list a test compares against.

    Prose may name an example; a value may not, because values are what the
    drift tests assert equality on, and that equality is what would force a
    ``core_lib`` edit before a new plugin could ship.
    """
    inventory = {
        name.casefold()
        for name in (
            *registered_money_management(),
            *(spec.name for spec in build_default_registry().list()),
            *(spec.name for spec in TALIB_PATTERN_REGISTRY.list()),
        )
    }
    recorded = {
        (entry.id, text)
        for entry in PLATFORM_CAPABILITIES.values()
        for text in _strings_in(entry.value)
        if text.casefold() in inventory
    }

    assert recorded == set()


def test_deployment_scans_exactly_two_packages() -> None:
    packages = (
        discovery.STRATEGY_PACKAGE.__name__,
        discovery.MONEY_MANAGEMENT_PACKAGE.__name__,
    )

    assert packages == capability("deployment.packages").value
