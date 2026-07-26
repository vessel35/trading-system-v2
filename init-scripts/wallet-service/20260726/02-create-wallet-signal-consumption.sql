\set ON_ERROR_STOP on

BEGIN;

-- This wallet-owned receipt is the only acknowledgement of a signal. The
-- signal-service trading_signals row remains immutable and read-only here.
CREATE TABLE IF NOT EXISTS public.wallet_signal_consumption (
    wallet_id VARCHAR(80) NOT NULL,
    signal_id VARCHAR(120) NOT NULL,
    mode VARCHAR(10) NOT NULL DEFAULT 'paper',
    consumed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (wallet_id, signal_id),
    CONSTRAINT ck_wallet_signal_consumption_paper_only CHECK (mode = 'paper')
);

CREATE INDEX IF NOT EXISTS ix_wallet_signal_consumption_consumed
    ON public.wallet_signal_consumption (wallet_id, consumed_at DESC);

COMMENT ON TABLE public.wallet_signal_consumption IS
    'Wallet-owned paper receipt; source trading_signals remains read-only.';

GRANT SELECT, INSERT ON TABLE public.wallet_signal_consumption TO wallet_writer;

COMMIT;
