"""Verify policy form defaults are frozen before strategy-list requests."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar, cast

import backtest_service.config.run_config as run_config
import pytest
import web_api.repository as repository
from core_lib.money_management import (
    AccountRiskSnapshot,
    MarketSnapshot,
    MoneyManagementBase,
    MoneyManagementFactory,
    MoneyManagementPlan,
    PolicyIndicatorRequirement,
    RiskLimits,
)
from core_lib.types import DecisionIntent
from pydantic import BaseModel, TypeAdapter, field_validator, model_serializer
from trading_plugins import build_strategy_registry, registered_money_management
from web_api.database import SignalConnection

_HOOKS = {
    "construct": 0,
    "post_init": 0,
    "resolved_config": 0,
    "default_factory": 0,
    "validator": 0,
    "serializer": 0,
}


class _CountedSettings(BaseModel):
    values: list[int]

    @field_validator("values")
    @classmethod
    def _count_validation(cls, value: list[int]) -> list[int]:
        _HOOKS["validator"] += 1
        return value

    @model_serializer(mode="wrap")
    def _count_serialization(self, handler: Any) -> object:
        _HOOKS["serializer"] += 1
        return handler(self)


def _counted_settings() -> _CountedSettings:
    _HOOKS["default_factory"] += 1
    return _CountedSettings(values=[7])


@dataclass(frozen=True, slots=True)
class _CountedPolicy(MoneyManagementBase):
    settings: _CountedSettings = field(default_factory=_counted_settings)

    id: ClassVar[str] = "counted-default"
    version: ClassVar[str] = "1.0.0"

    def __new__(cls, *args: object, **kwargs: object) -> _CountedPolicy:
        _HOOKS["construct"] += 1
        return object.__new__(cls)

    def __post_init__(self) -> None:
        _HOOKS["post_init"] += 1

    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        return ()

    def resolved_config(self) -> Mapping[str, object]:
        _HOOKS["resolved_config"] += 1
        return {"mode": self.id, "settings": self.settings}

    def plan_entry(
        self,
        decision: DecisionIntent,
        market: MarketSnapshot,
        account: AccountRiskSnapshot,
        global_limits: RiskLimits,
    ) -> MoneyManagementPlan:
        raise NotImplementedError


def _adapter_for(
    policies: Mapping[str, type[MoneyManagementBase]],
) -> TypeAdapter[Any]:
    generated = run_config._deployed_money_management_models(policies)
    return run_config._money_management_adapter(
        (
            run_config.ManualMoneyManagementConfig,
            run_config.TurtleMoneyManagementConfig,
            *generated,
        )
    )


def test_fixed_policy_hooks_run_during_freeze_and_not_during_two_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The documented 1/1/1/1/2/1 counts belong to this exact fixture."""
    policies: dict[str, type[MoneyManagementBase]] = dict(registered_money_management())
    policies[_CountedPolicy.id] = _CountedPolicy
    adapter = _adapter_for({_CountedPolicy.id: _CountedPolicy})
    adapter_calls = 0
    json_calls = 0
    real_validate = adapter.validate_python
    real_dumps = json.dumps

    def count_validation(*args: Any, **kwargs: Any) -> Any:
        nonlocal adapter_calls
        adapter_calls += 1
        return real_validate(*args, **kwargs)

    def count_json(*args: Any, **kwargs: Any) -> str:
        nonlocal json_calls
        json_calls += 1
        return real_dumps(*args, **kwargs)

    monkeypatch.setattr(adapter, "validate_python", count_validation)
    monkeypatch.setattr(run_config, "_MONEY_MANAGEMENT_ADAPTER", adapter)
    monkeypatch.setattr(json, "dumps", count_json)
    for name in _HOOKS:
        _HOOKS[name] = 0

    frozen = repository._freeze_money_management_defaults(
        policies,
        [_CountedPolicy.id],
    )

    assert _HOOKS == {
        "construct": 1,
        "post_init": 1,
        "resolved_config": 1,
        "default_factory": 1,
        "validator": 2,
        "serializer": 1,
    }
    assert adapter_calls == 2
    assert json_calls == 1
    frozen_counts = (_HOOKS.copy(), adapter_calls, json_calls)

    monkeypatch.setattr(repository, "_FROZEN_MONEY_MANAGEMENT_DEFAULTS", frozen)
    first = repository._default_money_management(_CountedPolicy.id)
    cast("dict[str, object]", first["settings"])["values"] = [99]
    second = repository._default_money_management(_CountedPolicy.id)

    assert second == {
        "mode": _CountedPolicy.id,
        "settings": {"values": [7]},
    }
    assert (_HOOKS, adapter_calls, json_calls) == frozen_counts


