ALTER TABLE public.backtest_summary
    ADD COLUMN IF NOT EXISTS expected_candle_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS observed_candle_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS source_absent_gap_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS partial_bucket_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS data_coverage_ratio DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_consecutive_gap_bars INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_consecutive_gap_seconds BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS data_coverage_passed BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS unobservable_funding_boundary_count
        INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS data_gap_exit_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE public.backtest_summary
    DROP CONSTRAINT IF EXISTS ck_backtest_summary_coverage;

ALTER TABLE public.backtest_summary
    ADD CONSTRAINT ck_backtest_summary_coverage CHECK (
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
    );
