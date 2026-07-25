"""Typed HTTP contracts for the P0 catalog API."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, JsonValue

DecimalString = Annotated[
    str,
    Field(
        description="Exact PostgreSQL NUMERIC value serialized without floating-point conversion.",
        json_schema_extra={"format": "decimal"},
    ),
]


class Page(BaseModel):
    """Offset page metadata."""

    limit: int
    offset: int
    total: int
    has_more: bool


class RunListItem(BaseModel):
    """Thin catalog row with an optional stored summary."""

    run_id: str
    run_name: str
    status: str
    strategy_id: str
    strategy_name: str
    symbol: str
    exchange: str
    timeframe: str
    market_type: str
    period_start: datetime
    period_end: datetime
    created_at: datetime
    sweep_id: str | None
    config_hash: str
    trade_count: int | None
    pf: float | None
    sortino: float | None
    calmar_or_mar: float | None
    sqn: float | None
    mdd: float | None
    ror: float | None
    win_rate: float | None
    net_pnl_total: DecimalString | None
    gate_verdict: str | None
    decision_route: str | None
    integrity_status: str | None
    data_coverage_ratio: float | None
    summary_present: bool


class RunListResponse(BaseModel):
    """Catalog collection envelope."""

    data: list[RunListItem]
    page: Page


class RunHeader(BaseModel):
    """Reproducibility header mirroring every backtest_run column."""

    run_id: str
    run_seq: int
    run_name: str
    status: str
    strategy_id: str
    strategy_name: str
    strategy_version: str
    params_json: JsonValue
    params_schema_version: str
    symbol: str
    exchange: str
    timeframe: str
    market_type: str
    period_start: datetime
    period_end: datetime
    warmup_start: datetime | None
    warmup_candles: int
    data_source: str
    indicator_mode: str
    trigger_feed: str
    fill_timing: str
    initial_capital: DecimalString
    sizing_method: str
    risk_per_trade: DecimalString | None
    position_size_pct: DecimalString | None
    framework_compliant: bool
    cost_values_json: JsonValue
    seed: int
    engine_version: str
    core_lib_version: str
    config_hash: str
    profile_ref: str | None
    strategy_profile_json: JsonValue | None
    envelope_status_declared: str | None
    sweep_id: str | None
    fold_label: str | None
    evidence_path: str | None
    evidence_hash: str | None
    evidence_retained: bool
    evidence_expires_at: datetime | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None
    created_at: datetime
    resolved_indicators_json: JsonValue
    source_data_hash: str | None


class RunSummary(BaseModel):
    """Stored backtest_summary row; values are never recomputed here."""

    run_id: str
    trade_count: int
    win_count: int
    loss_count: int
    r_excluded_count: int
    pf: float | None
    sortino: float | None
    calmar_or_mar: float | None
    calmar_basis: str | None
    sqn: float | None
    mdd: float | None
    ror: float | None
    sharpe: float | None
    win_rate: float | None
    payoff: float | None
    expectancy_r: float | None
    ulcer: float | None
    kelly: float | None
    annualization: str
    initial_capital: DecimalString
    final_equity: DecimalString | None
    net_pnl_total: DecimalString | None
    gross_pnl_total: DecimalString | None
    total_fee: DecimalString | None
    total_slippage: DecimalString | None
    total_funding: DecimalString | None
    total_liquidation_penalty: DecimalString | None
    integrity_passed: bool
    integrity_status: str
    integrity_failed_json: JsonValue | None
    gate_passed: bool | None
    gate_stage: str | None
    gate_verdict: str | None
    gate_failed_json: JsonValue | None
    envelope_result: str | None
    envelope_deviated_json: JsonValue | None
    decision_route: str | None
    decision_rationale: str | None
    oos_degradation: float | None
    psr: float | None
    harness_json: JsonValue | None
    computed_at: datetime
    expected_candle_count: int
    observed_candle_count: int
    source_absent_gap_count: int
    partial_bucket_count: int
    data_coverage_ratio: float
    max_consecutive_gap_bars: int
    max_consecutive_gap_seconds: int
    data_coverage_passed: bool
    unobservable_funding_boundary_count: int
    data_gap_exit_count: int


SummaryStatus = Literal["available", "pending", "failed", "orphaned", "missing"]


class RunSummaryResponse(BaseModel):
    """0..1 stored summary with a status-derived absence explanation."""

    run_id: str
    run_status: str
    summary_status: SummaryStatus
    summary: RunSummary | None


class CatalogHealth(BaseModel):
    status: Literal["connected"]
    database: str
    read_only: bool
    run_count: int
    schema_version: str | None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    catalog: CatalogHealth
    core_lib_version: str
    web_api_version: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: JsonValue | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
