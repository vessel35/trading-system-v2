"""Expose PostgreSQL adapters for the service-owned IO boundaries."""

from .data_feed import CryptoDataFeed, ReadConnection
from .money_management_registry import SignalMoneyManagementRegistry
from .signal_sink import PostgresSignalSink, WriteConnection
from .strategy_registry import SignalStrategyRegistry

__all__ = [
    "CryptoDataFeed",
    "PostgresSignalSink",
    "ReadConnection",
    "SignalMoneyManagementRegistry",
    "SignalStrategyRegistry",
    "WriteConnection",
]
