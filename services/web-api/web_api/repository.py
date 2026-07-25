"""SQL repository for P0 catalog reads."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from web_api.database import CatalogConnection, get_settings
from web_api.models import (
    CatalogHealth,
    HealthResponse,
    Page,
    RunHeader,
    RunListItem,
    RunListResponse,
    RunSummary,
    RunSummaryResponse,
    SummaryStatus,
)

RUN_HEADER_COLUMNS = """
    run_id, run_seq, run_name, status, strategy_id, strategy_name,
    strategy_version, params_json, params_schema_version, symbol, exchange,
    timeframe, market_type, period_start, period_end, warmup_start,
    warmup_candles, data_source, indicator_mode, trigger_feed, fill_timing,
    initial_capital, sizing_method, risk_per_trade, position_size_pct,
    framework_compliant, cost_values_json, seed, engine_version,
    core_lib_version, config_hash, profile_ref, strategy_profile_json,
    envelope_status_declared, sweep_id, fold_label, evidence_path,
    evidence_hash, evidence_retained, evidence_expires_at, error_message,
    started_at, finished_at, created_at, resolved_indicators_json,
    source_data_hash
"""

RUN_LIST_COLUMNS = """
    r.run_id, r.run_name, r.status, r.strategy_id, r.strategy_name,
    r.symbol, r.exchange, r.timeframe, r.market_type, r.period_start,
    r.period_end, r.created_at, r.sweep_id, r.config_hash,
    s.trade_count, s.pf, s.sortino, s.calmar_or_mar, s.sqn, s.mdd, s.ror,
    s.win_rate, s.net_pnl_total, s.gate_verdict, s.decision_route,
    s.integrity_status, s.data_coverage_ratio,
    (s.run_id IS NOT NULL) AS summary_present
"""

RUN_SUMMARY_COLUMNS = """
    run_id, trade_count, win_count, loss_count, r_excluded_count, pf,
    sortino, calmar_or_mar, calmar_basis, sqn, mdd, ror, sharpe, win_rate,
    payoff, expectancy_r, ulcer, kelly, annualization, initial_capital,
    final_equity, net_pnl_total, gross_pnl_total, total_fee, total_slippage,
    total_funding, total_liquidation_penalty, integrity_passed,
    integrity_status, integrity_failed_json, gate_passed, gate_stage,
    gate_verdict, gate_failed_json, envelope_result, envelope_deviated_json,
    decision_route, decision_rationale, oos_degradation, psr, harness_json,
    computed_at, expected_candle_count, observed_candle_count,
    source_absent_gap_count, partial_bucket_count, data_coverage_ratio,
    max_consecutive_gap_bars, max_consecutive_gap_seconds,
    data_coverage_passed, unobservable_funding_boundary_count,
    data_gap_exit_count
