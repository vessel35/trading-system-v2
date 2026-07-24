"""Define the deterministic, self-contained Evidence SQLite schema."""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Mapping, Sequence
from decimal import Decimal
from types import MappingProxyType
from typing import Final

EVIDENCE_SCHEMA_VERSION: Final = "1.3.0"
MINIMUM_SQLITE_VERSION: Final = (3, 37, 0)
DECIMAL_PLACES: Final = 8
DECIMAL_SCALE: Final = Decimal(10) ** DECIMAL_PLACES
MAX_SQLITE_INTEGER: Final = (1 << 63) - 1

BASIC_TABLES: Final = (
    "BACKTEST_RUN_LOCAL",
    "SOURCE_DATA_SNAPSHOT",
    "INDICATOR_DEFINITION",
    "INDICATOR_SNAPSHOT",
    "SIGNAL",
    "DECISION",
    "EXECUTION",
    "FUNDING_SETTLEMENT",
    "TRADE",
    "POSITION",
    "PORTFOLIO_PNL",
    "OUTCOME_BUCKET",
    "INTEGRITY_CHECK",
    "CHART_SUMMARY",
)
EXTENSION_TABLES: Final = (
    "CANDIDATE_EVENT",
    "TRADE_FEATURE_SNAPSHOT",
    "CONDITION_SIGNATURE",
    "CONDITIONAL_EXPECTANCY",
    "MISSED_OPPORTUNITY",
    "DRAWDOWN_RUNUP_EPISODE",
    "FINDING_CLAIM",
)
EVIDENCE_TABLES: Final = BASIC_TABLES + EXTENSION_TABLES

INTEGRITY_CHECK_NAMES: Final = (
    "accounting_identity",
    "timestamp_order",
    "cost_once",
    "net_of_cost",
    "deterministic",
    "evidence_complete",
)
OPTIONAL_INTEGRITY_CHECK_NAMES: Final = ("trailing_parity",)
DECISION_CONTRACT_KEYS: Final = (
    "primary_metric",
    "observed_value",
    "success_threshold",
    "failure_threshold",
    "edge_distinguishable",
)
OPTIONAL_DECISION_CONTRACT_KEYS: Final = ("higher_is_better",)
EVAL_DECISION_KEYS: Final = (
    "observed_value",
    "edge_distinguishable",
    "decision_route",
    "higher_is_better",
)

HASH_EXCLUDED_TABLES: Final = frozenset({"FINDING_CLAIM"})
HASH_TABLES: Final = tuple(
    sorted(table for table in EVIDENCE_TABLES if table not in HASH_EXCLUDED_TABLES)
)
# ``backtest_run_id`` is TRADE's schema-level alias of the same instance
# identifier, not an additional logical identity field.
HASH_GLOBAL_EXCLUDED_COLUMNS: Final = frozenset({"run_id", "backtest_run_id"})
HASH_EXCLUDED_COLUMNS: Final = MappingProxyType(
    {
        "BACKTEST_RUN_LOCAL": frozenset(
            {"run_seq", "run_name", "prereg_json", "created_at"}
        ),
        "INTEGRITY_CHECK": frozenset({"checked_at"}),
        "FINDING_CLAIM": frozenset({"created_at"}),
    }
)
# The deterministic check depends on the external catalog's previous run.  Its
# row is the sole row-level exclusion; all input-derived integrity rows remain
# part of the logical Evidence hash.
HASH_EXCLUDED_ROWS: Final = MappingProxyType(
    {"INTEGRITY_CHECK": ("check_name <> 'deterministic'",)}
)
ENTITY_SORT_KEYS: Final = MappingProxyType(
    {
        "BACKTEST_RUN_LOCAL": ("run_id",),
        "SOURCE_DATA_SNAPSHOT": ("source_kind", "symbol", "timeframe", "snapshot_id"),
        "INDICATOR_DEFINITION": ("indicator_key",),
        "INDICATOR_SNAPSHOT": ("feature_ts", "indicator_key", "snapshot_seq"),
        "SIGNAL": ("decision_ts", "signal_id"),
        "DECISION": ("decision_ts", "decision_id"),
        "EXECUTION": ("execution_ts", "execution_id"),
        "FUNDING_SETTLEMENT": ("settled_at", "settlement_id"),
        "TRADE": ("entry_time", "trade_id"),
        "POSITION": ("ts", "position_seq"),
        "PORTFOLIO_PNL": ("ts", "equity_seq"),
        "OUTCOME_BUCKET": ("subject_kind", "subject_id", "bucket_name", "bucket_id"),
        "INTEGRITY_CHECK": ("check_name", "check_id"),
        "CHART_SUMMARY": ("series_name", "bucket_ts", "summary_seq"),
        "CANDIDATE_EVENT": ("ts", "candidate_id"),
        "TRADE_FEATURE_SNAPSHOT": ("trade_id", "phase", "tfs_id"),
        "CONDITION_SIGNATURE": ("signature_key",),
        "CONDITIONAL_EXPECTANCY": ("signature_key", "ce_id"),
        "MISSED_OPPORTUNITY": ("ts", "miss_id"),
        "DRAWDOWN_RUNUP_EPISODE": ("kind", "start_ts", "episode_id"),
    }
)

