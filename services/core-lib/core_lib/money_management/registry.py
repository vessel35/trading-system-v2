"""Construct registered money-management policies from validated mappings."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from .policies import (
    ManualMoneyManagement,
    MoneyManagementBase,
    MoneyManagementPolicy,
    TurtleMoneyManagement,
)

MONEY_MANAGEMENT_SCHEMA_VERSION: Final = "1.0.0"
"""How a submitted ``money_management`` mapping is interpreted.

Raise this whenever the accepted names, their defaults, or their ranges change,
so a stored configuration can be replayed the way it was originally read instead
of being reinterpreted under whatever the current defaults happen to be.
"""


BUILTIN_POLICIES: Final[Mapping[str, type[MoneyManagementBase]]] = MappingProxyType(
    {
        ManualMoneyManagement.id: ManualMoneyManagement,
        TurtleMoneyManagement.id: TurtleMoneyManagement,
    }
)
"""The policies the platform ships. Deployed ones are passed in, never added here."""


class MoneyManagementFactory:
    """Validate one mode-specific configuration and construct its policy."""

    @staticmethod
    def version() -> str:
        """Return the schema version this factory resolves configurations under."""
        return MONEY_MANAGEMENT_SCHEMA_VERSION

    @staticmethod
    def create(
        raw_config: Mapping[str, object],
        policies: Mapping[str, type[MoneyManagementBase]] = BUILTIN_POLICIES,
    ) -> MoneyManagementPolicy:
        """Build the policy the configuration names, from whatever is registered.

        The accepted names and their defaults come from the policy class itself
        rather than a branch here, so a deployed policy needs no edit in this file
        to be configurable. The class validates its own values on construction.
        """
        mode = raw_config.get("mode", ManualMoneyManagement.id)
        if not isinstance(mode, str):
            raise TypeError("money-management mode must be a string")
        policy_class = policies.get(mode)
        if policy_class is None:
            raise ValueError(f"unsupported money-management mode: {mode!r}")
        declared = getattr(policy_class, "__dataclass_fields__", None)
        if declared is None:
            raise TypeError(
                f"money-management policy {mode!r} must be a dataclass so its settings, "
                "names, and defaults are declared in one place"
            )
        settings = set(declared)
        _reject_extra(raw_config, {"mode", *settings})
        return policy_class(**{name: raw_config[name] for name in settings if name in raw_config})


def money_management_modes(
    policies: Mapping[str, type[MoneyManagementBase]] = BUILTIN_POLICIES,
) -> tuple[str, ...]:
    """Return the modes a configuration may name, in a stable order."""
    return tuple(sorted(policies))


def _reject_extra(raw: Mapping[str, object], allowed: set[str]) -> None:
    extra = set(raw) - allowed
    if extra:
        raise ValueError(f"unexpected money-management parameters: {sorted(extra)}")


MONEY_MANAGEMENT_MODES: Final = money_management_modes()
