-- Maintain the per-series OHLCV holdings summary the operator console reads.
--
-- The console previously derived holdings by aggregating the whole 1m base table on
-- every page load, so its cost grew with retained history rather than with what it
-- displayed. This summary carries one row per series and is maintained as the base
-- table changes, which turns that page load into a small indexed read.
--
-- Maintenance is statement-level with transition tables: one bounded update per
-- statement instead of one per row, which keeps million-row backfills cheap. An
-- INSERT ... ON CONFLICT DO UPDATE contributes only its genuinely inserted rows to
-- the NEW transition table, so the counter follows real insertions.

CREATE TABLE IF NOT EXISTS public.ohlcv_futures_inventory (
    symbol VARCHAR(30) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    available_from TIMESTAMPTZ,
    available_to TIMESTAMPTZ,
    row_count BIGINT NOT NULL DEFAULT 0,
    refreshed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_ohlcv_futures_inventory PRIMARY KEY (symbol, exchange, timeframe),
    CONSTRAINT ck_ohlcv_futures_inventory_row_count CHECK (row_count >= 0),
    CONSTRAINT ck_ohlcv_futures_inventory_bounds CHECK (
        (available_from IS NULL AND available_to IS NULL)
        OR (available_from IS NOT NULL AND available_to IS NOT NULL
            AND available_from <= available_to)
    )
);

COMMENT ON TABLE public.ohlcv_futures_inventory IS
    'Per-series holdings summary of ohlcv_futures, maintained by statement triggers.';
COMMENT ON COLUMN public.ohlcv_futures_inventory.row_count IS
    'Stored rows for the series. Expected rows and gaps are derived by the reader.';
COMMENT ON COLUMN public.ohlcv_futures_inventory.refreshed_at IS
    'When this row last changed; a full rebuild stamps it for every series.';

