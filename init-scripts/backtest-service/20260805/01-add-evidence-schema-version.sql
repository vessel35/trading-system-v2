\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE public.backtest_run
    ADD COLUMN IF NOT EXISTS evidence_schema_version VARCHAR(40);

UPDATE public.backtest_run
SET evidence_schema_version = 'unknown'
WHERE evidence_schema_version IS NULL;

ALTER TABLE public.backtest_run
    ALTER COLUMN evidence_schema_version SET NOT NULL;

DROP INDEX IF EXISTS public.ix_backtest_run_determinism_key;

CREATE INDEX ix_backtest_run_determinism_key
    ON public.backtest_run (config_hash, source_data_hash, evidence_schema_version);

COMMENT ON COLUMN public.backtest_run.evidence_schema_version IS
    'Immutable Evidence artifact schema version; unknown marks pre-migration rows whose version cannot be identified.';

COMMIT;
