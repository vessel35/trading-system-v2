"""Assemble adapters from injected handles without opening a live connection."""

from __future__ import annotations

from core_lib.strategy import AdapterManager, InProcessStrategyRegistry
from core_lib.strategy.adaptees import STRATEGY_ID as VESSEL_STRATEGY_ID
from core_lib.strategy.adaptees import VesselReference

from signal_service.application import SignalGenerationService, SignalQueue
from signal_service.infrastructure import (
    CryptoDataFeed,
    PostgresSignalSink,
    ReadConnection,
    SignalStrategyRegistry,
    WriteConnection,
)


def build_signal_generator(
    *,
    crypto_reader: ReadConnection,
    registry_reader: ReadConnection,
    signal_writer: WriteConnection,
    queue: SignalQueue | None = None,
) -> SignalGenerationService:
    """Wire the v2 core path while leaving connection policy to the operator."""
    plugins = InProcessStrategyRegistry()
    plugins.register(VESSEL_STRATEGY_ID, VesselReference)
    manager = AdapterManager(
        SignalStrategyRegistry(registry_reader),
        plugins,
    )
    return SignalGenerationService(
        CryptoDataFeed(crypto_reader),
        manager,
        PostgresSignalSink(signal_writer),
        queue=queue,
    )


__all__ = ["build_signal_generator"]
