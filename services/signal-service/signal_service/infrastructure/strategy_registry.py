"""Read Adaptee metadata from the sole permitted signal_db registry table."""

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


class SignalStrategyRegistry(StrategyRegistry):
    """Mirror the backtest catalog adapter with a read-only signal-service view."""

    def __init__(self, connection: ReadConnection) -> None:
        self._connection = connection

    def get(self, strategy_id: str) -> dict[str, object]:
        """Return one catalog entry without reading deployment tables."""
        row = self._connection.execute(_GET_SQL, (strategy_id,)).fetchone()
        if row is None:
            raise KeyError(strategy_id)
        return catalog_row_entry(row)

    def list(self) -> list[dict[str, object]]:
        """Return catalog entries in stable strategy-id order."""
        rows = self._connection.execute(_LIST_SQL, ()).fetchall()
        return [catalog_row_entry(row) for row in rows]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        """Keep registry mutation outside the generation loop."""
        del strategy_id, meta
        raise PermissionError("SignalStrategyRegistry is read-only in the generation slice")
