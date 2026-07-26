"""Assemble the inert paper wallet driver from explicitly injected adapters."""

from decimal import Decimal

from core_lib.ports import CostModel

from wallet_service.application import SignalQueue, WalletService
from wallet_service.core import RiskPolicy
from wallet_service.infrastructure import (
    PaperBroker,
    PaperCostModel,
    PostgresWalletRepository,
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
