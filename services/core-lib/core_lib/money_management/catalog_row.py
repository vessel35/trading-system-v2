"""Define and validate the external money-management catalog row shape."""

from __future__ import annotations

from collections.abc import Sequence

MONEY_MANAGEMENT_CATALOG_COLUMNS: tuple[str, ...] = (
    "mode",
    "class_name",
    "module_path",
    "display_name",
    "description",
    "policy_version",
    "settings_names",
    "is_active",
    "is_deprecated",
    "registered_at",
    "updated_at",
)


def money_management_catalog_row_entry(row: Sequence[object]) -> dict[str, object]:
    """Map one database row after checking its length and settings-name values."""
    if len(row) != len(MONEY_MANAGEMENT_CATALOG_COLUMNS):
        raise ValueError("money_management_registry SELECT returned an unexpected row shape")
    result = dict(zip(MONEY_MANAGEMENT_CATALOG_COLUMNS, row, strict=True))
    settings_names = result["settings_names"]
    if not isinstance(settings_names, list) or any(
        not isinstance(name, str) for name in settings_names
    ):
        raise TypeError("settings_names must decode to a list of strings")
    return result


__all__ = ["MONEY_MANAGEMENT_CATALOG_COLUMNS", "money_management_catalog_row_entry"]