def _fault(
    error_type: type[Exception] | type[SystemExit],
    phase: str,
) -> BaseException:
    return error_type(f"{phase} failed")


def _failing_policy(
    phase: str,
    error_type: type[Exception] | type[SystemExit],
) -> tuple[type[MoneyManagementBase], type[BaseModel]]:
    class FailingSettings(BaseModel):
        value: int = 1

        @field_validator("value")
        @classmethod
        def _fail_validation(cls, value: int) -> int:
            if phase in {"first_validator", "second_validator"}:
                raise _fault(error_type, phase)
            return value

        @model_serializer(mode="wrap")
        def _fail_serialization(self, handler: Any) -> object:
            if phase == "serializer":
                raise _fault(error_type, phase)
            return handler(self)

    def settings_default() -> FailingSettings:
        if phase == "default_factory":
            raise _fault(error_type, phase)
        return FailingSettings.model_construct(value=1)

    @dataclass(frozen=True)
    class FailingPolicy(MoneyManagementBase):
        settings: FailingSettings = field(default_factory=settings_default)

        id: ClassVar[str] = "failing-default"
        version: ClassVar[str] = "1.0.0"

        def __new__(cls, *args: object, **kwargs: object) -> FailingPolicy:
            if phase == "construct":
                raise _fault(error_type, phase)
            return object.__new__(cls)

        def __post_init__(self) -> None:
            if phase == "post_init":
                raise _fault(error_type, phase)

        def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
            return ()

        def resolved_config(self) -> Mapping[str, object]:
            if phase == "resolved_config":
                raise _fault(error_type, phase)
            settings: object = self.settings
            if phase == "first_validator":
                settings = {"value": 1}
            return {"mode": self.id, "settings": settings}

        def plan_entry(
            self,
            decision: DecisionIntent,
            market: MarketSnapshot,
            account: AccountRiskSnapshot,
            global_limits: RiskLimits,
        ) -> MoneyManagementPlan:
            raise NotImplementedError

    # ``from __future__ import annotations`` stores the local nested type as a
    # string that ``get_type_hints`` cannot resolve from module globals. A real
    # deployed policy's setting type is module-visible, so make this fixture
    # present the same resolved annotation surface.
    FailingPolicy.__annotations__["settings"] = FailingSettings
    return FailingPolicy, FailingSettings


@pytest.mark.parametrize("error_type", [RuntimeError, SystemExit])
@pytest.mark.parametrize(
    "phase",
    [
        "construct",
        "post_init",
        "resolved_config",
        "default_factory",
        "first_validator",
        "second_validator",
        "serializer",
    ],
)
def test_each_default_phase_fault_removes_only_that_default(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    phase: str,
    error_type: type[Exception] | type[SystemExit],
) -> None:
    policy, _ = _failing_policy(phase, error_type)
    policies: dict[str, type[MoneyManagementBase]] = dict(registered_money_management())
    policies[policy.id] = policy
    adapter = _adapter_for({policy.id: policy})
    monkeypatch.setattr(run_config, "_MONEY_MANAGEMENT_ADAPTER", adapter)

    frozen = repository._freeze_money_management_defaults(
        policies,
        ["manual", policy.id],
    )

    assert set(frozen) == {"manual"}
    assert "has no valid default configuration" in caplog.text


@dataclass(frozen=True)
class _RequiredSettingPolicy(MoneyManagementBase):
    required_value: int

    id: ClassVar[str] = "required-setting"
    version: ClassVar[str] = "1.0.0"

    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        return ()

    def resolved_config(self) -> Mapping[str, object]:
        return {"mode": self.id, "required_value": self.required_value}

    def plan_entry(
        self,
        decision: DecisionIntent,
        market: MarketSnapshot,
        account: AccountRiskSnapshot,
        global_limits: RiskLimits,
    ) -> MoneyManagementPlan:
        raise NotImplementedError


