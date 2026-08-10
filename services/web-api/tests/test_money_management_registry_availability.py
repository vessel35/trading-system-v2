"""Keep policy visibility, submission, and runtime on one registry verdict."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest
from core_lib.money_management import (
    MoneyManagementBase,
    MoneyManagementReconciliationState,
    policy_settings,
    reconcile_money_management_availability,
)
from fastapi import Request
from fastapi.testclient import TestClient
from trading_plugins import build_strategy_registry, registered_money_management
from web_api.database import SignalConnection, signal_connection
from web_api.main import (
    ApiError,
    _validated_run_config,
    app,
    custom_openapi,
    money_management_context,
)
from web_api.repository import StrategyRepository


def _registration(
    policy: type[MoneyManagementBase],
    *,
    is_active: bool = True,
) -> dict[str, object]:
    return {
        "mode": policy.id,
        "class_name": policy.__name__,
        "module_path": policy.__module__,
        "display_name": policy.id.title(),
        "description": "test registration",
        "policy_version": policy.version,
        "settings_names": sorted(policy_settings(policy)),
        "is_active": is_active,
        "is_deprecated": False,
        "registered_at": datetime(2026, 8, 10, tzinfo=UTC),
        "updated_at": datetime(2026, 8, 10, tzinfo=UTC),
    }


def _registrations(*, manual_active: bool = True) -> list[dict[str, object]]:
    policies = registered_money_management()
    return [
        _registration(policies["manual"], is_active=manual_active),
        _registration(policies["turtle"]),
    ]


def _payload() -> dict[str, object]:
    return {
        "run_name": "policy-registry-test",
        "strategy_id": "vessel-reference",
        "params": {},
        "money_management": {"mode": "manual"},
        "symbol": "BTC/USDT:USDT",
        "exchange": "binance",
        "timeframe": "1h",
        "market_type": "futures",
        "data_source": "crypto_data.ohlcv_futures",
        "start": "2025-07-01T00:00:00Z",
        "end": "2025-07-04T00:00:00Z",
        "initial_capital": "10000.00",
        "seed": 0,
        "sizing_method": "risk_based",
        "risk_per_trade": 0.01,
        "cost_values": {
            "futures_taker_fee_rate": "0.0004",
            "futures_entry_slippage_rate": "0.0005",
            "exit_slippage_rate": "0.0001",
            "funding_fallback_rate": "0.0001",
        },
        "indicator_mode": "auto",
        "explicit_indicators": [],
        "trigger_feed": "tf_candle",
        "fill_timing": "next_bar",
        "profile_ref": "vessel-reference-v1",
    }


class _Result:
    def __init__(
        self,
        *,
        one: dict[str, object] | None = None,
        many: list[dict[str, object]] | None = None,
    ) -> None:
        self._one = one
        self._many = [] if many is None else many

    def fetchone(self) -> dict[str, object] | None:
        return self._one

    def fetchall(self) -> list[dict[str, object]]:
        return list(self._many)


class _SignalConnection:
    def __init__(
        self,
        registrations: list[dict[str, object]] | None,
    ) -> None:
        self._registrations = registrations

    def execute(self, query: str) -> _Result:
        if "to_regclass('public.strategy_registry')" in query:
            return _Result(one={"relation": None})
        if "to_regclass('public.money_management_registry')" in query:
            relation = None if self._registrations is None else "money_management_registry"
            return _Result(one={"relation": relation})
        if "FROM public.money_management_registry" in query:
            return _Result(many=[] if self._registrations is None else self._registrations)
        raise AssertionError(f"unexpected query: {query}")


def test_inactive_mode_has_the_same_screen_and_submission_verdict() -> None:
    policies = dict(registered_money_management())
    registrations = _registrations(manual_active=False)
    availability = reconcile_money_management_availability(registrations, policies)
    repository = StrategyRepository(
        cast(SignalConnection, _SignalConnection(None)),
        build_strategy_registry(),
        money_management_policies=policies,
        money_management_registrations=registrations,
    )

    option = repository.list().data[0]
    manual = next(item for item in option.money_management_availability if item.mode == "manual")
    assert option.supported_money_management == ["manual", "turtle"]
    assert manual.runnable is False
    assert manual.unrunnable_reason is MoneyManagementReconciliationState.INACTIVE

    with pytest.raises(ApiError) as error:
        _validated_run_config(_payload(), availability)
    assert error.value.details == [
        {
            "field": "money_management.mode",
            "message": "money-management mode 'manual' is not runnable: inactive",
            "type": "money_management_unavailable",
        }
    ]


def test_web_request_uses_the_registry_verdict_for_choices_and_submission() -> None:
    connection = cast(SignalConnection, _SignalConnection(_registrations(manual_active=False)))
    app.dependency_overrides[signal_connection] = lambda: connection
    try:
        with TestClient(app) as client:
            option = client.get("/api/v1/strategies").json()["data"][0]
            response = client.post("/api/v1/run-config:validate", json=_payload())
    finally:
        app.dependency_overrides.clear()

    manual = next(
        item for item in option["money_management_availability"] if item["mode"] == "manual"
    )
    assert manual == {
        "mode": "manual",
        "runnable": False,
        "unrunnable_reason": "inactive",
    }
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "money_management_unavailable"


def test_deployed_unregistered_mode_remains_in_the_screen_response() -> None:
    policies = dict(registered_money_management())
    registrations = [_registration(policies["turtle"])]
    option = (
        StrategyRepository(
            cast(SignalConnection, _SignalConnection(None)),
            build_strategy_registry(),
            money_management_policies=policies,
            money_management_registrations=registrations,
        )
        .list()
        .data[0]
    )

    manual = next(item for item in option.money_management_availability if item.mode == "manual")
    assert manual.runnable is False
    assert manual.unrunnable_reason is MoneyManagementReconciliationState.DEPLOYED_ONLY
    assert "manual" in option.supported_money_management


def test_missing_table_keeps_all_deployed_modes_runnable() -> None:
    policies = dict(registered_money_management())
    availability = reconcile_money_management_availability(None, policies)

    assert {item.mode for item in availability if item.runnable} == set(policies)
    assert _validated_run_config(_payload(), availability).money_management is not None


def test_database_registration_state_does_not_change_the_openapi_document() -> None:
    policies = dict(registered_money_management())
    request = cast(Request, SimpleNamespace(app=app))
    original = app.openapi_schema
    original_description = app.description
    original_policies = getattr(app.state, "money_management_policies", None)
    try:
        app.state.money_management_policies = policies
        app.openapi_schema = None
        missing_document = deepcopy(custom_openapi())
        money_management_context(
            request,
            cast(SignalConnection, _SignalConnection(_registrations(manual_active=False))),
        )
        app.openapi_schema = None
        registered_document = deepcopy(custom_openapi())
    finally:
        app.openapi_schema = original
        app.description = original_description
        app.state.money_management_policies = original_policies

    schema = registered_document["components"]["schemas"]["StrategyOption"]
    assert "money_management_availability" in schema["properties"]
    assert registered_document == missing_document
