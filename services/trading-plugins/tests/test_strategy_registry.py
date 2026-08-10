"""Verify that the deployed strategy package alone builds isolated registries."""

import pytest
from core_lib import strategy as core_strategy
from trading_plugins import build_strategy_registry, discover_strategies
from trading_plugins.strategies.vessel_reference import STRATEGY_ID, VesselReference


def test_strategy_package_scan_alone_discovers_vessel_reference() -> None:
    found, faults = discover_strategies()

    assert faults == ()
    assert dict(found) == {STRATEGY_ID: VesselReference}
    assert not hasattr(core_strategy, "STRATEGY_ALLOWLIST")
    assert not hasattr(core_strategy, "build_strategy_registry")


def test_registry_builder_returns_fresh_discovery_only_registries() -> None:
    first = build_strategy_registry()
    second = build_strategy_registry()

    assert first is not second
    assert first.list() == [STRATEGY_ID]
    assert second.list() == [STRATEGY_ID]
    first.unregister(STRATEGY_ID)
    assert first.list() == []
    assert second.list() == [STRATEGY_ID]

    with pytest.raises(ValueError, match="already registered"):
        second.register(STRATEGY_ID, VesselReference)
