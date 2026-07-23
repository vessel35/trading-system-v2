"""Write normalized, self-contained Evidence and derive its deterministic hash."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Final

from core_lib.ports import EvidenceSink

from .evidence_schema import (
    ENTITY_SORT_KEYS,
    EVAL_DECISION_KEYS,
    EVIDENCE_SCHEMA_VERSION,
    EVIDENCE_TABLES,
    HASH_EXCLUDED_COLUMNS,
    HASH_EXCLUDED_TABLES,
    HASH_GLOBAL_EXCLUDED_COLUMNS,
    HASH_TABLES,
    INTEGRITY_CHECK_NAMES,
    TIMESTAMP_ORDER_AUDIT_SQL,
    _plain_shortest_float,
    canonical_json,
    initialize_evidence_schema,
    scale_decimal,
)

_US: Final = b"\x1f"
_RS: Final = b"\x1e"
_GS: Final = b"\x1d"
_NUL: Final = b"\x00"


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """One schema-owned Evidence entity and its declared column values."""

    table: str
    values: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class _Episode:
    kind: str
    start_ts: int
    end_ts: int
    recovery_ts: int | None
    peak_equity: int
    trough_equity: int
    depth_pct: float


def epoch_milliseconds(value: datetime) -> int:
    """Return an aware timestamp as a deterministic UTC epoch-millisecond integer."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Evidence timestamps must be timezone-aware")
    normalized = value.astimezone(UTC)
    return int(normalized.timestamp() * 1_000)


def _record_parts(entity: object) -> tuple[str, Mapping[str, object]]:
    if isinstance(entity, EvidenceRecord):
        return entity.table, entity.values
    if isinstance(entity, Mapping):
        table = entity.get("table")
        values = entity.get("values")
        if isinstance(table, str) and isinstance(values, Mapping):
            if any(not isinstance(key, str) for key in values):
                raise TypeError("Evidence column names must be strings")
            return table, values
    raise TypeError("Evidence entities must be EvidenceRecord or {table, values} mappings")


def _normalize_value(column: str, value: object) -> object:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, datetime):
        return epoch_milliseconds(value)
    if isinstance(value, Decimal):
        return scale_decimal(value)
    if isinstance(value, Enum):
        return value.value
    if column.endswith("_json") and isinstance(value, Mapping | Sequence):
        if isinstance(value, str | bytes | bytearray):
            return value
        return canonical_json(value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"Evidence REAL column {column} must be finite")
    if isinstance(value, str | int | float | bytes):
        return value
    raise TypeError(f"unsupported Evidence value for {column}: {type(value).__name__}")


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _serialize_value(value: object) -> bytes:
    if value is None:
        return _NUL
    if isinstance(value, bool):
        return str(int(value)).encode()
    if isinstance(value, int):
        return str(value).encode()
    if isinstance(value, float):
        return _plain_shortest_float(value).encode()
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, bytes):
        return value
    raise TypeError(f"unsupported SQLite hash value: {type(value).__name__}")


