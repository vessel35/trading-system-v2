\set ON_ERROR_STOP on

BEGIN;

-- Lock and fingerprint the existing relation before any destructive action.
-- A target-schema table is retained on reruns. Only the exact legacy layout is
-- eligible for replacement, and its rows must be either empty or the two known
-- seed examples. DROP without CASCADE also refuses database-level dependents.
DO $$
DECLARE
    is_target_schema BOOLEAN;
    is_legacy_schema BOOLEAN;
    registry_row_count BIGINT;
    rsi_seed_count BIGINT;
    macd_seed_count BIGINT;
    referencing_fk_count BIGINT;
    referencing_view_count BIGINT;
    referencing_function_count BIGINT;
BEGIN
    IF to_regclass('public.strategy_registry') IS NULL THEN
        RETURN;
    END IF;

    LOCK TABLE public.strategy_registry IN ACCESS EXCLUSIVE MODE;

    SELECT
        count(*) = 14
        AND count(*) FILTER (
            WHERE column_name = ANY (ARRAY[
                'strategy_id',
                'class_name',
                'module_path',
                'display_name',
                'description',
                'strategy_version',
                'supported_timeframes',
                'required_indicators_json',
                'min_history',
                'default_params_json',
                'is_active',
                'is_deprecated',
                'registered_at',
                'updated_at'
            ])
        ) = 14
    INTO is_target_schema
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'strategy_registry';

    IF is_target_schema THEN
        RETURN;
    END IF;

    SELECT
        count(*) = 15
        AND count(*) FILTER (
            WHERE column_name = ANY (ARRAY[
                'id',
                'class_name',
                'module_path',
                'display_name',
                'description',
                'version',
                'min_compatible_version',
                'parameter_schema',
                'default_parameters',
                'supported_timeframes',
                'required_indicators',
                'is_available',
                'is_deprecated',
                'registered_at',
                'updated_at'
            ])
        ) = 15
    INTO is_legacy_schema
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'strategy_registry';

    IF NOT is_legacy_schema THEN
        RAISE EXCEPTION
            'refusing to replace strategy_registry with an unknown column layout';
    END IF;

    SELECT
        count(*),
        count(*) FILTER (WHERE id = 1 AND class_name = 'RSIStrategy'),
        count(*) FILTER (WHERE id = 2 AND class_name = 'MACDStrategy')
    INTO registry_row_count, rsi_seed_count, macd_seed_count
    FROM public.strategy_registry;

    IF registry_row_count <> 0
       AND NOT (
           registry_row_count = 2
           AND rsi_seed_count = 1
           AND macd_seed_count = 1
       )
    THEN
        RAISE EXCEPTION
            'refusing to replace strategy_registry: expected no rows or the two known seed examples, found % rows',
            registry_row_count;
    END IF;

    SELECT count(*)
    INTO referencing_fk_count
    FROM pg_constraint
    WHERE confrelid = 'public.strategy_registry'::regclass
      AND conrelid <> 'public.strategy_registry'::regclass;

    SELECT count(DISTINCT dependent_view.oid)
    INTO referencing_view_count
    FROM pg_depend dependency
    JOIN pg_rewrite rewrite_rule
      ON rewrite_rule.oid = dependency.objid
    JOIN pg_class dependent_view
      ON dependent_view.oid = rewrite_rule.ev_class
    WHERE dependency.refobjid = 'public.strategy_registry'::regclass
      AND dependent_view.oid <> 'public.strategy_registry'::regclass;

    SELECT count(*)
    INTO referencing_function_count
    FROM pg_depend
    WHERE refobjid = 'public.strategy_registry'::regclass
      AND classid = 'pg_proc'::regclass;

    IF referencing_fk_count > 0
       OR referencing_view_count > 0
       OR referencing_function_count > 0
    THEN
        RAISE EXCEPTION
            'refusing to replace referenced strategy_registry: foreign keys %, views %, functions %',
            referencing_fk_count,
            referencing_view_count,
            referencing_function_count;
    END IF;

    DROP TABLE public.strategy_registry;
END
$$;

CREATE TABLE IF NOT EXISTS public.strategy_registry (
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

CREATE INDEX IF NOT EXISTS ix_strategy_registry_active
    ON public.strategy_registry (strategy_id)
    WHERE is_active AND NOT is_deprecated;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'signal_writer') THEN
        GRANT ALL PRIVILEGES ON TABLE public.strategy_registry TO signal_writer;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'traderreader') THEN
        GRANT SELECT ON TABLE public.strategy_registry TO traderreader;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO signal_reader;
GRANT SELECT ON TABLE public.strategy_registry TO signal_reader;

COMMIT;
