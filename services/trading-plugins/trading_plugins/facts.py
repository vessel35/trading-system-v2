"""Expose repository-owned strategy facts without copying deployment inventory."""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Mapping, Sequence
from dataclasses import MISSING, asdict, fields
from enum import Enum
from typing import Any, Final, Literal, cast

from core_lib.capabilities import PLATFORM_CAPABILITIES, Capability
from core_lib.indicators.registry import build_default_registry
from core_lib.money_management import (
    MoneyManagementBase,
    PolicyIndicatorRequirement,
    policy_settings,
    reconcile_money_management_availability,
)
from core_lib.patterns import TALIB_PATTERN_REGISTRY
from core_lib.ports import StrategyRegistry
from core_lib.strategy import (
    AdapterClass,
    AdapterManager,
    InProcessStrategyRegistry,
    StrategyConfig,
    reconcile_strategy_registries,
)

from .discovery import discover_money_management, discover_strategies

type JSONScalar = str | int | float | bool | None
type JSONValue = JSONScalar | list[JSONValue] | dict[str, JSONValue]
type JSONObject = dict[str, JSONValue]
type PluginKind = Literal["strategy", "money_management"]

_PATTERN_DEFINITION_REFERENCE: Final = "docs/references/candlestick_pattern_calc_spec.md"
_PATTERN_DEFINITION_CHECK: Final = (
    f"Check this pattern definition against {_PATTERN_DEFINITION_REFERENCE}."
)
_NOT_CHECKED: Final = (
    "execution timeframe support",
    "series resolution",
    "policy input arity",
    "live-signal capability",
    "return-type violation on the first decision",
)
_USAGE: Final = (
    "usage: python -m trading_plugins.facts "
    "<capabilities|series|deployed|declaration|registration_sql|catalog_precheck> [args]"
)


class FactsError(ValueError):
    """A readable lookup failure safe to return from the command-line boundary."""


