"""Define external Adaptee catalog registration and lookup operations."""

from abc import ABC, abstractmethod


class StrategyRegistry(ABC):
    """Access an injected external Adaptee implementation catalog."""

    @abstractmethod
    def get(self, strategy_id: str) -> dict[str, object]:
        """Return one catalog entry by strategy id."""

    @abstractmethod
    def list(self) -> list[dict[str, object]]:
        """Return all catalog entries."""

    @abstractmethod
    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        """Register one strategy implementation entry."""
