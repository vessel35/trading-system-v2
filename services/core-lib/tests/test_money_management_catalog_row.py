"""Verify the single external money-management catalog row contract."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from core_lib.money_management import (
    MONEY_MANAGEMENT_CATALOG_COLUMNS,
    money_management_catalog_row_entry,
)


def _catalog_row() -> tuple[object, ...]:
    return (
        "manual",
        "ManualMoneyManagement",
        "trading_plugins.money_management.manual",
        "Manual",
        "Legacy-compatible fixed protection and leverage.",
        "1.0.0",
        ["atr_stop_multiple", "leverage", "reward_risk"],
        True,
        False,
        datetime(2026, 8, 10, tzinfo=UTC),
        datetime(2026, 8, 10, tzinfo=UTC),
    )


def test_money_management_catalog_row_preserves_the_shared_shape() -> None:
    entry = money_management_catalog_row_entry(_catalog_row())

    assert tuple(entry) == MONEY_MANAGEMENT_CATALOG_COLUMNS
    assert entry["mode"] == "manual"
    assert entry["settings_names"] == ["atr_stop_multiple", "leverage", "reward_risk"]


def test_money_management_catalog_row_rejects_a_wrong_row_length() -> None:
    with pytest.raises(ValueError, match="unexpected row shape"):
        money_management_catalog_row_entry(_catalog_row()[:-1])


@pytest.mark.parametrize("replacement", ["leverage", ("leverage",), ["leverage", 3]])
def test_money_management_catalog_row_rejects_non_string_lists(replacement: object) -> None:
    row = list(_catalog_row())
    row[6] = replacement

    with pytest.raises(TypeError, match="list of strings"):
        money_management_catalog_row_entry(row)
