"""Assemble the inert paper wallet driver from explicitly injected adapters."""

from decimal import Decimal

from core_lib.ports import CostModel

from wallet_service.application import SignalQueue, WalletService
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
