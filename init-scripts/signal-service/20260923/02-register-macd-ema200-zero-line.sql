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
    'macd-ema200-zero-line',
    'MacdEma200ZeroLine',
    'trading_plugins.strategies.macd_ema200_zero_line',
    'MACD EMA200 Zero Line',
    'MACD(12, 26, 9) above its signal below zero (long) or below its signal above zero (short) on the EMA 200 side; the policy stop and target exit. Source: docs/samples_for_strategy_agent/02.MACD_EMA200_ZeroLine.md',
    '1.0.0',
    ARRAY['1h', '4h']::text[],
    '[{"name":"EMA","params":{"period":200}},{"name":"MACD","params":{"fast_period":12,"signal_period":9,"slow_period":26}}]'::jsonb,
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
