"""Verify the explicit strategy deployment allowlist and isolated registries."""

import pytest
from core_lib.strategy import STRATEGY_ALLOWLIST, build_strategy_registry
from core_lib.strategy.adaptees import STRATEGY_ID, VesselReference


def test_strategy_allowlist_has_the_exact_deployed_contents_and_unique_ids() -> None:
    assert dict(STRATEGY_ALLOWLIST) == {STRATEGY_ID: VesselReference}
    assert len(STRATEGY_ALLOWLIST) == len(set(STRATEGY_ALLOWLIST))


def test_registry_builder_returns_fresh_registries_that_reject_duplicate_ids() -> None:
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