WRITER_CONTRACT_COLUMNS: Final = MappingProxyType(
    {
        "Fill": frozenset({"reference_price", "gap_filled", "qty_truncated"}),
        "Trade": frozenset({"liquidation_penalty"}),
        "FundingSettlement": frozenset(
            {
                "settled_at",
                "funding_rate",
                "settle_price",
                "settle_price_source",
                "position_notional",
                "payment_amount",
                "theoretical_payment_amount",
            }
        ),
    }
)

_CURRENT_EPOCH_MS_SQL = "CAST((julianday('now') - 2440587.5) * 86400000 AS INTEGER)"
_HEX_64_CHECK = (
    "length({column}) = 64 AND lower({column}) = {column} AND {column} NOT GLOB '*[^0-9a-f]*'"
)

SCHEMA_DDL: Final = f"""
CREATE TABLE IF NOT EXISTS BACKTEST_RUN_LOCAL (
    run_id TEXT PRIMARY KEY,
    run_seq INTEGER NOT NULL CHECK (run_seq > 0),
    run_name TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    params_json TEXT NOT NULL DEFAULT '{{}}',
    resolved_indicators_json TEXT NOT NULL DEFAULT '[]',
    params_schema_version TEXT NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    market_type TEXT NOT NULL,
    period_start INTEGER NOT NULL,
    period_end INTEGER NOT NULL,
    warmup_start INTEGER,
    warmup_candles INTEGER NOT NULL DEFAULT 0 CHECK (warmup_candles >= 0),
    indicator_mode TEXT NOT NULL DEFAULT 'auto'
        CHECK (indicator_mode IN ('auto', 'explicit', 'all')),
    trigger_feed TEXT NOT NULL DEFAULT 'tf_candle'
        CHECK (trigger_feed IN ('tf_candle', 'm1_subcandle')),
    fill_timing TEXT NOT NULL DEFAULT 'next_bar'
        CHECK (fill_timing IN ('next_bar', 'immediate')),
    initial_capital INTEGER NOT NULL CHECK (initial_capital > 0),
    sizing_method TEXT NOT NULL DEFAULT 'risk_based'
        CHECK (sizing_method IN ('risk_based', 'pct')),
    risk_per_trade REAL,
    position_size_pct REAL,
    framework_compliant INTEGER NOT NULL DEFAULT 1
        CHECK (framework_compliant IN (0, 1)),
    cost_values_json TEXT NOT NULL DEFAULT '{{}}',
    data_quality_criteria_json TEXT NOT NULL,
    seed INTEGER NOT NULL DEFAULT 0,
    engine_version TEXT NOT NULL,
    core_lib_version TEXT NOT NULL,
    config_hash TEXT NOT NULL
        CHECK ({_HEX_64_CHECK.format(column="config_hash")}),
    profile_ref TEXT,
    strategy_profile_json TEXT,
    envelope_status_declared TEXT
        CHECK (
            envelope_status_declared IS NULL
            OR envelope_status_declared IN ('provisional', 'updating', 'established')
        ),
    prereg_json TEXT,
    eval_decision_json TEXT,
    evidence_schema_version TEXT NOT NULL,
    created_at INTEGER NOT NULL DEFAULT ({_CURRENT_EPOCH_MS_SQL}),
    CHECK (period_start < period_end),
    CHECK (warmup_start IS NULL OR warmup_start <= period_start),
    CHECK (
        (
            sizing_method = 'risk_based'
            AND risk_per_trade > 0.0
            AND risk_per_trade <= 0.01
            AND position_size_pct IS NULL
        )
        OR (
            sizing_method = 'pct'
            AND position_size_pct > 0.0
            AND position_size_pct <= 1.0
            AND risk_per_trade IS NULL
        )
    )
) STRICT;

CREATE TRIGGER IF NOT EXISTS backtest_run_local_single_row
BEFORE INSERT ON BACKTEST_RUN_LOCAL
WHEN EXISTS (SELECT 1 FROM BACKTEST_RUN_LOCAL)
BEGIN
    SELECT RAISE(ABORT, 'an Evidence file contains exactly one run');
END;

CREATE TABLE IF NOT EXISTS SOURCE_DATA_SNAPSHOT (
    snapshot_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    source_kind TEXT NOT NULL
        CHECK (source_kind IN ('ohlcv', 'funding', 'mark_price')),
    source_ref TEXT NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    timeframe TEXT,
    resampled_from TEXT,
    range_start INTEGER NOT NULL,
    range_end INTEGER NOT NULL,
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    gap_count INTEGER NOT NULL DEFAULT 0 CHECK (gap_count >= 0),
    fallback_used INTEGER NOT NULL DEFAULT 0 CHECK (fallback_used IN (0, 1)),
    fallback_count INTEGER NOT NULL DEFAULT 0 CHECK (fallback_count >= 0),
    content_hash TEXT NOT NULL
        CHECK ({_HEX_64_CHECK.format(column="content_hash")}),
    note TEXT,
    CHECK (range_start <= range_end),
    CHECK (
        (source_kind = 'ohlcv' AND timeframe IS NOT NULL)
        OR (source_kind <> 'ohlcv' AND timeframe IS NULL)
    ),
    CHECK (
        (fallback_used = 0 AND fallback_count = 0)
        OR (fallback_used = 1 AND fallback_count > 0)
    )
) STRICT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_source_data_snapshot_kind_timeframe
    ON SOURCE_DATA_SNAPSHOT(source_kind, symbol, ifnull(timeframe, ''));

CREATE TABLE IF NOT EXISTS INDICATOR_DEFINITION (
    indicator_key TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    indicator_name TEXT NOT NULL,
    params_json TEXT NOT NULL DEFAULT '{{}}',
    impl_version TEXT NOT NULL,
    pinned_impl INTEGER NOT NULL DEFAULT 0 CHECK (pinned_impl IN (0, 1)),
    min_history INTEGER NOT NULL CHECK (min_history >= 1),
    computation_mode TEXT NOT NULL DEFAULT 'vectorized'
        CHECK (computation_mode IN ('vectorized', 'incremental')),
    enabled_reason TEXT NOT NULL CHECK (enabled_reason IN ('auto', 'explicit', 'all'))
) STRICT;

CREATE TABLE IF NOT EXISTS INDICATOR_SNAPSHOT (
    snapshot_seq INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    indicator_key TEXT NOT NULL REFERENCES INDICATOR_DEFINITION(indicator_key),
    feature_ts INTEGER NOT NULL,
    candle_open_time INTEGER NOT NULL,
    candle_close_time INTEGER NOT NULL,
    value REAL,
    value_json TEXT,
    is_warmup INTEGER NOT NULL DEFAULT 0 CHECK (is_warmup IN (0, 1)),
    CHECK ((value IS NULL) <> (value_json IS NULL)),
    CHECK (candle_open_time < candle_close_time),
    CHECK (candle_close_time <= feature_ts)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_indicator_snapshot_key_feature_ts
    ON INDICATOR_SNAPSHOT(indicator_key, feature_ts);
CREATE INDEX IF NOT EXISTS idx_indicator_snapshot_feature_ts
    ON INDICATOR_SNAPSHOT(feature_ts);

CREATE TABLE IF NOT EXISTS SIGNAL (
    signal_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    decision_ts INTEGER NOT NULL,
    feature_ts INTEGER NOT NULL,
    candle_open_time INTEGER NOT NULL,
    candle_close_time INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    price REAL NOT NULL CHECK (price > 0.0),
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    stop_loss REAL CHECK (stop_loss > 0.0),
    take_profit REAL CHECK (take_profit > 0.0),
    market_type TEXT NOT NULL,
    leverage INTEGER CHECK (leverage >= 1),
    reason TEXT NOT NULL,
    metadata_json TEXT,
    derived_intent TEXT NOT NULL CHECK (derived_intent IN ('enter', 'exit', 'reverse')),
    derived_side TEXT CHECK (derived_side IN ('LONG', 'SHORT')),
    is_warmup INTEGER NOT NULL DEFAULT 0 CHECK (is_warmup IN (0, 1)),
    CHECK (feature_ts <= decision_ts),
    CHECK (candle_open_time < candle_close_time),
    CHECK (decision_ts = candle_close_time),
    CHECK (
        (
            derived_intent = 'exit'
            AND stop_loss IS NULL
            AND take_profit IS NULL
            AND derived_side IS NULL
        )
        OR (
            derived_intent IN ('enter', 'reverse')
            AND (stop_loss IS NOT NULL OR take_profit IS NOT NULL)
            AND derived_side IS NOT NULL
        )
    )
) STRICT;

CREATE INDEX IF NOT EXISTS idx_signal_decision_ts ON SIGNAL(decision_ts);

CREATE TABLE IF NOT EXISTS DECISION (
    decision_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    signal_id INTEGER REFERENCES SIGNAL(signal_id),
    decision_ts INTEGER NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('enter', 'exit', 'reverse', 'skip')),
    skip_reason TEXT,
    intended_side TEXT CHECK (intended_side IN ('LONG', 'SHORT')),
    intended_qty REAL CHECK (intended_qty >= 0.0),
    stop_price REAL CHECK (stop_price > 0.0),
    take_profit_price REAL CHECK (take_profit_price > 0.0),
    risk_amount REAL CHECK (risk_amount >= 0.0),
    stop_distance REAL CHECK (stop_distance > 0.0),
    sizing_method TEXT DEFAULT 'risk_based'
        CHECK (sizing_method IN ('risk_based', 'pct')),
    framework_compliant INTEGER NOT NULL DEFAULT 1
        CHECK (framework_compliant IN (0, 1)),
    planned_execution_ts INTEGER,
    CHECK (
        (action = 'skip' AND skip_reason IS NOT NULL)
        OR (action <> 'skip' AND skip_reason IS NULL)
    ),
    CHECK (planned_execution_ts IS NULL OR decision_ts < planned_execution_ts)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_decision_decision_ts ON DECISION(decision_ts);

CREATE TABLE IF NOT EXISTS EXECUTION (
    execution_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    decision_id INTEGER REFERENCES DECISION(decision_id),
    order_id TEXT NOT NULL,
    execution_ts INTEGER NOT NULL,
    trigger_subcandle_ts INTEGER,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    position_side TEXT NOT NULL CHECK (position_side IN ('LONG', 'SHORT', 'BOTH')),
    order_type TEXT NOT NULL DEFAULT 'MARKET'
        CHECK (
            order_type IN (
                'MARKET',
                'LIMIT',
                'STOP_MARKET',
                'TAKE_PROFIT_MARKET',
                'TRAILING_STOP_MARKET'
            )
        ),
    reference_price INTEGER NOT NULL CHECK (reference_price > 0),
    price INTEGER NOT NULL CHECK (price > 0),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    notional INTEGER NOT NULL CHECK (notional > 0),
    fee INTEGER NOT NULL DEFAULT 0 CHECK (fee >= 0),
    slippage INTEGER NOT NULL DEFAULT 0 CHECK (slippage >= 0),
    liquidity TEXT NOT NULL DEFAULT 'taker' CHECK (liquidity IN ('taker', 'maker')),
    reduce_only INTEGER NOT NULL DEFAULT 0 CHECK (reduce_only IN (0, 1)),
    exit_reason TEXT
        CHECK (
            exit_reason IN (
                'STOP_LOSS',
                'TAKE_PROFIT',
                'TRAILING_STOP',
                'LIQUIDATION',
                'SIGNAL_EXIT',
                'REVERSAL',
                'DATA_GAP',
                'END_OF_DATA'
            )
        ),
    gap_filled INTEGER NOT NULL DEFAULT 0 CHECK (gap_filled IN (0, 1)),
    qty_truncated INTEGER NOT NULL DEFAULT 0 CHECK (qty_truncated IN (0, 1)),
    CHECK (decision_id IS NOT NULL OR exit_reason = 'END_OF_DATA'),
    CHECK (trigger_subcandle_ts IS NULL OR trigger_subcandle_ts < execution_ts)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_execution_execution_ts ON EXECUTION(execution_ts);
CREATE INDEX IF NOT EXISTS idx_execution_decision_id ON EXECUTION(decision_id);

CREATE TABLE IF NOT EXISTS FUNDING_SETTLEMENT (
    settlement_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    trade_id INTEGER NOT NULL REFERENCES TRADE(trade_id),
    settled_at INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    position_side TEXT NOT NULL CHECK (position_side IN ('LONG', 'SHORT', 'BOTH')),
    funding_rate REAL NOT NULL,
    rate_source TEXT NOT NULL DEFAULT 'measured'
        CHECK (rate_source IN ('measured', 'fallback')),
    settle_price INTEGER NOT NULL CHECK (settle_price > 0),
    settle_price_source TEXT NOT NULL DEFAULT 'boundary_open'
        CHECK (settle_price_source IN ('boundary_open', 'prev_close')),
    position_notional INTEGER NOT NULL CHECK (position_notional > 0),
    payment_amount INTEGER NOT NULL,
    theoretical_payment_amount INTEGER NOT NULL,
    CHECK (
        payment_amount = 0
        OR (
            position_side = 'LONG'
            AND (
                (funding_rate > 0.0 AND payment_amount < 0)
                OR (funding_rate < 0.0 AND payment_amount > 0)
            )
        )
        OR (
            position_side = 'SHORT'
            AND (
                (funding_rate > 0.0 AND payment_amount > 0)
                OR (funding_rate < 0.0 AND payment_amount < 0)
            )
        )
        OR (position_side = 'BOTH' AND payment_amount = 0)
    ),
    CHECK (
        theoretical_payment_amount = 0
        OR (
            position_side = 'LONG'
            AND (
                (funding_rate > 0.0 AND theoretical_payment_amount < 0)
                OR (funding_rate < 0.0 AND theoretical_payment_amount > 0)
            )
        )
        OR (
            position_side = 'SHORT'
            AND (
                (funding_rate > 0.0 AND theoretical_payment_amount > 0)
                OR (funding_rate < 0.0 AND theoretical_payment_amount < 0)
            )
        )
        OR (position_side = 'BOTH' AND theoretical_payment_amount = 0)
    ),
    CHECK (abs(payment_amount) <= abs(theoretical_payment_amount)),
    CHECK (
        payment_amount = 0
        OR (payment_amount < 0 AND theoretical_payment_amount < 0)
        OR (payment_amount > 0 AND theoretical_payment_amount > 0)
    ),
    UNIQUE (trade_id, settled_at)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_funding_settlement_settled_at
    ON FUNDING_SETTLEMENT(settled_at);
CREATE INDEX IF NOT EXISTS idx_funding_settlement_trade_id
    ON FUNDING_SETTLEMENT(trade_id);

CREATE TABLE IF NOT EXISTS TRADE (
    trade_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    backtest_run_id TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'backtest' CHECK (source_type = 'backtest'),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    market_type TEXT NOT NULL,
    entry_execution_id INTEGER NOT NULL REFERENCES EXECUTION(execution_id),
    exit_execution_id INTEGER REFERENCES EXECUTION(execution_id),
    entry_price INTEGER NOT NULL CHECK (entry_price > 0),
    entry_quantity INTEGER NOT NULL CHECK (entry_quantity > 0),
    entry_time INTEGER NOT NULL,
    exit_price INTEGER CHECK (exit_price > 0),
    exit_quantity INTEGER CHECK (exit_quantity > 0),
    exit_time INTEGER,
    exit_reason TEXT
        CHECK (
            exit_reason IN (
                'STOP_LOSS',
                'TAKE_PROFIT',
                'TRAILING_STOP',
                'LIQUIDATION',
                'SIGNAL_EXIT',
                'REVERSAL',
                'DATA_GAP',
                'END_OF_DATA'
            )
        ),
    gross_pnl INTEGER,
    total_fee INTEGER NOT NULL DEFAULT 0 CHECK (total_fee >= 0),
    slippage INTEGER NOT NULL DEFAULT 0 CHECK (slippage >= 0),
    liquidation_penalty INTEGER NOT NULL DEFAULT 0 CHECK (liquidation_penalty >= 0),
    funding_cost INTEGER NOT NULL DEFAULT 0,
    net_pnl INTEGER,
    return_pct REAL,
    r0 INTEGER CHECK (r0 > 0),
    r_multiple REAL,
    leverage INTEGER NOT NULL DEFAULT 1 CHECK (leverage >= 1),
    liquidated INTEGER NOT NULL DEFAULT 0 CHECK (liquidated IN (0, 1)),
    strategy_id TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    hold_duration_seconds INTEGER CHECK (hold_duration_seconds >= 0),
    signal_confidence REAL
        CHECK (signal_confidence >= 0.0 AND signal_confidence <= 1.0),
    reason TEXT,
    CHECK (run_id = backtest_run_id),
    CHECK (
        (
            exit_execution_id IS NULL
            AND exit_price IS NULL
            AND exit_quantity IS NULL
            AND exit_time IS NULL
            AND exit_reason IS NULL
            AND gross_pnl IS NULL
            AND net_pnl IS NULL
        )
        OR (
            exit_execution_id IS NOT NULL
            AND exit_price IS NOT NULL
            AND exit_quantity IS NOT NULL
            AND exit_time IS NOT NULL
            AND exit_reason IS NOT NULL
            AND gross_pnl IS NOT NULL
            AND net_pnl IS NOT NULL
            AND entry_time < exit_time
        )
    ),
    CHECK (
        net_pnl IS NULL
        OR net_pnl = (
            gross_pnl
            - total_fee
            - slippage
            - funding_cost
            - liquidation_penalty
        )
    ),
    CHECK (
        (liquidated = 1 AND exit_reason = 'LIQUIDATION')
        OR (liquidated = 0 AND exit_reason IS NOT 'LIQUIDATION')
    )
) STRICT;

CREATE INDEX IF NOT EXISTS idx_trade_entry_time ON TRADE(entry_time);
CREATE INDEX IF NOT EXISTS idx_trade_exit_reason ON TRADE(exit_reason);

CREATE TABLE IF NOT EXISTS POSITION (
    position_seq INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    trade_id INTEGER REFERENCES TRADE(trade_id),
    ts INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    average_price INTEGER NOT NULL CHECK (average_price >= 0),
    total_cost INTEGER NOT NULL CHECK (total_cost >= 0),
    current_price INTEGER NOT NULL CHECK (current_price > 0),
    mark_price INTEGER NOT NULL CHECK (mark_price > 0),
    mark_price_source TEXT NOT NULL DEFAULT 'candle_close'
        CHECK (mark_price_source IN ('measured', 'candle_close')),
    unrealized_pnl INTEGER NOT NULL DEFAULT 0,
    leverage INTEGER NOT NULL DEFAULT 1 CHECK (leverage >= 1),
    margin_type TEXT NOT NULL DEFAULT 'ISOLATED'
        CHECK (margin_type IN ('CROSS', 'ISOLATED')),
    margin INTEGER NOT NULL CHECK (margin >= 0),
    entry_price INTEGER CHECK (entry_price > 0),
    liquidation_price INTEGER CHECK (liquidation_price > 0),
    funding_fee_total INTEGER NOT NULL DEFAULT 0,
    CHECK (quantity > 0 OR trade_id IS NULL)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_position_ts ON POSITION(ts);

CREATE TABLE IF NOT EXISTS PORTFOLIO_PNL (
    equity_seq INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    ts INTEGER NOT NULL,
    cash_balance INTEGER NOT NULL CHECK (cash_balance >= 0),
    position_value INTEGER NOT NULL,
    total_equity INTEGER NOT NULL,
    intrabar_low_equity INTEGER,
    realized_pnl_cum INTEGER NOT NULL DEFAULT 0,
    unrealized_pnl INTEGER NOT NULL DEFAULT 0,
    fee_cum INTEGER NOT NULL DEFAULT 0 CHECK (fee_cum >= 0),
    slippage_cum INTEGER NOT NULL DEFAULT 0 CHECK (slippage_cum >= 0),
    funding_cum INTEGER NOT NULL DEFAULT 0,
    peak_equity INTEGER NOT NULL,
    drawdown_pct REAL NOT NULL DEFAULT 0.0 CHECK (drawdown_pct <= 0.0),
    open_positions INTEGER NOT NULL DEFAULT 0 CHECK (open_positions >= 0),
    CHECK (cash_balance + position_value = total_equity),
    CHECK (intrabar_low_equity IS NULL OR intrabar_low_equity <= total_equity),
    CHECK (peak_equity >= total_equity)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_portfolio_pnl_ts ON PORTFOLIO_PNL(ts);

CREATE TABLE IF NOT EXISTS OUTCOME_BUCKET (
    bucket_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    subject_kind TEXT NOT NULL
        CHECK (subject_kind IN ('signal', 'trade', 'missed_opportunity')),
    subject_id INTEGER NOT NULL,
    bucket_name TEXT NOT NULL,
    bucket_value TEXT NOT NULL,
    r_multiple REAL,
    note TEXT,
    UNIQUE (subject_kind, subject_id, bucket_name),
    CHECK (
        bucket_name <> 'outcome_class'
        OR bucket_value IN (
            'top_winner',
            'normal_winner',
            'small_loser',
            'tail_loser',
            'cost_churn',
            'missed_opportunity'
        )
    )
) STRICT;

CREATE INDEX IF NOT EXISTS idx_outcome_bucket_name_value
    ON OUTCOME_BUCKET(bucket_name, bucket_value);

CREATE TABLE IF NOT EXISTS INTEGRITY_CHECK (
    check_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    check_name TEXT NOT NULL
        CHECK (
            check_name IN (
                'accounting_identity',
                'timestamp_order',
                'cost_once',
                'net_of_cost',
                'deterministic',
                'evidence_complete',
                'trailing_parity'
            )
        ),
    passed INTEGER NOT NULL CHECK (passed IN (0, 1)),
    detail_json TEXT,
    sample_ref TEXT,
    checked_at INTEGER NOT NULL DEFAULT ({_CURRENT_EPOCH_MS_SQL}),
    UNIQUE (run_id, check_name)
) STRICT;

CREATE TABLE IF NOT EXISTS CHART_SUMMARY (
    summary_seq INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    series_name TEXT NOT NULL
        CHECK (series_name IN ('equity', 'drawdown', 'trade_marker', 'monthly_return')),
    bucket_ts INTEGER NOT NULL,
    value REAL,
    payload_json TEXT
) STRICT;

CREATE TABLE IF NOT EXISTS CANDIDATE_EVENT (
    candidate_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    ts INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    trigger_rule TEXT NOT NULL,
    passed_filters_json TEXT NOT NULL DEFAULT '[]',
    blocked_by TEXT,
    would_be_side TEXT CHECK (would_be_side IN ('LONG', 'SHORT')),
    would_be_qty INTEGER CHECK (would_be_qty >= 0),
    realized INTEGER NOT NULL DEFAULT 0 CHECK (realized IN (0, 1)),
    linked_trade_id INTEGER REFERENCES TRADE(trade_id),
    CHECK (
        (realized = 1 AND linked_trade_id IS NOT NULL AND blocked_by IS NULL)
        OR (realized = 0 AND linked_trade_id IS NULL)
    )
) STRICT;

CREATE TABLE IF NOT EXISTS TRADE_FEATURE_SNAPSHOT (
    tfs_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    trade_id INTEGER NOT NULL REFERENCES TRADE(trade_id),
    phase TEXT NOT NULL CHECK (phase IN ('entry', 'exit', 'mae', 'mfe')),
    ts INTEGER NOT NULL,
    features_json TEXT NOT NULL DEFAULT '{{}}',
    regime_tag TEXT,
    excursion_r REAL,
    UNIQUE (trade_id, phase)
) STRICT;

CREATE TABLE IF NOT EXISTS CONDITION_SIGNATURE (
    signature_key TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    taxonomy_version TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    subject_kind TEXT NOT NULL DEFAULT 'trade'
        CHECK (subject_kind IN ('trade', 'episode')),
    sample_count INTEGER NOT NULL DEFAULT 0 CHECK (sample_count >= 0)
) STRICT;

CREATE TABLE IF NOT EXISTS CONDITIONAL_EXPECTANCY (
    ce_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    signature_key TEXT NOT NULL REFERENCES CONDITION_SIGNATURE(signature_key),
    sample_count INTEGER NOT NULL CHECK (sample_count >= 1),
    win_rate REAL CHECK (win_rate >= 0.0 AND win_rate <= 1.0),
    payoff REAL CHECK (payoff > 0.0),
    expectancy_r REAL,
    pf REAL CHECK (pf >= 0.0),
    ci_low REAL,
    ci_high REAL,
    is_significant INTEGER NOT NULL DEFAULT 0 CHECK (is_significant IN (0, 1)),
    UNIQUE (signature_key),
    CHECK (ci_low IS NULL OR ci_high IS NULL OR ci_low <= ci_high),
    CHECK (
        is_significant = 0
        OR (
            ci_low IS NOT NULL
            AND ci_high IS NOT NULL
            AND (ci_low > 0.0 OR ci_high < 0.0)
        )
    )
) STRICT;

CREATE TABLE IF NOT EXISTS MISSED_OPPORTUNITY (
    miss_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    ts INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    source_rule TEXT NOT NULL,
    missing_reason TEXT NOT NULL,
    potential_r REAL,
    potential_move_pct REAL,
    nearest_candidate_id INTEGER REFERENCES CANDIDATE_EVENT(candidate_id)
) STRICT;

CREATE TABLE IF NOT EXISTS DRAWDOWN_RUNUP_EPISODE (
    episode_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    kind TEXT NOT NULL CHECK (kind IN ('drawdown', 'runup')),
    start_ts INTEGER NOT NULL,
    end_ts INTEGER NOT NULL,
    recovery_ts INTEGER,
    peak_equity INTEGER NOT NULL,
    trough_equity INTEGER NOT NULL,
    depth_pct REAL NOT NULL,
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds >= 0),
    trade_count INTEGER NOT NULL DEFAULT 0 CHECK (trade_count >= 0),
    contributing_trades_json TEXT,
    CHECK (start_ts < end_ts),
    CHECK (recovery_ts IS NULL OR recovery_ts >= end_ts),
    CHECK (
        (kind = 'drawdown' AND depth_pct <= 0.0)
        OR (kind = 'runup' AND depth_pct >= 0.0)
    )
) STRICT;

CREATE TABLE IF NOT EXISTS FINDING_CLAIM (
    finding_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES BACKTEST_RUN_LOCAL(run_id),
    claim TEXT NOT NULL,
    evidence_ref_json TEXT NOT NULL
        CHECK (evidence_ref_json <> '[]'),
    confidence TEXT NOT NULL DEFAULT 'low'
        CHECK (confidence IN ('low', 'medium', 'high')),
    proposed_change TEXT,
    next_prereg_ref TEXT,
    created_at INTEGER NOT NULL DEFAULT ({_CURRENT_EPOCH_MS_SQL})
) STRICT;
"""

