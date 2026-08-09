"""Prove the additive strategy-runnability response contract."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, fields
from pathlib import Path
from typing import ClassVar, cast

import pytest
import web_api.repository as repository_module
from core_lib.ports import StrategyRegistry
from core_lib.strategy import (
    AdapterManager,
    FieldSpec,
    InProcessStrategyRegistry,
    ParameterSchema,
    ResolvedConfig,
    StrategyMetadata,
    StrategyProfile,
    StrategyReconciliationState,
)
from core_lib.types import Position, TradingSignal
from pydantic import ValidationError
from web_api.database import SignalConnection
from web_api.models import StrategyOption, StrategyProfileResponse
from web_api.repository import StrategyRepository


class _FixtureStrategy:
    """Small generic strategy whose declaration reads can be counted or failed."""

    VERSION = "9.9.9"
    metadata_calls: ClassVar[int] = 0
    schema_calls: ClassVar[int] = 0
    metadata_failure: ClassVar[BaseException | None] = None
    schema_failure: ClassVar[BaseException | None] = None

    def __init__(self, config: ResolvedConfig) -> None:
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        cls.metadata_calls += 1
        if cls.metadata_failure is not None:
            raise cls.metadata_failure
        return StrategyMetadata(
            required_indicators=[{"name": "EMA", "params": {"period": 55}}],
            min_history=77,
            supported_timeframes=["4h"],
            profile=StrategyProfile(
                id="runnability-fixture-v1",
                family="trend",
                bar="4h",
                expected_win_rate=(0.0, 0.6),
                expected_payoff=(0.0, 3.0),
                tail_shape="right_fat",
                holding_horizon="",
                primary_metric="calmar",
                risk_adjusted_pref="sortino",
                profit_structure_to_preserve="test-edge",
                envelope_tolerance=0.0,
                envelope_status="provisional",
            ),
        )

    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        cls.schema_calls += 1
        if cls.schema_failure is not None:
            raise cls.schema_failure
        return ParameterSchema(fields={"edge": FieldSpec(type="number", default=3.5)})

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> TradingSignal | None:
        del market_data, current_position
        return None


class _RuntimeReadFailure(_FixtureStrategy):
    pass


class _SystemExitReadFailure(_FixtureStrategy):
    pass


class _RowsCursor:
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
        return self._many


class _RowsConnection:
    def __init__(self, rows: list[dict[str, object]], *, table_exists: bool = True) -> None:
        self.rows = rows
        self.table_exists = table_exists

    def execute(self, query: str) -> _RowsCursor:
        if "to_regclass" in query:
            relation = "strategy_registry" if self.table_exists else None
            return _RowsCursor(one={"relation": relation})
        assert "class_name, module_path" in query
        return _RowsCursor(many=self.rows)


class _Catalog(StrategyRegistry):
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = {str(row["strategy_id"]): dict(row) for row in rows}

    def get(self, strategy_id: str) -> dict[str, object]:
        try:
            return dict(self.rows[strategy_id])
        except KeyError as error:
            raise KeyError(strategy_id) from error

    def list(self) -> list[dict[str, object]]:
        return [dict(row) for row in self.rows.values()]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        self.rows[strategy_id] = {"strategy_id": strategy_id, **meta}


def _row(
    strategy_id: str,
    *,
    adaptee_class: type[_FixtureStrategy] = _FixtureStrategy,
    **overrides: object,
) -> dict[str, object]:
    return {
        "strategy_id": strategy_id,
        "display_name": f"Row {strategy_id}",
        "strategy_version": "row-version",
        "supported_timeframes": ["4h"],
        "required_indicators_json": [{"name": "EMA", "params": {"period": 55}}],
        "min_history": 77,
        "default_params_json": {"row": True},
        "is_active": True,
        "is_deprecated": False,
        "class_name": adaptee_class.__name__,
        "module_path": adaptee_class.__module__,
        **overrides,
    }


def _repository(
    rows: list[dict[str, object]],
    registry: InProcessStrategyRegistry,
    *,
    table_exists: bool = True,
) -> StrategyRepository:
    connection = cast(
        SignalConnection,
        _RowsConnection(rows, table_exists=table_exists),
    )
    return StrategyRepository(connection, registry)


def _register(
    *entries: tuple[str, type[_FixtureStrategy]],
) -> InProcessStrategyRegistry:
    registry = InProcessStrategyRegistry()
    for strategy_id, strategy_class in entries:
        strategy_class.metadata_failure = None
        strategy_class.schema_failure = None
        registry.register(strategy_id, strategy_class)
    return registry


def _assert_bidirectional_pair(option: StrategyOption) -> None:
    assert option.runnable is (option.unrunnable_reason is None)
    assert (option.unrunnable_reason is not None) is (not option.runnable)


def _assert_profile_pair(option: StrategyOption) -> None:
    assert (option.profile is None) is (option.profile_id is None)
    if option.profile is not None:
        assert option.profile.id == option.profile_id


def _profile_payload(profile_id: str) -> StrategyProfileResponse:
    return StrategyProfileResponse(
        id=profile_id,
        family="trend",
        bar="4h",
        expected_win_rate=(0.0, 0.6),
        expected_payoff=(0.0, 3.0),
        tail_shape="right_fat",
        holding_horizon="",
        primary_metric="calmar",
        risk_adjusted_pref="sortino",
        profit_structure_to_preserve="test-edge",
        envelope_tolerance=0.0,
        envelope_status="provisional",
    )


def test_normal_and_all_seven_reasons_are_projected_without_unioning_membership() -> None:
    registry = _register(
        ("healthy", _FixtureStrategy),
        ("identity", _FixtureStrategy),
        ("declaration", _FixtureStrategy),
        ("deprecated", _FixtureStrategy),
        ("inactive", _FixtureStrategy),
        ("read-failed", _RuntimeReadFailure),
        ("not-in-catalog", _FixtureStrategy),
    )
    _RuntimeReadFailure.metadata_failure = RuntimeError("broken declaration")
    rows = [
        _row("healthy"),
        _row("catalog-only"),
        _row("identity", module_path="strategies.stale"),
        _row("declaration", min_history=1),
        _row("deprecated", is_deprecated=True),
        _row("inactive", is_active=False),
        _row("read-failed", adaptee_class=_RuntimeReadFailure),
    ]

    options = _repository(rows, registry).list().data

    assert [option.strategy_id for option in options] == [
        "healthy",
        "catalog-only",
        "identity",
        "declaration",
        "deprecated",
        "inactive",
        "read-failed",
    ]
    assert {option.strategy_id: option.unrunnable_reason for option in options} == {
        "healthy": None,
        "catalog-only": StrategyReconciliationState.CATALOG_ONLY,
        "identity": StrategyReconciliationState.IDENTITY_MISMATCH,
        "declaration": StrategyReconciliationState.DECLARATION_MISMATCH,
        "deprecated": StrategyReconciliationState.DEPRECATED,
        "inactive": StrategyReconciliationState.INACTIVE,
        "read-failed": StrategyReconciliationState.DECLARATION_READ_FAILED,
    }
    assert {option.strategy_id: option.profile_id for option in options} == {
        "healthy": "runnability-fixture-v1",
        "catalog-only": None,
        "identity": None,
        "declaration": None,
        "deprecated": None,
        "inactive": None,
        "read-failed": None,
    }
    assert options[0].profile is not None
    assert options[0].profile.model_dump() == asdict(_FixtureStrategy.get_metadata().profile)
    assert all(option.profile is None for option in options[1:])
    for option in options:
        _assert_bidirectional_pair(option)
        _assert_profile_pair(option)

    fallback = (
        _repository(
            [],
            _register(("allowlist-only", _FixtureStrategy)),
            table_exists=False,
        )
        .list()
        .data
    )
    assert len(fallback) == 1
    assert fallback[0].unrunnable_reason is StrategyReconciliationState.ALLOWLIST_ONLY
    assert fallback[0].profile_id is None
    assert fallback[0].profile is None
    _assert_bidirectional_pair(fallback[0])
    _assert_profile_pair(fallback[0])


def test_strategy_option_rejects_both_invalid_runnability_pairs() -> None:
    def option(
        *,
        runnable: bool,
        reason: StrategyReconciliationState | None,
    ) -> StrategyOption:
        return StrategyOption(
            strategy_id="fixture",
            display_name="Fixture",
            strategy_version="1.0.0",
            profile_id="declared-profile-unlike-fixture-v1",
            profile=_profile_payload("declared-profile-unlike-fixture-v1"),
            supported_timeframes=["1h"],
            required_indicators=[],
            min_history=1,
            default_params={},
            supported_money_management=[],
            default_money_management={},
            is_active=True,
            is_deprecated=False,
            runnable=runnable,
            unrunnable_reason=reason,
            source="strategy_registry",
        )

    with pytest.raises(ValidationError, match="runnable must be true exactly"):
        option(
            runnable=True,
            reason=StrategyReconciliationState.INACTIVE,
        )
    with pytest.raises(ValidationError, match="runnable must be true exactly"):
        option(runnable=False, reason=None)


def test_strategy_option_rejects_profile_presence_and_identity_mismatches() -> None:
    values = {
        "strategy_id": "fixture",
        "display_name": "Fixture",
        "strategy_version": "1.0.0",
        "supported_timeframes": ["1h"],
        "required_indicators": [],
        "min_history": 1,
        "default_params": {},
        "supported_money_management": [],
        "default_money_management": {},
        "is_active": True,
        "is_deprecated": False,
        "runnable": True,
        "unrunnable_reason": None,
        "source": "strategy_registry",
    }

    with pytest.raises(ValidationError, match="both be present or both be null"):
        StrategyOption(
            **values,  # type: ignore[arg-type]
            profile_id="declared-profile",
            profile=None,
        )
    with pytest.raises(ValidationError, match="profile.id must equal profile_id"):
        StrategyOption(
            **values,  # type: ignore[arg-type]
            profile_id="declared-profile",
            profile=_profile_payload("different-profile"),
        )


def test_openapi_model_requires_exactly_the_closed_additive_runnability_contract() -> None:
    schema = StrategyOption.model_json_schema()

    assert {"runnable", "unrunnable_reason"} <= set(schema["required"])
    reason_schema = schema["properties"]["unrunnable_reason"]
    assert reason_schema["anyOf"] == [
        {
            "enum": [
                "catalog_only",
                "allowlist_only",
                "identity_mismatch",
                "inactive",
                "deprecated",
                "declaration_mismatch",
                "declaration_read_failed",
            ],
            "type": "string",
        },
        {"type": "null"},
    ]
    assert schema["properties"]["profile_id"]["anyOf"] == [
        {"type": "string"},
        {"type": "null"},
    ]
    assert "profile_id" in schema["required"]
    assert schema["properties"]["profile"]["anyOf"] == [
        {"$ref": "#/$defs/StrategyProfileResponse"},
        {"type": "null"},
    ]
    assert "profile" in schema["required"]

    profile_schema = schema["$defs"]["StrategyProfileResponse"]
    assert set(profile_schema["properties"]) == {field.name for field in fields(StrategyProfile)}
    assert set(profile_schema["required"]) == {field.name for field in fields(StrategyProfile)}
    for name in ("expected_win_rate", "expected_payoff"):
        assert profile_schema["properties"][name] == {
            "maxItems": 2,
            "minItems": 2,
            "prefixItems": [{"type": "number"}, {"type": "number"}],
            "title": name.replace("_", " ").title(),
            "type": "array",
        }


def test_profile_response_matches_dataclass_and_evidence_json_shape() -> None:
    declared = _FixtureStrategy.get_metadata().profile
    option = (
        _repository(
            [_row("fixture")],
            _register(("fixture", _FixtureStrategy)),
        )
        .list()
        .data[0]
    )

    assert set(StrategyProfileResponse.model_fields) == {
        field.name for field in fields(StrategyProfile)
    }
    assert option.profile is not None
    assert option.profile.model_dump() == asdict(declared)
    assert option.profile.model_dump(mode="json") == json.loads(json.dumps(asdict(declared)))
    assert option.profile.model_dump(mode="json")["expected_win_rate"] == [0.0, 0.6]
    assert option.profile.model_dump(mode="json")["expected_payoff"] == [0.0, 3.0]
    assert option.profile.holding_horizon == ""
    assert option.profile.envelope_tolerance == 0.0


def test_code_registry_profile_uses_the_same_present_and_null_conditions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _register(("fixture", _FixtureStrategy))
    null_option = _repository([], registry, table_exists=False).list().data[0]
    assert null_option.profile_id is None
    assert null_option.profile is None
    _assert_profile_pair(null_option)

    def no_finding(*args: object, **kwargs: object) -> None:
        del args, kwargs

    monkeypatch.setattr(repository_module, "reconcile_strategy_entry", no_finding)
    present_option = _repository([], registry, table_exists=False).list().data[0]
    declared = _FixtureStrategy.get_metadata().profile
    assert present_option.profile_id == declared.id
    assert present_option.profile is not None
    assert present_option.profile.model_dump() == asdict(declared)
    _assert_profile_pair(present_option)


def test_committed_frontend_type_keeps_profile_ranges_as_two_number_tuples() -> None:
    repository_root = Path(__file__).parents[3]
    generated = (repository_root / "apps/web/src/api/schema.d.ts").read_text(encoding="utf-8")

    assert 'profile: components["schemas"]["StrategyProfileResponse"] | null;' in generated
    assert re.search(r"expected_win_rate:\s*\[\s*number,\s*number\s*\];", generated)
    assert re.search(r"expected_payoff:\s*\[\s*number,\s*number\s*\];", generated)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"min_history": 1}, StrategyReconciliationState.DECLARATION_MISMATCH),
        (
            {"supported_timeframes": ["5m"]},
            StrategyReconciliationState.DECLARATION_MISMATCH,
        ),
        (
            {"required_indicators_json": [{"name": "RSI", "params": {"period": 14}}]},
            StrategyReconciliationState.DECLARATION_MISMATCH,
        ),
    ],
)
def test_each_registered_declaration_drift_is_unrunnable(
    overrides: dict[str, object],
    expected: StrategyReconciliationState,
) -> None:
    registry = _register(("fixture", _FixtureStrategy))
    row = _row("fixture")
    row.update(overrides)

    option = _repository([row], registry).list().data[0]

    assert option.unrunnable_reason is expected
    assert option.runnable is False


def test_overlapping_reasons_follow_the_canonical_precedence() -> None:
    identity_registry = _register(("identity", _FixtureStrategy))
    identity = (
        _repository(
            [_row("identity", module_path="strategies.stale", is_active=False)],
            identity_registry,
        )
        .list()
        .data[0]
    )
    assert identity.unrunnable_reason is StrategyReconciliationState.IDENTITY_MISMATCH

    declaration_registry = _register(("declaration", _FixtureStrategy))
    declaration = (
        _repository(
            [_row("declaration", min_history=1, is_deprecated=True)],
            declaration_registry,
        )
        .list()
        .data[0]
    )
    assert declaration.unrunnable_reason is StrategyReconciliationState.DECLARATION_MISMATCH

    read_registry = _register(("read", _RuntimeReadFailure))
    _RuntimeReadFailure.metadata_failure = RuntimeError("broken declaration")
    read_failed = (
        _repository(
            [_row("read", adaptee_class=_RuntimeReadFailure, is_active=False)],
            read_registry,
        )
        .list()
        .data[0]
    )
    assert read_failed.unrunnable_reason is StrategyReconciliationState.DECLARATION_READ_FAILED


def test_declaration_errors_and_system_exit_are_isolated_from_other_rows() -> None:
    registry = _register(
        ("healthy", _FixtureStrategy),
        ("runtime", _RuntimeReadFailure),
        ("system-exit", _SystemExitReadFailure),
    )
    _RuntimeReadFailure.metadata_failure = RuntimeError("ordinary failure")
    _SystemExitReadFailure.schema_failure = SystemExit(19)

    options = (
        _repository(
            [
                _row("runtime", adaptee_class=_RuntimeReadFailure),
                _row("healthy"),
                _row("system-exit", adaptee_class=_SystemExitReadFailure),
            ],
            registry,
        )
        .list()
        .data
    )

    assert {option.strategy_id: option.unrunnable_reason for option in options} == {
        "runtime": StrategyReconciliationState.DECLARATION_READ_FAILED,
        "healthy": None,
        "system-exit": StrategyReconciliationState.DECLARATION_READ_FAILED,
    }


def test_each_declaration_is_read_once_and_one_snapshot_fills_existing_fields() -> None:
    registry = _register(("fixture", _FixtureStrategy))
    _FixtureStrategy.metadata_calls = 0
    _FixtureStrategy.schema_calls = 0

    option = _repository([_row("fixture")], registry).list().data[0]

    assert (_FixtureStrategy.metadata_calls, _FixtureStrategy.schema_calls) == (1, 1)
    assert option.profile_id == "runnability-fixture-v1"
    assert option.model_dump(
        exclude={"runnable", "unrunnable_reason", "profile_id", "profile"}
    ) == {
        "strategy_id": "fixture",
        "display_name": "Row fixture",
        "strategy_version": "9.9.9",
        "supported_timeframes": ["4h"],
        "required_indicators": [{"name": "EMA", "params": {"period": 55}}],
        "min_history": 77,
        "default_params": {"edge": 3.5},
        "supported_money_management": [],
        "default_money_management": {},
        "is_active": True,
        "is_deprecated": False,
        "source": "strategy_registry",
    }

    _FixtureStrategy.metadata_calls = 0
    _FixtureStrategy.schema_calls = 0
    _repository([], registry, table_exists=False).list()
    assert (_FixtureStrategy.metadata_calls, _FixtureStrategy.schema_calls) == (1, 1)


@pytest.mark.parametrize(
    ("overrides", "runnable"),
    [
        ({}, True),
        ({"module_path": "strategies.stale"}, False),
        ({"min_history": 1}, False),
        ({"is_deprecated": True}, False),
        ({"is_active": False}, False),
    ],
)
def test_list_runnability_matches_adapter_manager_creation(
    overrides: dict[str, object],
    runnable: bool,
) -> None:
    row = _row("fixture")
    row.update(overrides)
    registry = _register(("fixture", _FixtureStrategy))
    option = _repository([row], registry).list().data[0]
    manager = AdapterManager(_Catalog([row]), registry)

    assert option.runnable is runnable
    if runnable:
        manager.create("fixture", {"strategy_id": "fixture", "params": {}})
    else:
        with pytest.raises((KeyError, ValueError, RuntimeError)):
            manager.create("fixture", {"strategy_id": "fixture", "params": {}})


def test_read_failure_and_membership_findings_are_also_rejected_by_manager() -> None:
    read_registry = _register(("read", _RuntimeReadFailure))
    read_row = _row("read", adaptee_class=_RuntimeReadFailure)
    _RuntimeReadFailure.metadata_failure = RuntimeError("broken declaration")
    option = _repository([read_row], read_registry).list().data[0]
    assert option.runnable is False
    with pytest.raises(RuntimeError, match="broken declaration"):
        AdapterManager(_Catalog([read_row]), read_registry).create(
            "read", {"strategy_id": "read", "params": {}}
        )

    catalog_only = (
        _repository(
            [_row("catalog-only")],
            InProcessStrategyRegistry(),
        )
        .list()
        .data[0]
    )
    assert catalog_only.runnable is False
    with pytest.raises(KeyError, match="not registered"):
        AdapterManager(_Catalog([_row("catalog-only")]), InProcessStrategyRegistry()).create(
            "catalog-only", {"strategy_id": "catalog-only", "params": {}}
        )

    allowlist_registry = _register(("allowlist-only", _FixtureStrategy))
    allowlist_only = (
        _repository(
            [],
            allowlist_registry,
            table_exists=False,
        )
        .list()
        .data[0]
    )
    assert allowlist_only.runnable is False
    with pytest.raises(KeyError, match="allowlist-only"):
        AdapterManager(_Catalog([]), allowlist_registry).create(
            "allowlist-only", {"strategy_id": "allowlist-only", "params": {}}
        )
