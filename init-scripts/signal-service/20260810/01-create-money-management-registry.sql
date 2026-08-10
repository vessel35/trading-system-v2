\set ON_ERROR_STOP on

BEGIN;

CREATE OR REPLACE FUNCTION public.money_management_settings_names_are_canonical(
    names TEXT[]
)
RETURNS BOOLEAN
LANGUAGE SQL
IMMUTABLE
PARALLEL SAFE
AS $function$
    SELECT names = COALESCE(
        array_agg(DISTINCT name ORDER BY name),
        ARRAY[]::text[]
    )
    FROM unnest(names) AS name
$function$;

CREATE TABLE IF NOT EXISTS public.money_management_registry (
    mode VARCHAR(80) PRIMARY KEY,
    class_name VARCHAR(255) NOT NULL UNIQUE,
    module_path VARCHAR(500) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    policy_version VARCHAR(20) NOT NULL,
    settings_names TEXT[] NOT NULL DEFAULT ARRAY[]::text[],
    is_active BOOLEAN NOT NULL DEFAULT false,
    is_deprecated BOOLEAN NOT NULL DEFAULT false,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_money_management_registry_mode CHECK (
        mode ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
    ),
    CONSTRAINT ck_money_management_registry_settings_names CHECK (
        array_position(settings_names, NULL) IS NULL
        AND public.money_management_settings_names_are_canonical(settings_names)
    )
);

CREATE INDEX IF NOT EXISTS ix_money_management_registry_active
    ON public.money_management_registry (mode)
    WHERE is_active AND NOT is_deprecated;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'signal_writer') THEN
        GRANT ALL PRIVILEGES ON TABLE public.money_management_registry TO signal_writer;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'traderreader') THEN
        GRANT SELECT ON TABLE public.money_management_registry TO traderreader;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO signal_reader;
GRANT SELECT ON TABLE public.money_management_registry TO signal_reader;

INSERT INTO public.money_management_registry (
    mode,
    class_name,
    module_path,
    display_name,
    description,
    policy_version,
    settings_names,
    is_active,
    is_deprecated
)
VALUES
    (
        'manual',
        'ManualMoneyManagement',
        'trading_plugins.money_management.manual',
        'Manual',
        'Reproduce the legacy Vessel ATR stop, fixed target, and leverage.',
        '1.0.0',
        ARRAY['atr_stop_multiple', 'leverage', 'reward_risk']::text[],
        true,
        false
    ),
    (
        'turtle',
        'TurtleMoneyManagement',
        'trading_plugins.money_management.turtle',
        'Turtle',
        'Apply Turtle-derived daily N sizing under the platform 1% risk cap.',
        '1.0.0',
        ARRAY['leverage_cap', 'n_period', 'n_timeframe', 'stop_n_multiple']::text[],
        true,
        false
    )
ON CONFLICT (mode) DO UPDATE
SET class_name = excluded.class_name,
    module_path = excluded.module_path,
    display_name = excluded.display_name,
    description = excluded.description,
    policy_version = excluded.policy_version,
    settings_names = excluded.settings_names,
    is_active = excluded.is_active,
    is_deprecated = excluded.is_deprecated,
    updated_at = CURRENT_TIMESTAMP
WHERE (
    money_management_registry.class_name,
    money_management_registry.module_path,
    money_management_registry.display_name,
    money_management_registry.description,
    money_management_registry.policy_version,
    money_management_registry.settings_names,
    money_management_registry.is_active,
    money_management_registry.is_deprecated
) IS DISTINCT FROM (
    excluded.class_name,
    excluded.module_path,
    excluded.display_name,
    excluded.description,
    excluded.policy_version,
    excluded.settings_names,
    excluded.is_active,
    excluded.is_deprecated
);

COMMIT;
