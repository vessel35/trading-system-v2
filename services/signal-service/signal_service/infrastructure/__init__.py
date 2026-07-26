"""Expose PostgreSQL adapters for the three service-owned IO boundaries."""

from .data_feed import CryptoDataFeed, ReadConnection
from .signal_sink import PostgresSignalSink, WriteConnection
from .strategy_registry import SignalStrategyRegistry

__all__ = [
    "CryptoDataFeed",
    "PostgresSignalSink",
    "ReadConnection",
    "SignalStrategyRegistry",
    "WriteConnection",
]
