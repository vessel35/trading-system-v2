\set ON_ERROR_STOP on

\connect crypto_data

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE public.ohlcv_futures (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(30) NOT NULL,
    exchange VARCHAR(20) NOT NULL DEFAULT 'binance',
    timeframe VARCHAR(10) NOT NULL,
    open NUMERIC(20, 8) NOT NULL,
    high NUMERIC(20, 8) NOT NULL,
    low NUMERIC(20, 8) NOT NULL,
    close NUMERIC(20, 8) NOT NULL,
    volume NUMERIC(30, 8),
    quote_volume NUMERIC(30, 8),
    trade_count INTEGER,
    ingest_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_ohlcv_futures
        PRIMARY KEY (time, symbol, exchange, timeframe),
    CONSTRAINT ck_ohlcv_futures_1m_source CHECK (timeframe = '1m'),
    CONSTRAINT ck_ohlcv_futures_prices CHECK (
        open > 0
        AND high > 0
        AND low > 0
        AND close > 0
        AND high >= greatest(open, close)
        AND low <= least(open, close)
    ),
    CONSTRAINT ck_ohlcv_futures_volume CHECK (
        volume IS NULL OR volume >= 0
    ),
    CONSTRAINT ck_ohlcv_futures_quote_volume CHECK (
        quote_volume IS NULL OR quote_volume >= 0
    ),
    CONSTRAINT ck_ohlcv_futures_trade_count CHECK (
        trade_count IS NULL OR trade_count >= 0
    )
);

COMMENT ON TABLE public.ohlcv_futures IS
    'Confirmed Binance futures 1m candles owned by trading-system-v2.';
COMMENT ON COLUMN public.ohlcv_futures.time IS
    'UTC candle open time; only confirmed candles may be stored.';
COMMENT ON COLUMN public.ohlcv_futures.ingest_time IS
    'Wall-clock ingestion metadata, excluded from decisions and deterministic hashes.';

SELECT create_hypertable(
    'public.ohlcv_futures',
    by_range('time', INTERVAL '1 day'),
    if_not_exists => TRUE
);

CREATE INDEX ix_ohlcv_futures_symbol_time
    ON public.ohlcv_futures (symbol, exchange, time DESC);

CREATE TABLE public.funding_rates (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(30) NOT NULL,
    exchange VARCHAR(20) NOT NULL DEFAULT 'binance',
    funding_rate NUMERIC(20, 10) NOT NULL,
    mark_price NUMERIC(20, 8),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_funding_rates PRIMARY KEY (time, symbol, exchange),
    CONSTRAINT ck_funding_rates_mark_price CHECK (
        mark_price IS NULL OR mark_price > 0
    )
);

COMMENT ON TABLE public.funding_rates IS
    'Observed funding rates at settlement boundaries; missing rows are not zero rates.';
COMMENT ON COLUMN public.funding_rates.funding_rate IS
    'Observed rate retained at source precision (10 decimal places).';

SELECT create_hypertable(
    'public.funding_rates',
    by_range('time', INTERVAL '7 days'),
    if_not_exists => TRUE
);

CREATE INDEX ix_funding_rates_symbol_time
    ON public.funding_rates (symbol, exchange, time DESC);

CREATE MATERIALIZED VIEW public.ohlcv_futures_5m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '5 minutes', time) AS time,
    symbol,
    exchange,
    '5m'::VARCHAR(10) AS timeframe,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume,
    sum(quote_volume) AS quote_volume,
    sum(trade_count) AS trade_count
FROM public.ohlcv_futures
WHERE timeframe = '1m'
GROUP BY time_bucket(INTERVAL '5 minutes', time), symbol, exchange
WITH NO DATA;

CREATE MATERIALIZED VIEW public.ohlcv_futures_15m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '15 minutes', time) AS time,
    symbol,
    exchange,
    '15m'::VARCHAR(10) AS timeframe,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume,
    sum(quote_volume) AS quote_volume,
    sum(trade_count) AS trade_count
FROM public.ohlcv_futures
WHERE timeframe = '1m'
GROUP BY time_bucket(INTERVAL '15 minutes', time), symbol, exchange
WITH NO DATA;

CREATE MATERIALIZED VIEW public.ohlcv_futures_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '1 hour', time) AS time,
    symbol,
    exchange,
    '1h'::VARCHAR(10) AS timeframe,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume,
    sum(quote_volume) AS quote_volume,
    sum(trade_count) AS trade_count
FROM public.ohlcv_futures
WHERE timeframe = '1m'
GROUP BY time_bucket(INTERVAL '1 hour', time), symbol, exchange
WITH NO DATA;

CREATE MATERIALIZED VIEW public.ohlcv_futures_4h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '4 hours', time) AS time,
    symbol,
    exchange,
    '4h'::VARCHAR(10) AS timeframe,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume,
    sum(quote_volume) AS quote_volume,
    sum(trade_count) AS trade_count
FROM public.ohlcv_futures
WHERE timeframe = '1m'
GROUP BY time_bucket(INTERVAL '4 hours', time), symbol, exchange
WITH NO DATA;

CREATE MATERIALIZED VIEW public.ohlcv_futures_1d
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '1 day', time) AS time,
    symbol,
    exchange,
    '1d'::VARCHAR(10) AS timeframe,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume,
    sum(quote_volume) AS quote_volume,
    sum(trade_count) AS trade_count
FROM public.ohlcv_futures
WHERE timeframe = '1m'
GROUP BY time_bucket(INTERVAL '1 day', time), symbol, exchange
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'public.ohlcv_futures_5m',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE
);
SELECT add_continuous_aggregate_policy(
    'public.ohlcv_futures_15m',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '15 minutes',
    if_not_exists => TRUE
);
SELECT add_continuous_aggregate_policy(
    'public.ohlcv_futures_1h',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);
SELECT add_continuous_aggregate_policy(
    'public.ohlcv_futures_4h',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '4 hours',
    if_not_exists => TRUE
);
SELECT add_continuous_aggregate_policy(
    'public.ohlcv_futures_1d',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

ALTER TABLE public.ohlcv_futures SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol,exchange,timeframe',
    timescaledb.compress_orderby = 'time DESC'
);
ALTER TABLE public.funding_rates SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol,exchange',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy(
    'public.ohlcv_futures',
    compress_after => INTERVAL '7 days',
    if_not_exists => TRUE
);
SELECT add_compression_policy(
    'public.funding_rates',
    compress_after => INTERVAL '7 days',
    if_not_exists => TRUE
);

SELECT add_retention_policy(
    'public.ohlcv_futures',
    drop_after => INTERVAL '2000 days',
    if_not_exists => TRUE
);
SELECT add_retention_policy(
    'public.funding_rates',
    drop_after => INTERVAL '2000 days',
    if_not_exists => TRUE
);

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO data_writer, data_reader;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON TABLE public.ohlcv_futures, public.funding_rates
    TO data_writer;
GRANT SELECT
    ON TABLE
        public.ohlcv_futures,
        public.funding_rates,
        public.ohlcv_futures_5m,
        public.ohlcv_futures_15m,
        public.ohlcv_futures_1h,
        public.ohlcv_futures_4h,
        public.ohlcv_futures_1d
    TO data_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO data_reader;
