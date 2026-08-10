"""Construct registered money-management policies from validated mappings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields
from typing import Any, Final, cast

from .policies import MoneyManagementBase

MONEY_MANAGEMENT_SCHEMA_VERSION: Final = "1.1.0"
"""How a submitted ``money_management`` mapping is interpreted.

Raise this whenever the accepted names, their defaults, or their ranges change,
so a stored configuration can be replayed the way it was originally read instead
of being reinterpreted under whatever the current defaults happen to be.
"""


class MoneyManagementFactory:
    """Validate one mode-specific configuration and construct its policy."""

    @staticmethod
    def version() -> str:
        """Return the schema version this factory resolves configurations under."""
        return MONEY_MANAGEMENT_SCHEMA_VERSION

    @staticmethod
    def create(
        raw_config: Mapping[str, object],
        policies: Mapping[str, type[MoneyManagementBase]],
    ) -> MoneyManagementBase:
        """Build the policy the configuration names, from whatever is registered.

        The accepted names and their defaults come from the policy class itself
        rather than a branch here, so a deployed policy needs no edit in this file
        to be configurable. The class validates its own values on construction.
        """
        mode = raw_config.get("mode")
        if not isinstance(mode, str):
            raise TypeError("money-management mode must be a string")
        policy_class = policies.get(mode)
        if policy_class is None:
            raise ValueError(f"unsupported money-management mode: {mode!r}")
        settings = policy_settings(policy_class)
        _reject_extra(raw_config, {"mode", *settings})
        return policy_class(**{name: raw_config[name] for name in settings if name in raw_config})


def policy_settings(policy_class: type[MoneyManagementBase]) -> frozenset[str]:
    """Return the configuration names a policy accepts.

    ``__dataclass_fields__`` also carries ``id`` and ``version``, which name the
    policy rather than configure it; passing them to the constructor fails with a
    message about an unexpected argument instead of an unknown setting.
    """
    if not hasattr(policy_class, "__dataclass_fields__"):
        raise TypeError(
            f"money-management policy {policy_class.__name__!r} must be a dataclass so its "
            "settings, names, and defaults are declared in one place"
        )
    # ``fields`` is what drops the ClassVar entries that ``__dataclass_fields__``
    # still carries, and those are the naming attributes rather than settings.
    declared = cast("Any", policy_class)
    return frozenset(field.name for field in fields(declared) if field.init)


def money_management_modes(
    policies: Mapping[str, type[MoneyManagementBase]],
) -> tuple[str, ...]:
    """Return the modes a configuration may name, in a stable order."""
    return tuple(sorted(policies))


def _reject_extra(raw: Mapping[str, object], allowed: set[str]) -> None:
    extra = set(raw) - allowed
    if extra:
        raise ValueError(f"unexpected money-management parameters: {sorted(extra)}")
