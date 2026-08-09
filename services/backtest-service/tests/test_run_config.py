"""Verify RunConfig owns run settings but not strategy parameter semantics."""

import logging
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar, cast

import pytest
from backtest_service.config import RunConfig
from backtest_service.config.run_config import (
    SELECTABLE_MONEY_MANAGEMENT_MODES,
    _deployed_money_management_models,
)
from core_lib.money_management import (
    AccountRiskSnapshot,
    MarketSnapshot,
    MoneyManagementBase,
    MoneyManagementPlan,
    PolicyIndicatorRequirement,
    RiskLimits,
)
from core_lib.types import DecisionIntent
from pydantic import ValidationError


def _raw_config() -> dict[str, object]:
    return {
        "run_name": "btc-breakout-oos",
        "strategy_id": "fake-breakout",
        "params": {"strategy_owned_unknown": {"nested": True}},
        "symbol": "BTCUSDT",
        "exchange": "binance",
        "timeframe": "1h",
        "market_type": "futures",
        "data_source": "crypto_data.ohlcv_futures",
        "start": datetime(2025, 1, 1, tzinfo=UTC),
        "end": datetime(2026, 1, 1, tzinfo=UTC),
        "initial_capital": Decimal("10000"),
        "profile_ref": "breakout-v1",
    }


def test_valid_config_defaults_and_manager_selection() -> None:
    """Validate run-level fields and pass strategy params through untouched."""
    config = RunConfig.model_validate(_raw_config())
    config.revalidate()
    assert config.fill_timing == "next_bar"
    assert config.trigger_feed == "tf_candle"
    assert config.indicator_mode == "auto"
    assert config.risk_per_trade == 0.01
    assert config.money_management.mode == "manual"
    assert config.selection() == {
        "strategy_id": "fake-breakout",
        "params": {"strategy_owned_unknown": {"nested": True}},
        "symbol": "BTCUSDT",
        "timeframe": "1h",
    }


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"end": datetime(2024, 1, 1, tzinfo=UTC)}, "start must be earlier"),
        ({"fill_timing": "immediate"}, "next_bar"),
        ({"risk_per_trade": 0.0101}, "risk_per_trade"),
        ({"position_size_pct": 0.2}, "position_size_pct"),
        ({"run_name": "../escape"}, "filename-safe"),
        ({"start": datetime(2025, 1, 1)}, "timezone-aware"),
        ({"cost_values": {"unknown_rate": "0.1"}}, "unknown cost parameter"),
        ({"cost_values": {"gap_multiplier": "0.5"}}, "at least one"),
    ],
)
def test_run_config_rejects_invalid_contracts(
    updates: dict[str, object],
    message: str,
) -> None:
    raw = {**_raw_config(), **updates}
    with pytest.raises((ValidationError, NotImplementedError), match=message):
        RunConfig.model_validate(raw)


def test_pct_sizing_requires_only_its_own_fraction() -> None:
    raw = {
        **_raw_config(),
        "sizing_method": "pct",
        "position_size_pct": 0.2,
    }
    config = RunConfig.model_validate(raw)
    assert config.risk_per_trade is None
    assert config.position_size_pct == 0.2


def test_reserved_m1_feed_fails_loudly_instead_of_falling_back() -> None:
    raw = {**_raw_config(), "trigger_feed": "m1_subcandle"}
    with pytest.raises(NotImplementedError, match="reserved"):
        RunConfig.model_validate(raw)


def test_explicit_indicator_mode_requires_a_well_formed_nonempty_selection() -> None:
    with pytest.raises(ValidationError, match="requires explicit_indicators"):
        RunConfig.model_validate({**_raw_config(), "indicator_mode": "explicit"})
    config = RunConfig.model_validate(
        {
            **_raw_config(),
            "indicator_mode": "explicit",
            "explicit_indicators": [{"name": "EMA", "params": {"period": 9}}],
        }
    )
    assert config.explicit_indicators == [{"name": "EMA", "params": {"period": 9}}]


