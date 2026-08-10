"""Keep the atomic registry seed aligned with deployed policy declarations."""

from __future__ import annotations

import re
from pathlib import Path

from core_lib.money_management import MoneyManagementBase, policy_settings
from trading_plugins.money_management.manual import ManualMoneyManagement
from trading_plugins.money_management.turtle import TurtleMoneyManagement

_POLICIES: tuple[type[MoneyManagementBase], ...] = (
    ManualMoneyManagement,
    TurtleMoneyManagement,
)


def _script() -> str:
    repository_root = Path(__file__).resolve().parents[3]
    return (
        repository_root
        / "init-scripts/signal-service/20260810/01-create-money-management-registry.sql"
    ).read_text()


def test_registry_table_and_both_policy_rows_share_one_transaction() -> None:
    sql = _script()

    assert sql.count("BEGIN;") == 1
    assert sql.count("COMMIT;") == 1
    assert sql.index("BEGIN;") < sql.index("CREATE TABLE")
    assert sql.index("CREATE TABLE") < sql.index("INSERT INTO public.money_management_registry")
    assert sql.index("INSERT INTO public.money_management_registry") < sql.index("COMMIT;")
    assert sql.count("INSERT INTO public.money_management_registry") == 1
    assert "ON CONFLICT (mode) DO UPDATE" in sql
    assert ") IS DISTINCT FROM (" in sql

    for policy in _POLICIES:
        assert f"'{policy.id}'" in sql
        assert f"'{policy.__name__}'" in sql
        assert f"'{policy.__module__}'" in sql
        assert f"'{policy.version}'" in sql


def test_seeded_settings_names_are_sorted_policy_declarations() -> None:
    sql = _script()
    arrays = {
        mode: re.findall(r"'([^']+)'", values)
        for mode, values in re.findall(
            r"\(\s*'(manual|turtle)'.*?ARRAY\[(.*?)\]::text\[\]",
            sql,
            re.DOTALL,
        )
    }

    assert arrays == {policy.id: sorted(policy_settings(policy)) for policy in _POLICIES}
    assert "array_position(settings_names, NULL) IS NULL" in sql
    assert "array_agg(DISTINCT name ORDER BY name)" in sql
