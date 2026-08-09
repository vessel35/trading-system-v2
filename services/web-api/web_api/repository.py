"""SQL repository for P0 catalog reads."""

import json
import logging
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Final, Literal, cast

from backtest_service.config.run_config import (
    SELECTABLE_MONEY_MANAGEMENT_MODES,
    freeze_money_management_config,
)
from core_lib.eval import thresholds
from core_lib.money_management import MoneyManagementBase, MoneyManagementFactory
from core_lib.strategy import AdapterClass, InProcessStrategyRegistry, StrategyConfig
from pydantic import BaseModel
from trading_plugins import registered_money_management

from web_api.database import CatalogConnection, CryptoConnection, SignalConnection, get_settings
from web_api.models import (
    BacktestTag,
    Candle,
    CandleCollection,
    CandlePage,
    CatalogHealth,
    DataSourceCoverage,
    DataSourceInventory,
    HealthResponse,
    InventoryItem,
    Page,
    Preregistration,
    PreregistrationResponse,
    RunComparisonItem,
    RunComparisonResponse,
    RunHeader,
    RunListItem,
    RunListResponse,
    RunSummary,
    RunSummaryResponse,
    RunTagsResponse,
    StrategyListResponse,
    StrategyOption,
    SummaryStatus,
    SweepResponse,
    TagFacet,
    TagFacetsResponse,
    TagFacetValue,
    TagType,
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
    source_data_hash, deleted_at
"""

RUN_LIST_COLUMNS = """
    r.run_id, r.run_name, r.status, r.strategy_id, r.strategy_name,
    r.symbol, r.exchange, r.timeframe, r.market_type, r.period_start,
    r.period_end, r.created_at, r.sweep_id, r.config_hash, r.deleted_at,
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

_LOGGER = logging.getLogger(__name__)

DeletedFilter = Literal["exclude", "only", "include"]


DELETED_FILTER_SQL: dict[DeletedFilter, str | None] = {
    "exclude": "r.deleted_at IS NULL",
    "only": "r.deleted_at IS NOT NULL",
    "include": None,
}

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
    tag_type: TagType | None = None
    tag_value: str | None = None
    created_at_from: datetime | None = None
    created_at_to: datetime | None = None
    period_start_from: datetime | None = None
    period_start_to: datetime | None = None
    period_end_from: datetime | None = None
    period_end_to: datetime | None = None
    deleted: DeletedFilter = "exclude"
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


def _selectable_modes(supported: Sequence[str]) -> list[str]:
    """Keep only the modes a run would actually accept.

    A policy can be registered and still be left out of the run configuration
    union, because its settings do not form a schema. Offering such a mode would
    show a choice that is refused the moment it is submitted.
    """
    return [mode for mode in supported if mode in SELECTABLE_MONEY_MANAGEMENT_MODES]


def _freeze_money_management_defaults(
    policies: Mapping[str, type[MoneyManagementBase]] | None = None,
    modes: Sequence[str] | None = None,
) -> Mapping[str, str]:
    """Build each selectable policy once and retain its strict JSON defaults.

    Model discovery and final-union assembly have already completed in
    ``run_config`` before this Web API module is imported. Default construction
    remains independent per mode: a bad default removes only that default, not
    the mode from the already accepted selectable set.
    """
    registered = registered_money_management() if policies is None else policies
    selectable = sorted(SELECTABLE_MONEY_MANAGEMENT_MODES if modes is None else modes)
    frozen: dict[str, str] = {}
    for mode in selectable:
        try:
            policy = MoneyManagementFactory.create({"mode": mode}, registered)
            resolved = dict(policy.resolved_config())
            frozen[mode] = freeze_money_management_config(resolved, expected_mode=mode)
        except (Exception, SystemExit):  # noqa: BLE001 - isolate one deployed default
            _LOGGER.exception("money-management mode %s has no valid default configuration", mode)
    return MappingProxyType(frozen)


_FROZEN_MONEY_MANAGEMENT_DEFAULTS: Final = _freeze_money_management_defaults()


def _default_money_management(mode: str | None) -> dict[str, object]:
    """Return a fresh JSON-native copy of the named policy's frozen defaults.

    The values used to be a fixed manual-shaped dictionary, which was wrong for
    Turtle and meaningless for a policy deployed as a file, since nothing here
    knows what settings such a policy has. The policy is asked once when this Web
    API module loads. Requests only parse retained JSON, so they cannot run a
    deployed constructor, validator, serializer, or registry lookup. Parsing on
    every call also prevents nested dictionaries or lists from being shared
    between responses.
    """
    if mode is None:
        return {}
    encoded = _FROZEN_MONEY_MANAGEMENT_DEFAULTS.get(mode)
    if encoded is None:
        return {}
    decoded = json.loads(encoded)
    if not isinstance(decoded, dict):
        raise TypeError("frozen money-management default must be a JSON object")
    return cast("dict[str, object]", decoded)


def _money_management_options(
    supported: Sequence[str],
    default: str | None,
) -> tuple[list[str], dict[str, object]]:
    """Project one consistent selectable-mode list and declared default."""
    modes = _selectable_modes(supported)
    if default not in modes:
        return modes, {}
    return modes, _default_money_management(default)


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
        deleted_filter = DELETED_FILTER_SQL[query.deleted]
        if deleted_filter is not None:
            filters.append(deleted_filter)
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

        if query.tag_type is not None or query.tag_value is not None:
            tag_filters = ["t.run_id = r.run_id"]
            if query.tag_type is not None:
                tag_filters.append("t.tag_type = %s")
                params.append(query.tag_type)
            if query.tag_value is not None:
                tag_filters.append("t.tag_value = %s")
                params.append(query.tag_value)
            filters.append(
                f"EXISTS (SELECT 1 FROM public.backtest_tag t WHERE {' AND '.join(tag_filters)})"
            )

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

    def get_prereg(self, run_id: str) -> PreregistrationResponse | None:
        exists = self._connection.execute(
            "SELECT 1 FROM public.backtest_run WHERE run_id = %s",
            (run_id,),
        ).fetchone()
        if exists is None:
            return None
        row = self._connection.execute(
            """
            SELECT run_id, hypothesis, weakness_addressed, primary_metric,
                   success_criteria_json, failure_criteria_json,
                   profile_update_declared, related_finding_ref, declared_by,
                   declared_at, locked_at
            FROM public.backtest_prereg
            WHERE run_id = %s
            """,
            (run_id,),
        ).fetchone()
        prereg = Preregistration.model_validate(row) if row is not None else None
        return PreregistrationResponse(run_id=run_id, prereg=prereg)

    def compare_runs(
        self,
        *,
        run_ids: list[str] | None,
        sweep_id: str | None,
    ) -> RunComparisonResponse:
        compared_by: Literal["run_ids", "sweep_id"] = (
            "run_ids" if run_ids is not None else "sweep_id"
        )
        selected_ids = run_ids
        if selected_ids is None:
            rows = self._connection.execute(
                """
                SELECT run_id
                FROM public.backtest_run
                WHERE sweep_id = %s
                ORDER BY run_seq
                """,
                (sweep_id,),
            ).fetchall()
            selected_ids = [str(row["run_id"]) for row in rows]

        items: list[RunComparisonItem] = []
        missing: list[str] = []
        for run_id in selected_ids:
            run = self.get_run(run_id)
            summary_response = self.get_summary(run_id)
            if run is None or summary_response is None:
                missing.append(run_id)
                continue
            items.append(
                RunComparisonItem(
                    run=run,
                    summary_status=summary_response.summary_status,
                    summary=summary_response.summary,
                )
            )
        if missing:
            raise KeyError(",".join(missing))
        return RunComparisonResponse(
            data=items,
            compared_by=compared_by,
            sweep_id=sweep_id,
        )

    def get_sweep(self, sweep_id: str) -> SweepResponse | None:
        comparison = self.compare_runs(run_ids=None, sweep_id=sweep_id)
        if not comparison.data:
            return None
        representative = next(
            (
                item
                for item in comparison.data
                if item.summary is not None and item.summary.harness_json is not None
            ),
            comparison.data[0],
        )
        summary = representative.summary
        overfit_limits = thresholds.overfit()
        return SweepResponse(
            sweep_id=sweep_id,
            representative_run_id=representative.run.run_id,
            runs=comparison.data,
            oos_degradation=summary.oos_degradation if summary is not None else None,
            psr=summary.psr if summary is not None else None,
            oos_degradation_limit=overfit_limits["oos_degradation_limit"],
            psr_minimum=overfit_limits["psr_minimum"],
            harness_json=summary.harness_json if summary is not None else None,
        )

    def get_tags(self, run_id: str) -> RunTagsResponse | None:
        exists = self._connection.execute(
            "SELECT 1 FROM public.backtest_run WHERE run_id = %s",
            (run_id,),
        ).fetchone()
        if exists is None:
            return None
        rows = self._connection.execute(
            """
            SELECT tag_id, run_id, tag_type, tag_value, created_at
            FROM public.backtest_tag
            WHERE run_id = %s
            ORDER BY tag_type, tag_value, tag_id
            """,
            (run_id,),
        ).fetchall()
        return RunTagsResponse(
            run_id=run_id,
            data=[BacktestTag.model_validate(row) for row in rows],
        )

    def get_tag(self, run_id: str, tag_type: TagType, tag_value: str) -> BacktestTag | None:
        row = self._connection.execute(
            """
            SELECT tag_id, run_id, tag_type, tag_value, created_at
            FROM public.backtest_tag
            WHERE run_id = %s AND tag_type = %s AND tag_value = %s
            """,
            (run_id, tag_type, tag_value),
        ).fetchone()
        return BacktestTag.model_validate(row) if row is not None else None

    def tag_facets(self) -> TagFacetsResponse:
        rows = self._connection.execute(
            """
            SELECT tag_type, tag_value, count(*) AS count
            FROM public.backtest_tag
            GROUP BY tag_type, tag_value
            ORDER BY tag_type, count(*) DESC, tag_value
            """
        ).fetchall()
        grouped: dict[TagType, list[TagFacetValue]] = {}
        for row in rows:
            tag_type = str(row["tag_type"])
            if tag_type not in {
                "classification",
                "purpose",
                "weakness",
                "improvement",
                "usability",
            }:
                continue
            typed_tag = cast(TagType, tag_type)
            grouped.setdefault(typed_tag, []).append(
                TagFacetValue(
                    tag_value=str(row["tag_value"]),
                    count=int(row["count"]),
                )
            )
        return TagFacetsResponse(
            data=[
                TagFacet(tag_type=tag_type, values=values) for tag_type, values in grouped.items()
            ]
        )

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


class StrategyRepository:
    """Read the signal-service registry, falling back to the in-process Adaptee."""

    def __init__(
        self,
        connection: SignalConnection,
        strategy_registry: InProcessStrategyRegistry,
    ) -> None:
        self._connection = connection
        self._strategy_registry = strategy_registry

    def list(self) -> StrategyListResponse:
        table = self._connection.execute(
            "SELECT to_regclass('public.strategy_registry') AS relation"
        ).fetchone()
        if table is not None and table["relation"] is not None:
            rows = self._connection.execute(
                """
                SELECT strategy_id, display_name, strategy_version,
                       supported_timeframes, required_indicators_json,
                       min_history, default_params_json, is_active, is_deprecated
                FROM public.strategy_registry
                ORDER BY strategy_id
                """
            ).fetchall()
            if rows:
                return StrategyListResponse(data=[self._database_option(row) for row in rows])
        return self._code_registry()

    def _database_option(self, row: Mapping[str, object]) -> StrategyOption:
        strategy_id = str(row["strategy_id"])
        try:
            strategy_class = self._strategy_registry.get(strategy_id)
        except KeyError:
            strategy_class = None
        metadata = None if strategy_class is None else strategy_class.get_metadata()
        support = None if metadata is None else metadata.money_management
        modes, default = (
            ([], {})
            if support is None
            else _money_management_options(
                support.supported,
                support.default,
            )
        )
        return StrategyOption(
            strategy_id=strategy_id,
            display_name=str(row["display_name"]),
            strategy_version=(
                str(getattr(strategy_class, "VERSION", row["strategy_version"]))
                if strategy_class is not None
                else str(row["strategy_version"])
            ),
            supported_timeframes=(
                list(metadata.supported_timeframes)
                if metadata is not None
                else list(cast(list[str], row["supported_timeframes"]))
            ),
            required_indicators=(
                metadata.required_indicators
                if metadata is not None
                else list(
                    cast(
                        list[dict[str, object]],
                        row["required_indicators_json"],
                    )
                )
            ),
            min_history=(
                metadata.min_history if metadata is not None else int(cast(int, row["min_history"]))
            ),
            default_params=(
                self._parameter_defaults(strategy_class)
                if strategy_class is not None
                else dict(cast(dict[str, object], row["default_params_json"]))
            ),
            supported_money_management=modes,
            default_money_management=default,
            is_active=bool(row["is_active"]),
            is_deprecated=bool(row["is_deprecated"]),
            source="strategy_registry",
        )

    def _code_registry(self) -> StrategyListResponse:
        options: list[StrategyOption] = []
        for strategy_id in self._strategy_registry.list():
            strategy_class = self._strategy_registry.get(strategy_id)
            metadata = strategy_class.get_metadata()
            modes, default = _money_management_options(
                metadata.money_management.supported,
                metadata.money_management.default,
            )
            options.append(
                StrategyOption(
                    strategy_id=strategy_id,
                    display_name=strategy_id.replace("-", " ").title(),
                    strategy_version=str(getattr(strategy_class, "VERSION", "1.0.0")),
                    supported_timeframes=list(metadata.supported_timeframes),
                    required_indicators=list(metadata.required_indicators),
                    min_history=metadata.min_history,
                    default_params=self._parameter_defaults(strategy_class),
                    supported_money_management=modes,
                    default_money_management=default,
                    is_active=True,
                    is_deprecated=False,
                    source="code_registry",
                )
            )
        return StrategyListResponse(data=options)

    @staticmethod
    def _parameter_defaults(strategy_class: AdapterClass) -> dict[str, object]:
        schema = StrategyConfig.json_schema(strategy_class.get_parameter_schema())
        properties = cast("Mapping[str, Mapping[str, object]]", schema["properties"])
        return {name: field["default"] for name, field in properties.items() if "default" in field}


class MarketDataRepository:
    """Whitelisted, read-only OHLCV aggregation matching the backtest feed."""

    def __init__(self, connection: CryptoConnection) -> None:
        self._connection = connection

    def candles(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: str,
        data_source: str,
        from_ts: datetime,
        to_ts: datetime,
        limit: int,
    ) -> CandleCollection:
        duration = self._timeframe_duration(timeframe)
        expected_count = int(duration / timedelta(minutes=1))
        table = self._source_table(data_source)
        duration_seconds = int(duration.total_seconds())
        query = f"""
            WITH source AS (
                SELECT time, open, high, low, close, volume, quote_volume, trade_count,
                       date_bin(
                           make_interval(secs => %s),
                           time,
                           TIMESTAMPTZ '1970-01-01 00:00:00+00'
                       ) AS bucket
                FROM public.{table}
                WHERE symbol = %s
                  AND exchange = %s
                  AND timeframe = '1m'
                  AND time >= %s
                  AND time < %s
            ),
            aggregated AS (
                SELECT bucket,
                       (array_agg(open ORDER BY time))[1] AS open,
                       max(high) AS high,
                       min(low) AS low,
                       (array_agg(close ORDER BY time DESC))[1] AS close,
                       sum(volume) AS volume,
                       CASE WHEN count(quote_volume) = count(*)
                            THEN sum(quote_volume) END AS quote_volume,
                       CASE WHEN count(trade_count) = count(*)
                            THEN sum(trade_count) END AS trade_count,
                       count(*) AS row_count,
                       min(time) AS first_time,
                       max(time) AS last_time,
                       bool_and(date_trunc('minute', time) = time) AS minute_aligned
                FROM source
                GROUP BY bucket
            ),
            complete AS (
                SELECT *, count(*) OVER () AS total
                FROM aggregated
                WHERE row_count = %s
                  AND minute_aligned
                  AND first_time = bucket
                  AND last_time = bucket + make_interval(secs => %s) - interval '1 minute'
                  AND bucket + make_interval(secs => %s) <= %s
            )
            SELECT *
            FROM complete
            ORDER BY bucket
            LIMIT %s
        """
        rows = self._connection.execute(
            query,
            (
                duration_seconds,
                symbol,
                exchange,
                from_ts,
                to_ts,
                expected_count,
                duration_seconds,
                duration_seconds,
                to_ts,
                limit + 1,
            ),
        ).fetchall()
        total = int(rows[0]["total"]) if rows else 0
        selected = rows[:limit]
        data = [
            Candle(
                open_time=row["bucket"],
                close_time=row["bucket"] + duration,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                quote_volume=(
                    float(row["quote_volume"]) if row["quote_volume"] is not None else None
                ),
                trade_count=(int(row["trade_count"]) if row["trade_count"] is not None else None),
            )
            for row in selected
        ]
        return CandleCollection(
            data=data,
            page=CandlePage(
                limit=limit,
                total=total,
                has_more=len(rows) > limit,
                truncated=len(rows) > limit,
                window_clamped=False,
                from_ts=from_ts,
                to_ts=to_ts,
                timeframe=timeframe,
            ),
        )

    def coverage(
        self,
        *,
        data_source: str,
        symbol: str,
        exchange: str,
    ) -> DataSourceCoverage:
        """Read one series' holdings from the same maintained summary."""
        table = self._source_table(data_source)
        row = self._connection.execute(
            f"""
            SELECT available_from, available_to, row_count
            FROM public.{table}_inventory
            WHERE symbol = %s AND exchange = %s AND timeframe = '1m'
            """,
            (symbol, exchange),
        ).fetchone()
        available_from = row["available_from"] if row else None
        available_to = row["available_to"] if row else None
        row_count = int(row["row_count"]) if row else 0
        expected = self._expected_1m_rows(available_from, available_to)
        return DataSourceCoverage(
            data_source=data_source,
            symbol=symbol,
            exchange=exchange,
            available_from=available_from,
            available_to=available_to,
            row_count=row_count,
            expected_1m_rows=expected,
            missing_1m_rows=max(0, expected - row_count),
        )

    def inventory(self, *, data_source: str) -> DataSourceInventory:
        """Read holdings from the maintained summary instead of aggregating the base.

        Aggregating ohlcv_futures on every page load cost time proportional to the whole
        retained history. The summary carries one row per series and is kept current by
        statement triggers on the base table, so this read stays small as history grows.
        """
        table = self._source_table(data_source)
        rows = self._connection.execute(
            f"""
            SELECT symbol, exchange, available_from, available_to, row_count
            FROM public.{table}_inventory
            WHERE timeframe = '1m'
            ORDER BY symbol, exchange
            """
        ).fetchall()
        items = [
            self._inventory_item(
                symbol=row["symbol"],
                exchange=row["exchange"],
                available_from=row["available_from"],
                available_to=row["available_to"],
                row_count=int(row["row_count"]),
            )
            for row in rows
        ]
        return DataSourceInventory(data_source=data_source, items=items)

    @staticmethod
    def _expected_1m_rows(
        available_from: datetime | None,
        available_to: datetime | None,
    ) -> int:
        """Count the minutes the stored span covers, endpoints included."""
        if available_from is None or available_to is None:
            return 0
        return int((available_to - available_from).total_seconds() // 60) + 1

    @classmethod
    def _inventory_item(
        cls,
        *,
        symbol: str,
        exchange: str,
        available_from: datetime | None,
        available_to: datetime | None,
        row_count: int,
    ) -> InventoryItem:
        expected = cls._expected_1m_rows(available_from, available_to)
        return InventoryItem(
            symbol=symbol,
            exchange=exchange,
            available_from=available_from,
            available_to=available_to,
            row_count=row_count,
            expected_1m_rows=expected,
            missing_1m_rows=max(0, expected - row_count),
            coverage_ratio=min(1.0, max(0.0, row_count / expected)) if expected else 0.0,
        )

    @staticmethod
    def _source_table(data_source: str) -> str:
        if data_source.endswith(".ohlcv_futures"):
            return "ohlcv_futures"
        if data_source.endswith(".ohlcv"):
            return "ohlcv"
        raise ValueError("run data_source is not a supported OHLCV table")

    @staticmethod
    def _timeframe_duration(timeframe: str) -> timedelta:
        if len(timeframe) < 2 or not timeframe[:-1].isdigit():
            raise ValueError("unsupported run timeframe")
        count = int(timeframe[:-1])
        seconds_per_unit = {"m": 60, "h": 3600, "d": 86400}
        unit_seconds = seconds_per_unit.get(timeframe[-1])
        if count < 1 or unit_seconds is None:
            raise ValueError("unsupported run timeframe")
        return timedelta(seconds=count * unit_seconds)
