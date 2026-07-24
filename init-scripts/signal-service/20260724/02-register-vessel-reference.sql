\set ON_ERROR_STOP on

BEGIN;

INSERT INTO public.strategy_registry (
    strategy_id,
    class_name,
    module_path,
    display_name,
    description,
    strategy_version,
    supported_timeframes,
    required_indicators_json,
    min_history,
    default_params_json,
    is_active,
    is_deprecated
)
VALUES (
    'vessel-reference',
    'VesselReference',
    'core_lib.strategy.adaptees.vessel_reference',
    'Vessel Reference',
    'Trailing-free Vessel reference Adaptee for deterministic pipeline validation.',
    '1.0.0',
    ARRAY['1h']::text[],
    '[
        {"name": "EMA", "params": {"period": 9}},
        {"name": "EMA", "params": {"period": 21}},
        {"name": "ATR", "params": {"period": 14}}
    ]'::jsonb,
    21,
    '{
        "atr_stop_multiple": 2.0,
        "reward_risk": 2.0,
        "leverage": 1
    }'::jsonb,
    true,
    false
)
ON CONFLICT (strategy_id) DO UPDATE
SET class_name = excluded.class_name,
    module_path = excluded.module_path,
    display_name = excluded.display_name,
    description = excluded.description,
    strategy_version = excluded.strategy_version,
    supported_timeframes = excluded.supported_timeframes,
    required_indicators_json = excluded.required_indicators_json,
    min_history = excluded.min_history,
    default_params_json = excluded.default_params_json,
    is_active = excluded.is_active,
    is_deprecated = excluded.is_deprecated,
    updated_at = CURRENT_TIMESTAMP
WHERE (
    strategy_registry.class_name,
    strategy_registry.module_path,
    strategy_registry.display_name,
    strategy_registry.description,
    strategy_registry.strategy_version,
    strategy_registry.supported_timeframes,
    strategy_registry.required_indicators_json,
    strategy_registry.min_history,
    strategy_registry.default_params_json,
    strategy_registry.is_active,
    strategy_registry.is_deprecated
) IS DISTINCT FROM (
    excluded.class_name,
    excluded.module_path,
    excluded.display_name,
    excluded.description,
    excluded.strategy_version,
    excluded.supported_timeframes,
    excluded.required_indicators_json,
    excluded.min_history,
    excluded.default_params_json,
    excluded.is_active,
    excluded.is_deprecated
);

COMMIT;
