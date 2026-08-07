"""Compare the external strategy catalog with deployed in-process classes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from core_lib.ports import StrategyRegistry

from .registry import AdapterClass, InProcessStrategyRegistry


class StrategyReconciliationState(StrEnum):
    """The five non-runnable or inconsistent catalog-to-code states."""

    CATALOG_ONLY = "catalog_only"
    ALLOWLIST_ONLY = "allowlist_only"
    IDENTITY_MISMATCH = "identity_mismatch"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


@dataclass(frozen=True, slots=True)
class StrategyImplementationIdentity:
    """The class and module identity compared without importing catalog paths."""

    class_name: str | None
    module_path: str | None


@dataclass(frozen=True, slots=True)
class StrategyReconciliation:
    """Describe one catalog-to-allowlist state and both available identities."""

    strategy_id: str
    state: StrategyReconciliationState
    catalog_identity: StrategyImplementationIdentity | None
    allowlist_identity: StrategyImplementationIdentity | None
    is_active: bool | None
    is_deprecated: bool | None


def reconcile_strategy_registries(
    catalog_registry: StrategyRegistry,
    adapter_registry: InProcessStrategyRegistry,
) -> tuple[StrategyReconciliation, ...]:
    """Return deterministic findings for the five reconciliation states.

    Active entries with matching identities are omitted. Membership differences take
    precedence over row flags, identity differences take precedence over lifecycle
    flags, and deprecation takes precedence over inactivity. This gives every strategy
    id at most one state while retaining the catalog flags in the result.
    """
    catalog_entries = _catalog_entries_by_id(catalog_registry.list())
    allowlist_ids = set(adapter_registry.list())
    findings: list[StrategyReconciliation] = []

    for strategy_id in sorted(set(catalog_entries) | allowlist_ids):
        catalog_entry = catalog_entries.get(strategy_id)
        adaptee_class = adapter_registry.get(strategy_id) if strategy_id in allowlist_ids else None
        catalog_identity = _catalog_identity(catalog_entry) if catalog_entry is not None else None
        allowlist_identity = (
            _allowlist_identity(adaptee_class) if adaptee_class is not None else None
        )
        is_active = _catalog_flag(catalog_entry, "is_active")
        is_deprecated = _catalog_flag(catalog_entry, "is_deprecated")

        if catalog_entry is None:
            state = StrategyReconciliationState.ALLOWLIST_ONLY
        elif adaptee_class is None:
            state = StrategyReconciliationState.CATALOG_ONLY
        elif catalog_identity != allowlist_identity:
            state = StrategyReconciliationState.IDENTITY_MISMATCH
        elif is_deprecated is True:
            state = StrategyReconciliationState.DEPRECATED
        elif is_active is False:
            state = StrategyReconciliationState.INACTIVE
        else:
            continue

        findings.append(
            StrategyReconciliation(
                strategy_id=strategy_id,
                state=state,
                catalog_identity=catalog_identity,
                allowlist_identity=allowlist_identity,
                is_active=is_active,
                is_deprecated=is_deprecated,
            )
        )

    return tuple(findings)


def _catalog_entries_by_id(
    entries: list[dict[str, object]],
) -> dict[str, Mapping[str, object]]:
    by_id: dict[str, Mapping[str, object]] = {}
    for entry in entries:
        strategy_id = entry.get("strategy_id")
        if not isinstance(strategy_id, str) or not strategy_id:
            raise ValueError("external catalog row has no valid strategy_id")
        if strategy_id in by_id:
            raise ValueError(f"external catalog contains a duplicate strategy_id: {strategy_id}")
        by_id[strategy_id] = entry
    return by_id


def _catalog_identity(entry: Mapping[str, object]) -> StrategyImplementationIdentity:
    class_name = entry.get("class_name")
    module_path = entry.get("module_path")
    return StrategyImplementationIdentity(
        class_name=class_name if isinstance(class_name, str) else None,
        module_path=module_path if isinstance(module_path, str) else None,
    )


def _allowlist_identity(adaptee_class: AdapterClass) -> StrategyImplementationIdentity:
    return StrategyImplementationIdentity(
        class_name=adaptee_class.__name__,
        module_path=adaptee_class.__module__,
    )


def _catalog_flag(entry: Mapping[str, object] | None, name: str) -> bool | None:
    if entry is None:
        return None
    value = entry.get(name)
    return value if isinstance(value, bool) else None


__all__ = [
    "StrategyImplementationIdentity",
    "StrategyReconciliation",
    "StrategyReconciliationState",
    "reconcile_strategy_registries",
]
