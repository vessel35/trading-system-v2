\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE public.backtest_run
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

-- The default catalog listing reads only rows that were never marked deleted,
-- so the supporting index covers exactly that partition instead of the table.
CREATE INDEX IF NOT EXISTS ix_backtest_run_visible_created_at
    ON public.backtest_run (created_at DESC, run_seq DESC)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_backtest_run_deleted_at
    ON public.backtest_run (deleted_at DESC)
    WHERE deleted_at IS NOT NULL;

COMMENT ON COLUMN public.backtest_run.deleted_at IS
    'Soft-delete marker. NULL means the run is listed normally; a timestamp hides it from the default catalog listing while every row, summary, and Evidence artifact is retained and remains reachable by run_id or by an explicit deleted-only query.';

COMMIT;
