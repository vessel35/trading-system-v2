\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS public.trading_signals (
    signal_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    strategy_id VARCHAR(80) NOT NULL,
    params_json JSONB NOT NULL,
    source_mode VARCHAR(10) NOT NULL,
    symbol VARCHAR(30) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    candle_open_time TIMESTAMPTZ NOT NULL,
    candle_close_time TIMESTAMPTZ NOT NULL,
    signal_time TIMESTAMPTZ NOT NULL,
    signal_type VARCHAR(4) NOT NULL,
    derived_intent VARCHAR(10) NOT NULL,
    derived_side VARCHAR(5),
    price NUMERIC(20, 8) NOT NULL,
    confidence NUMERIC(7, 6) NOT NULL,
    stop_loss NUMERIC(20, 8),
    take_profit NUMERIC(20, 8),
    market_type VARCHAR(10) NOT NULL,
    leverage INTEGER,
    reason TEXT NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_trading_signals_decision UNIQUE (
        strategy_id,
        params_json,
        source_mode,
        symbol,
        exchange,
        timeframe,
        candle_close_time
    ),
    CONSTRAINT ck_trading_signals_source_mode CHECK (
        source_mode IN ('paper', 'live')
    ),
    CONSTRAINT ck_trading_signals_times CHECK (
        candle_open_time < candle_close_time
        AND signal_time <= candle_close_time
    ),
    CONSTRAINT ck_trading_signals_signal_type CHECK (
        signal_type IN ('BUY', 'SELL', 'HOLD')
    ),
    CONSTRAINT ck_trading_signals_intent CHECK (
        derived_intent IN ('enter', 'reverse', 'exit')
    ),
    CONSTRAINT ck_trading_signals_side CHECK (
        derived_side IS NULL OR derived_side IN ('long', 'short')
    ),
    CONSTRAINT ck_trading_signals_price CHECK (
        price > 0
        AND (stop_loss IS NULL OR stop_loss > 0)
        AND (take_profit IS NULL OR take_profit > 0)
    ),
    CONSTRAINT ck_trading_signals_confidence CHECK (
        confidence >= 0 AND confidence <= 1
    ),
    CONSTRAINT ck_trading_signals_market_type CHECK (
        market_type IN ('spot', 'futures')
    ),
    CONSTRAINT ck_trading_signals_leverage CHECK (
        leverage IS NULL OR leverage > 0
    ),
    CONSTRAINT ck_trading_signals_metadata CHECK (
        jsonb_typeof(metadata_json) = 'object'
    ),
    CONSTRAINT ck_trading_signals_params CHECK (
        jsonb_typeof(params_json) = 'object'
    )
);

COMMENT ON TABLE public.trading_signals IS
    'Operational paper/live decisions produced from finalized v2 candles.';
COMMENT ON COLUMN public.trading_signals.signal_type IS
    'Persistence-only direction derived by the signal-service driver.';
COMMENT ON COLUMN public.trading_signals.derived_intent IS
    'Driver-derived enter, reverse, or exit action; not strategy judgment logic.';
COMMENT ON COLUMN public.trading_signals.params_json IS
    'Core-resolved Adaptee parameters included in the idempotency identity.';

CREATE INDEX IF NOT EXISTS ix_trading_signals_created
    ON public.trading_signals (created_at DESC);

GRANT USAGE ON SCHEMA public TO signal_writer;
GRANT SELECT, INSERT ON TABLE public.trading_signals TO signal_writer;
GRANT USAGE, SELECT
    ON SEQUENCE public.trading_signals_signal_id_seq
    TO signal_writer;

COMMIT;
