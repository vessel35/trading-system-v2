\set ON_ERROR_STOP on

BEGIN;

-- This wallet-owned receipt is the only acknowledgement of a signal. The
-- signal-service trading_signals row remains immutable and read-only here.
CREATE TABLE IF NOT EXISTS public.wallet_signal_consumption (
    wallet_id VARCHAR(80) NOT NULL,
    signal_id VARCHAR(120) NOT NULL,
    mode VARCHAR(10) NOT NULL DEFAULT 'paper',
    status VARCHAR(10) NOT NULL,
    consumed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (wallet_id, signal_id),
    CONSTRAINT ck_wallet_signal_consumption_paper_only CHECK (mode = 'paper')
);

ALTER TABLE public.wallet_signal_consumption
    ADD COLUMN IF NOT EXISTS status VARCHAR(10) NOT NULL DEFAULT 'filled';

ALTER TABLE public.wallet_signal_consumption
    ALTER COLUMN status DROP DEFAULT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_wallet_signal_consumption_status'
          AND conrelid = 'public.wallet_signal_consumption'::regclass
    ) THEN
        ALTER TABLE public.wallet_signal_consumption
            ADD CONSTRAINT ck_wallet_signal_consumption_status
            CHECK (status IN ('filled', 'rejected', 'skipped'));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS ix_wallet_signal_consumption_consumed
    ON public.wallet_signal_consumption (wallet_id, consumed_at DESC);

COMMENT ON TABLE public.wallet_signal_consumption IS
    'Wallet-owned terminal paper disposition; source trading_signals remains read-only.';

GRANT SELECT, INSERT ON TABLE public.wallet_signal_consumption TO wallet_writer;

COMMIT;