def _plain(value: object) -> JSONValue:
    """Convert declarations to strict JSON values without stringifying unknown objects."""
    if isinstance(value, Enum):
        return _plain(value.value)
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise FactsError("a declared fact contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        result: JSONObject = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise FactsError("a declared fact contains a non-string object key")
            result[key] = _plain(item)
        return result
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    raise FactsError(f"a declared fact has unsupported type {type(value).__name__!r}")


def _object(value: object) -> JSONObject:
    plain = _plain(value)
    if not isinstance(plain, dict):
        raise FactsError("a declared fact expected an object")
    return plain


def _capability_payload(entry: Capability) -> JSONObject:
    return {
        "id": entry.id,
        "statement": entry.statement,
        "value": _plain(entry.value),
        "proof": entry.proof.value,
        "verified_by": list(entry.verified_by),
    }


def capabilities(identifier: str | None = None) -> JSONObject | list[JSONObject]:
    """Return every platform capability, or the exact entry named by ``identifier``."""
    if identifier is None:
        return [_capability_payload(entry) for entry in PLATFORM_CAPABILITIES.values()]
    entry = PLATFORM_CAPABILITIES.get(identifier)
    if entry is None:
        raise FactsError(f"unknown capability: {identifier}")
    return _capability_payload(entry)


def series(name: str | None = None) -> list[JSONObject]:
    """Return registered indicator combinations and candlestick patterns."""
    result: list[JSONObject] = []
    for indicator_spec in build_default_registry().list():
        if name is None or indicator_spec.name == name:
            result.append(
                {
                    "name": indicator_spec.name,
                    "params": _object(indicator_spec.params),
                    "min_history": indicator_spec.min_history,
                    "kind": "indicator",
                    "pinned_impl": indicator_spec.pinned_impl,
                }
            )
    for pattern_spec in TALIB_PATTERN_REGISTRY.list():
        if name is None or pattern_spec.name == name:
            result.append(
                {
                    "name": pattern_spec.name,
                    "params": _object(pattern_spec.params),
                    "min_history": pattern_spec.min_history,
                    "kind": "pattern",
                    "version": pattern_spec.version,
                    "definition_check": _PATTERN_DEFINITION_CHECK,
                }
            )
    if name is not None and not result:
        raise FactsError(f"unknown series: {name}")
    return result


def _plugin_kind(kind: str) -> PluginKind:
    if kind == "strategy" or kind == "money_management":
        return cast(PluginKind, kind)
    raise FactsError(f"unknown plugin kind: {kind}")


def deployed(kind: str) -> JSONObject:
    """Return plugins found in the fixed package and every isolated discovery fault."""
    resolved_kind = _plugin_kind(kind)
    if resolved_kind == "strategy":
        strategies, faults = discover_strategies()
        items = [
            {
                "identifier": identifier,
                "class_name": plugin_class.__name__,
                "module_path": plugin_class.__module__,
            }
            for identifier, plugin_class in sorted(strategies.items())
        ]
    else:
        policies, faults = discover_money_management()
        items = [
            {
                "identifier": identifier,
                "class_name": plugin_class.__name__,
                "module_path": plugin_class.__module__,
            }
            for identifier, plugin_class in sorted(policies.items())
        ]
    return {
        "kind": resolved_kind,
        "items": cast(JSONValue, items),
        "faults": [{"module": fault.module, "reason": fault.reason} for fault in faults],
    }


def _strategy_declaration(identifier: str) -> JSONObject:
    found, faults = discover_strategies()
    strategy_class = found.get(identifier)
    if strategy_class is None:
        if faults:
            return {
                "kind": "strategy",
                "identifier": identifier,
                "discovery_faults": [
                    {"module": fault.module, "reason": fault.reason} for fault in faults
                ],
            }
        raise FactsError(f"unknown strategy: {identifier}")
    try:
        metadata = strategy_class.get_metadata()
        parameter_schema = StrategyConfig.json_schema(strategy_class.get_parameter_schema())
    except (Exception, SystemExit) as error:
        raise FactsError(f"could not read strategy declaration: {identifier}") from error

    version = vars(strategy_class).get("VERSION")
    if version is not None and not isinstance(version, str):
        raise FactsError(f"strategy version is not a string: {identifier}")
    support = metadata.money_management
    return {
        "kind": "strategy",
        "identifier": identifier,
        "class_name": strategy_class.__name__,
        "module_path": strategy_class.__module__,
        "version": version,
        "metadata": {
            "required_indicators": _plain(metadata.required_indicators),
            "min_history": metadata.min_history,
            "supported_timeframes": list(metadata.supported_timeframes),
            "decision_contract": metadata.decision_contract.value,
            "money_management": {
                "supported": list(support.supported),
                "default": support.default,
                "supports_external_stop": support.supports_external_stop,
                "supports_external_take_profit": support.supports_external_take_profit,
                "supports_signal_exit": support.supports_signal_exit,
                "supports_pyramiding": support.supports_pyramiding,
            },
        },
        "profile": _object(asdict(metadata.profile)),
        "parameter_schema": _object(parameter_schema),
    }


def _policy_settings(
    policy_class: type[MoneyManagementBase],
) -> tuple[JSONObject, dict[str, object] | None]:
    setting_names = policy_settings(policy_class)
    settings: JSONObject = {}
    constructor_values: dict[str, object] = {}
    every_setting_has_default = True
    for declared in fields(cast(Any, policy_class)):
        if declared.name not in setting_names:
            continue
        if declared.default is not MISSING:
            value = declared.default
        elif declared.default_factory is not MISSING:
            value = declared.default_factory()
        else:
            settings[declared.name] = {"has_default": False}
            every_setting_has_default = False
            continue
        settings[declared.name] = {
            "has_default": True,
            "default": _plain(value),
        }
        constructor_values[declared.name] = value
    return settings, constructor_values if every_setting_has_default else None


def _policy_requirement(requirement: PolicyIndicatorRequirement) -> JSONObject:
    return {
        "name": requirement.name,
        "params": _object(requirement.params),
        "timeframe": requirement.timeframe,
        "min_history": requirement.min_history,
    }


def _policy_declaration(identifier: str) -> JSONObject:
    found, _ = discover_money_management()
    policy_class = found.get(identifier)
    if policy_class is None:
        raise FactsError(f"unknown money-management policy: {identifier}")
    try:
        settings, constructor_values = _policy_settings(policy_class)
    except (Exception, SystemExit) as error:
        raise FactsError(f"could not read money-management declaration: {identifier}") from error

    requirements: list[JSONObject] = []
    requirements_unavailable_reason: str | None = None
    if constructor_values is None:
        requirements_unavailable_reason = "policy has settings without defaults"
    else:
        try:
            policy = policy_class(**constructor_values)
        except (Exception, SystemExit):
            requirements_unavailable_reason = "policy could not be constructed from defaults"
        else:
            try:
                requirements = [
                    _policy_requirement(requirement) for requirement in policy.required_indicators()
                ]
            except FactsError:
                raise
            except (Exception, SystemExit) as error:
                raise FactsError(
                    f"could not read money-management declaration: {identifier}"
                ) from error

    version = getattr(policy_class, "version", None)
    if not isinstance(version, str):
        raise FactsError(f"money-management version is not a string: {identifier}")
    return {
        "kind": "money_management",
        "identifier": identifier,
        "class_name": policy_class.__name__,
        "module_path": policy_class.__module__,
        "settings": settings,
        "version": version,
        "requires_signal_exit": policy_class.requires_signal_exit,
        "protection_and_leverage_ignore_account_state": (
            policy_class.protection_and_leverage_ignore_account_state
        ),
        "indicator_requirements": cast(JSONValue, requirements),
        "indicator_requirements_unavailable_reason": requirements_unavailable_reason,
    }


def declaration(kind: str, identifier: str) -> JSONObject:
    """Return the declaration owned by one discovered strategy or policy class."""
    resolved_kind = _plugin_kind(kind)
    if resolved_kind == "strategy":
        return _strategy_declaration(identifier)
    return _policy_declaration(identifier)


def _strict_json_text(value: object) -> str:
    return json.dumps(
        _plain(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sql_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise FactsError(f"{name} must be a string")
    return "'" + value.replace("'", "''") + "'"


def _sql_json(value: object) -> str:
    return f"{_sql_text(_strict_json_text(value), 'JSON')}::jsonb"


def _sql_text_array(values: object, name: str) -> str:
    if not isinstance(values, list | tuple) or any(not isinstance(item, str) for item in values):
        raise FactsError(f"{name} must be an array of strings")
    if not values:
        return "ARRAY[]::text[]"
    return "ARRAY[" + ", ".join(_sql_text(item, name) for item in values) + "]::text[]"


def _strategy_class(identifier: str) -> AdapterClass:
    found, _ = discover_strategies()
    strategy_class = found.get(identifier)
    if strategy_class is None:
        raise FactsError(f"unknown strategy: {identifier}")
    return strategy_class


def _policy_class(identifier: str) -> type[MoneyManagementBase]:
    found, _ = discover_money_management()
    policy_class = found.get(identifier)
    if policy_class is None:
        raise FactsError(f"unknown money-management policy: {identifier}")
    return policy_class


def _validate_module_path(kind: PluginKind, module_path: object) -> str:
    if not isinstance(module_path, str):
        raise FactsError("module_path must be a string")
    package = (
        "trading_plugins.strategies." if kind == "strategy" else "trading_plugins.money_management."
    )
    if not module_path.startswith(package):
        raise FactsError(f"module_path must be inside {package[:-1]}")
    return module_path


def _canonical_series(requirements: object) -> list[JSONObject]:
    if not isinstance(requirements, list | tuple):
        raise FactsError("required_indicators must be an array")
    result = [_object(requirement) for requirement in requirements]
    return sorted(result, key=_json_order_key)


def _json_order_key(value: JSONValue) -> tuple[Any, ...]:
    """Give JSON values one total order without comparing unlike Python types."""
    if value is None:
        return ("0-null",)
    if isinstance(value, bool):
        return ("1-boolean", value)
    if isinstance(value, int | float):
        return ("2-number", value)
    if isinstance(value, str):
        return ("3-string", value)
    if isinstance(value, list):
        return ("4-array", tuple(_json_order_key(item) for item in value))
    return (
        "5-object",
        tuple((key, _json_order_key(item)) for key, item in sorted(value.items())),
    )


def _strategy_registration_row(
    identifier: str,
    display_name: str,
    description: str,
    is_active: bool,
    default_params: Mapping[str, object] | None,
) -> JSONObject:
    strategy_class = _strategy_class(identifier)
    try:
        metadata = strategy_class.get_metadata()
    except (Exception, SystemExit) as error:
        raise FactsError(f"could not read strategy declaration: {identifier}") from error
    version = vars(strategy_class).get("VERSION")
    if not isinstance(version, str) or not version:
        raise FactsError(f"strategy version is not a non-empty string: {identifier}")
    if not isinstance(is_active, bool):
        raise FactsError("is_active must be a boolean")
    params = {} if default_params is None else _object(default_params)
    return {
        "strategy_id": identifier,
        "class_name": strategy_class.__name__,
        "module_path": _validate_module_path("strategy", strategy_class.__module__),
        "display_name": display_name,
        "description": description,
        "strategy_version": version,
        "supported_timeframes": _plain(metadata.supported_timeframes),
        "required_indicators_json": cast(
            JSONValue, _canonical_series(metadata.required_indicators)
        ),
        "min_history": metadata.min_history,
        "default_params_json": params,
        "is_active": is_active,
        "is_deprecated": False,
    }


def _policy_registration_row(
    identifier: str,
    display_name: str,
    description: str,
    is_active: bool,
) -> JSONObject:
    policy_class = _policy_class(identifier)
    if not isinstance(is_active, bool):
        raise FactsError("is_active must be a boolean")
    version = getattr(policy_class, "version", None)
    if not isinstance(version, str) or not version:
        raise FactsError(f"money-management version is not a non-empty string: {identifier}")
    return {
        "mode": identifier,
        "class_name": policy_class.__name__,
        "module_path": _validate_module_path("money_management", policy_class.__module__),
        "display_name": display_name,
        "description": description,
        "policy_version": version,
        "settings_names": cast(JSONValue, sorted(policy_settings(policy_class))),
        "is_active": is_active,
        "is_deprecated": False,
    }


def _registration_row(
    kind: PluginKind,
    identifier: str,
    display_name: str,
    description: str,
    is_active: bool,
    default_params: Mapping[str, object] | None,
) -> JSONObject:
    _sql_text(identifier, "identifier")
    _sql_text(display_name, "display_name")
    _sql_text(description, "description")
    if kind == "strategy":
        return _strategy_registration_row(
            identifier,
            display_name,
            description,
            is_active,
            default_params,
        )
    if default_params is not None:
        raise FactsError("default_params is only valid for a strategy")
    return _policy_registration_row(identifier, display_name, description, is_active)


def _sql_value(column: str, value: JSONValue) -> str:
    if column in {"supported_timeframes", "settings_names"}:
        return _sql_text_array(value, column)
    if column in {"required_indicators_json", "default_params_json"}:
        return _sql_json(value)
    if column in {"is_active", "is_deprecated"}:
        if not isinstance(value, bool):
            raise FactsError(f"{column} must be a boolean")
        return "true" if value else "false"
    if column == "min_history":
        if isinstance(value, bool) or not isinstance(value, int):
            raise FactsError("min_history must be an integer")
        return str(value)
    return _sql_text(value, column)


def registration_sql(
    kind: str,
    identifier: str,
    display_name: str,
    description: str,
    is_active: bool,
    default_params: Mapping[str, object] | None = None,
) -> str:
    """Generate one idempotent catalog statement without changing lifecycle on conflict."""
    resolved_kind = _plugin_kind(kind)
    row = _registration_row(
        resolved_kind,
        identifier,
        display_name,
        description,
        is_active,
        default_params,
    )
    columns = tuple(row)
    conflict_column = "strategy_id" if resolved_kind == "strategy" else "mode"
    update_columns = tuple(
        column
        for column in columns
        if column not in {conflict_column, "is_active", "is_deprecated"}
    )
    table = (
        "public.strategy_registry"
        if resolved_kind == "strategy"
        else "public.money_management_registry"
    )
    table_name = table.rsplit(".", 1)[-1]
    column_lines = ",\n".join(f"    {column}" for column in columns)
    value_lines = ",\n".join(f"    {_sql_value(column, row[column])}" for column in columns)
    set_lines = ",\n".join(f"    {column} = excluded.{column}" for column in update_columns)
    current_tuple = ",\n".join(f"    {table_name}.{column}" for column in update_columns)
    excluded_tuple = ",\n".join(f"    excluded.{column}" for column in update_columns)
    return (
        f"INSERT INTO {table} (\n{column_lines}\n)\n"
        f"VALUES (\n{value_lines}\n)\n"
        f"ON CONFLICT ({conflict_column}) DO UPDATE\n"
        f"SET\n{set_lines}\n"
        f"WHERE (\n{current_tuple}\n) IS DISTINCT FROM (\n{excluded_tuple}\n);"
    )


class _MemoryStrategyRegistry(StrategyRegistry):
    """Present one candidate row through the runtime's external-catalog port."""

    def __init__(self, identifier: str, row: Mapping[str, object]) -> None:
        self._identifier = identifier
        self._row = dict(row)

    def get(self, strategy_id: str) -> dict[str, object]:
        if strategy_id != self._identifier:
            raise KeyError(strategy_id)
        return dict(self._row)

    def list(self) -> list[dict[str, object]]:
        return [dict(self._row)]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError("catalog precheck is read-only")


def _precheck_strategy(identifier: str, row: Mapping[str, object]) -> JSONObject:
    strategy_class = _strategy_class(identifier)
    catalog = _MemoryStrategyRegistry(identifier, row)
    adapters = InProcessStrategyRegistry()
    adapters.register(identifier, strategy_class)
    findings = list(reconcile_strategy_registries(catalog, adapters))
    construction_error: str | None = None
    try:
        policies, _ = discover_money_management()
        params = row.get("default_params_json", {})
        AdapterManager(
            catalog,
            adapters,
            money_management_policies=policies,
        ).create(identifier, {"strategy_id": identifier, "params": params})
    except (Exception, SystemExit) as error:  # runtime owns the rules being reported here
        construction_error = f"{type(error).__name__}: {error}"
    result: JSONObject = {
        "kind": "strategy",
        "identifier": identifier,
        "passed": not findings and construction_error is None,
        "findings": _plain([asdict(finding) for finding in findings]),
        "adapter_construction_error": construction_error,
        "checks_performed": [
            "catalog identity and declaration",
            "catalog lifecycle",
            "adapter construction",
        ],
        "not_checked": list(_NOT_CHECKED),
    }
    return result


def _precheck_policy(identifier: str, row: Mapping[str, object]) -> JSONObject:
    policy_class = _policy_class(identifier)
    availability = reconcile_money_management_availability(
        [row],
        {identifier: policy_class},
    )
    findings = [item for item in availability if not item.runnable]
    return {
        "kind": "money_management",
        "identifier": identifier,
        "passed": not findings,
        "findings": _plain([asdict(finding) for finding in findings]),
        "adapter_construction_error": None,
        "checks_performed": [
            "catalog identity and declaration",
            "catalog lifecycle",
        ],
        "not_checked": list(_NOT_CHECKED),
    }


def catalog_precheck(
    kind: str,
    identifier: str,
    row: Mapping[str, object] | None = None,
) -> JSONObject:
    """Compare one candidate row using runtime comparators, without runtime simulation."""
    resolved_kind = _plugin_kind(kind)
    candidate = (
        _registration_row(resolved_kind, identifier, identifier, "", True, None)
        if row is None
        else _object(row)
    )
    if resolved_kind == "strategy":
        return _precheck_strategy(identifier, candidate)
    return _precheck_policy(identifier, candidate)


def _reject_json_constant(value: str) -> None:
    raise FactsError(f"JSON contains a non-finite number: {value}")


def _json_object_argument(value: str, name: str) -> JSONObject:
    try:
        parsed = json.loads(value, parse_constant=_reject_json_constant)
    except FactsError:
        raise
    except json.JSONDecodeError as error:
        raise FactsError(f"{name} must be valid JSON") from error
    try:
        return _object(parsed)
    except FactsError as error:
        raise FactsError(f"{name} must be a JSON object") from error


def _boolean_argument(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise FactsError("is_active must be true or false")


def _arguments(argv: Sequence[str]) -> JSONValue:
    if not argv:
        raise FactsError(_USAGE)
    name, *args = argv
    if name == "capabilities" and len(args) <= 1:
        return cast(JSONValue, capabilities(args[0] if args else None))
    if name == "series" and len(args) <= 1:
        return cast(JSONValue, series(args[0] if args else None))
    if name == "deployed" and len(args) == 1:
        return deployed(args[0])
    if name == "declaration" and len(args) == 2:
        return declaration(args[0], args[1])
    if name == "registration_sql" and len(args) in {5, 6}:
        default_params = (
            _json_object_argument(args[5], "default_params") if len(args) == 6 else None
        )
        return registration_sql(
            args[0],
            args[1],
            args[2],
            args[3],
            _boolean_argument(args[4]),
            default_params,
        )
    if name == "catalog_precheck" and len(args) in {2, 3}:
        row = _json_object_argument(args[2], "row") if len(args) == 3 else None
        return catalog_precheck(args[0], args[1], row)
    if name not in {
        "capabilities",
        "series",
        "deployed",
        "declaration",
        "registration_sql",
        "catalog_precheck",
    }:
        raise FactsError(f"unknown fact lookup: {name}")
    raise FactsError(_USAGE)


def _write(payload: JSONValue) -> None:
    print(json.dumps(payload, allow_nan=False, ensure_ascii=False, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    """Run one fact lookup and keep every command-line result JSON-shaped."""
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    try:
        payload = _arguments(arguments)
    except FactsError as error:
        _write({"error": error.args[0]})
        return 1
    except (Exception, SystemExit):  # noqa: BLE001 - never expose plugin exceptions
        _write({"error": "fact lookup failed"})
        return 1
    _write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "capabilities",
    "catalog_precheck",
    "declaration",
    "deployed",
    "main",
    "registration_sql",
    "series",
]