def test_extra_run_keys_are_forbidden() -> None:
    raw = {**_raw_config(), "strategy_parameter_schema": {"forbidden": True}}
    with pytest.raises(ValidationError, match="Extra inputs"):
        RunConfig.model_validate(raw)


def test_json_schema_exposes_run_choices_but_no_strategy_parameter_schema() -> None:
    schema = RunConfig.model_json_schema()
    properties = schema["properties"]
    assert properties["trigger_feed"]["enum"] == ["tf_candle", "m1_subcandle"]
    assert properties["fill_timing"]["enum"] == ["immediate", "next_bar"]
    assert properties["money_management"]["discriminator"]["propertyName"] == "mode"
    assert "strategy_parameter_schema" not in properties


def test_vessel_legacy_money_fields_normalize_to_manual_policy() -> None:
    config = RunConfig.model_validate(
        {
            **_raw_config(),
            "strategy_id": "vessel-reference",
            "params": {
                "leverage": 3,
                "reward_risk": 2.5,
                "atr_stop_multiple": 1.5,
            },
        }
    )
    assert config.money_management.model_dump() == {
        "mode": "manual",
        "leverage": 3,
        "reward_risk": 2.5,
        "atr_stop_multiple": 1.5,
    }
    assert config.params["reward_risk"] == 2.5


def test_turtle_policy_is_discriminated_and_requires_global_risk_sizing() -> None:
    config = RunConfig.model_validate(
        {
            **_raw_config(),
            "money_management": {
                "mode": "turtle",
                "n_period": 20,
                "n_timeframe": "1d",
                "stop_n_multiple": 2.0,
                "leverage_cap": 10,
            },
        }
    )
    assert config.money_management.mode == "turtle"
    with pytest.raises(ValidationError, match="risk_based"):
        RunConfig.model_validate(
            {
                **_raw_config(),
                "sizing_method": "pct",
                "position_size_pct": 0.2,
                "money_management": {"mode": "turtle"},
            }
        )
    with pytest.raises(ValidationError, match="Extra inputs"):
        RunConfig.model_validate(
            {
                **_raw_config(),
                "money_management": {"mode": "manual", "api_key": "forbidden"},
            }
        )


@dataclass(frozen=True, slots=True)
class _FactoryDefaultPolicy(MoneyManagementBase):
    """A policy whose only setting carries a factory default."""

    tags: tuple[str, ...] = field(default_factory=tuple)

    id: ClassVar[str] = "factory-default"
    version: ClassVar[str] = "1.0.0"

    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        return ()

    def resolved_config(self) -> Mapping[str, object]:
        return {"mode": self.id}

    def plan_entry(
        self,
        decision: DecisionIntent,
        market: MarketSnapshot,
        account: AccountRiskSnapshot,
        global_limits: RiskLimits,
    ) -> MoneyManagementPlan:
        raise NotImplementedError


class _Unexpressible:
    """A type Pydantic cannot build a schema for."""


@dataclass(frozen=True, slots=True)
class _UnexpressiblePolicy(MoneyManagementBase):
    """A policy whose setting has no schema, so it cannot be configured."""

    flavor: _Unexpressible = field(default_factory=_Unexpressible)

    id: ClassVar[str] = "unexpressible"
    version: ClassVar[str] = "1.0.0"

    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        return ()

    def resolved_config(self) -> Mapping[str, object]:
        return {"mode": self.id}

    def plan_entry(
        self,
        decision: DecisionIntent,
        market: MarketSnapshot,
        account: AccountRiskSnapshot,
        global_limits: RiskLimits,
    ) -> MoneyManagementPlan:
        raise NotImplementedError


