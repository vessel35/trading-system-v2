"""Read money-management registrations from signal_db without owning writes."""

from __future__ import annotations

from core_lib.money_management import (
    MONEY_MANAGEMENT_CATALOG_COLUMNS,
    money_management_catalog_row_entry,
)
from core_lib.ports import MoneyManagementRegistry

from .data_feed import ReadConnection

_SELECT_COLUMNS = ", ".join(MONEY_MANAGEMENT_CATALOG_COLUMNS)
_GET_SQL = f"""
SELECT {_SELECT_COLUMNS}
FROM public.money_management_registry
WHERE mode = %s
"""
_LIST_SQL = f"""
SELECT {_SELECT_COLUMNS}
FROM public.money_management_registry
ORDER BY mode
"""


class BacktestMoneyManagementRegistry(MoneyManagementRegistry):
    """Provide deterministic read-only access to policy registrations."""

    def __init__(self, connection: ReadConnection) -> None:
        self._connection = connection

    def get(self, mode: str) -> dict[str, object]:
        """Return one policy catalog entry by mode."""
        row = self._connection.execute(_GET_SQL, (mode,)).fetchone()
        if row is None:
            raise KeyError(mode)
        return money_management_catalog_row_entry(row)

    def list(self) -> list[dict[str, object]]:
        """Return all policy catalog entries in stable mode order."""
        rows = self._connection.execute(_LIST_SQL, ()).fetchall()
        return [money_management_catalog_row_entry(row) for row in rows]
