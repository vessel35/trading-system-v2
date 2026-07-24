\set ON_ERROR_STOP on

BEGIN;

-- The inherited v1 table is not part of the v2 schema. Preserve any local
-- development rows while removing it from the v2 public schema.
CREATE SCHEMA IF NOT EXISTS legacy_backtest_v1;

DO $$
BEGIN
    IF to_regclass('public.backtest_jobs') IS NOT NULL THEN
        IF to_regclass('legacy_backtest_v1.backtest_jobs') IS NOT NULL THEN
            RAISE EXCEPTION
                'cannot quarantine public.backtest_jobs: legacy_backtest_v1.backtest_jobs already exists';
        END IF;
        ALTER TABLE public.backtest_jobs SET SCHEMA legacy_backtest_v1;
    END IF;
END
$$;

SET ROLE backtest_writer;

CREATE SEQUENCE IF NOT EXISTS public.backtest_run_seq
    AS BIGINT
    START WITH 1
    INCREMENT BY 1
    MINVALUE 1
    NO MAXVALUE
    CACHE 1
    NO CYCLE;

CREATE TABLE IF NOT EXISTS public.backtest_run (
    run_id VARCHAR(48) PRIMARY KEY,
    run_seq BIGINT NOT NULL DEFAULT nextval('public.backtest_run_seq'),
    run_name VARCHAR(24) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'RUNNING',
    strategy_id VARCHAR(80) NOT NULL,
    strategy_name VARCHAR(120) NOT NULL,
    strategy_version VARCHAR(40) NOT NULL,
    params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    resolved_indicators_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    params_schema_version VARCHAR(40) NOT NULL,
    symbol VARCHAR(30) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    market_type VARCHAR(10) NOT NULL DEFAULT 'FUTURES',
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    warmup_start TIMESTAMPTZ,
    warmup_candles INTEGER NOT NULL DEFAULT 0,
    data_source VARCHAR(60) NOT NULL,
    indicator_mode VARCHAR(10) NOT NULL DEFAULT 'auto',
    trigger_feed VARCHAR(16) NOT NULL DEFAULT 'tf_candle',
    fill_timing VARCHAR(12) NOT NULL DEFAULT 'next_bar',
    initial_capital NUMERIC(28, 8) NOT NULL,
    sizing_method VARCHAR(12) NOT NULL DEFAULT 'risk_based',
    risk_per_trade NUMERIC(5, 4),
    position_size_pct NUMERIC(5, 4),
    framework_compliant BOOLEAN NOT NULL DEFAULT true,
    cost_values_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    seed BIGINT NOT NULL DEFAULT 0,
    engine_version VARCHAR(40) NOT NULL,
    core_lib_version VARCHAR(40) NOT NULL,
    config_hash VARCHAR(64) NOT NULL,
    source_data_hash VARCHAR(64),
    profile_ref VARCHAR(80),
    strategy_profile_json JSONB,
    envelope_status_declared VARCHAR(16),
    sweep_id VARCHAR(64),
    fold_label VARCHAR(40),
    evidence_path TEXT,
    evidence_hash VARCHAR(64),
    evidence_retained BOOLEAN NOT NULL DEFAULT true,
    evidence_expires_at TIMESTAMPTZ,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_backtest_run_run_seq UNIQUE (run_seq),
    CONSTRAINT ck_backtest_run_run_seq_positive CHECK (run_seq > 0),
    CONSTRAINT ck_backtest_run_run_name CHECK (run_name ~ '^[a-z0-9-]+$'),
    CONSTRAINT ck_backtest_run_run_id CHECK (
        run_id ~ (
            '^BT_[0-9]{8}_'
            || lpad(
                run_seq::text,
                greatest(6, length(run_seq::text)),
                '0'
            )
            || '_'
            || run_name
            || '$'
        )
    ),
    CONSTRAINT ck_backtest_run_status CHECK (
        status IN ('RUNNING', 'COMPLETED', 'EVALUATED', 'FAILED', 'ORPHANED')
    ),
    CONSTRAINT ck_backtest_run_market_type CHECK (market_type IN ('SPOT', 'FUTURES')),
    CONSTRAINT ck_backtest_run_period CHECK (period_start < period_end),
    CONSTRAINT ck_backtest_run_warmup_candles CHECK (warmup_candles >= 0),
    CONSTRAINT ck_backtest_run_indicator_mode CHECK (
        indicator_mode IN ('auto', 'explicit', 'all')
    ),
    CONSTRAINT ck_backtest_run_trigger_feed CHECK (
        trigger_feed IN ('tf_candle', 'm1_subcandle')
    ),
    CONSTRAINT ck_backtest_run_fill_timing CHECK (
        fill_timing IN ('next_bar', 'immediate')
    ),
    CONSTRAINT ck_backtest_run_initial_capital CHECK (
        initial_capital > 0
        AND initial_capital <= 92233720368.54775807
    ),
    CONSTRAINT ck_backtest_run_sizing_method CHECK (
        sizing_method IN ('risk_based', 'pct')
    ),
    CONSTRAINT ck_backtest_run_risk_per_trade CHECK (
        risk_per_trade IS NULL
        OR (risk_per_trade > 0 AND risk_per_trade <= 0.0100)
    ),
    CONSTRAINT ck_backtest_run_position_size_pct CHECK (
        position_size_pct IS NULL
        OR (position_size_pct > 0 AND position_size_pct <= 1.0000)
    ),
    CONSTRAINT ck_backtest_run_sizing_values CHECK (
        (
            sizing_method = 'risk_based'
            AND risk_per_trade IS NOT NULL
            AND position_size_pct IS NULL
            AND framework_compliant
        )
        OR (
            sizing_method = 'pct'
            AND risk_per_trade IS NULL
            AND position_size_pct IS NOT NULL
            AND NOT framework_compliant
        )
    ),
    CONSTRAINT ck_backtest_run_config_hash CHECK (
        config_hash ~ '^[0-9A-Fa-f]{64}$'
    ),
    CONSTRAINT ck_backtest_run_source_data_hash CHECK (
        source_data_hash IS NULL
        OR source_data_hash ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT ck_backtest_run_envelope_status CHECK (
        envelope_status_declared IS NULL
        OR envelope_status_declared IN ('provisional', 'updating', 'established')
    ),
    CONSTRAINT ck_backtest_run_evidence_hash CHECK (
        evidence_hash IS NULL
        OR evidence_hash ~ '^[0-9A-Fa-f]{64}$'
    ),
    CONSTRAINT ck_backtest_run_timestamps CHECK (
        finished_at IS NULL OR finished_at >= started_at
    )
);

-- CREATE TABLE IF NOT EXISTS does not update an already-applied constraint.
-- Replace it explicitly so rerunning this migration upgrades existing databases.
ALTER TABLE public.backtest_run
    DROP CONSTRAINT IF EXISTS ck_backtest_run_run_id;
ALTER TABLE public.backtest_run
    ADD CONSTRAINT ck_backtest_run_run_id CHECK (
        run_id ~ (
            '^BT_[0-9]{8}_'
            || lpad(
                run_seq::text,
                greatest(6, length(run_seq::text)),
                '0'
            )
            || '_'
            || run_name
            || '$'
        )
    );

ALTER SEQUENCE public.backtest_run_seq
    OWNED BY public.backtest_run.run_seq;

COMMENT ON SEQUENCE public.backtest_run_seq IS
    'Sole run sequence issuer. Issued values are never reclaimed or reused, including failed runs.';
COMMENT ON COLUMN public.backtest_run.run_id IS
    'Engine assembles BT_<UTC YYYYMMDD>_<run_seq left-padded to at least 6 digits>_<run_name> after obtaining run_seq and before creating Evidence.';
COMMENT ON COLUMN public.backtest_run.config_hash IS
    'SHA-256 over 23 inputs, in order: strategy_id, strategy_version, params_json, resolved_indicators_json, params_schema_version, symbol, exchange, timeframe, market_type, period_start, period_end, data_source, indicator_mode, trigger_feed, fill_timing, initial_capital, sizing_method, risk_per_trade, position_size_pct, cost_values_json, seed, engine_version, core_lib_version.';

CREATE INDEX IF NOT EXISTS ix_backtest_run_strategy_period
    ON public.backtest_run (strategy_id, symbol, timeframe, period_start);
CREATE INDEX IF NOT EXISTS ix_backtest_run_status
    ON public.backtest_run (status);
CREATE INDEX IF NOT EXISTS ix_backtest_run_sweep_id
    ON public.backtest_run (sweep_id);
CREATE INDEX IF NOT EXISTS ix_backtest_run_config_hash
    ON public.backtest_run (config_hash);
CREATE INDEX IF NOT EXISTS ix_backtest_run_determinism_key
    ON public.backtest_run (config_hash, source_data_hash);
CREATE INDEX IF NOT EXISTS ix_backtest_run_created_at_desc
    ON public.backtest_run (created_at DESC);

CREATE TABLE IF NOT EXISTS public.backtest_summary (
    run_id VARCHAR(48) PRIMARY KEY
        REFERENCES public.backtest_run (run_id) ON DELETE CASCADE,
    trade_count INTEGER NOT NULL DEFAULT 0,
    win_count INTEGER NOT NULL DEFAULT 0,
    loss_count INTEGER NOT NULL DEFAULT 0,
    r_excluded_count INTEGER NOT NULL DEFAULT 0,
    pf DOUBLE PRECISION,
    sortino DOUBLE PRECISION,
    calmar_or_mar DOUBLE PRECISION,
    calmar_basis VARCHAR(8),
    sqn DOUBLE PRECISION,
    mdd DOUBLE PRECISION,
    ror DOUBLE PRECISION,
    sharpe DOUBLE PRECISION,
    win_rate DOUBLE PRECISION,
    payoff DOUBLE PRECISION,
    expectancy_r DOUBLE PRECISION,
    ulcer DOUBLE PRECISION,
    kelly DOUBLE PRECISION,
    annualization VARCHAR(24) NOT NULL DEFAULT 'daily_resample_sqrt365',
    initial_capital NUMERIC(28, 8) NOT NULL,
    final_equity NUMERIC(28, 8),
    net_pnl_total NUMERIC(28, 8),
    gross_pnl_total NUMERIC(28, 8),
    total_fee NUMERIC(28, 8),
    total_slippage NUMERIC(28, 8),
    total_funding NUMERIC(28, 8),
    total_liquidation_penalty NUMERIC(28, 8),
    expected_candle_count INTEGER NOT NULL DEFAULT 0,
    observed_candle_count INTEGER NOT NULL DEFAULT 0,
    source_absent_gap_count INTEGER NOT NULL DEFAULT 0,
    partial_bucket_count INTEGER NOT NULL DEFAULT 0,
    data_coverage_ratio DOUBLE PRECISION NOT NULL DEFAULT 0,
    max_consecutive_gap_bars INTEGER NOT NULL DEFAULT 0,
    max_consecutive_gap_seconds BIGINT NOT NULL DEFAULT 0,
    data_coverage_passed BOOLEAN NOT NULL DEFAULT false,
    unobservable_funding_boundary_count INTEGER NOT NULL DEFAULT 0,
    data_gap_exit_count INTEGER NOT NULL DEFAULT 0,
    integrity_passed BOOLEAN NOT NULL DEFAULT false,
    integrity_status VARCHAR(24) NOT NULL DEFAULT 'diagnostic_only',
    integrity_failed_json JSONB,
    gate_passed BOOLEAN,
    gate_stage VARCHAR(2),
    gate_verdict VARCHAR(24),
    gate_failed_json JSONB,
    envelope_result VARCHAR(16),
    envelope_deviated_json JSONB,
    decision_route VARCHAR(16),
    decision_rationale TEXT,
    oos_degradation DOUBLE PRECISION,
    psr DOUBLE PRECISION,
    harness_json JSONB,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_backtest_summary_counts CHECK (
        trade_count >= 0
        AND win_count >= 0
        AND loss_count >= 0
        AND r_excluded_count >= 0
        AND win_count + loss_count <= trade_count
        AND r_excluded_count <= trade_count
    ),
    CONSTRAINT ck_backtest_summary_coverage CHECK (
        expected_candle_count >= 0
        AND observed_candle_count BETWEEN 0 AND expected_candle_count
        AND source_absent_gap_count >= 0
        AND partial_bucket_count >= 0
        AND source_absent_gap_count + partial_bucket_count
            = expected_candle_count - observed_candle_count
        AND data_coverage_ratio BETWEEN 0 AND 1
        AND max_consecutive_gap_bars >= 0
        AND max_consecutive_gap_seconds >= 0
        AND unobservable_funding_boundary_count >= 0
        AND data_gap_exit_count >= 0
    ),
    CONSTRAINT ck_backtest_summary_calmar_basis CHECK (
        calmar_basis IS NULL OR calmar_basis IN ('calmar', 'mar')
    ),
    CONSTRAINT ck_backtest_summary_mdd CHECK (mdd IS NULL OR mdd BETWEEN 0 AND 1),
    CONSTRAINT ck_backtest_summary_ror CHECK (ror IS NULL OR ror BETWEEN 0 AND 1),
    CONSTRAINT ck_backtest_summary_win_rate CHECK (
        win_rate IS NULL OR win_rate BETWEEN 0 AND 1
    ),
    CONSTRAINT ck_backtest_summary_initial_capital CHECK (
        initial_capital > 0
        AND initial_capital <= 92233720368.54775807
    ),
    CONSTRAINT ck_backtest_summary_money_bounds CHECK (
        (final_equity IS NULL OR abs(final_equity) <= 92233720368.54775807)
        AND (net_pnl_total IS NULL OR abs(net_pnl_total) <= 92233720368.54775807)
        AND (gross_pnl_total IS NULL OR abs(gross_pnl_total) <= 92233720368.54775807)
        AND (total_fee IS NULL OR total_fee BETWEEN 0 AND 92233720368.54775807)
        AND (
            total_slippage IS NULL
            OR total_slippage BETWEEN 0 AND 92233720368.54775807
        )
        AND (
            total_funding IS NULL
            OR abs(total_funding) <= 92233720368.54775807
        )
        AND (
            total_liquidation_penalty IS NULL
            OR total_liquidation_penalty BETWEEN 0 AND 92233720368.54775807
        )
    ),
    CONSTRAINT ck_backtest_summary_net_pnl CHECK (
        num_nonnulls(
            net_pnl_total,
            gross_pnl_total,
            total_fee,
            total_slippage,
            total_funding,
            total_liquidation_penalty
        ) < 6
        OR net_pnl_total = (
            gross_pnl_total
            - total_fee
            - total_slippage
            - total_funding
            - total_liquidation_penalty
        )
    ),
    CONSTRAINT ck_backtest_summary_integrity_status CHECK (
        integrity_status IN ('passed', 'diagnostic_only')
        AND (
            (integrity_passed AND integrity_status = 'passed')
            OR (NOT integrity_passed AND integrity_status = 'diagnostic_only')
        )
    ),
    CONSTRAINT ck_backtest_summary_integrity_failed_json CHECK (
        integrity_failed_json IS NULL
        OR jsonb_typeof(integrity_failed_json) = 'array'
    ),
    CONSTRAINT ck_backtest_summary_gate_stage CHECK (
        gate_stage IS NULL OR gate_stage IN ('A', 'B')
    ),
    CONSTRAINT ck_backtest_summary_gate_verdict CHECK (
        gate_verdict IS NULL
        OR gate_verdict IN ('pass', 'not_promotable', 'established_regression')
    ),
    CONSTRAINT ck_backtest_summary_gate_failed_json CHECK (
        gate_failed_json IS NULL OR jsonb_typeof(gate_failed_json) = 'array'
    ),
    CONSTRAINT ck_backtest_summary_envelope_result CHECK (
        envelope_result IS NULL
        OR envelope_result IN ('in_range', 'warning', 'reject')
    ),
    CONSTRAINT ck_backtest_summary_envelope_deviated_json CHECK (
        envelope_deviated_json IS NULL
        OR jsonb_typeof(envelope_deviated_json) = 'array'
    ),
    CONSTRAINT ck_backtest_summary_decision_route CHECK (
        decision_route IS NULL
        OR decision_route IN ('promote', 'partial_keep', 'retest', 'abandon')
    ),
    CONSTRAINT ck_backtest_summary_psr CHECK (psr IS NULL OR psr BETWEEN 0 AND 1)
);

CREATE INDEX IF NOT EXISTS ix_backtest_summary_decision_route
    ON public.backtest_summary (decision_route);
CREATE INDEX IF NOT EXISTS ix_backtest_summary_gate_pf
    ON public.backtest_summary (gate_passed, pf);
CREATE INDEX IF NOT EXISTS ix_backtest_summary_sortino
    ON public.backtest_summary (sortino);

CREATE TABLE IF NOT EXISTS public.backtest_prereg (
    run_id VARCHAR(48) PRIMARY KEY
        REFERENCES public.backtest_run (run_id) ON DELETE CASCADE,
    hypothesis TEXT NOT NULL,
    weakness_addressed TEXT,
    primary_metric VARCHAR(40) NOT NULL,
    success_criteria_json JSONB NOT NULL,
    failure_criteria_json JSONB,
    profile_update_declared BOOLEAN NOT NULL DEFAULT false,
    related_finding_ref VARCHAR(80),
    declared_by VARCHAR(60) NOT NULL,
    declared_at TIMESTAMPTZ NOT NULL,
    locked_at TIMESTAMPTZ
);

CREATE OR REPLACE FUNCTION public.prevent_locked_backtest_prereg_update()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.locked_at IS NOT NULL THEN
        RAISE EXCEPTION 'locked backtest_prereg rows are immutable';
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_backtest_prereg_locked
    ON public.backtest_prereg;
CREATE TRIGGER trg_backtest_prereg_locked
    BEFORE UPDATE ON public.backtest_prereg
    FOR EACH ROW
    EXECUTE FUNCTION public.prevent_locked_backtest_prereg_update();

CREATE TABLE IF NOT EXISTS public.backtest_tag (
    tag_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    run_id VARCHAR(48) NOT NULL
        REFERENCES public.backtest_run (run_id) ON DELETE CASCADE,
    tag_type VARCHAR(24) NOT NULL,
    tag_value VARCHAR(120) NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_backtest_tag_run_type_value UNIQUE (run_id, tag_type, tag_value),
    CONSTRAINT ck_backtest_tag_type CHECK (
        tag_type IN ('classification', 'purpose', 'weakness', 'improvement', 'usability')
    )
);

CREATE INDEX IF NOT EXISTS ix_backtest_tag_type_value
    ON public.backtest_tag (tag_type, tag_value);

RESET ROLE;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO backtest_reader;

COMMIT;
