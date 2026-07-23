"""Define strategy contracts, configuration, profiles, and lifecycle."""

from .base import StrategyAdapter, StrategyMetadata
from .config import (
    SCHEMA_VERSION,
    CrossValidator,
    FieldSpec,
    ParameterSchema,
    ResolvedConfig,
    StrategyConfig,
)
from .factory import AdapterFactory
from .manager import AdapterManager
from .profile import StrategyProfile
from .registry import (
    DEFAULT_STRATEGY_REGISTRY,
    AdapterClass,
    InProcessStrategyRegistry,
)

__all__ = [
    "DEFAULT_STRATEGY_REGISTRY",
    "SCHEMA_VERSION",
    "AdapterClass",
    "AdapterFactory",
    "AdapterManager",
    "CrossValidator",
    "FieldSpec",
    "InProcessStrategyRegistry",
    "ParameterSchema",
    "ResolvedConfig",
    "StrategyAdapter",
    "StrategyConfig",
    "StrategyMetadata",
    "StrategyProfile",
]
