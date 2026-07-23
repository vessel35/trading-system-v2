"""Read Adaptee metadata from the one permitted signal_db table."""

from __future__ import annotations

from collections.abc import Sequence

from core_lib.ports import StrategyRegistry

from .data_feed import ReadConnection

_COLUMNS = (
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
_SELECT_COLUMNS = ", ".join(_COLUMNS)
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


def _entry(row: Sequence[object]) -> dict[str, object]:
    if len(row) != len(_COLUMNS):
        raise ValueError("strategy_registry SELECT returned an unexpected row shape")
    result = dict(zip(_COLUMNS, row, strict=True))
    if not isinstance(result["required_indicators_json"], list):
        raise TypeError("required_indicators_json must decode to a list")
    if not isinstance(result["default_params_json"], dict):
        raise TypeError("default_params_json must decode to a dict")
    return result


class BacktestStrategyRegistry(StrategyRegistry):
    """Provide deterministic read-only access to signal_db.strategy_registry."""

    def __init__(self, connection: ReadConnection) -> None:
        self._connection = connection

    def get(self, strategy_id: str) -> dict[str, object]:
        """Return one catalog entry without reading any other signal_db table."""
        row = self._connection.execute(_GET_SQL, (strategy_id,)).fetchone()
        if row is None:
            raise KeyError(strategy_id)
        return _entry(row)

    def list(self) -> list[dict[str, object]]:
        """Return all catalog entries in stable strategy-id order."""
        rows = self._connection.execute(_LIST_SQL, ()).fetchall()
        return [_entry(row) for row in rows]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        """Reject writes because signal-service owns catalog registration."""
        del strategy_id, meta
        raise PermissionError(
            "BacktestStrategyRegistry is read-only; signal-service owns registration"
        )
