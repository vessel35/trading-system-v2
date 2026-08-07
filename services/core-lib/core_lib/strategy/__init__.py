"""Define strategy contracts, configuration, profiles, and lifecycle."""

from .allowlist import STRATEGY_ALLOWLIST, build_strategy_registry
from .base import (
    MoneyManagementSupport,
    StrategyAdapter,
    StrategyBase,
    StrategyMetadata,
    StrategyRuntime,
)
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
from .reconciliation import (
    StrategyImplementationIdentity,
    StrategyReconciliation,
    StrategyReconciliationState,
    reconcile_strategy_registries,
)
from .registry import (
    AdapterClass,
    InProcessStrategyRegistry,
)

__all__ = [
    "SCHEMA_VERSION",
    "STRATEGY_ALLOWLIST",
    "AdapterClass",
    "AdapterFactory",
    "AdapterManager",
    "CrossValidator",
    "FieldSpec",
    "InProcessStrategyRegistry",
    "MoneyManagementSupport",
    "ParameterSchema",
    "ResolvedConfig",
    "StrategyAdapter",
    "StrategyBase",
    "StrategyConfig",
    "StrategyImplementationIdentity",
    "StrategyMetadata",
    "StrategyProfile",
    "StrategyReconciliation",
    "StrategyReconciliationState",
    "StrategyRuntime",
    "build_strategy_registry",
    "reconcile_strategy_registries",
]
