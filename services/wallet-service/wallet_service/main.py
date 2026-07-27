"""Assemble and run the paper wallet from explicitly injected adapters."""

import logging
import signal
import threading
import time
from collections.abc import Callable
from decimal import Decimal
from threading import Event
from types import FrameType

from core_lib.ports import CostModel
from service_commons.observability import configure_logging

from wallet_service.application import SignalQueue, WalletPollingRunner, WalletService
from wallet_service.core import RiskPolicy
from wallet_service.infrastructure import (
    PaperBroker,
    PaperCostModel,
    PostgresSignalQueue,
    PostgresWalletRepository,
    ReadConnection,
    WriteConnection,
)


def build_paper_wallet(
    *,
    wallet_id: str,
    queue: SignalQueue,
    connection: WriteConnection,
    policy: RiskPolicy,
    initial_cash: Decimal,
    cost_model: CostModel | None = None,
    schema: str = "public",
) -> WalletService:
    """Wire paper-only dependencies without starting a loop or reading an environment."""
    injected_costs = PaperCostModel() if cost_model is None else cost_model
    return WalletService(
        wallet_id,
        queue,
        PaperBroker(injected_costs),
        PostgresWalletRepository(connection, schema=schema),
        policy,
        initial_cash=initial_cash,
    )


def build_signal_db_paper_wallet(
    *,
    wallet_id: str,
    signal_reader: ReadConnection,
    crypto_reader: ReadConnection,
    wallet_reader: ReadConnection,
    wallet_writer: WriteConnection,
    policy: RiskPolicy,
    initial_cash: Decimal,
    cost_model: CostModel | None = None,
    signal_schema: str = "public",
    crypto_schema: str = "public",
    wallet_schema: str = "public",
) -> WalletService:
    """Wire the three read boundaries to the wallet-owned atomic paper ledger."""
    queue = PostgresSignalQueue(
        signal_reader,
        crypto_reader,
        wallet_reader,
        wallet_id=wallet_id,
        signal_schema=signal_schema,
        crypto_schema=crypto_schema,
        wallet_schema=wallet_schema,
    )
    return build_paper_wallet(
        wallet_id=wallet_id,
        queue=queue,
        connection=wallet_writer,
        policy=policy,
        initial_cash=initial_cash,
        cost_model=cost_model,
        schema=wallet_schema,
    )


def run_paper_wallet(
    service: WalletService,
    *,
    poll_interval_seconds: int = 60,
    poll_buffer_seconds: int = 2,
    wall_clock: Callable[[], float] = time.time,
    sleep: Callable[[float], object] | None = None,
    stop_event: Event | None = None,
) -> None:
    """Run and close an injected paper wallet on cooperative process shutdown."""

    configure_logging(logging.INFO)
    runner = WalletPollingRunner(
        service,
        poll_interval_seconds=poll_interval_seconds,
        poll_buffer_seconds=poll_buffer_seconds,
        wall_clock=wall_clock,
        sleep=sleep,
        stop_event=stop_event,
    )
    try:
        _run_with_shutdown_signals(runner)
    finally:
        service.close()


def _run_with_shutdown_signals(runner: WalletPollingRunner) -> None:
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
