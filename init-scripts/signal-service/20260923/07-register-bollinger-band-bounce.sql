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
    'bollinger-band-bounce',
    'BollingerBandBounce',
    'trading_plugins.strategies.bollinger_band_bounce',
    'Bollinger Band Bounce',
    'Fade a close at or below the lower Bollinger band (20-period, 2 SD) with a long and a close at or above the upper band with a short; exits are the manual policy''s stop and target. The strategy declares manual atr_stop_multiple 1.5 and reward_risk 1.5 as its default settings, so a run submitted without settings reproduces the source. Source: docs/samples_for_strategy_agent/06.Bollinger_Band_Bounce.md',
    '1.0.0',
    ARRAY['1h']::text[],
    '[{"name":"Bollinger Bands","params":{"multiplier":2.0,"period":20}}]'::jsonb,
    1,
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
