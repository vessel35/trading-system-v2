"""Expose the deployed strategies and policies the platform should load."""

from .discovery import (
    build_strategy_registry,
    discover_money_management,
    discover_strategies,
)

__all__ = [
    "build_strategy_registry",
    "discover_money_management",
    "discover_strategies",
]
