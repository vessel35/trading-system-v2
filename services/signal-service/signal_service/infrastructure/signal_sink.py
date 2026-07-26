"""Persist driver-derived operational signals to signal_db."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Protocol

from signal_service.application import SignalSink
from signal_service.domain import PersistedSignal

_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
_INSERT_SQL = """
INSERT INTO {relation} (
    strategy_id,
    source_mode,
    symbol,
    exchange,
    timeframe,
    candle_open_time,
    candle_close_time,
    signal_time,
    signal_type,
    derived_intent,
    derived_side,
    price,
    confidence,
    stop_loss,
    take_profit,
    market_type,
    leverage,
    reason,
    metadata_json
)
VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
)
ON CONFLICT (
    strategy_id,
    source_mode,
    symbol,
    timeframe,
    candle_close_time
) DO NOTHING
RETURNING signal_id
"""


def _insert_sql(schema: str) -> str:
    if _IDENTIFIER.fullmatch(schema) is None:
        raise ValueError("schema must be a lowercase PostgreSQL identifier")
    return _INSERT_SQL.format(relation=f'"{schema}".trading_signals')


class WriteResult(Protocol):
    """The minimal result needed to distinguish insert from duplicate."""

    def fetchone(self) -> Sequence[object] | None:
        """Return the inserted identity or no row."""


class WriteConnection(Protocol):
    """The single parameterized INSERT surface used by the sink."""

    def execute(
        self,
        query: str,
        params: tuple[object, ...],
    ) -> WriteResult:
        """Execute one operational write."""


class PostgresSignalSink(SignalSink):
    """Insert only into the signal-service-owned trading_signals table."""

    def __init__(self, connection: WriteConnection, *, schema: str = "public") -> None:
        self._connection = connection
        self._insert_sql = _insert_sql(schema)

    def store(self, signal: PersistedSignal) -> bool:
        """Persist an idempotent envelope and report whether it was new."""
        decision = signal.signal
        candle = signal.candle
        row = self._connection.execute(
            self._insert_sql,
            (
                signal.strategy_id,
                signal.mode.value,
                decision.symbol,
                candle.exchange,
                signal.timeframe,
                candle.open_time,
                candle.close_time,
                decision.timestamp,
                signal.signal_type.value,
                signal.intent.value,
                None if signal.side is None else signal.side.value,
                decision.price,
                decision.confidence,
                decision.stop_loss,
                decision.take_profit,
                decision.market_type.value,
                decision.leverage,
                decision.reason,
                json.dumps(decision.metadata, sort_keys=True, separators=(",", ":")),
            ),
        ).fetchone()
        return row is not None
