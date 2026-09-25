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
    'three-bar-reversion',
    'ThreeBarReversion',
    'trading_plugins.strategies.three_bar_reversion',
    'Three Bar Reversion',
    'Buy on the bar that completes three consecutive red candles, sell short on three consecutive green; exits are the manual policy''s stop and target. Run with manual atr_stop_multiple 1.5 and reward_risk 1.5 to reproduce the source. Source: docs/samples_for_strategy_agent/05.Three_Bar_Reversion.md',
    '1.0.0',
    ARRAY['1h']::text[],
    '[]'::jsonb,
    3,
    '{}'::jsonb,
    true,
    false
)
ON CONFLICT (strategy_id) DO UPDATE
SET
    class_name = excluded.class_name,
    module_path = excluded.module_path,
    display_name = excluded.display_name,
    description = excluded.description,
    strategy_version = excluded.strategy_version,
    supported_timeframes = excluded.supported_timeframes,
    required_indicators_json = excluded.required_indicators_json,
    min_history = excluded.min_history,
    default_params_json = excluded.default_params_json
WHERE (
    strategy_registry.class_name,
    strategy_registry.module_path,
    strategy_registry.display_name,
    strategy_registry.description,
    strategy_registry.strategy_version,
    strategy_registry.supported_timeframes,
    strategy_registry.required_indicators_json,
    strategy_registry.min_history,
    strategy_registry.default_params_json
) IS DISTINCT FROM (
    excluded.class_name,
    excluded.module_path,
    excluded.display_name,
    excluded.description,
    excluded.strategy_version,
    excluded.supported_timeframes,
    excluded.required_indicators_json,
    excluded.min_history,
    excluded.default_params_json
);

COMMIT;
