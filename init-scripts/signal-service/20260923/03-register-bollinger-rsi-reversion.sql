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
    'bollinger-rsi-reversion',
    'BollingerRsiReversion',
    'trading_plugins.strategies.bollinger_rsi_reversion',
    'Bollinger RSI Reversion',
    'Close outside Bollinger Bands(20, 2.0) with an RSI(14) extreme enters; the close returning to the middle band exits. Source: docs/samples_for_strategy_agent/03.BollingerRSI_MeanReversion.md',
    '1.0.0',
    ARRAY['1h', '4h']::text[],
    '[{"name":"Bollinger Bands","params":{"multiplier":2.0,"period":20}},{"name":"RSI","params":{"period":14}}]'::jsonb,
    1,
    '{"rsi_overbought":70.0,"rsi_oversold":30.0}'::jsonb,
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
