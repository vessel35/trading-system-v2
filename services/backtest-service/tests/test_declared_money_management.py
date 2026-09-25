"""Verify that a run configuration fills omitted policy settings from the strategy.

The declaration is read through ``backtest_service.config.declarations``; these
tests replace its cache with fake declarations so no deployed strategy is needed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import MappingProxyType

import pytest
from backtest_service.config import RunConfig
from backtest_service.config import declarations as declarations_module
from backtest_service.harness.harness import Harness
from core_lib.strategy import MoneyManagementSupport
from pydantic import ValidationError

_START = datetime(2026, 1, 1, tzinfo=UTC)


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "run_name": "declared-fixture",
        "strategy_id": "declaring-fixture",
        "params": {},
        "symbol": "BTCUSDT",
        "exchange": "binance",
        "timeframe": "1h",
        "market_type": "futures",
        "data_source": "fixture",
        "start": _START,
        "end": _START + timedelta(days=2),
        "initial_capital": Decimal("10000"),
        "profile_ref": "declaring-fixture-v1",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def declaring(monkeypatch: pytest.MonkeyPatch) -> MoneyManagementSupport:
    support = MoneyManagementSupport(
        supported=("manual",),
        default="manual",
        default_settings={"manual": {"atr_stop_multiple": 1.5, "reward_risk": 1.5}},
        supports_external_stop=True,
        supports_external_take_profit=True,
    )
    monkeypatch.setattr(
        declarations_module,
        "_declarations",
        lambda: MappingProxyType({"declaring-fixture": support}),
    )
    return support


def test_an_omitted_setting_is_filled_from_the_declaration(
    declaring: MoneyManagementSupport,
) -> None:
    config = RunConfig.model_validate(_payload())

    assert config.money_management.mode == "manual"
    assert config.money_management.model_dump() == {
        "mode": "manual",
        "leverage": 1,
        "reward_risk": 1.5,
        "atr_stop_multiple": 1.5,
    }
    assert dict(config.money_management_submitted) == {"mode": "manual"}


def test_a_submitted_setting_wins_over_the_declaration(declaring: MoneyManagementSupport) -> None:
    config = RunConfig.model_validate(
        _payload(money_management={"mode": "manual", "atr_stop_multiple": 3.0})
    )

    assert config.money_management.model_dump() == {
        "mode": "manual",
        "leverage": 1,
        "reward_risk": 1.5,
        "atr_stop_multiple": 3.0,
    }
    assert dict(config.money_management_submitted) == {"mode": "manual", "atr_stop_multiple": 3.0}


def test_a_declaration_outside_the_policy_range_is_refused_at_submission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    support = MoneyManagementSupport(
        supported=("manual",),
        default="manual",
        default_settings={"manual": {"atr_stop_multiple": 20.0}},
    )
    monkeypatch.setattr(
        declarations_module,
        "_declarations",
        lambda: MappingProxyType({"declaring-fixture": support}),
    )

    with pytest.raises(ValidationError, match="atr_stop_multiple"):
        RunConfig.model_validate(_payload())


def test_an_undeclared_strategy_keeps_the_policy_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(declarations_module, "_declarations", lambda: MappingProxyType({}))

    config = RunConfig.model_validate(_payload())

    assert config.money_management.model_dump() == {
        "mode": "manual",
        "leverage": 1,
        "reward_risk": 2.0,
        "atr_stop_multiple": 2.0,
    }
    assert dict(config.money_management_submitted) == {"mode": "manual"}


def test_the_submission_record_cannot_be_claimed_by_the_caller(
    declaring: MoneyManagementSupport,
) -> None:
    with pytest.raises(ValidationError, match="extra"):
        RunConfig.model_validate(
            _payload(_money_management_submitted={"mode": "manual", "leverage": 9})
        )


def test_vessel_legacy_fields_move_before_the_declaration_applies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    support = MoneyManagementSupport(
        supported=("manual", "turtle"),
        default="manual",
        default_settings={"manual": {"atr_stop_multiple": 1.5}},
        supports_external_stop=True,
        supports_external_take_profit=True,
        supports_signal_exit=True,
    )
    monkeypatch.setattr(
        declarations_module,
        "_declarations",
        lambda: MappingProxyType({"vessel-reference": support}),
    )

    config = RunConfig.model_validate(
        _payload(
            strategy_id="vessel-reference",
            params={"leverage": 3, "reward_risk": 2.5, "fast": 10},
            profile_ref="vessel-reference-v3",
        )
    )

    assert config.params == {"fast": 10}
    assert config.money_management.model_dump() == {
        "mode": "manual",
        "leverage": 3,
        "reward_risk": 2.5,
        "atr_stop_multiple": 2.0,
    }
    assert dict(config.money_management_submitted) == {
        "mode": "manual",
        "leverage": 3,
        "reward_risk": 2.5,
        "atr_stop_multiple": 2.0,
    }


def test_a_derived_segment_keeps_the_resolved_settings(declaring: MoneyManagementSupport) -> None:
    parent = RunConfig.model_validate(_payload())

    segment = Harness._segment_config(parent, _START, _START + timedelta(days=1), "is")

    assert segment.money_management.model_dump() == parent.money_management.model_dump()
    assert dict(segment.money_management_submitted) == parent.money_management.model_dump()


def test_revalidation_and_copies_keep_the_submission(declaring: MoneyManagementSupport) -> None:
    config = RunConfig.model_validate(_payload(money_management={"mode": "manual"}))
    config.revalidate()
    copied = config.model_copy(update={"run_name": "declared-copy"})

    assert dict(config.money_management_submitted) == {"mode": "manual"}
    assert dict(copied.money_management_submitted) == {"mode": "manual"}
