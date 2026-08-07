"""Declare the explicitly deployed strategy classes and build isolated registries."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from .adaptees import STRATEGY_ID as VESSEL_STRATEGY_ID
from .adaptees import VesselReference
from .registry import AdapterClass, InProcessStrategyRegistry

STRATEGY_ALLOWLIST: Final[Mapping[str, AdapterClass]] = MappingProxyType(
    {
        VESSEL_STRATEGY_ID: VesselReference,
    }
)


def build_strategy_registry() -> InProcessStrategyRegistry:
    """Build a fresh registry from the explicit deployment allowlist."""
    registry = InProcessStrategyRegistry()
    for strategy_id, adaptee_class in STRATEGY_ALLOWLIST.items():
        registry.register(strategy_id, adaptee_class)
    return registry


__all__ = ["STRATEGY_ALLOWLIST", "build_strategy_registry"]
