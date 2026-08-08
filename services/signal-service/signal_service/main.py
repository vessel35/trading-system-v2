"""Assemble and run signal polling from explicitly injected operator handles."""

from __future__ import annotations

import logging
import signal
import threading
import time
from collections.abc import Callable
from threading import Event
from types import FrameType

from core_lib.strategy import AdapterManager
from service_commons.observability import configure_logging
from trading_plugins import build_strategy_registry, registered_money_management

from signal_service.application import (
    SignalGenerationService,
    SignalGenerator,
    SignalPollingRunner,
    SignalQueue,
)
from signal_service.core import SignalGenerationConfig
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
    manager = AdapterManager(
        SignalStrategyRegistry(registry_reader),
        build_strategy_registry(),
        money_management_policies=registered_money_management(),
    )
    return SignalGenerationService(
        CryptoDataFeed(crypto_reader),
        manager,
        PostgresSignalSink(signal_writer),
        queue=queue,
    )


def run_signal_generator(
    generator: SignalGenerator,
    config: SignalGenerationConfig,
    *,
    poll_interval_seconds: int = 60,
    poll_buffer_seconds: int = 2,
    wall_clock: Callable[[], float] = time.time,
    sleep: Callable[[float], object] | None = None,
    stop_event: Event | None = None,
) -> None:
    """Run the injected generator until SIGINT, SIGTERM, or an explicit stop."""

    configure_logging(logging.INFO)
    runner = SignalPollingRunner(
        generator,
        config,
        poll_interval_seconds=poll_interval_seconds,
        poll_buffer_seconds=poll_buffer_seconds,
        wall_clock=wall_clock,
        sleep=sleep,
        stop_event=stop_event,
    )
    _run_with_shutdown_signals(runner)


def _run_with_shutdown_signals(runner: SignalPollingRunner) -> None:
    if threading.current_thread() is not threading.main_thread():
        runner.run()
        return

    previous_handlers = {
        signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)
    }

    def request_stop(signum: int, frame: FrameType | None) -> None:
        del signum, frame
        runner.stop()

    try:
        for signum in previous_handlers:
            signal.signal(signum, request_stop)
        runner.run()
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


__all__ = ["build_signal_generator", "run_signal_generator"]