TIMESTAMP_ORDER_AUDIT_SQL: Final = """
SELECT 'indicator_snapshot' AS source, snapshot_seq AS entity_id
FROM INDICATOR_SNAPSHOT
WHERE candle_close_time > feature_ts
UNION ALL
SELECT 'signal', signal_id
FROM SIGNAL
WHERE feature_ts > decision_ts OR candle_close_time <> decision_ts
UNION ALL
SELECT 'execution', e.execution_id
FROM EXECUTION AS e
JOIN DECISION AS d ON d.decision_id = e.decision_id
WHERE d.decision_ts >= e.execution_ts
ORDER BY source, entity_id
"""


def _plain_shortest_float(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("canonical JSON does not support non-finite numbers")
    shortest = repr(value)
    if "e" not in shortest and "E" not in shortest:
        is_negative_zero = value == 0.0 and math.copysign(1.0, value) < 0.0
        return shortest[:-2] if shortest.endswith(".0") and not is_negative_zero else shortest
    return format(Decimal(shortest), "f")


def _plain_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("canonical JSON does not support non-finite numbers")
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    if rendered in ("", "-0"):
        return "0"
    return rendered


def _canonical_json_value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _plain_shortest_float(value)
    if isinstance(value, Decimal):
        return _plain_decimal(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, Mapping):
        items: list[str] = []
        if not all(isinstance(key, str) for key in value):
            raise TypeError("canonical JSON object keys must be strings")
        for key in sorted(value):
            items.append(f"{_canonical_json_value(key)}:{_canonical_json_value(value[key])}")
        return "{" + ",".join(items) + "}"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "[" + ",".join(_canonical_json_value(item) for item in value) + "]"
    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_json(value: Mapping[str, object] | Sequence[object]) -> str:
    """Encode §5.3.1 canonical JSON with stable keys and plain shortest numbers."""
    return _canonical_json_value(value)


def encode_eval_decision(
    *,
    observed_value: int | float | Decimal,
    edge_distinguishable: bool,
    decision_route: str,
    higher_is_better: bool,
) -> str:
    """Encode only deterministic evaluation outputs written during finalize."""
    if isinstance(observed_value, bool) or not isinstance(observed_value, int | float | Decimal):
        raise TypeError("observed_value must be numeric")
    if not isinstance(edge_distinguishable, bool):
        raise TypeError("edge_distinguishable must be bool")
    if decision_route not in ("promote", "abandon", "retest", "partial_keep"):
        raise ValueError("decision_route is not a standard evaluation route")
    if not isinstance(higher_is_better, bool):
        raise TypeError("higher_is_better must be bool")
    return canonical_json(
        {
            "observed_value": observed_value,
            "edge_distinguishable": edge_distinguishable,
            "decision_route": decision_route,
            "higher_is_better": higher_is_better,
        }
    )


def restore_decision_contract(
    prereg_json: str,
    eval_decision_json: str,
) -> dict[str, object]:
    """Restore the M6 Decision inputs from preregistration plus finalize output."""
    prereg = json.loads(prereg_json)
    evaluation = json.loads(eval_decision_json)
    if not isinstance(prereg, dict) or not isinstance(evaluation, dict):
        raise TypeError("Decision Evidence documents must be JSON objects")
    missing_prereg = {
        "primary_metric",
        "success_threshold",
        "failure_threshold",
        "higher_is_better",
    } - prereg.keys()
    if missing_prereg:
        raise ValueError(f"prereg_json missing Decision keys: {sorted(missing_prereg)}")
    if set(evaluation) != set(EVAL_DECISION_KEYS):
        raise ValueError("eval_decision_json must contain exactly the finalize keys")
    prereg_higher_is_better = prereg["higher_is_better"]
    evaluation_higher_is_better = evaluation["higher_is_better"]
    if not isinstance(prereg_higher_is_better, bool):
        raise TypeError("prereg_json higher_is_better must be bool")
    if not isinstance(evaluation_higher_is_better, bool):
        raise TypeError("eval_decision_json higher_is_better must be bool")
    if evaluation_higher_is_better is not prereg_higher_is_better:
        raise ValueError(
            "eval_decision_json higher_is_better does not match authoritative prereg_json"
        )
    return {
        "primary_metric": prereg["primary_metric"],
        "observed_value": evaluation["observed_value"],
        "success_threshold": prereg["success_threshold"],
        "failure_threshold": prereg["failure_threshold"],
        "edge_distinguishable": evaluation["edge_distinguishable"],
        "higher_is_better": prereg_higher_is_better,
        "decision_route": evaluation["decision_route"],
    }


def scale_decimal(value: Decimal) -> int:
    """Scale a normalizer-quantized Decimal without crossing through float."""
    if not isinstance(value, Decimal):
        raise TypeError("Evidence fixed-precision values must be Decimal")
    scaled = value * DECIMAL_SCALE
    if scaled != scaled.to_integral_value():
        raise ValueError("Evidence Decimal values must be quantized to 8 places")
    result = int(scaled)
    if abs(result) > MAX_SQLITE_INTEGER:
        raise OverflowError("scaled Evidence value exceeds SQLite INTEGER range")
    return result


def restore_decimal(value: int) -> Decimal:
    """Restore an exact Decimal from its 1e8-scaled SQLite INTEGER."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("scaled Evidence values must be int")
    return Decimal(value) / DECIMAL_SCALE


def initialize_evidence_schema(connection: sqlite3.Connection) -> None:
    """Enable foreign keys and create all 21 STRICT Evidence entities."""
    if sqlite3.sqlite_version_info < MINIMUM_SQLITE_VERSION:
        version = ".".join(str(part) for part in MINIMUM_SQLITE_VERSION)
        raise RuntimeError(f"Evidence requires SQLite {version} or newer")
    connection.execute("PRAGMA foreign_keys = ON")
    if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
        raise RuntimeError("Evidence requires foreign key enforcement")
    connection.executescript(SCHEMA_DDL)
