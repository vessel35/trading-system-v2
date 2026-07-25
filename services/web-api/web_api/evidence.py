"""Read-only access to one run's immutable SQLite Evidence artifact."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from web_api.database import get_settings
from web_api.models import (
    CandidateEvent,
    ChartSummary,
    CursorPage,
    DrawdownEpisode,
    EquityPoint,
    EvidenceCollection,
    Execution,
    FundingSettlement,
    IntegrityCheck,
    OutcomeBucket,
    Position,
    Trade,
    TradeFeature,
)

DECIMAL_SCALE = Decimal(10) ** 8


class EvidenceUnavailableError(RuntimeError):
    """The catalog points at Evidence that cannot be read safely."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _iso8601(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def _decimal_string(value: int) -> str:
    return format(Decimal(value) / DECIMAL_SCALE, "f")


def _json_value(value: str | None) -> object | None:
    if value is None:
        return None
    try:
        return cast(object, json.loads(value))
    except json.JSONDecodeError as exc:
        raise EvidenceUnavailableError("evidence_payload_invalid") from exc


def _boolean(value: int) -> bool:
    return bool(value)


@contextmanager
def open_evidence(evidence_path: str | None) -> Iterator[sqlite3.Connection]:
    """Resolve only the catalog basename under EVIDENCE_ROOT and open it read-only."""

    if not evidence_path:
        raise EvidenceUnavailableError("catalog_evidence_path_missing")
    filename = Path(evidence_path).name
    if not filename:
        raise EvidenceUnavailableError("catalog_evidence_path_invalid")
    path = get_settings().evidence_root / filename
    if not path.is_file():
        raise EvidenceUnavailableError("evidence_file_missing")
    try:
        connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
            connection.close()
            raise EvidenceUnavailableError("evidence_not_read_only")
        connection.execute(
            "SELECT evidence_schema_version FROM BACKTEST_RUN_LOCAL LIMIT 1"
        ).fetchone()
    except EvidenceUnavailableError:
        raise
    except sqlite3.Error as exc:
        raise EvidenceUnavailableError("evidence_file_invalid") from exc
    try:
        yield connection
    finally:
        connection.close()


def _where(
    filters: Sequence[tuple[str, object | None]],
    *,
    cursor_column: str,
    after_seq: int,
) -> tuple[str, list[object]]:
    clauses = [f"{cursor_column} > ?"]
    values: list[object] = [after_seq]
    for clause, value in filters:
        if value is not None:
            clauses.append(clause)
            values.append(value)
    return " AND ".join(clauses), values


