\set ON_ERROR_STOP on

BEGIN;

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
VALUES (
    'signal_exit_atr',
    'SignalExitAtrMoneyManagement',
    'trading_plugins.money_management.signal_exit_atr',
    'Signal Exit ATR',
    'ATR-multiple stop with no target; the strategy''s EXIT decision closes the trade (authoring contract section 5.3.1 example, deployed).',
    '1.0.0',
    ARRAY['atr_period', 'atr_stop_multiple', 'leverage_cap']::text[],
    true,
    false
)
ON CONFLICT (mode) DO UPDATE
SET
    class_name = excluded.class_name,
    module_path = excluded.module_path,
    display_name = excluded.display_name,
    description = excluded.description,
    policy_version = excluded.policy_version,
    settings_names = excluded.settings_names
WHERE (
    money_management_registry.class_name,
    money_management_registry.module_path,
    money_management_registry.display_name,
    money_management_registry.description,
    money_management_registry.policy_version,
    money_management_registry.settings_names
) IS DISTINCT FROM (
    excluded.class_name,
    excluded.module_path,
    excluded.display_name,
    excluded.description,
    excluded.policy_version,
    excluded.settings_names
);

COMMIT;