class BacktestEvidenceSink(EvidenceSink):
    """Persist one run per SQLite file and hash normalized logical Evidence."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._path: Path | None = None
        self._connection: sqlite3.Connection | None = None
        self._run_id: str | None = None
        self._integrity: dict[str, bool] = {}

    @property
    def path(self) -> str | None:
        """Return the bound Evidence path, if any."""
        return None if self._path is None else str(self._path)

    @property
    def integrity_results(self) -> dict[str, bool]:
        """Return the last finalized integrity facts without exposing mutable state."""
        return dict(self._integrity)

    @property
    def connection(self) -> sqlite3.Connection:
        """Expose the bound connection for deterministic derivation and inspection."""
        if self._connection is None:
            raise RuntimeError("bind must be called before Evidence access")
        return self._connection

    def bind(self, run_id: str) -> str:
        """Open exactly ``<run_id>.sqlite`` after the catalog issued the identifier."""
        if not run_id or "/" in run_id or "\\" in run_id or run_id in {".", ".."}:
            raise ValueError("run_id must be a filename-safe catalog identifier")
        if self._connection is not None:
            raise RuntimeError("this Evidence sink is already bound")
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._root / f"{run_id}.sqlite"
        if path.exists():
            raise FileExistsError(path)
        connection = sqlite3.connect(path)
        try:
            initialize_evidence_schema(connection)
        except Exception:
            connection.close()
            raise
        self._path = path
        self._connection = connection
        self._run_id = run_id
        return str(path)

    def record(self, entity: object) -> None:
        """Normalize and insert one schema-declared entity."""
        table, raw_values = _record_parts(entity)
        if table not in EVIDENCE_TABLES:
            raise ValueError(f"unknown Evidence entity: {table}")
        if table in HASH_EXCLUDED_TABLES:
            raise PermissionError("FINDING_CLAIM is owned by the post-finalize analysis layer")
        values = dict(raw_values)
        if "run_id" not in values:
            values["run_id"] = self._require_run_id()
        if values["run_id"] != self._require_run_id():
            raise ValueError("an Evidence file cannot contain another run_id")
        declared = self._columns(table)
        unknown = set(values) - set(declared)
        if unknown:
            raise ValueError(f"{table} has unknown columns: {sorted(unknown)}")
        normalized = {name: _normalize_value(name, value) for name, value in values.items()}
        columns = tuple(normalized)
        placeholders = ", ".join("?" for _ in columns)
        sql = (
            f"INSERT INTO {_quote_identifier(table)} "
            f"({', '.join(_quote_identifier(name) for name in columns)}) "
            f"VALUES ({placeholders})"
        )
        self.connection.execute(sql, tuple(normalized[name] for name in columns))
        self.connection.commit()

    def set_eval_decision(self, eval_decision_json: str) -> None:
        """Store the canonical finalize decision before the final Evidence hash."""
        if not isinstance(eval_decision_json, str):
            raise TypeError("eval_decision_json must be canonical JSON text")
        parsed = json.loads(eval_decision_json)
        if not isinstance(parsed, dict) or set(parsed) != set(EVAL_DECISION_KEYS):
            raise ValueError("eval_decision_json must contain exactly the finalize keys")
        if canonical_json(parsed) != eval_decision_json:
            raise ValueError("eval_decision_json must use canonical JSON serialization")
        self.connection.execute(
            """
            UPDATE BACKTEST_RUN_LOCAL
            SET eval_decision_json = ?
            WHERE run_id = ?
            """,
            (eval_decision_json, self._require_run_id()),
        )
        self.connection.commit()

    def audit(self, *, require_eval_decision: bool = False) -> dict[str, bool]:
        """Compute the six standard integrity facts from persisted records."""
        connection = self.connection
        accounting_identity = connection.execute(
            """
            SELECT COUNT(*)
            FROM PORTFOLIO_PNL
            WHERE cash_balance + position_value <> total_equity
            """
        ).fetchone() == (0,)
        timestamp_order = connection.execute(TIMESTAMP_ORDER_AUDIT_SQL).fetchall() == []
        cost_once = connection.execute(
            """
            SELECT t.trade_id
            FROM TRADE AS t
            LEFT JOIN EXECUTION AS entry_e
                ON entry_e.execution_id = t.entry_execution_id
            LEFT JOIN EXECUTION AS exit_e
                ON exit_e.execution_id = t.exit_execution_id
            WHERE t.total_fee <> coalesce(entry_e.fee, 0) + coalesce(exit_e.fee, 0)
               OR t.slippage <> coalesce(entry_e.slippage, 0) + coalesce(exit_e.slippage, 0)
            ORDER BY t.trade_id
            """
        ).fetchall() == []
        net_of_cost = connection.execute(
            """
            SELECT trade_id
            FROM TRADE
            WHERE net_pnl IS NOT NULL
              AND net_pnl <> (
                  gross_pnl - total_fee - slippage
                  - funding_cost - liquidation_penalty
              )
            ORDER BY trade_id
            """
        ).fetchall() == []
        foreign_keys_clean = connection.execute("PRAGMA foreign_key_check").fetchall() == []
        local = connection.execute(
            """
            SELECT COUNT(*), min(eval_decision_json IS NOT NULL)
            FROM BACKTEST_RUN_LOCAL
            """
        ).fetchone()
        missing_signal_decisions = connection.execute(
            """
            SELECT s.signal_id
            FROM SIGNAL AS s
            LEFT JOIN DECISION AS d ON d.signal_id = s.signal_id
            WHERE s.is_warmup = 0 AND d.decision_id IS NULL
            ORDER BY s.signal_id
            """
        ).fetchall()
        missing_executions = connection.execute(
            """
            SELECT d.decision_id
            FROM DECISION AS d
            LEFT JOIN EXECUTION AS e ON e.decision_id = d.decision_id
            WHERE d.action <> 'skip' AND e.execution_id IS NULL
            ORDER BY d.decision_id
            """
        ).fetchall()
        has_grid = connection.execute("SELECT 1 FROM PORTFOLIO_PNL LIMIT 1").fetchone()
        evidence_complete = (
            foreign_keys_clean
            and local is not None
            and local[0] == 1
            and (not require_eval_decision or local[1] == 1)
            and not missing_signal_decisions
            and not missing_executions
            and has_grid is not None
        )
        return {
            "accounting_identity": accounting_identity,
            "timestamp_order": timestamp_order,
            "cost_once": cost_once,
            "net_of_cost": net_of_cost,
            "deterministic": True,
            "evidence_complete": evidence_complete,
        }

    def finalize(self, run_id: str) -> str:
        """Write deterministic derivations and checks, then hash the complete state."""
        if run_id != self._require_run_id():
            raise ValueError("finalize run_id does not match the bound Evidence file")
        self._derive_chart_summaries()
        self._derive_outcome_buckets()
        self._derive_drawdown_runup_episodes()
        results = self.audit(require_eval_decision=True)
        self._write_integrity_checks(results)
        first = self.normalized_bytes()
        second = self.normalized_bytes()
        results["deterministic"] = first == second
        if not results["deterministic"]:
            self._write_integrity_checks(results)
        final_bytes = self.normalized_bytes()
        self._integrity = results
        self.connection.commit()
        return hashlib.sha256(final_bytes).hexdigest()

    def normalized_bytes(self) -> bytes:
        """Serialize all hash-owned rows using the §5.3.1 separators and ordering."""
        groups: list[bytes] = []
        for table in HASH_TABLES:
            columns = [
                name
                for name in self._columns(table)
                if name not in HASH_GLOBAL_EXCLUDED_COLUMNS
                and name not in HASH_EXCLUDED_COLUMNS.get(table, frozenset())
            ]
            sort_keys = ENTITY_SORT_KEYS[table]
            sql = (
                f"SELECT {', '.join(_quote_identifier(name) for name in columns)} "
                f"FROM {_quote_identifier(table)} "
                f"ORDER BY {', '.join(_quote_identifier(name) for name in sort_keys)}"
            )
            rows = self.connection.execute(sql).fetchall()
            groups.append(
                _RS.join(_US.join(_serialize_value(value) for value in row) for row in rows)
            )
        return _GS.join(groups)

    def close(self) -> None:
        """Commit and close the bound SQLite connection."""
        if self._connection is not None:
            self._connection.commit()
            self._connection.close()
            self._connection = None

    def _derive_chart_summaries(self) -> None:
        rows = self.connection.execute(
            """
            SELECT equity_seq, run_id, ts, total_equity, drawdown_pct
            FROM PORTFOLIO_PNL
            ORDER BY ts, equity_seq
            """
        ).fetchall()
        for equity_seq, run_id, timestamp, equity, drawdown in rows:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO CHART_SUMMARY (
                    summary_seq, run_id, series_name, bucket_ts, value
                ) VALUES (?, ?, 'equity', ?, ?)
                """,
                (2 * equity_seq - 1, run_id, timestamp, float(Decimal(equity) / Decimal(10**8))),
            )
            self.connection.execute(
                """
                INSERT OR IGNORE INTO CHART_SUMMARY (
                    summary_seq, run_id, series_name, bucket_ts, value
                ) VALUES (?, ?, 'drawdown', ?, ?)
                """,
                (2 * equity_seq, run_id, timestamp, drawdown),
            )
        self.connection.commit()

    def _derive_outcome_buckets(self) -> None:
        trades = self.connection.execute(
            """
            SELECT trade_id, run_id, gross_pnl, net_pnl, r_multiple
            FROM TRADE
            WHERE net_pnl IS NOT NULL
            ORDER BY trade_id
            """
        ).fetchall()
        for trade_id, run_id, gross_pnl, net_pnl, r_multiple in trades:
            if gross_pnl > 0 and net_pnl <= 0:
                bucket = "cost_churn"
            elif r_multiple is not None and r_multiple >= 2.0:
                bucket = "top_winner"
            elif net_pnl > 0:
                bucket = "normal_winner"
            elif r_multiple is not None and r_multiple <= -1.0:
                bucket = "tail_loser"
            else:
                bucket = "small_loser"
            self.connection.execute(
                """
                INSERT OR IGNORE INTO OUTCOME_BUCKET (
                    bucket_id, run_id, subject_kind, subject_id,
                    bucket_name, bucket_value, r_multiple
                ) VALUES (?, ?, 'trade', ?, 'outcome_class', ?, ?)
                """,
                (trade_id, run_id, trade_id, bucket, r_multiple),
            )
        self.connection.commit()

    def _derive_drawdown_runup_episodes(self) -> None:
        rows = self.connection.execute(
            """
            SELECT ts, total_equity
            FROM PORTFOLIO_PNL
            ORDER BY ts, equity_seq
            """
        ).fetchall()
        if len(rows) < 2:
            return
        episodes = [
            *self._relative_episodes(rows, kind="drawdown"),
            *self._relative_episodes(rows, kind="runup"),
        ]
        episodes.sort(key=lambda row: (row.kind, row.start_ts))
        for episode_id, episode in enumerate(episodes, start=1):
            start_ts = episode.start_ts
            terminal_ts = episode.recovery_ts or episode.end_ts
            trade_ids = [
                int(row[0])
                for row in self.connection.execute(
                    """
                    SELECT trade_id
                    FROM TRADE
                    WHERE entry_time <= ? AND exit_time >= ?
                    ORDER BY trade_id
                    """,
                    (terminal_ts, start_ts),
                ).fetchall()
            ]
            self.connection.execute(
                """
                INSERT OR IGNORE INTO DRAWDOWN_RUNUP_EPISODE (
                    episode_id, run_id, kind, start_ts, end_ts, recovery_ts,
                    peak_equity, trough_equity, depth_pct, duration_seconds,
                    trade_count, contributing_trades_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode_id,
                    self._require_run_id(),
                    episode.kind,
                    start_ts,
                    episode.end_ts,
                    episode.recovery_ts,
                    episode.peak_equity,
                    episode.trough_equity,
                    episode.depth_pct,
                    max(0, (terminal_ts - start_ts) // 1_000),
                    len(trade_ids),
                    canonical_json(trade_ids),
                ),
            )
        self.connection.commit()

    @staticmethod
    def _relative_episodes(
        rows: Sequence[tuple[int, int]],
        *,
        kind: str,
    ) -> list[_Episode]:
        if kind not in {"drawdown", "runup"}:
            raise ValueError("episode kind must be drawdown or runup")
        episodes: list[_Episode] = []
        anchor_ts, anchor_equity = rows[0]
        extreme_ts, extreme_equity = anchor_ts, anchor_equity
        active = False
        for timestamp, equity in rows[1:]:
            moved_against_anchor = (
                equity < anchor_equity if kind == "drawdown" else equity > anchor_equity
            )
            recovered = (
                equity >= anchor_equity if kind == "drawdown" else equity <= anchor_equity
            )
            if not active and moved_against_anchor:
                active = True
                extreme_ts, extreme_equity = timestamp, equity
                continue
            if active:
                more_extreme = (
                    equity < extreme_equity if kind == "drawdown" else equity > extreme_equity
                )
                if more_extreme:
                    extreme_ts, extreme_equity = timestamp, equity
                if recovered:
                    episodes.append(
                        BacktestEvidenceSink._episode(
                            kind,
                            anchor_ts,
                            anchor_equity,
                            extreme_ts,
                            extreme_equity,
                            timestamp,
                        )
                    )
                    active = False
                    anchor_ts, anchor_equity = timestamp, equity
                    extreme_ts, extreme_equity = timestamp, equity
                    continue
            if not active:
                improves_anchor = (
                    equity > anchor_equity if kind == "drawdown" else equity < anchor_equity
                )
                if improves_anchor:
                    anchor_ts, anchor_equity = timestamp, equity
        if active:
            episodes.append(
                BacktestEvidenceSink._episode(
                    kind,
                    anchor_ts,
                    anchor_equity,
                    extreme_ts,
                    extreme_equity,
                    None,
                )
            )
        return episodes

    @staticmethod
    def _episode(
        kind: str,
        anchor_ts: int,
        anchor_equity: int,
        extreme_ts: int,
        extreme_equity: int,
        recovery_ts: int | None,
    ) -> _Episode:
        if extreme_ts <= anchor_ts:
            raise ValueError("episode extreme must occur after its anchor")
        if kind == "drawdown":
            peak, trough = anchor_equity, extreme_equity
            depth = extreme_equity / anchor_equity - 1.0
        else:
            peak, trough = extreme_equity, anchor_equity
            depth = extreme_equity / anchor_equity - 1.0
        return _Episode(
            kind=kind,
            start_ts=anchor_ts,
            end_ts=extreme_ts,
            recovery_ts=recovery_ts,
            peak_equity=peak,
            trough_equity=trough,
            depth_pct=depth,
        )

    def _write_integrity_checks(self, results: Mapping[str, bool]) -> None:
        if tuple(results) != INTEGRITY_CHECK_NAMES:
            raise ValueError("integrity results must use the six canonical keys in order")
        for check_id, name in enumerate(INTEGRITY_CHECK_NAMES, start=1):
            detail = canonical_json({"passed": results[name]})
            self.connection.execute(
                """
                INSERT INTO INTEGRITY_CHECK (
                    check_id, run_id, check_name, passed, detail_json
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id, check_name) DO UPDATE SET
                    passed = excluded.passed,
                    detail_json = excluded.detail_json
                """,
                (check_id, self._require_run_id(), name, int(results[name]), detail),
            )
        self.connection.commit()

    def _columns(self, table: str) -> tuple[str, ...]:
        rows = self.connection.execute(
            f"SELECT name FROM pragma_table_info({_quote_identifier(table)}) ORDER BY cid"
        ).fetchall()
        if not rows:
            raise RuntimeError(f"Evidence schema has no table {table}")
        return tuple(str(row[0]) for row in rows)

    def _require_run_id(self) -> str:
        if self._run_id is None:
            raise RuntimeError("bind must be called before Evidence writes")
        return self._run_id


__all__ = [
    "BacktestEvidenceSink",
    "EVIDENCE_SCHEMA_VERSION",
    "EvidenceRecord",
    "epoch_milliseconds",
    "initialize_evidence_schema",
]
