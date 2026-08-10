"""Compare registered money-management rows with deployed policy classes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from .policies import MoneyManagementBase
from .registry import policy_settings


class MoneyManagementReconciliationState(StrEnum):
    """The closed set of reasons a policy mode cannot run."""

    REGISTERED_ONLY = "registered_only"
    DEPLOYED_ONLY = "deployed_only"
    IDENTITY_MISMATCH = "identity_mismatch"
    DECLARATION_MISMATCH = "declaration_mismatch"
    DEPRECATED = "deprecated"
    INACTIVE = "inactive"


@dataclass(frozen=True, slots=True)
class MoneyManagementAvailability:
    """Give one policy mode one runnable answer and at most one reason."""

    mode: str
    runnable: bool
    reason: MoneyManagementReconciliationState | None


def reconcile_money_management_availability(
    registrations: Sequence[Mapping[str, object]] | None,
    deployed_policies: Mapping[str, type[MoneyManagementBase]],
) -> tuple[MoneyManagementAvailability, ...]:
    """Return one deterministic availability answer for every known policy mode.

    ``None`` means the registry table does not exist and preserves the pre-registry
    behavior in which every deployed policy is runnable. An empty sequence means the
    table exists but has no rows, so every deployed policy is present without a
    registration and is not runnable.
    """
    if registrations is None:
        return tuple(
            MoneyManagementAvailability(mode=mode, runnable=True, reason=None)
            for mode in sorted(deployed_policies)
        )

    registered_by_mode = _registrations_by_mode(registrations)
    results: list[MoneyManagementAvailability] = []
    for mode in sorted(set(registered_by_mode) | set(deployed_policies)):
        registration = registered_by_mode.get(mode)
        policy = deployed_policies.get(mode)
        reason = _unrunnable_reason(registration, policy)
        results.append(
            MoneyManagementAvailability(
                mode=mode,
                runnable=reason is None,
                reason=reason,
            )
        )
    return tuple(results)


def _unrunnable_reason(
    registration: Mapping[str, object] | None,
    policy: type[MoneyManagementBase] | None,
) -> MoneyManagementReconciliationState | None:
    if registration is None:
        return MoneyManagementReconciliationState.DEPLOYED_ONLY
    if policy is None:
        return MoneyManagementReconciliationState.REGISTERED_ONLY
    if (
        registration.get("class_name") != policy.__name__
        or registration.get("module_path") != policy.__module__
    ):
        return MoneyManagementReconciliationState.IDENTITY_MISMATCH
    registered_settings = registration.get("settings_names")
    if not isinstance(registered_settings, list) or set(registered_settings) != set(
        policy_settings(policy)
    ):
        return MoneyManagementReconciliationState.DECLARATION_MISMATCH
    if registration.get("is_deprecated") is True:
        return MoneyManagementReconciliationState.DEPRECATED
    if registration.get("is_active") is False:
        return MoneyManagementReconciliationState.INACTIVE
    return None


def _registrations_by_mode(
    registrations: Sequence[Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    by_mode: dict[str, Mapping[str, object]] = {}
    for registration in registrations:
        mode = registration.get("mode")
        if not isinstance(mode, str) or not mode:
            raise ValueError("money-management registration has no valid mode")
        if mode in by_mode:
            raise ValueError(f"money-management registry contains a duplicate mode: {mode}")
        by_mode[mode] = registration
    return by_mode


__all__ = [
    "MoneyManagementAvailability",
    "MoneyManagementReconciliationState",
    "reconcile_money_management_availability",
]
