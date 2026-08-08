"""Verify fake-Adaptee registration, creation sequence, and lifecycle."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar, cast

import pytest
from core_lib.ports import StrategyRegistry
from core_lib.strategy import (
    AdapterManager,
    FieldSpec,
    InProcessStrategyRegistry,
    MoneyManagementSupport,
    ParameterSchema,
    ResolvedConfig,
    StrategyAdapter,
    StrategyImplementationIdentity,
    StrategyMetadata,
    StrategyProfile,
    StrategyReconciliationState,
)
from core_lib.types import Position, TradingSignal


class FakeAdaptee:
    """Minimal stateless Adaptee used to verify platform orchestration only."""

    events: ClassVar[list[str]] = []

    def __init__(self, config: ResolvedConfig) -> None:
        self.events.append("init")
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        cls.events.append("metadata")
        return StrategyMetadata(
            required_indicators=[{"name": "EMA", "params": {"period": 21}}],
            min_history=55,
            supported_timeframes=["1h"],
            profile=StrategyProfile(
                id="fake-profile",
                family="breakout",
                bar="1h",
                expected_win_rate=(0.3, 0.6),
                expected_payoff=(1.5, 3.0),
                tail_shape="right_fat",
                holding_horizon="multi_day",
                primary_metric="calmar",
                risk_adjusted_pref="sortino",
                profit_structure_to_preserve="large_winners",
                envelope_tolerance=0.1,
                envelope_status="provisional",
            ),
        )

    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        cls.events.append("schema")
        return ParameterSchema(
            fields={
                "fast": FieldSpec(type="integer", range=(1, 20), required=True),
                "slow": FieldSpec(type="integer", default=30, range=(2, 100)),
            },
            cross_validators=(cls._validate_periods,),
        )

    @classmethod
    def _validate_periods(cls, params: Mapping[str, object]) -> None:
        cls.events.append("cross")
        fast = params["fast"]
        slow = params["slow"]
        if not isinstance(fast, int) or not isinstance(slow, int):
            raise TypeError("periods must be integers")
        if fast >= slow:
            raise ValueError("fast must be less than slow")

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> TradingSignal | None:
        del market_data, current_position
        return None


class FakeCatalog(StrategyRegistry):
    """In-memory stand-in for the injected external StrategyRegistry port."""

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.rows: dict[str, dict[str, object]] = {}

    def add_active_fake(self, strategy_id: str = "fake-breakout") -> None:
        self.rows[strategy_id] = {
            "strategy_id": strategy_id,
            "class_name": FakeAdaptee.__name__,
            "module_path": FakeAdaptee.__module__,
            "is_active": True,
            "is_deprecated": False,
        }

    def get(self, strategy_id: str) -> dict[str, object]:
        self.events.append("catalog_get")
        try:
            return dict(self.rows[strategy_id])
        except KeyError as error:
            raise KeyError(strategy_id) from error

    def list(self) -> list[dict[str, object]]:
        return [dict(row) for row in self.rows.values()]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        self.events.append("catalog_register")
        self.rows[strategy_id] = {"strategy_id": strategy_id, **meta}


class MoneyManagedAdaptee(FakeAdaptee):
    """Declare a bounded policy surface for runtime-composition tests."""

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        metadata = super().get_metadata()
        metadata.money_management = MoneyManagementSupport(
            supported=("manual",),
            default="manual",
            supports_external_stop=True,
            supports_external_take_profit=True,
            supports_signal_exit=True,
        )
        return metadata


def make_manager() -> tuple[AdapterManager, InProcessStrategyRegistry, FakeCatalog]:
    plugins = InProcessStrategyRegistry()
    plugins.register("fake-breakout", FakeAdaptee)
    FakeAdaptee.events.clear()
    catalog = FakeCatalog(FakeAdaptee.events)
    catalog.add_active_fake()
    return AdapterManager(catalog, plugins), plugins, catalog


def test_in_process_registration_is_deterministic_and_rejects_duplicates() -> None:
    _, plugins, _ = make_manager()
    assert plugins.list() == ["fake-breakout"]
    assert plugins.get("fake-breakout") is FakeAdaptee
    with pytest.raises(ValueError, match="already registered"):
        plugins.register("fake-breakout", FakeAdaptee)


def test_create_sequence_is_catalog_schema_resolve_then_constructor() -> None:
    manager, _, _ = make_manager()
    adapter = manager.create(
        "fake-breakout",
        {"strategy_id": "fake-breakout", "params": {"fast": 10}},
    )
    assert isinstance(adapter, StrategyAdapter)
    assert isinstance(adapter, FakeAdaptee)
    assert adapter.config.params == {"fast": 10, "slow": 30}
    # The Adaptee metadata is read right after the catalog lookup so a registration
    # that disagrees with the class it names is refused before any work is done.
    assert FakeAdaptee.events == ["catalog_get", "metadata", "schema", "cross", "init"]
    assert adapter.analyze({}, None) is None


def test_create_rejects_argument_and_raw_config_strategy_id_mismatch() -> None:
    manager, _, _ = make_manager()
    with pytest.raises(ValueError, match="does not match"):
        manager.create(
            "fake-breakout",
            {"strategy_id": "another-strategy", "params": {"fast": 10}},
        )


def test_lifecycle_activates_and_deactivates_only_created_adaptees() -> None:
    manager, _, _ = make_manager()
    manager.create(
        "fake-breakout",
        {"strategy_id": "fake-breakout", "params": {"fast": 10}},
    )
    assert manager.is_active("fake-breakout") is False
    manager.activate("fake-breakout")
    assert manager.is_active("fake-breakout") is True
    manager.deactivate("fake-breakout")
    assert manager.is_active("fake-breakout") is False
    with pytest.raises(KeyError, match="has not been created"):
        manager.activate("missing")


def test_catalog_access_is_delegated_and_inactive_rows_cannot_execute() -> None:
    manager, _, catalog = make_manager()
    assert manager.list_registered() == ["fake-breakout"]
    manager.register("fake-breakout", {"class_name": FakeAdaptee.__name__})
    assert FakeAdaptee.events == ["catalog_register"]

    catalog.rows["fake-breakout"]["is_active"] = False
    with pytest.raises(ValueError, match="inactive"):
        manager.create(
            "fake-breakout",
            {"strategy_id": "fake-breakout", "params": {"fast": 10}},
        )


def test_runtime_composes_only_a_strategy_supported_money_policy() -> None:
    events: list[str] = []
    plugins = InProcessStrategyRegistry()
    plugins.register("money-breakout", MoneyManagedAdaptee)
    catalog = FakeCatalog(events)
    catalog.rows["money-breakout"] = {
        "strategy_id": "money-breakout",
        "class_name": MoneyManagedAdaptee.__name__,
        "module_path": MoneyManagedAdaptee.__module__,
        "is_active": True,
        "is_deprecated": False,
    }
    manager = AdapterManager(catalog, plugins)
    runtime = manager.create_runtime(
        "money-breakout",
        {"strategy_id": "money-breakout", "params": {"fast": 10}},
        {"mode": "manual", "leverage": 3},
    )
    assert isinstance(runtime.strategy, MoneyManagedAdaptee)
    assert runtime.money_management is not None
    assert runtime.money_management.id == "manual"

    with pytest.raises(ValueError, match="does not support"):
        manager.create_runtime(
            "money-breakout",
            {"strategy_id": "money-breakout", "params": {"fast": 10}},
            {"mode": "turtle"},
        )


def test_registration_that_disagrees_with_the_adaptee_is_refused() -> None:
    """How much history a run reads follows these declarations, so drift is refused.

    The catalog carries the same facts as the Adaptee so operators and the console can
    read them without importing code. Nothing reconciled the two, so a registration
    could describe a run that never happens. Either side could be the stale one, so a
    disagreement is refused rather than silently resolved.
    """
    for field, value, expected in (
        ("min_history", 21, "min_history"),
        ("supported_timeframes", ["4h"], "supported_timeframes"),
        (
            "required_indicators_json",
            [{"name": "EMA", "params": {"period": 200}}],
            "required_indicators",
        ),
    ):
        manager, _, catalog = make_manager()
        catalog.rows["fake-breakout"][field] = value
        with pytest.raises(ValueError, match=expected):
            manager.create(
                "fake-breakout",
                {"strategy_id": "fake-breakout", "params": {"fast": 10}},
            )


def test_a_registration_that_agrees_with_the_adaptee_is_accepted() -> None:
    manager, _, catalog = make_manager()
    catalog.rows["fake-breakout"].update(
        {
            "min_history": 55,
            "supported_timeframes": ["1h"],
            # Key order and list order must not matter; only the identities do.
            "required_indicators_json": [{"params": {"period": 21}, "name": "EMA"}],
        }
    )

    adapter = manager.create(
        "fake-breakout",
        {"strategy_id": "fake-breakout", "params": {"fast": 10}},
    )

    assert adapter.get_metadata().min_history == 55


def test_catalog_reconciliation_returns_five_distinct_states() -> None:
    plugins = InProcessStrategyRegistry()
    for strategy_id in (
        "allowlist-only",
        "deprecated",
        "healthy",
        "identity-mismatch",
        "inactive",
    ):
        plugins.register(strategy_id, FakeAdaptee)

    catalog = FakeCatalog([])
    for strategy_id in (
        "catalog-only",
        "deprecated",
        "healthy",
        "identity-mismatch",
        "inactive",
    ):
        catalog.rows[strategy_id] = {
            "strategy_id": strategy_id,
            "class_name": FakeAdaptee.__name__,
            "module_path": FakeAdaptee.__module__,
            "is_active": True,
            "is_deprecated": False,
        }
    catalog.rows["catalog-only"].update(
        {"class_name": "CatalogOnly", "module_path": "strategies.catalog_only"}
    )
    catalog.rows["identity-mismatch"]["module_path"] = "strategies.stale"
    catalog.rows["inactive"]["is_active"] = False
    catalog.rows["deprecated"].update({"is_active": False, "is_deprecated": True})

    findings = AdapterManager(catalog, plugins).reconcile_catalog()

    assert [finding.strategy_id for finding in findings] == [
        "allowlist-only",
        "catalog-only",
        "deprecated",
        "identity-mismatch",
        "inactive",
    ]
    assert {finding.strategy_id: finding.state for finding in findings} == {
        "allowlist-only": StrategyReconciliationState.ALLOWLIST_ONLY,
        "catalog-only": StrategyReconciliationState.CATALOG_ONLY,
        "deprecated": StrategyReconciliationState.DEPRECATED,
        "identity-mismatch": StrategyReconciliationState.IDENTITY_MISMATCH,
        "inactive": StrategyReconciliationState.INACTIVE,
    }
    assert "healthy" not in {finding.strategy_id for finding in findings}

    mismatch = next(finding for finding in findings if finding.strategy_id == "identity-mismatch")
    assert mismatch.catalog_identity == StrategyImplementationIdentity(
        class_name=FakeAdaptee.__name__,
        module_path="strategies.stale",
    )
    assert mismatch.allowlist_identity == StrategyImplementationIdentity(
        class_name=FakeAdaptee.__name__,
        module_path=FakeAdaptee.__module__,
    )


@dataclass(frozen=True, slots=True)
class UndeclaredExitPolicy:
    """A policy that satisfies the protocol's shape but not its exit declaration.

    The protocol is structural, so a class that never mentions
    ``requires_signal_exit`` still looked like a policy. It plans no take-profit,
    which is exactly the case the declaration exists to catch.
    """

    id: ClassVar[str] = "undeclared"
    version: ClassVar[str] = "1.0.0"

    def required_indicators(self) -> tuple[object, ...]:
        return ()

    def resolved_config(self) -> Mapping[str, object]:
        return {"mode": self.id}

    def plan_entry(self, *args: object, **kwargs: object) -> object:
        raise NotImplementedError


class UndeclaredSupportAdaptee(FakeAdaptee):
    """A strategy that cannot close a position on its own signal."""

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        metadata = super().get_metadata()
        metadata.money_management = MoneyManagementSupport(
            supported=("undeclared",),
            default="undeclared",
            supports_external_stop=True,
            supports_external_take_profit=True,
            supports_signal_exit=False,
        )
        return metadata


def test_a_policy_that_does_not_declare_its_exit_need_is_refused() -> None:
    """Reading a missing declaration as false opened trades nothing could close."""
    events: list[str] = []
    plugins = InProcessStrategyRegistry()
    plugins.register("money-breakout", UndeclaredSupportAdaptee)
    catalog = FakeCatalog(events)
    catalog.rows["money-breakout"] = {
        "strategy_id": "money-breakout",
        "class_name": UndeclaredSupportAdaptee.__name__,
        "module_path": UndeclaredSupportAdaptee.__module__,
        "is_active": True,
        "is_deprecated": False,
    }
    manager = AdapterManager(
        catalog,
        plugins,
        money_management_policies={"undeclared": cast("Any", UndeclaredExitPolicy)},
    )

    with pytest.raises(ValueError, match="does not declare requires_signal_exit"):
        manager.create_runtime(
            "money-breakout",
            {"strategy_id": "money-breakout", "params": {"fast": 10}},
            {"mode": "undeclared"},
        )
