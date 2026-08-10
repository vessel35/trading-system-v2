"""Define and validate the external strategy catalog row shape."""

from __future__ import annotations

from collections.abc import Sequence

CATALOG_COLUMNS: tuple[str, ...] = (
    "strategy_id",
    "class_name",
    "module_path",
    "display_name",
    "description",
    "strategy_version",
    "supported_timeframes",
    "required_indicators_json",
    "min_history",
    "default_params_json",
    "is_active",
    "is_deprecated",
    "registered_at",
    "updated_at",
)


def catalog_row_entry(row: Sequence[object]) -> dict[str, object]:
    """Map one database row after checking its shape and decoded JSON values."""
    if len(row) != len(CATALOG_COLUMNS):
        raise ValueError("strategy_registry SELECT returned an unexpected row shape")
    result = dict(zip(CATALOG_COLUMNS, row, strict=True))
    if not isinstance(result["required_indicators_json"], list):
        raise TypeError("required_indicators_json must decode to a list")
    if not isinstance(result["default_params_json"], dict):
        raise TypeError("default_params_json must decode to a dict")
    return result


__all__ = ["CATALOG_COLUMNS", "catalog_row_entry"]
