"""Define short-lived queue and wallet_db application boundaries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from core_lib.ports import CostModel
from core_lib.types import Candle, Fill, Order, OrderRequest

from wallet_service.domain import PaperSignal, SignalConsumptionStatus, WalletExecution


class SignalQueue(ABC):
    """Supply already-derived paper signals without prescribing a transport."""

    @abstractmethod
    def receive(self) -> PaperSignal | None:
        """Return the next paper signal, or no work."""

    def close(self) -> None:
        """Release queue-owned source connections, if any."""
        return None


class WalletRepository(ABC):
    """Commit or roll back wallet-owned execution facts atomically."""

    @abstractmethod
    def store(self, execution: WalletExecution) -> bool:
        """Persist one signal transaction, returning false for an idempotent replay."""

    @abstractmethod
    def record_consumption(
        self,
        wallet_id: str,
        signal_id: str,
        status: SignalConsumptionStatus,
        consumed_at: datetime,
    ) -> bool:
        """Persist a terminal non-fill receipt without creating ledger facts."""


class PaperExecutionBroker(Protocol):
    """Extend the shared Broker port with deterministic paper candle context."""

    @property
    def cost_model(self) -> CostModel:
        """Expose injected cost values for shared liquidation calculation."""

    def configure_execution(
        self,
        decision_candle: Candle,
        execution_candle: Candle,
        *,
        wallet_id: str,
        signal_id: str,
        equity: Decimal,
        available_margin: Decimal,
        leverage: int,
        risk_fraction: float | None,
    ) -> None:
        """Bind the explicit paper context used by the next submit."""

    def submit(self, request: OrderRequest) -> Fill:
        """Normalize and simulate one paper fill."""

    def open_orders(self) -> list[Order]:
        """Return active normalized paper orders."""

    def cancel(self, order_id: str) -> None:
        """Cancel an active normalized paper order."""
