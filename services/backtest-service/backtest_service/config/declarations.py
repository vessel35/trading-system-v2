"""Look up what a deployed strategy declares about its money-management settings.

The run configuration fills a setting the submission left out from the strategy's
``MoneyManagementSupport.default_settings`` before the policy's own default
applies. That declaration lives on the deployed class, so it is read through the
plugin discovery the platform already uses for policies.

Discovery is deferred to the first lookup rather than done at import. ``RunConfig``
is imported by processes that only expose its schema, and tests register fake
strategies in in-process registries; neither should pay for importing every
deployed strategy module, nor fail because one of them does.
"""

from __future__ import annotations

from functools import cache
from types import MappingProxyType
from typing import TYPE_CHECKING

from trading_plugins import discover_strategies

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core_lib.strategy import MoneyManagementSupport


@cache
def _declarations() -> Mapping[str, MoneyManagementSupport]:
    """Read every deployed strategy's declaration once; skip the ones that fail."""
    found, _faults = discover_strategies()
    declared: dict[str, MoneyManagementSupport] = {}
    for strategy_id, strategy_class in found.items():
        try:
            declared[strategy_id] = strategy_class.get_metadata().money_management
        except (Exception, SystemExit):  # noqa: BLE001 - one deployed class must not block the rest
            continue
    return MappingProxyType(declared)


def declared_money_management(strategy_id: object) -> MoneyManagementSupport | None:
    """Return the declaration for a deployed strategy id, or ``None`` when unknown."""
    if not isinstance(strategy_id, str):
        return None
    return _declarations().get(strategy_id)


__all__ = ["declared_money_management"]
