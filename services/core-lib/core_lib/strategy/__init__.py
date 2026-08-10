"""Define strategy contracts, configuration, profiles, and lifecycle."""

from .base import (
    MoneyManagementSupport,
    StrategyAdapter,
    StrategyBase,
    StrategyDecisionContract,
    StrategyMetadata,
    StrategyRuntime,
    validate_strategy_result,
)
from .catalog_row import CATALOG_COLUMNS, catalog_row_entry
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
    catalog_declaration_mismatch,
    reconcile_strategy_entry,
    reconcile_strategy_registries,
    strategy_identity_matches,
)
from .registry import (
    AdapterClass,
    InProcessStrategyRegistry,
)

__all__ = [
    "CATALOG_COLUMNS",
    "SCHEMA_VERSION",
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
    "StrategyDecisionContract",
    "StrategyImplementationIdentity",
    "StrategyMetadata",
    "StrategyProfile",
    "StrategyReconciliation",
    "StrategyReconciliationState",
    "StrategyRuntime",
    "catalog_declaration_mismatch",
    "catalog_row_entry",
    "reconcile_strategy_entry",
    "reconcile_strategy_registries",
    "strategy_identity_matches",
    "validate_strategy_result",
]