-- Rebuild holdings from the base table. This is the authority the incremental path is
-- checked against, and the repair for changes triggers cannot observe: retention drops
-- whole chunks as DDL, which fires no DELETE trigger, so dropped history would
-- otherwise leave available_from stale.
--
-- The rebuild walks one series at a time. Aggregating the whole table in a single
-- GROUP BY over symbol, exchange and timeframe terminates the backend on this
-- TimescaleDB build, while the same aggregate with the series fixed is ordinary work,
-- so the series list is enumerated through the (symbol, exchange) index and each one
-- is summarized on its own.
CREATE OR REPLACE FUNCTION public.refresh_ohlcv_futures_inventory(
    target_symbol VARCHAR DEFAULT NULL,
    target_exchange VARCHAR DEFAULT NULL,
    target_timeframe VARCHAR DEFAULT NULL
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    series RECORD;
    touched BIGINT := 0;
    written BIGINT;
BEGIN
    FOR series IN
        WITH RECURSIVE walked AS (
            (
                SELECT symbol, exchange
                FROM public.ohlcv_futures
                ORDER BY symbol, exchange
                LIMIT 1
            )
            UNION ALL
            SELECT following.symbol, following.exchange
            FROM walked,
            LATERAL (
                SELECT source.symbol, source.exchange
                FROM public.ohlcv_futures AS source
                WHERE (source.symbol, source.exchange) > (walked.symbol, walked.exchange)
                ORDER BY source.symbol, source.exchange
                LIMIT 1
            ) AS following
        )
        SELECT symbol, exchange FROM walked
        WHERE (target_symbol IS NULL OR symbol = target_symbol)
          AND (target_exchange IS NULL OR exchange = target_exchange)
    LOOP
        INSERT INTO public.ohlcv_futures_inventory AS inventory (
            symbol, exchange, timeframe, available_from, available_to, row_count, refreshed_at
        )
        SELECT
            series.symbol, series.exchange, source.timeframe,
            min(source.time), max(source.time), count(*), CURRENT_TIMESTAMP
        FROM public.ohlcv_futures AS source
        WHERE source.symbol = series.symbol
          AND source.exchange = series.exchange
          AND (target_timeframe IS NULL OR source.timeframe = target_timeframe)
        GROUP BY source.timeframe
        ON CONFLICT (symbol, exchange, timeframe) DO UPDATE
        SET available_from = excluded.available_from,
            available_to = excluded.available_to,
            row_count = excluded.row_count,
            refreshed_at = excluded.refreshed_at;
        GET DIAGNOSTICS written = ROW_COUNT;
        touched := touched + written;
    END LOOP;

    -- A series whose rows are all gone is no longer enumerated above, so it is emptied
    -- rather than left advertising history the table no longer holds.
    UPDATE public.ohlcv_futures_inventory AS inventory
    SET available_from = NULL,
        available_to = NULL,
        row_count = 0,
        refreshed_at = CURRENT_TIMESTAMP
    WHERE (target_symbol IS NULL OR inventory.symbol = target_symbol)
      AND (target_exchange IS NULL OR inventory.exchange = target_exchange)
      AND (target_timeframe IS NULL OR inventory.timeframe = target_timeframe)
      AND inventory.row_count <> 0
      AND NOT EXISTS (
          SELECT 1
          FROM public.ohlcv_futures AS source
          WHERE source.symbol = inventory.symbol
            AND source.exchange = inventory.exchange
            AND source.timeframe = inventory.timeframe
      );
    GET DIAGNOSTICS written = ROW_COUNT;
    RETURN touched + written;
END $$;

COMMENT ON FUNCTION public.refresh_ohlcv_futures_inventory IS
    'Rebuild holdings from ohlcv_futures. Call after retention drops chunks.';

CREATE OR REPLACE FUNCTION public.ohlcv_futures_inventory_on_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO public.ohlcv_futures_inventory AS inventory (
        symbol, exchange, timeframe, available_from, available_to, row_count, refreshed_at
    )
    SELECT
        symbol, exchange, timeframe,
        min(time), max(time), count(*), CURRENT_TIMESTAMP
    FROM inserted
    GROUP BY symbol, exchange, timeframe
    ON CONFLICT (symbol, exchange, timeframe) DO UPDATE
    SET available_from = LEAST(
            COALESCE(inventory.available_from, excluded.available_from),
            excluded.available_from
        ),
        available_to = GREATEST(
            COALESCE(inventory.available_to, excluded.available_to),
            excluded.available_to
        ),
        row_count = inventory.row_count + excluded.row_count,
        refreshed_at = excluded.refreshed_at;
    RETURN NULL;
END $$;

-- Deletion can remove the row that defined either bound, and the surviving bound is
-- not derivable from the deleted set, so the summary is recomputed. A compressed
-- hypertable rejects DELETE triggers that carry a transition table, so the deleted
-- rows are not visible here and every series is rebuilt. Ordinary ingestion never
-- deletes: this path exists for corrections and manual repair, where paying one full
-- rebuild per statement buys a summary that is always right.
CREATE OR REPLACE FUNCTION public.ohlcv_futures_inventory_on_delete()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM public.refresh_ohlcv_futures_inventory();
    RETURN NULL;
END $$;

-- An UPDATE only affects holdings when it moves a row's `time`, which changes the
-- bounds without changing the count. Ingestion never does this: the collector upserts
-- on the primary key, so a conflicting row keeps the time it matched on. Firing per
-- row under a WHEN guard therefore costs nothing during ingestion, where a
-- statement-level recompute would rebuild a whole series on every overlapping page.
CREATE OR REPLACE FUNCTION public.ohlcv_futures_inventory_on_time_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM public.refresh_ohlcv_futures_inventory(NEW.symbol, NEW.exchange, NEW.timeframe);
    IF OLD.symbol IS DISTINCT FROM NEW.symbol
        OR OLD.exchange IS DISTINCT FROM NEW.exchange
        OR OLD.timeframe IS DISTINCT FROM NEW.timeframe
    THEN
        PERFORM public.refresh_ohlcv_futures_inventory(
            OLD.symbol, OLD.exchange, OLD.timeframe
        );
    END IF;
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS trg_ohlcv_futures_inventory_insert ON public.ohlcv_futures;
CREATE TRIGGER trg_ohlcv_futures_inventory_insert
    AFTER INSERT ON public.ohlcv_futures
    REFERENCING NEW TABLE AS inserted
    FOR EACH STATEMENT
    EXECUTE FUNCTION public.ohlcv_futures_inventory_on_insert();

DROP TRIGGER IF EXISTS trg_ohlcv_futures_inventory_delete ON public.ohlcv_futures;
CREATE TRIGGER trg_ohlcv_futures_inventory_delete
    AFTER DELETE ON public.ohlcv_futures
    FOR EACH STATEMENT
    EXECUTE FUNCTION public.ohlcv_futures_inventory_on_delete();

DROP TRIGGER IF EXISTS trg_ohlcv_futures_inventory_update ON public.ohlcv_futures;
CREATE TRIGGER trg_ohlcv_futures_inventory_update
    AFTER UPDATE ON public.ohlcv_futures
    FOR EACH ROW
    WHEN (
        OLD.time IS DISTINCT FROM NEW.time
        OR OLD.symbol IS DISTINCT FROM NEW.symbol
        OR OLD.exchange IS DISTINCT FROM NEW.exchange
        OR OLD.timeframe IS DISTINCT FROM NEW.timeframe
    )
    EXECUTE FUNCTION public.ohlcv_futures_inventory_on_time_change();

-- Seed the summary from whatever the table already holds.
SELECT public.refresh_ohlcv_futures_inventory();

GRANT SELECT ON TABLE public.ohlcv_futures_inventory TO data_reader;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON TABLE public.ohlcv_futures_inventory TO data_writer;
