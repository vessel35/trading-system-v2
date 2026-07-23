\set ON_ERROR_STOP on

BEGIN;

-- The operator must verify that the legacy catalog is empty, or obtain explicit
-- approval to discard its rows, immediately before executing this migration.
DROP TABLE IF EXISTS public.strategy_registry;

CREATE TABLE public.strategy_registry (
    strategy_id VARCHAR(80) PRIMARY KEY,
    class_name VARCHAR(255) NOT NULL UNIQUE,
    module_path VARCHAR(500) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    strategy_version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    supported_timeframes TEXT[] NOT NULL DEFAULT ARRAY['1h']::text[],
    required_indicators_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    min_history INTEGER NOT NULL DEFAULT 100,
    default_params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT false,
    is_deprecated BOOLEAN NOT NULL DEFAULT false,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_strategy_registry_strategy_id CHECK (
        strategy_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
    ),
    CONSTRAINT ck_strategy_registry_supported_timeframes CHECK (
        cardinality(supported_timeframes) > 0
        AND array_position(supported_timeframes, NULL) IS NULL
    ),
    CONSTRAINT ck_strategy_registry_required_indicators CHECK (
        jsonb_typeof(required_indicators_json) = 'array'
    ),
    CONSTRAINT ck_strategy_registry_min_history CHECK (min_history >= 1),
    CONSTRAINT ck_strategy_registry_default_params CHECK (
        jsonb_typeof(default_params_json) = 'object'
    )
);

CREATE INDEX ix_strategy_registry_active
    ON public.strategy_registry (strategy_id)
    WHERE is_active AND NOT is_deprecated;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'signal_writer') THEN
        GRANT ALL PRIVILEGES ON TABLE public.strategy_registry TO signal_writer;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'signal_reader') THEN
        GRANT SELECT ON TABLE public.strategy_registry TO signal_reader;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'traderreader') THEN
        GRANT SELECT ON TABLE public.strategy_registry TO traderreader;
    END IF;
END
$$;

COMMIT;
