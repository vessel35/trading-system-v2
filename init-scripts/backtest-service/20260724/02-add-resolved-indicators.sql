\set ON_ERROR_STOP on

BEGIN;

SET ROLE backtest_writer;

ALTER TABLE public.backtest_run
    ADD COLUMN IF NOT EXISTS resolved_indicators_json JSONB NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.backtest_run.resolved_indicators_json IS
    'Canonical resolved indicator identities (name, params, implementation version) used by this run.';
COMMENT ON COLUMN public.backtest_run.config_hash IS
    'SHA-256 over 23 inputs, in order: strategy_id, strategy_version, params_json, resolved_indicators_json, params_schema_version, symbol, exchange, timeframe, market_type, period_start, period_end, data_source, indicator_mode, trigger_feed, fill_timing, initial_capital, sizing_method, risk_per_trade, position_size_pct, cost_values_json, seed, engine_version, core_lib_version.';

COMMIT;
