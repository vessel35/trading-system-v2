"""Prove policy registration reconciliation without activating it in production."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

import pytest
from core_lib.money_management import (
    AccountRiskSnapshot,
    MarketSnapshot,
    MoneyManagementAvailability,
    MoneyManagementBase,
    MoneyManagementPlan,
    MoneyManagementReconciliationState,
    PolicyIndicatorRequirement,
    RiskLimits,
    reconcile_money_management_availability,
)
from core_lib.types import DecisionIntent


@dataclass(frozen=True, slots=True)
class _AlphaPolicy(MoneyManagementBase):
    alpha: int = 1
    beta: float = 2.0

    id: ClassVar[str] = "alpha"
    version: ClassVar[str] = "1.0.0"

    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        return ()

    def resolved_config(self) -> Mapping[str, object]:
        return {"mode": self.id, "alpha": self.alpha, "beta": self.beta}

    def plan_entry(
        self,
        decision: DecisionIntent,
        market: MarketSnapshot,
        account: AccountRiskSnapshot,
        global_limits: RiskLimits,
    ) -> MoneyManagementPlan:
        del decision, market, account, global_limits
        raise NotImplementedError


def _registration(
    *,
    mode: str = "alpha",
    class_name: str = "_AlphaPolicy",
    module_path: str = __name__,
    policy_version: str = "1.0.0",
    settings_names: list[str] | None = None,
    is_active: bool = True,
    is_deprecated: bool = False,
) -> dict[str, object]:
    return {
        "mode": mode,
        "class_name": class_name,
        "module_path": module_path,
        "policy_version": policy_version,
        "settings_names": ["alpha", "beta"] if settings_names is None else settings_names,
        "is_active": is_active,
        "is_deprecated": is_deprecated,
    }


def _one(
    registrations: list[dict[str, object]] | None,
    deployed: Mapping[str, type[MoneyManagementBase]],
) -> MoneyManagementAvailability:
    return reconcile_money_management_availability(registrations, deployed)[0]


@pytest.mark.parametrize(
    ("registrations", "deployed", "expected"),
    [
        (
            [_registration(mode="orphan")],
            {},
            MoneyManagementReconciliationState.REGISTERED_ONLY,
        ),
        (
            [],
            {"alpha": _AlphaPolicy},
            MoneyManagementReconciliationState.DEPLOYED_ONLY,
        ),
        (
            [_registration(class_name="OtherPolicy")],
            {"alpha": _AlphaPolicy},
            MoneyManagementReconciliationState.IDENTITY_MISMATCH,
        ),
        (
            [_registration(settings_names=["alpha"])],
            {"alpha": _AlphaPolicy},
            MoneyManagementReconciliationState.DECLARATION_MISMATCH,
        ),
        (
            [_registration(is_deprecated=True)],
            {"alpha": _AlphaPolicy},
            MoneyManagementReconciliationState.DEPRECATED,
        ),
        (
            [_registration(is_active=False)],
            {"alpha": _AlphaPolicy},
            MoneyManagementReconciliationState.INACTIVE,
        ),
    ],
)
def test_each_unrunnable_policy_state_is_distinct(
    registrations: list[dict[str, object]],
    deployed: Mapping[str, type[MoneyManagementBase]],
    expected: MoneyManagementReconciliationState,
) -> None:
    result = _one(registrations, deployed)

    assert result == MoneyManagementAvailability(
        mode=result.mode,
        runnable=False,
        reason=expected,
    )


def test_deprecated_precedes_inactive() -> None:
    result = _one(
        [_registration(is_active=False, is_deprecated=True)],
        {"alpha": _AlphaPolicy},
    )

    assert result.reason is MoneyManagementReconciliationState.DEPRECATED


@pytest.mark.parametrize(
    ("registration", "expected"),
    [
        (
            _registration(
                class_name="OtherPolicy",
                settings_names=["other"],
                is_active=False,
                is_deprecated=True,
            ),
            MoneyManagementReconciliationState.IDENTITY_MISMATCH,
        ),
        (
            _registration(
                settings_names=["other"],
                is_active=False,
                is_deprecated=True,
            ),
            MoneyManagementReconciliationState.DECLARATION_MISMATCH,
        ),
    ],
)
def test_identity_and_declaration_precede_lifecycle(
    registration: dict[str, object],
    expected: MoneyManagementReconciliationState,
) -> None:
    result = _one([registration], {"alpha": _AlphaPolicy})

    assert result.reason is expected


def test_settings_order_is_ignored_but_a_different_name_is_rejected() -> None:
    matching = _one(
        [_registration(settings_names=["beta", "alpha"])],
        {"alpha": _AlphaPolicy},
    )
    mismatching = _one(
        [_registration(settings_names=["alpha", "gamma"])],
        {"alpha": _AlphaPolicy},
    )

    assert matching == MoneyManagementAvailability(mode="alpha", runnable=True, reason=None)
    assert mismatching.reason is MoneyManagementReconciliationState.DECLARATION_MISMATCH


def test_policy_version_drift_does_not_block_the_policy() -> None:
    result = _one(
        [_registration(policy_version="999.0.0")],
        {"alpha": _AlphaPolicy},
    )

    assert result == MoneyManagementAvailability(mode="alpha", runnable=True, reason=None)


def test_missing_table_and_empty_table_have_different_meanings() -> None:
    missing_table = _one(None, {"alpha": _AlphaPolicy})
    empty_table = _one([], {"alpha": _AlphaPolicy})

    assert missing_table == MoneyManagementAvailability(mode="alpha", runnable=True, reason=None)
    assert empty_table == MoneyManagementAvailability(
        mode="alpha",
        runnable=False,
        reason=MoneyManagementReconciliationState.DEPLOYED_ONLY,
    )


def test_deployed_policy_without_registration_remains_in_the_result() -> None:
    results = reconcile_money_management_availability(
        [_registration(mode="registered", class_name="RegisteredPolicy")],
        {"alpha": _AlphaPolicy},
    )

    assert [result.mode for result in results] == ["alpha", "registered"]
    assert results[0] == MoneyManagementAvailability(
        mode="alpha",
        runnable=False,
        reason=MoneyManagementReconciliationState.DEPLOYED_ONLY,
    )


def test_reconciliation_state_has_exactly_the_six_reachable_reasons() -> None:
    assert set(MoneyManagementReconciliationState) == {
        MoneyManagementReconciliationState.REGISTERED_ONLY,
        MoneyManagementReconciliationState.DEPLOYED_ONLY,
        MoneyManagementReconciliationState.IDENTITY_MISMATCH,
        MoneyManagementReconciliationState.DECLARATION_MISMATCH,
        MoneyManagementReconciliationState.DEPRECATED,
        MoneyManagementReconciliationState.INACTIVE,
    }
