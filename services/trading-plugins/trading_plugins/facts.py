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
)
from core_lib.patterns import TALIB_PATTERN_REGISTRY
from core_lib.strategy import StrategyConfig

from .discovery import discover_money_management, discover_strategies

type JSONScalar = str | int | float | bool | None
type JSONValue = JSONScalar | list[JSONValue] | dict[str, JSONValue]
type JSONObject = dict[str, JSONValue]
type PluginKind = Literal["strategy", "money_management"]

_PATTERN_DEFINITION_REFERENCE: Final = "docs/references/candlestick_pattern_calc_spec.md"
_PATTERN_DEFINITION_CHECK: Final = (
    f"Check this pattern definition against {_PATTERN_DEFINITION_REFERENCE}."
)
_USAGE: Final = (
    "usage: python -m trading_plugins.facts <capabilities|series|deployed|declaration> [args]"
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
    if name not in {"capabilities", "series", "deployed", "declaration"}:
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


__all__ = ["capabilities", "declaration", "deployed", "main", "series"]
