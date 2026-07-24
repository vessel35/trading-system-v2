"""Verify fake-Adaptee registration, creation sequence, and lifecycle."""

from collections.abc import Mapping
from typing import ClassVar

import pytest
from core_lib.ports import StrategyRegistry
from core_lib.strategy import (
    AdapterManager,
    FieldSpec,
    InProcessStrategyRegistry,
    ParameterSchema,
    ResolvedConfig,
    StrategyAdapter,
    StrategyMetadata,
    StrategyProfile,
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
    assert FakeAdaptee.events == ["catalog_get", "schema", "cross", "init"]
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
