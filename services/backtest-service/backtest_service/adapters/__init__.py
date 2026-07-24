"""Implement backtest-specific core port adapters."""

from .broker import BacktestBroker
from .catalog_store import BacktestCatalogStore
from .clock import BacktestClock
from .cost_model import BacktestCostModel
from .data_feed import BacktestDataFeed
from .evidence_sink import BacktestEvidenceSink, EvidenceRecord
from .strategy_registry import BacktestStrategyRegistry

__all__ = [
    "BacktestBroker",
    "BacktestCatalogStore",
    "BacktestClock",
    "BacktestCostModel",
    "BacktestDataFeed",
    "BacktestEvidenceSink",
    "BacktestStrategyRegistry",
    "EvidenceRecord",
]
