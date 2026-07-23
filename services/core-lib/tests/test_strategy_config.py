"""Verify schema-first strategy configuration interpretation."""

from collections.abc import Mapping
from typing import cast

import pytest
from core_lib.strategy import (
    FieldSpec,
    ParameterSchema,
    ResolvedConfig,
    StrategyConfig,
)


def fast_before_slow(params: Mapping[str, object]) -> None:
    fast = params["fast"]
    slow = params["slow"]
    if not isinstance(fast, int) or not isinstance(slow, int):
        raise TypeError("fast and slow must be integers")
    if fast >= slow:
        raise ValueError("fast must be less than slow")


def make_schema(*, extra_forbidden: bool = True) -> ParameterSchema:
    return ParameterSchema(
        fields={
            "fast": FieldSpec(type="integer", range=(1, 20), required=True),
            "slow": FieldSpec(type="integer", default=30, range=(2, 100)),
            "enabled": FieldSpec(type="boolean", default=True),
        },
        extra_forbidden=extra_forbidden,
        cross_validators=(fast_before_slow,),
    )


def test_resolve_merges_defaults_and_returns_deeply_immutable_config() -> None:
    resolved = StrategyConfig.resolve(
        make_schema(),
        {"strategy_id": "fake-breakout", "params": {"fast": 10}},
    )
    assert resolved == ResolvedConfig(
        strategy_id="fake-breakout",
        params={"enabled": True, "fast": 10, "slow": 30},
        schema_version=StrategyConfig.version(),
    )
    mutable_view = cast(dict[str, object], resolved.params)
    with pytest.raises(TypeError):
        mutable_view["fast"] = 11


def test_resolve_rejects_wrapper_extra_type_range_and_cross_field_errors() -> None:
    schema = make_schema()
    with pytest.raises(ValueError, match="shape mismatch"):
        StrategyConfig.resolve(schema, {"strategy_id": "fake", "fast": 10})
    with pytest.raises(ValueError, match="unexpected"):
        StrategyConfig.resolve(
            schema,
            {"strategy_id": "fake", "params": {"fast": 10, "unknown": 1}},
        )
    with pytest.raises(TypeError, match="integer"):
        StrategyConfig.resolve(
            schema,
            {"strategy_id": "fake", "params": {"fast": 10.5}},
        )
    with pytest.raises(ValueError, match="above maximum"):
        StrategyConfig.resolve(
            schema,
            {"strategy_id": "fake", "params": {"fast": 21}},
        )
    with pytest.raises(ValueError, match="fast must be less"):
        StrategyConfig.resolve(
            schema,
            {"strategy_id": "fake", "params": {"fast": 20, "slow": 20}},
        )


def test_resolve_requires_declared_required_fields() -> None:
    with pytest.raises(ValueError, match="required"):
        StrategyConfig.resolve(
            make_schema(),
            {"strategy_id": "fake", "params": {}},
        )


def test_extra_allowed_schema_preserves_caller_owned_values() -> None:
    raw_extra = {"nested": [1, 2]}
    resolved = StrategyConfig.resolve(
        make_schema(extra_forbidden=False),
        {
            "strategy_id": "fake",
            "params": {"fast": 10, "custom": raw_extra},
        },
    )
    raw_extra["nested"].append(3)
    assert resolved.params["custom"] != raw_extra


def test_json_schema_exposes_fields_but_not_cross_validator_code() -> None:
    rendered = StrategyConfig.json_schema(make_schema())
    assert rendered["additionalProperties"] is False
    assert rendered["required"] == ["fast"]
    properties = cast(dict[str, dict[str, object]], rendered["properties"])
    assert properties["fast"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 20,
    }
    assert properties["slow"]["default"] == 30
    assert "cross_validators" not in rendered


def test_serialize_is_normalized_and_json_ready() -> None:
    resolved = StrategyConfig.resolve(
        ParameterSchema(
            fields={
                "windows": FieldSpec(type="array", default=[9, 21]),
            }
        ),
        {"strategy_id": "fake", "params": {}},
    )
    assert StrategyConfig.serialize(resolved) == {
        "strategy_id": "fake",
        "params": {"windows": [9, 21]},
        "schema_version": "1.0.0",
    }