class EvidenceRepository:
    """Whitelisted queries and schema-aware restoration for one Evidence file."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def _collection(
        self,
        *,
        table: str,
        cursor_column: str,
        model: type[BaseModel],
        decoder: Any,
        after_seq: int,
        limit: int,
        filters: Sequence[tuple[str, object | None]] = (),
        select: str = "*",
        joins: str = "",
        order_by: str | None = None,
    ) -> EvidenceCollection[Any]:
        where, params = _where(filters, cursor_column=cursor_column, after_seq=after_seq)
        count_where, count_params = _where(
            filters,
            cursor_column=cursor_column,
            after_seq=0,
        )
        count_row = self._connection.execute(
            f"SELECT count(*) FROM {table} {joins} WHERE {count_where}",
            count_params,
        ).fetchone()
        total = int(count_row[0]) if count_row is not None else 0
        rows = self._connection.execute(
            f"""
            SELECT {select}
            FROM {table}
            {joins}
            WHERE {where}
            ORDER BY {order_by or cursor_column}
            LIMIT ?
            """,
            [*params, limit + 1],
        ).fetchall()
        has_more = len(rows) > limit
        selected = rows[:limit]
        data = [model.model_validate(decoder(dict(row))) for row in selected]
        next_after_seq = int(selected[-1][cursor_column.split(".")[-1]]) if selected else None
        return EvidenceCollection(
            data=data,
            page=CursorPage(
                limit=limit,
                after_seq=after_seq,
                next_after_seq=next_after_seq,
                total=total,
                has_more=has_more,
            ),
        )

    def trades(
        self,
        *,
        after_seq: int,
        limit: int,
        exit_reason: str | None,
        side: str | None,
        liquidated: bool | None,
        entry_time_from: int | None,
        entry_time_to: int | None,
    ) -> EvidenceCollection[Trade]:
        decimal_columns = {
            "entry_price",
            "entry_quantity",
            "exit_price",
            "exit_quantity",
            "gross_pnl",
            "total_fee",
            "slippage",
            "liquidation_penalty",
            "funding_cost",
            "net_pnl",
            "r0",
        }

        def decode(row: dict[str, Any]) -> dict[str, Any]:
            for column in decimal_columns:
                if row[column] is not None:
                    row[column] = _decimal_string(row[column])
            for column in ("entry_time", "exit_time"):
                if row[column] is not None:
                    row[column] = _iso8601(row[column])
            row["liquidated"] = _boolean(row["liquidated"])
            return row

        return self._collection(
            table="TRADE",
            cursor_column="trade_id",
            model=Trade,
            decoder=decode,
            after_seq=after_seq,
            limit=limit,
            filters=(
                ("exit_reason = ?", exit_reason),
                ("side = ?", side),
                ("liquidated = ?", int(liquidated) if liquidated is not None else None),
                ("entry_time >= ?", entry_time_from),
                ("entry_time <= ?", entry_time_to),
            ),
        )

    def executions(
        self,
        *,
        after_seq: int,
        limit: int,
        trade_id: int | None,
    ) -> EvidenceCollection[Execution]:
        decimal_columns = {
            "reference_price",
            "price",
            "quantity",
            "notional",
            "fee",
            "slippage",
        }

        def decode(row: dict[str, Any]) -> dict[str, Any]:
            for column in decimal_columns:
                row[column] = _decimal_string(row[column])
            for column in ("execution_ts", "trigger_subcandle_ts"):
                if row[column] is not None:
                    row[column] = _iso8601(row[column])
            for column in ("reduce_only", "gap_filled", "qty_truncated"):
                row[column] = _boolean(row[column])
            return row

        return self._collection(
            table="EXECUTION AS e",
            cursor_column="e.execution_id",
            model=Execution,
            decoder=decode,
            after_seq=after_seq,
            limit=limit,
            filters=(("t.trade_id = ?", trade_id),),
            select="e.*, t.trade_id AS trade_id",
            joins="""
                LEFT JOIN (
                    SELECT execution_id, MIN(trade_id) AS trade_id
                    FROM (
                        SELECT entry_execution_id AS execution_id, trade_id
                        FROM TRADE
                        UNION ALL
                        SELECT exit_execution_id AS execution_id, trade_id
                        FROM TRADE
                        WHERE exit_execution_id IS NOT NULL
                    ) AS execution_trade_links
                    GROUP BY execution_id
                ) AS t ON t.execution_id = e.execution_id
            """,
        )

    def funding_settlements(
        self,
        *,
        after_seq: int,
        limit: int,
        trade_id: int | None,
    ) -> EvidenceCollection[FundingSettlement]:
        decimal_columns = {
            "settle_price",
            "position_notional",
            "payment_amount",
            "theoretical_payment_amount",
        }

        def decode(row: dict[str, Any]) -> dict[str, Any]:
            for column in decimal_columns:
                row[column] = _decimal_string(row[column])
            row["settled_at"] = _iso8601(row["settled_at"])
            return row

        return self._collection(
            table="FUNDING_SETTLEMENT",
            cursor_column="settlement_id",
            model=FundingSettlement,
            decoder=decode,
            after_seq=after_seq,
            limit=limit,
            filters=(("trade_id = ?", trade_id),),
        )

    def equity(
        self,
        *,
        after_seq: int,
        limit: int,
    ) -> EvidenceCollection[EquityPoint]:
        decimal_columns = {
            "cash_balance",
            "position_value",
            "total_equity",
            "intrabar_low_equity",
            "realized_pnl_cum",
            "unrealized_pnl",
            "fee_cum",
            "slippage_cum",
            "funding_cum",
            "peak_equity",
        }

        def decode(row: dict[str, Any]) -> dict[str, Any]:
            for column in decimal_columns:
                if row[column] is not None:
                    row[column] = _decimal_string(row[column])
            row["ts"] = _iso8601(row["ts"])
            return row

        return self._collection(
            table="PORTFOLIO_PNL",
            cursor_column="equity_seq",
            model=EquityPoint,
            decoder=decode,
            after_seq=after_seq,
            limit=limit,
        )

    def chart_summaries(
        self,
        *,
        after_seq: int,
        limit: int,
        series_name: str | None,
    ) -> EvidenceCollection[ChartSummary]:
        def decode(row: dict[str, Any]) -> dict[str, Any]:
            row["bucket_ts"] = _iso8601(row["bucket_ts"])
            row["payload_json"] = _json_value(row["payload_json"])
            return row

        return self._collection(
            table="CHART_SUMMARY",
            cursor_column="summary_seq",
            model=ChartSummary,
            decoder=decode,
            after_seq=after_seq,
            limit=limit,
            filters=(("series_name = ?", series_name),),
        )

    def positions(
        self,
        *,
        after_seq: int,
        limit: int,
        trade_id: int | None,
    ) -> EvidenceCollection[Position]:
        decimal_columns = {
            "quantity",
            "average_price",
            "total_cost",
            "current_price",
            "mark_price",
            "unrealized_pnl",
            "margin",
            "entry_price",
            "liquidation_price",
            "funding_fee_total",
        }

        def decode(row: dict[str, Any]) -> dict[str, Any]:
            for column in decimal_columns:
                if row[column] is not None:
                    row[column] = _decimal_string(row[column])
            row["ts"] = _iso8601(row["ts"])
            return row

        return self._collection(
            table="POSITION",
            cursor_column="position_seq",
            model=Position,
            decoder=decode,
            after_seq=after_seq,
            limit=limit,
            filters=(("trade_id = ?", trade_id),),
        )

    def integrity_checks(
        self,
        *,
        after_seq: int,
        limit: int,
    ) -> EvidenceCollection[IntegrityCheck]:
        def decode(row: dict[str, Any]) -> dict[str, Any]:
            row["passed"] = _boolean(row["passed"])
            row["detail_json"] = _json_value(row["detail_json"])
            row["checked_at"] = _iso8601(row["checked_at"])
            return row

        return self._collection(
            table="INTEGRITY_CHECK",
            cursor_column="check_id",
            model=IntegrityCheck,
            decoder=decode,
            after_seq=after_seq,
            limit=limit,
        )

    def outcome_buckets(
        self,
        *,
        after_seq: int,
        limit: int,
        subject_kind: str | None,
        subject_id: int | None,
        bucket_name: str | None,
    ) -> EvidenceCollection[OutcomeBucket]:
        return self._collection(
            table="OUTCOME_BUCKET",
            cursor_column="bucket_id",
            model=OutcomeBucket,
            decoder=lambda row: row,
            after_seq=after_seq,
            limit=limit,
            filters=(
                ("subject_kind = ?", subject_kind),
                ("subject_id = ?", subject_id),
                ("bucket_name = ?", bucket_name),
            ),
        )

    def drawdown_episodes(
        self,
        *,
        after_seq: int,
        limit: int,
        kind: str | None,
    ) -> EvidenceCollection[DrawdownEpisode]:
        def decode(row: dict[str, Any]) -> dict[str, Any]:
            for column in ("start_ts", "end_ts", "recovery_ts"):
                if row[column] is not None:
                    row[column] = _iso8601(row[column])
            for column in ("peak_equity", "trough_equity"):
                row[column] = _decimal_string(row[column])
            row["contributing_trades_json"] = _json_value(row["contributing_trades_json"])
            return row

        return self._collection(
            table="DRAWDOWN_RUNUP_EPISODE",
            cursor_column="episode_id",
            model=DrawdownEpisode,
            decoder=decode,
            after_seq=after_seq,
            limit=limit,
            filters=(("kind = ?", kind),),
        )

    def trade_features(
        self,
        *,
        after_seq: int,
        limit: int,
        trade_id: int | None,
        phase: str | None,
    ) -> EvidenceCollection[TradeFeature]:
        def decode(row: dict[str, Any]) -> dict[str, Any]:
            row["ts"] = _iso8601(row["ts"])
            row["features_json"] = _json_value(row["features_json"])
            return row

        return self._collection(
            table="TRADE_FEATURE_SNAPSHOT",
            cursor_column="tfs_id",
            model=TradeFeature,
            decoder=decode,
            after_seq=after_seq,
            limit=limit,
            filters=(("trade_id = ?", trade_id), ("phase = ?", phase)),
        )

    def candidate_events(
        self,
        *,
        after_seq: int,
        limit: int,
        linked_trade_id: int | None,
        realized: bool | None,
    ) -> EvidenceCollection[CandidateEvent]:
        def decode(row: dict[str, Any]) -> dict[str, Any]:
            row["ts"] = _iso8601(row["ts"])
            row["passed_filters_json"] = _json_value(row["passed_filters_json"])
            if row["would_be_qty"] is not None:
                row["would_be_qty"] = _decimal_string(row["would_be_qty"])
            row["realized"] = _boolean(row["realized"])
            return row

        return self._collection(
            table="CANDIDATE_EVENT",
            cursor_column="candidate_id",
            model=CandidateEvent,
            decoder=decode,
            after_seq=after_seq,
            limit=limit,
            filters=(
                ("linked_trade_id = ?", linked_trade_id),
                ("realized = ?", int(realized) if realized is not None else None),
            ),
        )
