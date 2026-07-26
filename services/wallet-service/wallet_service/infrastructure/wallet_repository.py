"""Persist one paper signal's fills, position, and accounting transaction."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from wallet_service.application import WalletRepository
from wallet_service.domain import SignalConsumptionStatus, WalletExecution

_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")

_INSERT_CONSUMPTION = """
INSERT INTO {consumption} (
    wallet_id, signal_id, mode, status, consumed_at
)
VALUES (%s, %s, 'paper', %s, %s)
ON CONFLICT (wallet_id, signal_id) DO NOTHING
RETURNING signal_id
"""

_INSERT_FILL = """
INSERT INTO {fills} (
    wallet_id, signal_id, mode, order_id, symbol, side, position_side,
    reference_price, price, quantity, fee, slippage, liquidity,
    executed_at, reduce_only, exit_reason, gap_filled, qty_truncated
)
VALUES (
    %s, %s, 'paper', %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s
)
ON CONFLICT (wallet_id, signal_id, reduce_only) DO NOTHING
RETURNING fill_id
"""

_DELETE_POSITIONS = """
DELETE FROM {positions}
WHERE wallet_id = %s
  AND symbol = %s
"""

_INSERT_POSITION = """
INSERT INTO {positions} (
    wallet_id, mode, symbol, side, quantity, average_price, total_cost,
    current_price, unrealized_pnl, market_type, leverage, margin_type,
    margin, entry_price, mark_price, liquidation_price, funding_fee_total,
    updated_at
)
VALUES (
    %s, 'paper', %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s
)
"""

_INSERT_ACCOUNTING = """
INSERT INTO {accounting} (
    wallet_id, signal_id, mode, occurred_at, cash_balance, position_value,
    total_equity, fee_total, slippage_total
)
VALUES (%s, %s, 'paper', %s, %s, %s, %s, %s, %s)
ON CONFLICT (wallet_id, signal_id) DO NOTHING
RETURNING snapshot_id
"""

_UPSERT_ACCOUNT = """
INSERT INTO {accounts} (
    wallet_id, mode, cash_balance, total_equity, updated_at
)
VALUES (%s, 'paper', %s, %s, %s)
ON CONFLICT (wallet_id) DO UPDATE
SET cash_balance = EXCLUDED.cash_balance,
    total_equity = EXCLUDED.total_equity,
    updated_at = EXCLUDED.updated_at
"""


class WriteResult(Protocol):
    """The minimal cursor result needed for idempotency."""

    def fetchone(self) -> Sequence[object] | None:
        """Return one inserted identity or no row."""


class WriteConnection(Protocol):
    """The transactional DB-API surface used by the repository."""

    def execute(
        self,
        query: str,
        params: tuple[object, ...],
    ) -> WriteResult:
        """Execute one wallet-owned statement."""

    def commit(self) -> None:
        """Commit the complete signal transaction."""

    def rollback(self) -> None:
        """Roll back the complete signal transaction."""


def _relation(schema: str, table: str) -> str:
    if _IDENTIFIER.fullmatch(schema) is None:
        raise ValueError("schema must be a lowercase PostgreSQL identifier")
    return f'"{schema}".{table}'


class PostgresWalletRepository(WalletRepository):
    """Write only the v2 wallet-service paper schema."""

    def __init__(self, connection: WriteConnection, *, schema: str = "public") -> None:
        self._connection = connection
        self._insert_consumption = _INSERT_CONSUMPTION.format(
            consumption=_relation(schema, "wallet_signal_consumption"),
        )
        self._insert_fill = _INSERT_FILL.format(
            fills=_relation(schema, "fills"),
        )
        self._delete_positions = _DELETE_POSITIONS.format(
            positions=_relation(schema, "positions"),
        )
        self._insert_position = _INSERT_POSITION.format(
            positions=_relation(schema, "positions"),
        )
        self._insert_accounting = _INSERT_ACCOUNTING.format(
            accounting=_relation(schema, "accounting_snapshots"),
        )
        self._upsert_account = _UPSERT_ACCOUNT.format(
            accounts=_relation(schema, "wallet_accounts"),
        )

    def store(self, execution: WalletExecution) -> bool:
        """Commit fills, final position, and accounting or roll back all of them."""
        try:
            inserted_consumption = self._connection.execute(
                self._insert_consumption,
                (
                    execution.wallet_id,
                    execution.signal_id,
                    SignalConsumptionStatus.FILLED.value,
                    execution.accounting.occurred_at,
                ),
            ).fetchone()
            if inserted_consumption is None:
                self._connection.rollback()
                return False

            for fill in execution.fills:
                inserted = self._connection.execute(
                    self._insert_fill,
                    (
                        execution.wallet_id,
                        execution.signal_id,
                        fill.order_id,
                        fill.symbol,
                        fill.side.value,
                        fill.position_side.value,
                        fill.reference_price,
                        fill.price,
                        fill.quantity,
                        fill.fee,
                        fill.slippage,
                        fill.liquidity,
                        fill.timestamp,
                        fill.reduce_only,
                        None if fill.exit_reason is None else fill.exit_reason.value,
                        fill.gap_filled,
                        fill.qty_truncated,
                    ),
                ).fetchone()
                if inserted is None:
                    self._connection.rollback()
                    return False

            self._connection.execute(
                self._delete_positions,
                (execution.wallet_id, execution.symbol),
            )
            position = execution.position
            if position is not None:
                self._connection.execute(
                    self._insert_position,
                    (
                        execution.wallet_id,
                        position.symbol,
                        position.side.value,
                        position.quantity,
                        position.average_price,
                        position.total_cost,
                        position.current_price,
                        position.unrealized_pnl,
                        position.market_type.value,
                        position.leverage,
                        position.margin_type.value,
                        position.margin,
                        position.entry_price,
                        position.mark_price,
                        position.liquidation_price,
                        position.funding_fee_total,
                        execution.accounting.occurred_at,
                    ),
                )

            accounting = execution.accounting
            inserted_accounting = self._connection.execute(
                self._insert_accounting,
                (
                    execution.wallet_id,
                    execution.signal_id,
                    accounting.occurred_at,
                    accounting.cash_balance,
                    accounting.position_value,
                    accounting.total_equity,
                    accounting.fee_total,
                    accounting.slippage_total,
                ),
            ).fetchone()
            if inserted_accounting is None:
                self._connection.rollback()
                return False
            self._connection.execute(
                self._upsert_account,
                (
                    execution.wallet_id,
                    accounting.cash_balance,
                    accounting.total_equity,
                    accounting.occurred_at,
                ),
            )
            self._connection.commit()
            return True
        except Exception:
            self._connection.rollback()
            raise

    def record_consumption(
        self,
        wallet_id: str,
        signal_id: str,
        status: SignalConsumptionStatus,
        consumed_at: datetime,
    ) -> bool:
        """Commit a rejected/skipped receipt without any fill or accounting row."""
        normalized_status = SignalConsumptionStatus(status)
        if normalized_status is SignalConsumptionStatus.FILLED:
            raise ValueError("filled consumption must be committed with its ledger")
        try:
            inserted = self._connection.execute(
                self._insert_consumption,
                (
                    wallet_id,
                    signal_id,
                    normalized_status.value,
                    consumed_at,
                ),
            ).fetchone()
            self._connection.commit()
            return inserted is not None
        except Exception:
            self._connection.rollback()
            raise
