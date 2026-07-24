\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE public.backtest_run
    ADD COLUMN IF NOT EXISTS source_data_hash VARCHAR(64);

ALTER TABLE public.backtest_run
    DROP CONSTRAINT IF EXISTS ck_backtest_run_source_data_hash;

ALTER TABLE public.backtest_run
    ADD CONSTRAINT ck_backtest_run_source_data_hash CHECK (
        source_data_hash IS NULL
        OR source_data_hash ~ '^[0-9a-f]{64}$'
    );

CREATE INDEX IF NOT EXISTS ix_backtest_run_determinism_key
    ON public.backtest_run (config_hash, source_data_hash);

COMMENT ON COLUMN public.backtest_run.source_data_hash IS
    'SHA-256 fingerprint over ordered SOURCE_DATA_SNAPSHOT identities and content_hash values; paired with config_hash for deterministic comparison selection.';

COMMIT;
