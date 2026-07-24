"""Define the submit, open-order, and cancellation Broker port."""

from abc import ABC, abstractmethod

from core_lib.types import Fill, Order, OrderRequest


class Broker(ABC):
    """Execute normalized orders behind an environment-specific boundary."""

    @abstractmethod
    def submit(self, request: OrderRequest) -> Fill:
        """Submit a float request; implementations must use the shared normalizer."""

    @abstractmethod
    def open_orders(self) -> list[Order]:
        """Return all currently open orders."""

    @abstractmethod
    def cancel(self, order_id: str) -> None:
        """Cancel an open order by id."""
