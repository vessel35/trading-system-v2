"""Interpret, validate, serialize, and expose strategy configuration schemas."""

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

SCHEMA_VERSION: Final = "1.0.0"


class _Unset:
    __slots__ = ()


UNSET: Final = _Unset()

ParameterValue = object
CrossValidator = Callable[[Mapping[str, ParameterValue]], None]
NumericBound = int | float | None


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """The declared type, default, inclusive range, and required flag for one field."""

    type: str
    default: object = UNSET
    range: tuple[NumericBound, NumericBound] | None = None
    required: bool = False


@dataclass(frozen=True, slots=True)
class ParameterSchema:
    """An Adaptee-owned parameter declaration consumed by StrategyConfig."""

    fields: Mapping[str, FieldSpec]
    extra_forbidden: bool = True
    cross_validators: tuple[CrossValidator, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))
        object.__setattr__(self, "cross_validators", tuple(self.cross_validators))


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        sorted_items = sorted(value.items(), key=lambda pair: str(pair[0]))
        return MappingProxyType(
            {str(key): _freeze(item) for key, item in sorted_items}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        sorted_items = sorted(value.items(), key=lambda pair: str(pair[0]))
        return {str(key): _thaw(item) for key, item in sorted_items}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return [_thaw(item) for item in sorted(value, key=repr)]
    return value


@dataclass(frozen=True, slots=True)
class ResolvedConfig:
    """An immutable, schema-versioned strategy configuration."""

    strategy_id: str
    params: Mapping[str, ParameterValue]
    schema_version: str

    def __post_init__(self) -> None:
        if not self.strategy_id:
            raise ValueError("strategy_id must not be empty")
        object.__setattr__(self, "params", _freeze(dict(self.params)))


class StrategyConfig:
    """Stateless interpreter for Adaptee-owned parameter schemas."""

    _TYPE_ALIASES: Final = {
        "array": "array",
        "bool": "boolean",
        "boolean": "boolean",
        "dict": "object",
        "float": "number",
        "int": "integer",
        "integer": "integer",
        "list": "array",
        "number": "number",
        "object": "object",
        "str": "string",
        "string": "string",
    }

    @classmethod
    def resolve(
        cls,
        schema: ParameterSchema,
        raw_config: Mapping[str, object],
    ) -> ResolvedConfig:
        """Merge defaults and validate wrapper, fields, ranges, extras, and cross-rules."""
        wrapper_keys = set(raw_config)
        if wrapper_keys != {"strategy_id", "params"}:
            missing = {"strategy_id", "params"} - wrapper_keys
            extra = wrapper_keys - {"strategy_id", "params"}
            raise ValueError(
                f"raw_config shape mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
            )

        strategy_id = raw_config["strategy_id"]
        raw_params = raw_config["params"]
        if not isinstance(strategy_id, str) or not strategy_id:
            raise TypeError("strategy_id must be a non-empty string")
        if not isinstance(raw_params, Mapping):
            raise TypeError("params must be a mapping")
        if any(not isinstance(key, str) for key in raw_params):
            raise TypeError("parameter names must be strings")

        extras = set(raw_params) - set(schema.fields)
        if extras and schema.extra_forbidden:
            raise ValueError(f"unexpected strategy parameters: {sorted(extras)}")

        resolved: dict[str, object] = {}
        for name, spec in schema.fields.items():
            if name in raw_params:
                value = deepcopy(raw_params[name])
            elif spec.required:
                raise ValueError(f"required strategy parameter is missing: {name}")
            elif spec.default is not UNSET:
                value = deepcopy(spec.default)
            else:
                continue
            cls._validate_field(name, value, spec)
            resolved[name] = value

        if not schema.extra_forbidden:
            for name in extras:
                resolved[name] = deepcopy(raw_params[name])

        readonly_params = MappingProxyType(dict(resolved))
        for validator in schema.cross_validators:
            validator(readonly_params)

        return ResolvedConfig(
            strategy_id=strategy_id,
            params=resolved,
            schema_version=cls.version(),
        )

    @classmethod
    def _validate_field(cls, name: str, value: object, spec: FieldSpec) -> None:
        try:
            normalized_type = cls._TYPE_ALIASES[spec.type]
        except KeyError as error:
            raise ValueError(f"unsupported field type for {name}: {spec.type}") from error

        valid = {
            "array": isinstance(value, list),
            "boolean": isinstance(value, bool),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "object": isinstance(value, Mapping),
            "string": isinstance(value, str),
        }[normalized_type]
        if not valid:
            raise TypeError(f"strategy parameter {name} must be {normalized_type}")

        if spec.range is None:
            return
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(f"range is only supported for numeric parameter {name}")
        lower, upper = spec.range
        if lower is not None and value < lower:
            raise ValueError(f"strategy parameter {name} is below minimum {lower}")
        if upper is not None and value > upper:
            raise ValueError(f"strategy parameter {name} is above maximum {upper}")

    @classmethod
    def json_schema(cls, schema: ParameterSchema) -> dict[str, object]:
        """Render the Adaptee field declaration as JSON Schema for UI tooling."""
        properties: dict[str, object] = {}
        required: list[str] = []
        for name, spec in schema.fields.items():
            try:
                normalized_type = cls._TYPE_ALIASES[spec.type]
            except KeyError as error:
                raise ValueError(f"unsupported field type for {name}: {spec.type}") from error
            field_schema: dict[str, object] = {"type": normalized_type}
            if spec.default is not UNSET:
                field_schema["default"] = _thaw(spec.default)
            if spec.range is not None:
                lower, upper = spec.range
                if lower is not None:
                    field_schema["minimum"] = lower
                if upper is not None:
                    field_schema["maximum"] = upper
            properties[name] = field_schema
            if spec.required:
                required.append(name)
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": properties,
            "required": sorted(required),
            "additionalProperties": not schema.extra_forbidden,
        }

    @staticmethod
    def serialize(config: ResolvedConfig) -> dict[str, object]:
        """Return normalized JSON-ready Evidence/catalog data."""
        return {
            "strategy_id": config.strategy_id,
            "params": _thaw(config.params),
            "schema_version": config.schema_version,
        }

    @staticmethod
    def version() -> str:
        """Return the stable resolved-configuration schema version."""
        return SCHEMA_VERSION
