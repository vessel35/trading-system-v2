"""Typed HTTP contracts for the P0 catalog API."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, JsonValue

DecimalString = Annotated[
    str,
    Field(
        description=(
            "Exact fixed-point database value serialized without floating-point conversion."
        ),
        json_schema_extra={"format": "decimal"},
    ),
]


class Page(BaseModel):
    """Offset page metadata."""

    limit: int
    offset: int
    total: int
    has_more: bool


class CursorPage(BaseModel):
    """Evidence cursor metadata."""

    limit: int
    after_seq: int
    next_after_seq: int | None
    total: int
    has_more: bool


class EvidenceCollection[EvidenceItem](BaseModel):
    """Cursor-paged Evidence rows."""

    data: list[EvidenceItem]
    page: CursorPage


class Trade(BaseModel):
    trade_id: int
    run_id: str
    backtest_run_id: str
    source_type: str
    symbol: str
    side: str
    market_type: str
    entry_execution_id: int
    exit_execution_id: int | None
    entry_price: DecimalString
    entry_quantity: DecimalString
    entry_time: datetime
    exit_price: DecimalString | None
    exit_quantity: DecimalString | None
    exit_time: datetime | None
    exit_reason: str | None
    gross_pnl: DecimalString | None
    total_fee: DecimalString
    slippage: DecimalString
    liquidation_penalty: DecimalString
    funding_cost: DecimalString
    net_pnl: DecimalString | None
    return_pct: float | None
    r0: DecimalString | None
    r_multiple: float | None
    leverage: int
    liquidated: bool
    strategy_id: str
    strategy_name: str
    hold_duration_seconds: int | None
    signal_confidence: float | None
    reason: str | None


class Execution(BaseModel):
    execution_id: int
    run_id: str
    trade_id: int | None
    decision_id: int | None
    order_id: str
    execution_ts: datetime
    trigger_subcandle_ts: datetime | None
    symbol: str
    side: str
    position_side: str
    order_type: str
    reference_price: DecimalString
    price: DecimalString
    quantity: DecimalString
    notional: DecimalString
    fee: DecimalString
    slippage: DecimalString
    liquidity: str
    reduce_only: bool
    exit_reason: str | None
    gap_filled: bool
    qty_truncated: bool


class FundingSettlement(BaseModel):
    settlement_id: int
    run_id: str
    trade_id: int
    settled_at: datetime
    symbol: str
    position_side: str
    funding_rate: float
    rate_source: str
    settle_price: DecimalString
    settle_price_source: str
    position_notional: DecimalString
    payment_amount: DecimalString
    theoretical_payment_amount: DecimalString


class EquityPoint(BaseModel):
    equity_seq: int
    run_id: str
    ts: datetime
    cash_balance: DecimalString
    position_value: DecimalString
    total_equity: DecimalString
    intrabar_low_equity: DecimalString | None
    realized_pnl_cum: DecimalString
    unrealized_pnl: DecimalString
    fee_cum: DecimalString
    slippage_cum: DecimalString
    funding_cum: DecimalString
    peak_equity: DecimalString
    drawdown_pct: float
    open_positions: int


class ChartSummary(BaseModel):
    summary_seq: int
    run_id: str
    series_name: str
    bucket_ts: datetime
    value: float | None
    payload_json: JsonValue | None


class Position(BaseModel):
    position_seq: int
    run_id: str
    trade_id: int | None
    ts: datetime
    symbol: str
    side: str
    quantity: DecimalString
    average_price: DecimalString
    total_cost: DecimalString
    current_price: DecimalString
    mark_price: DecimalString
    mark_price_source: str
    unrealized_pnl: DecimalString
    leverage: int
    margin_type: str
    margin: DecimalString
    entry_price: DecimalString | None
    liquidation_price: DecimalString | None
    funding_fee_total: DecimalString


class IntegrityCheck(BaseModel):
    check_id: int
    run_id: str
    check_name: str
    passed: bool
    detail_json: JsonValue | None
    sample_ref: str | None
    checked_at: datetime


class OutcomeBucket(BaseModel):
    bucket_id: int
    run_id: str
    subject_kind: str
    subject_id: int
    bucket_name: str
    bucket_value: str
    r_multiple: float | None
    note: str | None


class DrawdownEpisode(BaseModel):
    episode_id: int
    run_id: str
    kind: str
    start_ts: datetime
    end_ts: datetime
    recovery_ts: datetime | None
    peak_equity: DecimalString
    trough_equity: DecimalString
    depth_pct: float
    duration_seconds: int
    trade_count: int
    contributing_trades_json: JsonValue | None


class TradeFeature(BaseModel):
    tfs_id: int
    run_id: str
    trade_id: int
    phase: str
    ts: datetime
    features_json: JsonValue
    regime_tag: str | None
    excursion_r: float | None


class CandidateEvent(BaseModel):
    candidate_id: int
    run_id: str
    ts: datetime
    symbol: str
    trigger_rule: str
    passed_filters_json: JsonValue
    blocked_by: str | None
    would_be_side: str | None
    would_be_qty: DecimalString | None
    realized: bool
    linked_trade_id: int | None


class Signal(BaseModel):
    signal_id: int
    run_id: str
    decision_ts: datetime
    feature_ts: datetime
    candle_open_time: datetime
    candle_close_time: datetime
    symbol: str
    price: float
    confidence: float
    stop_loss: float | None
    take_profit: float | None
    market_type: str
    leverage: int | None
    reason: str
    metadata_json: JsonValue | None
    derived_intent: str
    derived_side: str | None
    is_warmup: bool


class Decision(BaseModel):
    decision_id: int
    run_id: str
    signal_id: int | None
    decision_ts: datetime
    action: str
    skip_reason: str | None
    intended_side: str | None
    intended_qty: float | None
    stop_price: float | None
    take_profit_price: float | None
    risk_amount: float | None
    stop_distance: float | None
    sizing_method: str | None
    framework_compliant: bool
    planned_execution_ts: datetime | None


class IndicatorSnapshot(BaseModel):
    snapshot_seq: int
    run_id: str
    indicator_key: str
    indicator_name: str
    params_json: JsonValue
    impl_version: str
    pinned_impl: bool
    min_history: int
    computation_mode: str
    enabled_reason: str
    feature_ts: datetime
    candle_open_time: datetime
    candle_close_time: datetime
    value: float | None
    value_json: JsonValue | None
    is_warmup: bool


class MissedOpportunity(BaseModel):
    miss_id: int
    run_id: str
    ts: datetime
    symbol: str
    source_rule: str
    missing_reason: str
    potential_r: float | None
    potential_move_pct: float | None
    nearest_candidate_id: int | None


class ConditionalExpectancy(BaseModel):
    ce_id: int
    run_id: str
    signature_key: str
    taxonomy_version: str
    definition_json: JsonValue
    subject_kind: str
    signature_sample_count: int
    sample_count: int
    win_rate: float | None
    payoff: float | None
    expectancy_r: float | None
    pf: float | None
    ci_low: float | None
    ci_high: float | None
    is_significant: bool


class Finding(BaseModel):
    finding_id: int
    run_id: str
    claim: str
    evidence_ref_json: JsonValue
    confidence: str
    proposed_change: str | None
    next_prereg_ref: str | None
    created_at: datetime


class FindingsMeta(BaseModel):
    deterministic: Literal[False] = False
    hash_excluded: Literal[True] = True
    note: str = "FINDING_CLAIM is a post-hoc annotation layer excluded from Evidence hash."


class FindingsCollection(BaseModel):
    data: list[Finding]
    page: CursorPage
    meta: FindingsMeta


class Candle(BaseModel):
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float | None
    trade_count: int | None


class CandlePage(BaseModel):
    limit: int
    total: int
    has_more: bool
    from_ts: datetime
    to_ts: datetime
    timeframe: str
    source_timeframe: Literal["1m"] = "1m"


class CandleCollection(BaseModel):
    data: list[Candle]
    page: CandlePage


class Preregistration(BaseModel):
    run_id: str
    hypothesis: str
    weakness_addressed: str | None
    primary_metric: str
    success_criteria_json: JsonValue
    failure_criteria_json: JsonValue | None
    profile_update_declared: bool
    related_finding_ref: str | None
    declared_by: str
    declared_at: datetime
    locked_at: datetime | None


class PreregistrationResponse(BaseModel):
    run_id: str
    prereg: Preregistration | None


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


class RunComparisonItem(BaseModel):
    run: RunHeader
    summary_status: SummaryStatus
    summary: RunSummary | None


class RunComparisonResponse(BaseModel):
    data: list[RunComparisonItem]
    compared_by: Literal["run_ids", "sweep_id"]
    sweep_id: str | None


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
