\set ON_ERROR_STOP on

BEGIN;

-- This schema is deliberately paper-only. It contains no credentials,
-- exchange order identifiers, withdrawal destinations, or remote API state.
CREATE TABLE IF NOT EXISTS public.wallet_accounts (
    wallet_id VARCHAR(80) PRIMARY KEY,
    mode VARCHAR(10) NOT NULL DEFAULT 'paper',
    cash_balance NUMERIC(30, 8) NOT NULL,
    total_equity NUMERIC(30, 8) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_wallet_accounts_paper_only CHECK (mode = 'paper'),
    CONSTRAINT ck_wallet_accounts_balances CHECK (
        cash_balance >= 0 AND total_equity >= 0
    )
);

CREATE TABLE IF NOT EXISTS public.fills (
    fill_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    wallet_id VARCHAR(80) NOT NULL,
    signal_id VARCHAR(120) NOT NULL,
    mode VARCHAR(10) NOT NULL DEFAULT 'paper',
    order_id VARCHAR(120) NOT NULL,
    symbol VARCHAR(30) NOT NULL,
    side VARCHAR(4) NOT NULL,
    position_side VARCHAR(5) NOT NULL,
    reference_price NUMERIC(20, 8) NOT NULL,
    price NUMERIC(20, 8) NOT NULL,
    quantity NUMERIC(30, 8) NOT NULL,
    fee NUMERIC(30, 8) NOT NULL,
    slippage NUMERIC(30, 8) NOT NULL,
    liquidity VARCHAR(5) NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL,
    reduce_only BOOLEAN NOT NULL,
    exit_reason VARCHAR(30),
    gap_filled BOOLEAN NOT NULL DEFAULT FALSE,
    qty_truncated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_fills_wallet_order UNIQUE (wallet_id, order_id),
    CONSTRAINT uq_fills_signal_leg UNIQUE (wallet_id, signal_id, reduce_only),
    CONSTRAINT ck_fills_paper_only CHECK (mode = 'paper'),
    CONSTRAINT ck_fills_side CHECK (side IN ('buy', 'sell')),
    CONSTRAINT ck_fills_position_side CHECK (position_side IN ('long', 'short')),
    CONSTRAINT ck_fills_liquidity CHECK (liquidity IN ('maker', 'taker')),
    CONSTRAINT ck_fills_values CHECK (
        reference_price > 0
        AND price > 0
        AND quantity > 0
        AND fee >= 0
        AND slippage >= 0
    )
);

CREATE INDEX IF NOT EXISTS ix_fills_wallet_executed
    ON public.fills (wallet_id, executed_at DESC);

CREATE TABLE IF NOT EXISTS public.positions (
    wallet_id VARCHAR(80) NOT NULL,
    mode VARCHAR(10) NOT NULL DEFAULT 'paper',
    symbol VARCHAR(30) NOT NULL,
    side VARCHAR(5) NOT NULL,
    quantity NUMERIC(30, 8) NOT NULL,
    average_price NUMERIC(20, 8) NOT NULL,
    total_cost NUMERIC(30, 8) NOT NULL,
    current_price NUMERIC(20, 8) NOT NULL,
    unrealized_pnl NUMERIC(30, 8) NOT NULL,
    market_type VARCHAR(10) NOT NULL,
    leverage INTEGER NOT NULL,
    margin_type VARCHAR(10) NOT NULL,
    margin NUMERIC(30, 8) NOT NULL,
    entry_price NUMERIC(20, 8) NOT NULL,
    mark_price NUMERIC(20, 8) NOT NULL,
    liquidation_price NUMERIC(20, 8) NOT NULL,
    funding_fee_total NUMERIC(30, 8) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (wallet_id, symbol, side),
    CONSTRAINT ck_positions_paper_only CHECK (mode = 'paper'),
    CONSTRAINT ck_positions_side CHECK (side IN ('long', 'short')),
    CONSTRAINT ck_positions_market_type CHECK (market_type IN ('spot', 'futures')),
    CONSTRAINT ck_positions_margin_type CHECK (margin_type IN ('cross', 'isolated')),
    CONSTRAINT ck_positions_values CHECK (
        quantity > 0
        AND average_price > 0
        AND total_cost > 0
        AND leverage > 0
        AND margin >= 0
    )
);

CREATE TABLE IF NOT EXISTS public.accounting_snapshots (
    snapshot_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    wallet_id VARCHAR(80) NOT NULL,
    signal_id VARCHAR(120) NOT NULL,
    mode VARCHAR(10) NOT NULL DEFAULT 'paper',
    occurred_at TIMESTAMPTZ NOT NULL,
    cash_balance NUMERIC(30, 8) NOT NULL,
    position_value NUMERIC(30, 8) NOT NULL,
    total_equity NUMERIC(30, 8) NOT NULL,
    fee_total NUMERIC(30, 8) NOT NULL,
    slippage_total NUMERIC(30, 8) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_accounting_signal UNIQUE (wallet_id, signal_id),
    CONSTRAINT ck_accounting_paper_only CHECK (mode = 'paper'),
    CONSTRAINT ck_accounting_identity CHECK (
        total_equity = cash_balance + position_value
    ),
    CONSTRAINT ck_accounting_values CHECK (
        cash_balance >= 0
        AND position_value >= 0
        AND total_equity >= 0
        AND fee_total >= 0
        AND slippage_total >= 0
    )
);

CREATE INDEX IF NOT EXISTS ix_accounting_wallet_occurred
    ON public.accounting_snapshots (wallet_id, occurred_at DESC);

COMMENT ON TABLE public.wallet_accounts IS
    'Paper-only v2 wallet balances; no exchange credentials or remote order state.';
COMMENT ON TABLE public.fills IS
    'Deterministic paper fills produced by core_lib.execution.matcher.';
COMMENT ON TABLE public.positions IS
    'Current paper position materialized from core_lib.execution.PositionBook.';
COMMENT ON TABLE public.accounting_snapshots IS
    'Paper cash + position = equity snapshots checked by core_lib accounting.';

GRANT USAGE ON SCHEMA public TO wallet_writer;
GRANT SELECT, INSERT, UPDATE ON TABLE public.wallet_accounts TO wallet_writer;
GRANT SELECT, INSERT ON TABLE public.fills TO wallet_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.positions TO wallet_writer;
GRANT SELECT, INSERT ON TABLE public.accounting_snapshots TO wallet_writer;
GRANT USAGE, SELECT
    ON SEQUENCE public.fills_fill_id_seq,
                public.accounting_snapshots_snapshot_id_seq
    TO wallet_writer;

COMMIT;
