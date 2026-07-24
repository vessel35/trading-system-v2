"""Define the injected fee, slippage, funding, and liquidation CostModel port."""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

from core_lib.types import Order


class CostModel(ABC):
    """Inject cost values while leaving all cost formulas in ``core_lib.costs``."""

    @abstractmethod
    def fee(self, symbol: str, notional: Decimal) -> Decimal:
        """Return the applicable maker/taker fee rate."""

    @abstractmethod
    def slippage(self, order: Order, context: dict[str, object]) -> Decimal:
        """Return the effective adverse rate computed by the shared cost formula."""

    @abstractmethod
    def funding_rate(self, at: datetime) -> Decimal:
        """Return the configured fallback funding rate."""

    @abstractmethod
    def liq_params(self) -> dict[str, object]:
        """Return liquidation values such as the maintenance-margin rate."""