def test_required_setting_without_a_default_leaves_the_mode_without_a_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _adapter_for({_RequiredSettingPolicy.id: _RequiredSettingPolicy})
    monkeypatch.setattr(run_config, "_MONEY_MANAGEMENT_ADAPTER", adapter)
    policies: dict[str, type[MoneyManagementBase]] = dict(registered_money_management())
    policies[_RequiredSettingPolicy.id] = _RequiredSettingPolicy

    frozen = repository._freeze_money_management_defaults(
        policies,
        ["manual", _RequiredSettingPolicy.id],
    )

    assert set(frozen) == {"manual"}


@dataclass(frozen=True)
class _NonFinitePolicy(MoneyManagementBase):
    payload: float | None = math.nan

    id: ClassVar[str] = "non-finite"
    version: ClassVar[str] = "1.0.0"

    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        return ()

    def resolved_config(self) -> Mapping[str, object]:
        return {"mode": self.id, "payload": self.payload}

    def plan_entry(
        self,
        decision: DecisionIntent,
        market: MarketSnapshot,
        account: AccountRiskSnapshot,
        global_limits: RiskLimits,
    ) -> MoneyManagementPlan:
        raise NotImplementedError


def test_non_finite_json_is_rejected_without_removing_the_selectable_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _adapter_for({_NonFinitePolicy.id: _NonFinitePolicy})
    monkeypatch.setattr(run_config, "_MONEY_MANAGEMENT_ADAPTER", adapter)
    policies: dict[str, type[MoneyManagementBase]] = dict(registered_money_management())
    policies[_NonFinitePolicy.id] = _NonFinitePolicy

    frozen = repository._freeze_money_management_defaults(
        policies,
        ["manual", _NonFinitePolicy.id],
    )
    monkeypatch.setattr(
        repository,
        "SELECTABLE_MONEY_MANAGEMENT_MODES",
        frozenset({"manual", _NonFinitePolicy.id}),
    )

    assert set(frozen) == {"manual"}
    assert repository._selectable_modes(["manual", _NonFinitePolicy.id]) == [
        "manual",
        _NonFinitePolicy.id,
    ]


def test_requests_do_not_reenter_policy_or_union_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*args: object, **kwargs: object) -> object:
        raise AssertionError("request re-entered default assembly")

    monkeypatch.setattr(repository, "registered_money_management", explode)
    monkeypatch.setattr(MoneyManagementFactory, "create", staticmethod(explode))
    monkeypatch.setattr(repository, "freeze_money_management_config", explode)

    connection = cast("SignalConnection", _MissingTableConnection())
    registry = build_strategy_registry()
    first = repository.StrategyRepository(connection, registry).list()
    second = repository.StrategyRepository(connection, registry).list()

    first.model_dump_json()
    second.model_dump_json()
    assert first.data[0].default_money_management == second.data[0].default_money_management


class _MissingTableCursor:
    description: None = None

    def fetchone(self) -> None:
        return None

    def fetchall(self) -> list[object]:
        return []


class _MissingTableConnection:
    def execute(self, _query: str) -> _MissingTableCursor:
        return _MissingTableCursor()


@pytest.mark.parametrize(
    ("target", "expected"),
    [("backtest", {"create": 0, "resolved": 0}), ("web", {"create": 2, "resolved": 2})],
)
def test_only_the_web_api_cold_import_builds_form_defaults(
    target: str,
    expected: dict[str, int],
) -> None:
    script = r"""
import json
import sys

from core_lib.money_management import MoneyManagementFactory
from trading_plugins.money_management.manual import ManualMoneyManagement
from trading_plugins.money_management.turtle import TurtleMoneyManagement

counts = {"create": 0, "resolved": 0}
real_create = MoneyManagementFactory.create

def counted_create(*args, **kwargs):
    counts["create"] += 1
    return real_create(*args, **kwargs)

MoneyManagementFactory.create = staticmethod(counted_create)
for policy_class in (ManualMoneyManagement, TurtleMoneyManagement):
    original = policy_class.resolved_config
    def counted_resolved(self, original=original):
        counts["resolved"] += 1
        return original(self)
    policy_class.resolved_config = counted_resolved

if sys.argv[1] == "backtest":
    import backtest_service.config.run_config
else:
    import web_api.repository

print(json.dumps(counts, sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, target],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == expected
