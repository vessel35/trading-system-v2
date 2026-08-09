"""Compare the external strategy catalog with deployed in-process classes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from core_lib.ports import StrategyRegistry

from .base import StrategyMetadata
from .registry import AdapterClass, InProcessStrategyRegistry


class StrategyReconciliationState(StrEnum):
    """The closed set of non-runnable catalog-to-code states."""

    CATALOG_ONLY = "catalog_only"
    ALLOWLIST_ONLY = "allowlist_only"
    IDENTITY_MISMATCH = "identity_mismatch"
    DECLARATION_MISMATCH = "declaration_mismatch"
    DECLARATION_READ_FAILED = "declaration_read_failed"
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
    """Return one deterministic non-runnable finding per strategy.

    Active entries with matching identities are omitted. Membership differences take
    precedence over identity, declaration, and lifecycle findings. Declaration reads
    are isolated per strategy and performed at most once. This gives every strategy id
    at most one state while retaining the catalog flags in the result.
    """
    catalog_entries = _catalog_entries_by_id(catalog_registry.list())
    allowlist_ids = set(adapter_registry.list())
    findings: list[StrategyReconciliation] = []

    for strategy_id in sorted(set(catalog_entries) | allowlist_ids):
        catalog_entry = catalog_entries.get(strategy_id)
        adaptee_class = adapter_registry.get(strategy_id) if strategy_id in allowlist_ids else None
        metadata: StrategyMetadata | None = None
        declaration_read_failed = False
        if (
            catalog_entry is not None
            and adaptee_class is not None
            and strategy_identity_matches(catalog_entry, adaptee_class)
        ):
            try:
                metadata = adaptee_class.get_metadata()
            except (Exception, SystemExit):  # noqa: BLE001 - isolate deployed code per strategy
                declaration_read_failed = True

        finding = reconcile_strategy_entry(
            strategy_id,
            catalog_entry,
            adaptee_class,
            metadata=metadata,
            declaration_read_failed=declaration_read_failed,
        )
        if finding is not None:
            findings.append(finding)

    return tuple(findings)


def reconcile_strategy_entry(
    strategy_id: str,
    catalog_entry: Mapping[str, object] | None,
    adaptee_class: AdapterClass | None,
    *,
    metadata: StrategyMetadata | None = None,
    declaration_read_failed: bool = False,
) -> StrategyReconciliation | None:
    """Reconcile one pre-read declaration snapshot using the canonical precedence."""
    catalog_identity = _catalog_identity(catalog_entry) if catalog_entry is not None else None
    allowlist_identity = _allowlist_identity(adaptee_class) if adaptee_class is not None else None
    is_active = _catalog_flag(catalog_entry, "is_active")
    is_deprecated = _catalog_flag(catalog_entry, "is_deprecated")

    if catalog_entry is None:
        state = StrategyReconciliationState.ALLOWLIST_ONLY
    elif adaptee_class is None:
        state = StrategyReconciliationState.CATALOG_ONLY
    elif catalog_identity != allowlist_identity:
        state = StrategyReconciliationState.IDENTITY_MISMATCH
    elif declaration_read_failed:
        state = StrategyReconciliationState.DECLARATION_READ_FAILED
    elif metadata is None:
        raise ValueError("matching catalog and Adaptee require a declaration snapshot")
    elif catalog_declaration_mismatch(catalog_entry, metadata) is not None:
        state = StrategyReconciliationState.DECLARATION_MISMATCH
    elif is_deprecated is True:
        state = StrategyReconciliationState.DEPRECATED
    elif is_active is False:
        state = StrategyReconciliationState.INACTIVE
    else:
        return None

    return StrategyReconciliation(
        strategy_id=strategy_id,
        state=state,
        catalog_identity=catalog_identity,
        allowlist_identity=allowlist_identity,
        is_active=is_active,
        is_deprecated=is_deprecated,
    )


def strategy_identity_matches(
    catalog_entry: Mapping[str, object],
    adaptee_class: AdapterClass,
) -> bool:
    """Return whether a catalog row names the exact deployed class."""
    return _catalog_identity(catalog_entry) == _allowlist_identity(adaptee_class)


def catalog_declaration_mismatch(
    catalog_entry: Mapping[str, object],
    metadata: StrategyMetadata,
) -> str | None:
    """Return the shared Manager/reconciliation error for declaration drift."""
    registered_history = catalog_entry.get("min_history")
    if registered_history is not None and registered_history != metadata.min_history:
        return (
            "catalog min_history does not match the Adaptee: "
            f"{registered_history!r} != {metadata.min_history!r}"
        )
    registered_timeframes = catalog_entry.get("supported_timeframes")
    if registered_timeframes is not None and list(
        cast(Sequence[str], registered_timeframes)
    ) != list(metadata.supported_timeframes):
        return (
            "catalog supported_timeframes do not match the Adaptee: "
            f"{registered_timeframes!r} != {list(metadata.supported_timeframes)!r}"
        )
    registered_indicators = catalog_entry.get("required_indicators_json")
    if registered_indicators is not None and _indicator_identities(
        cast(Sequence[Mapping[str, object]], registered_indicators)
    ) != _indicator_identities(metadata.required_indicators):
        return (
            "catalog required_indicators do not match the Adaptee: "
            f"{registered_indicators!r} != {list(metadata.required_indicators)!r}"
        )
    return None


def _indicator_identities(
    requirements: Sequence[Mapping[str, object]],
) -> tuple[tuple[str, tuple[tuple[str, object], ...]], ...]:
    """Compare requirements by name and parameters, ignoring order and key order."""
    return tuple(
        sorted(
            (
                str(requirement["name"]),
                tuple(sorted(cast(Mapping[str, object], requirement.get("params", {})).items())),
            )
            for requirement in requirements
        )
    )


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
    "catalog_declaration_mismatch",
    "reconcile_strategy_entry",
    "strategy_identity_matches",
    "StrategyImplementationIdentity",
    "StrategyReconciliation",
    "StrategyReconciliationState",
    "reconcile_strategy_registries",
]