def test_a_factory_default_stays_optional_in_the_generated_model() -> None:
    """Reading only ``field.default`` turned a factory default into a required field."""
    (model,) = _deployed_money_management_models({"factory-default": _FactoryDefaultPolicy})

    value = model.model_validate({"mode": "factory-default"})

    assert value.model_dump() == {"mode": "factory-default", "tags": ()}


def test_a_policy_with_no_expressible_schema_is_skipped_not_raised() -> None:
    """One bad deployment must not fail this module's import for every run."""
    models = _deployed_money_management_models(
        {"unexpressible": _UnexpressiblePolicy, "factory-default": _FactoryDefaultPolicy}
    )

    assert [model.model_fields["mode"].default for model in models] == ["factory-default"]


def _check_with_mypy(tmp_path: Path, name: str, body: str) -> str:
    """Run the service's own checker over one probe function and return its output."""
    service = Path(__file__).resolve().parents[1]
    probe = tmp_path / f"probe_{name}.py"
    probe.write_text(
        "from backtest_service.config import (\n"
        "    ManualMoneyManagementConfig, RunConfig, TurtleMoneyManagementConfig,\n"
        ")\n\n\n"
        "def read(config: RunConfig) -> int:\n" + body
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--config-file",
            str(service / "pyproject.toml"),
            str(probe),
        ],
        capture_output=True,
        text=True,
        cwd=service,
        check=False,
    )
    return result.stdout


def test_the_checked_union_refuses_an_unconditional_built_in_field_access(
    tmp_path: Path,
) -> None:
    """A type checker must not approve an attribute a deployed policy lacks.

    The union is assembled at import time from what is deployed, so a checker
    cannot see it. While it named only the two built-in models, it narrowed
    ``mode != "manual"`` to Turtle and approved ``n_period``, which a deployed
    policy does not carry. This is checked by running the checker, because the
    defect exists only in its view and leaves no trace at run time.
    """
    refused = _check_with_mypy(
        tmp_path,
        "unsafe",
        '    if config.money_management.mode == "manual":\n'
        "        return 0\n"
        "    return config.money_management.n_period\n",
    )

    assert "has no attribute" in refused, refused


def test_the_checked_union_allows_comparing_any_deployed_mode_name(tmp_path: Path) -> None:
    """The checker stand-in must not be narrower than deployed ids at runtime."""
    accepted = _check_with_mypy(
        tmp_path,
        "deployed_name",
        '    if config.money_management.mode == "atr-only":\n        return 1\n    return 0\n',
    )

    assert "no issues found" in accepted, accepted


def test_the_checked_union_allows_built_in_fields_after_type_narrowing(tmp_path: Path) -> None:
    """Built-in settings remain readable after narrowing by their concrete types."""
    accepted = _check_with_mypy(
        tmp_path,
        "built_in_types",
        "    if isinstance(config.money_management, ManualMoneyManagementConfig):\n"
        "        return config.money_management.leverage\n"
        "    if isinstance(config.money_management, TurtleMoneyManagementConfig):\n"
        "        return config.money_management.n_period\n"
        "    return 0\n",
    )

    assert "no issues found" in accepted, accepted


@dataclass(frozen=True, slots=True)
class _ModeNamingPolicy(MoneyManagementBase):
    """A policy whose setting collides with the union's discriminator."""

    mode: str = "oops"

    id: ClassVar[str] = "mode-naming"
    version: ClassVar[str] = "1.0.0"

    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        return ()

    def resolved_config(self) -> Mapping[str, object]:
        return {"mode": self.id}

    def plan_entry(
        self,
        decision: DecisionIntent,
        market: MarketSnapshot,
        account: AccountRiskSnapshot,
        global_limits: RiskLimits,
    ) -> MoneyManagementPlan:
        raise NotImplementedError


