"""Read Adaptee metadata from the one permitted signal_db table."""

from __future__ import annotations

from core_lib.ports import StrategyRegistry
from core_lib.strategy import CATALOG_COLUMNS, catalog_row_entry

from .data_feed import ReadConnection

_SELECT_COLUMNS = ", ".join(CATALOG_COLUMNS)
_GET_SQL = f"""
SELECT {_SELECT_COLUMNS}
FROM public.strategy_registry
WHERE strategy_id = %s
"""
_LIST_SQL = f"""
SELECT {_SELECT_COLUMNS}
FROM public.strategy_registry
ORDER BY strategy_id
"""


class BacktestStrategyRegistry(StrategyRegistry):
    """Provide deterministic read-only access to signal_db.strategy_registry."""

    def __init__(self, connection: ReadConnection) -> None:
        self._connection = connection

    def get(self, strategy_id: str) -> dict[str, object]:
        """Return one catalog entry without reading any other signal_db table."""
        row = self._connection.execute(_GET_SQL, (strategy_id,)).fetchone()
        if row is None:
            raise KeyError(strategy_id)
        return catalog_row_entry(row)

    def list(self) -> list[dict[str, object]]:
        """Return all catalog entries in stable strategy-id order."""
        rows = self._connection.execute(_LIST_SQL, ()).fetchall()
        return [catalog_row_entry(row) for row in rows]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        """Reject writes because signal-service owns catalog registration."""
        del strategy_id, meta
        raise PermissionError(
            "BacktestStrategyRegistry is read-only; signal-service owns registration"
        )