"""

SORT_COLUMNS = {
    "created_at": "r.created_at",
    "pf": "s.pf",
    "sortino": "s.sortino",
    "net_pnl_total": "s.net_pnl_total",
}

DECIMAL_COLUMNS = {
    "initial_capital",
    "risk_per_trade",
    "position_size_pct",
    "final_equity",
    "net_pnl_total",
    "gross_pnl_total",
    "total_fee",
    "total_slippage",
    "total_funding",
    "total_liquidation_penalty",
}


class RunListQuery(BaseModel):
    strategy_id: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    exchange: str | None = None
    market_type: str | None = None
    status: str | None = None
    decision_route: str | None = None
    gate_passed: bool | None = None
    sweep_id: str | None = None
    config_hash: str | None = None
    created_at_from: datetime | None = None
    created_at_to: datetime | None = None
    period_start_from: datetime | None = None
    period_start_to: datetime | None = None
    period_end_from: datetime | None = None
    period_end_to: datetime | None = None
    sort: str = "-created_at"
    limit: int = 50
    offset: int = 0


def _decimal_strings(row: dict[str, Any]) -> dict[str, Any]:
    clean = dict(row)
    for column in DECIMAL_COLUMNS:
        value = clean.get(column)
        if isinstance(value, Decimal):
            clean[column] = format(value, "f")
    return clean


def _summary_status(run_status: str, summary_present: bool) -> SummaryStatus:
    if summary_present:
        return "available"
    if run_status == "RUNNING":
        return "pending"
    if run_status == "FAILED":
        return "failed"
    if run_status == "ORPHANED":
        return "orphaned"
    return "missing"


class CatalogRepository:
    """Catalog queries. Every connection is created with transaction read-only enabled."""

    def __init__(self, connection: CatalogConnection) -> None:
        self._connection = connection

    def list_runs(self, query: RunListQuery) -> RunListResponse:
        filters: list[str] = []
        params: list[object] = []
        equality_filters = {
            "strategy_id": "r.strategy_id",
            "symbol": "r.symbol",
            "timeframe": "r.timeframe",
            "exchange": "r.exchange",
            "market_type": "r.market_type",
            "status": "r.status",
            "decision_route": "s.decision_route",
            "gate_passed": "s.gate_passed",
            "sweep_id": "r.sweep_id",
            "config_hash": "r.config_hash",
        }
        values = query.model_dump()
        for field, column in equality_filters.items():
            value = values[field]
            if value is not None:
                filters.append(f"{column} = %s")
                params.append(value)

        range_filters = (
            ("created_at_from", "r.created_at", ">="),
            ("created_at_to", "r.created_at", "<="),
            ("period_start_from", "r.period_start", ">="),
            ("period_start_to", "r.period_start", "<="),
            ("period_end_from", "r.period_end", ">="),
            ("period_end_to", "r.period_end", "<="),
        )
        for field, column, operator in range_filters:
            value = values[field]
            if value is not None:
                filters.append(f"{column} {operator} %s")
                params.append(value)

        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        sort_name = query.sort.removeprefix("-")
        sort_column = SORT_COLUMNS.get(sort_name)
        if sort_column is None:
            allowed = ", ".join(SORT_COLUMNS)
            raise ValueError(f"sort must be one of: {allowed}, optionally prefixed by '-'")
        direction = "DESC" if query.sort.startswith("-") else "ASC"
        nulls = "NULLS LAST" if sort_name != "created_at" else ""

        count_sql = f"""
            SELECT count(*) AS total
            FROM public.backtest_run r
            LEFT JOIN public.backtest_summary s ON s.run_id = r.run_id
            {where}
            """
        total_row = self._connection.execute(count_sql, params).fetchone()
        total = int(total_row["total"]) if total_row is not None else 0

        data_sql = f"""
            SELECT {RUN_LIST_COLUMNS}
            FROM public.backtest_run r
            LEFT JOIN public.backtest_summary s ON s.run_id = r.run_id
            {where}
            ORDER BY {sort_column} {direction} {nulls}, r.run_seq DESC
            LIMIT %s OFFSET %s
            """
        rows = self._connection.execute(data_sql, [*params, query.limit, query.offset]).fetchall()
        data = [RunListItem.model_validate(_decimal_strings(row)) for row in rows]
        return RunListResponse(
            data=data,
            page=Page(
                limit=query.limit,
                offset=query.offset,
                total=total,
                has_more=query.offset + len(data) < total,
            ),
        )

    def get_run(self, run_id: str) -> RunHeader | None:
        query = f"SELECT {RUN_HEADER_COLUMNS} FROM public.backtest_run WHERE run_id = %s"
        row = self._connection.execute(query, (run_id,)).fetchone()
        return RunHeader.model_validate(_decimal_strings(row)) if row is not None else None

    def get_summary(self, run_id: str) -> RunSummaryResponse | None:
        run_row = self._connection.execute(
            "SELECT status FROM public.backtest_run WHERE run_id = %s",
            (run_id,),
        ).fetchone()
        if run_row is None:
            return None
        summary_query = (
            f"SELECT {RUN_SUMMARY_COLUMNS} FROM public.backtest_summary WHERE run_id = %s"
        )
        summary_row = self._connection.execute(summary_query, (run_id,)).fetchone()
        status = str(run_row["status"])
        summary = (
            RunSummary.model_validate(_decimal_strings(summary_row))
            if summary_row is not None
            else None
        )
        return RunSummaryResponse(
            run_id=run_id,
            run_status=status,
            summary_status=_summary_status(status, summary is not None),
            summary=summary,
        )

    def get_evidence_path(self, run_id: str) -> tuple[bool, str | None]:
        row = self._connection.execute(
            "SELECT evidence_path FROM public.backtest_run WHERE run_id = %s",
            (run_id,),
        ).fetchone()
        if row is None:
            return False, None
        value = row["evidence_path"]
        return True, str(value) if value is not None else None

    def health(self, *, core_lib_version: str, web_api_version: str) -> HealthResponse:
        probe = self._connection.execute(
            """
            SELECT
                current_setting('transaction_read_only') AS transaction_read_only,
                (SELECT count(*) FROM public.backtest_run) AS run_count,
                EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'backtest_run'
                      AND column_name = 'source_data_hash'
                ) AS current_run_schema,
                EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'backtest_summary'
                      AND column_name = 'data_coverage_ratio'
                ) AS current_summary_schema
            """
        ).fetchone()
        if probe is None:
            raise RuntimeError("catalog health query returned no row")
        schema_version = (
            "20260724"
            if bool(probe["current_run_schema"]) and bool(probe["current_summary_schema"])
            else None
        )
        return HealthResponse(
            status="ok",
            catalog=CatalogHealth(
                status="connected",
                database=get_settings().database,
                read_only=str(probe["transaction_read_only"]) == "on",
                run_count=int(probe["run_count"]),
                schema_version=schema_version,
            ),
            core_lib_version=core_lib_version,
            web_api_version=web_api_version,
        )
