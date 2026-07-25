"""Persist lightweight run metadata while PostgreSQL alone issues run identifiers."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from core_lib.ports import CatalogStore

from .evidence_schema import _plain_decimal, _plain_shortest_float, canonical_json
from .evidence_sink import epoch_milliseconds

_RUN_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_RUN_NAME_MAX_LENGTH = 24
_CONFIG_HASH_FIELDS = (
    "strategy_id",
    "strategy_version",
    "params_json",
    "resolved_indicators_json",
    "params_schema_version",
    "symbol",
    "exchange",
    "timeframe",
    "market_type",
    "period_start",
    "period_end",
    "data_source",
    "indicator_mode",
    "trigger_feed",
    "fill_timing",
    "initial_capital",
    "sizing_method",
    "risk_per_trade",
    "position_size_pct",
    "cost_values_json",
    "seed",
    "engine_version",
    "core_lib_version",
)
_RUN_INSERT_FIELDS = (
    "run_name",
    "strategy_id",
    "strategy_name",
    "strategy_version",
    "params_json",
    "resolved_indicators_json",
    "params_schema_version",
    "symbol",
    "exchange",
    "timeframe",
    "market_type",
    "period_start",
    "period_end",
    "warmup_start",
    "warmup_candles",
    "data_source",
    "indicator_mode",
    "trigger_feed",
    "fill_timing",
    "initial_capital",
    "sizing_method",
    "risk_per_trade",
    "position_size_pct",
    "framework_compliant",
    "cost_values_json",
    "seed",
    "engine_version",
    "core_lib_version",
    "config_hash",
    "profile_ref",
    "strategy_profile_json",
    "envelope_status_declared",
    "sweep_id",
    "fold_label",
)
_SUMMARY_FIELDS = (
    "run_id",
    "trade_count",
    "win_count",
    "loss_count",
    "r_excluded_count",
    "pf",
    "sortino",
    "calmar_or_mar",
    "calmar_basis",
    "sqn",
    "mdd",
    "ror",
    "sharpe",
    "win_rate",
    "payoff",
    "expectancy_r",
    "ulcer",
    "kelly",
    "annualization",
    "initial_capital",
    "final_equity",
    "net_pnl_total",
    "gross_pnl_total",
    "total_fee",
    "total_slippage",
    "total_funding",
    "total_liquidation_penalty",
    "expected_candle_count",
    "observed_candle_count",
    "source_absent_gap_count",
    "partial_bucket_count",
    "data_coverage_ratio",
    "max_consecutive_gap_bars",
    "max_consecutive_gap_seconds",
    "data_coverage_passed",
    "unobservable_funding_boundary_count",
    "data_gap_exit_count",
    "integrity_passed",
    "integrity_status",
    "integrity_failed_json",
    "gate_passed",
    "gate_stage",
    "gate_verdict",
    "gate_failed_json",
    "envelope_result",
    "envelope_deviated_json",
    "decision_route",
    "decision_rationale",
    "oos_degradation",
    "psr",
    "harness_json",
)
_JSON_FIELDS = frozenset(
    {
        "params_json",
        "resolved_indicators_json",
        "cost_values_json",
        "strategy_profile_json",
        "integrity_failed_json",
        "gate_failed_json",
        "envelope_deviated_json",
        "harness_json",
        "success_criteria_json",
        "failure_criteria_json",
    }
)


class QueryResult(Protocol):
    """The result surface shared by psycopg cursors and deterministic stubs."""

    def fetchone(self) -> Sequence[object] | None:
        """Return one selected row."""


class WriteConnection(Protocol):
    """The transactional execute surface required from the backtest_db driver."""

    def execute(
        self,
        query: str,
        params: Sequence[object] = (),
    ) -> QueryResult:
        """Execute one parameterized statement."""

    def commit(self) -> None:
        """Commit the current transaction."""

    def rollback(self) -> None:
        """Roll back the current transaction."""


@dataclass(frozen=True, slots=True)
class DeterminismReference:
    """Catalog facts needed for one cross-run deterministic comparison."""

    catalog_config_matches: bool
    catalog_source_matches: bool
    same_config_run_exists: bool
    comparison_run_id: str | None
    comparison_hash: str | None


def _mapping(value: object, *, name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise TypeError(f"{name} keys must be strings")
    return dict(value)


def _json_text(value: object, *, name: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping | Sequence) and not isinstance(
        value,
        str | bytes | bytearray,
    ):
        return canonical_json(value)
    raise TypeError(f"{name} must be JSON text, a mapping, or a sequence")


def _hash_scalar(value: object, *, json_field: bool = False) -> bytes:
    if value is None:
        return b"\x00"
    if json_field:
        return _json_text(value, name="config JSON").encode("utf-8")
    if isinstance(value, bool):
        return str(int(value)).encode()
    if isinstance(value, int):
        return str(value).encode()
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("config hash values must be finite")
        return _plain_shortest_float(value).encode()
    if isinstance(value, Decimal):
        return _plain_decimal(value).encode()
    if isinstance(value, datetime):
        return str(epoch_milliseconds(value)).encode()
    if isinstance(value, str):
        return value.encode("utf-8")
    raise TypeError(f"unsupported config hash value: {type(value).__name__}")


def normalized_config_hash(run_meta: Mapping[str, object]) -> str:
    """Hash the exact ordered §5.2.2 reproducibility inputs."""
    missing = set(_CONFIG_HASH_FIELDS) - set(run_meta)
    if missing:
        raise ValueError(f"run metadata missing config hash fields: {sorted(missing)}")
    values = [
        _hash_scalar(
            run_meta[field],
            json_field=field in {"params_json", "resolved_indicators_json", "cost_values_json"},
        )
        for field in _CONFIG_HASH_FIELDS
    ]
    return hashlib.sha256(b"\x1f".join(values)).hexdigest()


def _database_value(name: str, value: object) -> object:
    if name in _JSON_FIELDS and value is not None:
        return _json_text(value, name=name)
    if isinstance(value, str | int | float | bool | Decimal | datetime) or value is None:
        return value
    raise TypeError(f"unsupported catalog value for {name}: {type(value).__name__}")


def validate_catalog_run_name(run_name: object) -> str:
    """Return a catalog-safe run name or raise the canonical contract error."""

    if (
        not isinstance(run_name, str)
        or len(run_name) > _RUN_NAME_MAX_LENGTH
        or _RUN_NAME.fullmatch(run_name) is None
    ):
        raise ValueError("run_name must be at most 24 lowercase kebab-case characters")
    return run_name


class BacktestCatalogStore(CatalogStore):
    """Write only the four backtest_db catalog entities behind the CatalogStore port."""

    def __init__(self, connection: WriteConnection) -> None:
        self._connection = connection

    def register(self, run: object) -> str:
        """Atomically issue run_seq, assemble run_id, and open the RUNNING header."""
        meta = _mapping(run, name="run metadata")
        missing = set(_RUN_INSERT_FIELDS) - set(meta)
        if missing:
            raise ValueError(f"run metadata missing fields: {sorted(missing)}")
        run_name = validate_catalog_run_name(meta["run_name"])
        expected_hash = normalized_config_hash(meta)
        supplied_hash = meta["config_hash"]
        if supplied_hash != expected_hash:
            raise ValueError("config_hash does not match normalized run metadata")
        params = tuple(_database_value(field, meta[field]) for field in _RUN_INSERT_FIELDS)
        placeholders = ", ".join("%s" for _ in _RUN_INSERT_FIELDS)
        columns = ", ".join(_RUN_INSERT_FIELDS)
        sql = f"""
        WITH issued AS (
            SELECT
                nextval('public.backtest_run_seq') AS run_seq,
                to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYYMMDD') AS utc_day
        ),
        named AS (
            SELECT
                run_seq,
                'BT_' || utc_day || '_' ||
                lpad(run_seq::text, greatest(6, length(run_seq::text)), '0') ||
                '_' || %s AS run_id
            FROM issued
        )
        INSERT INTO public.backtest_run (
            run_id, run_seq, {columns}, evidence_path
        )
        SELECT
            named.run_id, named.run_seq, {placeholders}, named.run_id || '.sqlite'
        FROM named
        RETURNING run_id
        """
        try:
            row = self._connection.execute(sql, (run_name, *params)).fetchone()
            if row is None or not isinstance(row[0], str):
                raise RuntimeError("backtest_db did not return a run_id")
            self._connection.commit()
            return row[0]
        except Exception:
            self._connection.rollback()
            raise

    def save_prereg(self, prereg: object) -> None:
        """Insert and lock one preregistration before the first Engine decision."""
        values = _mapping(prereg, name="preregistration")
        required = {
            "run_id",
            "hypothesis",
            "primary_metric",
            "success_criteria_json",
            "profile_update_declared",
            "declared_by",
            "declared_at",
        }
        missing = required - set(values)
        if missing:
            raise ValueError(f"preregistration missing fields: {sorted(missing)}")
        fields = (
            "run_id",
            "hypothesis",
            "weakness_addressed",
            "primary_metric",
            "success_criteria_json",
            "failure_criteria_json",
            "profile_update_declared",
            "related_finding_ref",
            "declared_by",
            "declared_at",
        )
        params = tuple(_database_value(field, values.get(field)) for field in fields)
        try:
            self._connection.execute(
                f"""
                INSERT INTO public.backtest_prereg ({", ".join(fields)}, locked_at)
                VALUES ({", ".join("%s" for _ in fields)}, CURRENT_TIMESTAMP)
                """,
                params,
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def upsert_summary(self, summary: object) -> None:
        """Upsert final metadata and move the corresponding run to EVALUATED."""
        values = _mapping(summary, name="run summary")
        required = {
            "run_id",
            "trade_count",
            "win_count",
            "loss_count",
            "r_excluded_count",
            "initial_capital",
            "integrity_passed",
            "integrity_status",
            "evidence_hash",
        }
        missing = required - set(values)
        if missing:
            raise ValueError(f"run summary missing fields: {sorted(missing)}")
        fields = tuple(field for field in _SUMMARY_FIELDS if field in values)
        update_fields = tuple(field for field in fields if field != "run_id")
        params = tuple(_database_value(field, values[field]) for field in fields)
        update_clause = ", ".join(f"{field} = excluded.{field}" for field in update_fields)
        try:
            self._connection.execute(
                f"""
                INSERT INTO public.backtest_summary ({", ".join(fields)})
                VALUES ({", ".join("%s" for _ in fields)})
                ON CONFLICT (run_id) DO UPDATE SET {update_clause}
                """,
                params,
            )
            self._connection.execute(
                """
                UPDATE public.backtest_run
                SET status = 'EVALUATED',
                    evidence_hash = %s,
                    finished_at = CURRENT_TIMESTAMP,
                    evidence_expires_at = CASE
                        WHEN %s = 'promote'
                          OR envelope_status_declared = 'established'
                        THEN NULL
                        ELSE CURRENT_TIMESTAMP + INTERVAL '90 days'
                    END
                WHERE run_id = %s
                """,
                (
                    values["evidence_hash"],
                    values.get("decision_route"),
                    values["run_id"],
                ),
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def record_harness_aggregate(
        self,
        run_id: str,
        *,
        oos_degradation: float | None,
        psr: float | None,
        harness_json: object,
    ) -> None:
        """Stamp cross-run overfitting aggregates onto one representative summary."""
        params = (
            _database_value("oos_degradation", oos_degradation),
            _database_value("psr", psr),
            _database_value("harness_json", harness_json),
            run_id,
        )
        try:
            row = self._connection.execute(
                """
                UPDATE public.backtest_summary
                SET oos_degradation = %s,
                    psr = %s,
                    harness_json = %s
                WHERE run_id = %s
                RETURNING run_id
                """,
                params,
            ).fetchone()
            if row is None:
                raise RuntimeError("representative run summary is absent for harness aggregate")
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def determinism_reference(
        self,
        run_id: str,
        config_hash: str,
        source_data_hash: str,
    ) -> DeterminismReference:
        """Persist the source key and find the latest same-config, same-source run."""
        if (
            len(source_data_hash) != 64
            or source_data_hash.lower() != source_data_hash
            or any(character not in "0123456789abcdef" for character in source_data_hash)
        ):
            raise ValueError("source_data_hash must be lowercase SHA-256 hex")
        try:
            current = self._connection.execute(
                """
                UPDATE public.backtest_run
                SET source_data_hash = %s
                WHERE run_id = %s
                  AND (
                      source_data_hash IS NULL
                      OR source_data_hash = %s
                  )
                RETURNING config_hash, source_data_hash
                """,
                (source_data_hash, run_id, source_data_hash),
            ).fetchone()
            current_config_matches = current is not None and current[0] == config_hash
            current_source_matches = current is not None and current[1] == source_data_hash
            previous = self._connection.execute(
                """
                SELECT run_id, evidence_hash
                FROM public.backtest_run
                WHERE config_hash = %s
                  AND source_data_hash = %s
                  AND run_id <> %s
                  AND evidence_hash IS NOT NULL
                  AND status IN ('COMPLETED', 'EVALUATED')
                ORDER BY finished_at DESC NULLS LAST, run_seq DESC
                LIMIT 1
                """,
                (config_hash, source_data_hash, run_id),
            ).fetchone()
            same_config = self._connection.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM public.backtest_run
                    WHERE config_hash = %s
                      AND run_id <> %s
                      AND evidence_hash IS NOT NULL
                      AND status IN ('COMPLETED', 'EVALUATED')
                )
                """,
                (config_hash, run_id),
            ).fetchone()
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        same_config_run_exists = bool(same_config is not None and same_config[0])
        if previous is None:
            return DeterminismReference(
                current_config_matches,
                current_source_matches,
                same_config_run_exists,
                None,
                None,
            )
        previous_run_id, previous_hash = previous
        if not isinstance(previous_run_id, str) or not isinstance(previous_hash, str):
            raise TypeError("catalog determinism reference has invalid value types")
        return DeterminismReference(
            current_config_matches,
            current_source_matches,
            same_config_run_exists,
            previous_run_id,
            previous_hash,
        )

    def reconcile_orphaned(self) -> int:
        """Mark unfinished, unhashed RUNNING rows as ORPHANED without deleting them."""
        try:
            result = self._connection.execute(
                """
                UPDATE public.backtest_run
                SET status = 'ORPHANED',
                    error_message = coalesce(
                        error_message,
                        'registered run did not reach Evidence finalize'
                    ),
                    finished_at = coalesce(finished_at, CURRENT_TIMESTAMP),
                    evidence_expires_at = coalesce(
                        evidence_expires_at,
                        CURRENT_TIMESTAMP + INTERVAL '90 days'
                    )
                WHERE status = 'RUNNING' AND evidence_hash IS NULL
                RETURNING run_id
                """
            )
            count = 0
            while result.fetchone() is not None:
                count += 1
            self._connection.commit()
            return count
        except Exception:
            self._connection.rollback()
            raise


__all__ = [
    "BacktestCatalogStore",
    "DeterminismReference",
    "WriteConnection",
    "normalized_config_hash",
]