def test_a_policy_that_names_a_setting_mode_is_skipped_not_left_to_break_the_union(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The generated arm passed its own schema and then refused to join the union.

    That failure landed while RunConfig itself was being assembled, outside the
    isolation, so one deployment took manual validation and the OpenAPI document
    with it. The reason says which setting caused it, because the union's own
    complaint names only a field the author did not write.
    """
    with caplog.at_level(logging.ERROR):
        assert _deployed_money_management_models({"mode-naming": _ModeNamingPolicy}) == ()

    assert "may not declare a setting named 'mode'" in caplog.text


def test_the_selectable_modes_are_the_ones_the_union_accepts() -> None:
    """Anything that offers a choice reads this, so a shown mode is a valid mode."""
    assert SELECTABLE_MONEY_MANAGEMENT_MODES >= {"manual", "turtle"}
    for mode in SELECTABLE_MONEY_MANAGEMENT_MODES:
        assert RunConfig.model_validate(
            {**_raw_config(), "sizing_method": "risk_based", "money_management": {"mode": mode}}
        )


def _policy_with_annotation(mode: str, annotation: str) -> type[MoneyManagementBase]:
    """Build a policy whose one setting carries the given annotation.

    The class is assembled here rather than written out so the annotation stays
    data. Written as source, a type checker reads it too and refuses the file,
    which would take this test's own service out of the checked build.
    """
    namespace: dict[str, Any] = {
        "__annotations__": {"tag": annotation},
        "tag": 0,
        "id": mode,
        "version": "1.0.0",
        "required_indicators": lambda self: (),
        "resolved_config": lambda self: {"mode": mode},
        "plan_entry": lambda self, *args: None,
    }
    created = type(f"Policy{mode.title().replace('-', '')}", (MoneyManagementBase,), namespace)
    return cast("type[MoneyManagementBase]", dataclass(frozen=True)(created))


def _named_policy(
    mode: str,
    class_name: str,
    annotation: object = int,
    default: object = 0,
) -> type[MoneyManagementBase]:
    namespace: dict[str, Any] = {
        "__annotations__": {"setting": annotation},
        "setting": default,
        "id": mode,
        "version": "1.0.0",
        "required_indicators": lambda self: (),
        "resolved_config": lambda self: {"mode": mode, "setting": self.setting},
        "plan_entry": lambda self, *args: None,
    }
    created = type(class_name, (MoneyManagementBase,), namespace)
    return cast("type[MoneyManagementBase]", dataclass(frozen=True)(created))


def test_a_generated_arm_name_collision_skips_only_the_later_policy() -> None:
    first = _named_policy("alpha", "SamePolicy")
    second = _named_policy("beta", "SamePolicy")

    models = _deployed_money_management_models({"alpha": first, "beta": second})

    assert [model.model_fields["mode"].default for model in models] == ["alpha"]


def test_a_nested_schema_name_collision_skips_only_the_later_policy() -> None:
    first_settings: type[Any] = dataclass(frozen=True)(
        type("SharedSettings", (), {"__annotations__": {"value": str}, "value": "one"})
    )
    second_settings: type[Any] = dataclass(frozen=True)(
        type("SharedSettings", (), {"__annotations__": {"value": int}, "value": 2})
    )
    first = _named_policy(
        "alpha-nested",
        "AlphaNestedPolicy",
        first_settings,
        field(default_factory=first_settings),
    )
    second = _named_policy(
        "beta-nested",
        "BetaNestedPolicy",
        second_settings,
        field(default_factory=second_settings),
    )

    models = _deployed_money_management_models({"alpha-nested": first, "beta-nested": second})

    assert [model.model_fields["mode"].default for model in models] == ["alpha-nested"]


def test_an_annotation_that_ends_the_process_is_caught_like_any_other_fault() -> None:
    """Resolving annotations runs code the deployed file wrote.

    Catching only ``Exception`` let a file exit from its own annotation and end
    the process that imported this module, going around the isolation that the
    plugin discovery step already had.
    """
    policy = _policy_with_annotation("exiting-annotation", "__import__('sys').exit(7)")

    assert _deployed_money_management_models({"exiting-annotation": policy}) == ()
