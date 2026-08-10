"""Read money-management registrations through the Web API signal-db boundary."""

from __future__ import annotations

from core_lib.money_management import (
    MONEY_MANAGEMENT_CATALOG_COLUMNS,
    money_management_catalog_row_entry,
)

from web_api.database import SignalConnection

_SELECT_COLUMNS = ", ".join(MONEY_MANAGEMENT_CATALOG_COLUMNS)
_TABLE_SQL = "SELECT to_regclass('public.money_management_registry') AS relation"
_LIST_SQL = f"""
SELECT {_SELECT_COLUMNS}
FROM public.money_management_registry
ORDER BY mode
"""


def read_money_management_registrations(
    connection: SignalConnection,
) -> list[dict[str, object]] | None:
    """Return registrations, distinguishing a missing table from an empty one."""
    relation = connection.execute(_TABLE_SQL).fetchone()
    if relation is None or relation["relation"] is None:
        return None
    rows = connection.execute(_LIST_SQL).fetchall()
    return [
        money_management_catalog_row_entry(
            tuple(row[column] for column in MONEY_MANAGEMENT_CATALOG_COLUMNS)
        )
        for row in rows
    ]


__all__ = ["read_money_management_registrations"]
