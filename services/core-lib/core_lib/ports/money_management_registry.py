"""Define read-only access to the external money-management policy catalog."""

from abc import ABC, abstractmethod


class MoneyManagementRegistry(ABC):
    """Read policy registrations without exposing writes in this read-only preset.

    Unlike the legacy strategy port, this port omits ``register`` because operators
    apply the catalog SQL and no running service owns registry mutation.
    """

    @abstractmethod
    def get(self, mode: str) -> dict[str, object]:
        """Return one policy catalog entry by mode."""

    @abstractmethod
    def list(self) -> list[dict[str, object]] | None:
        """Return registrations, or ``None`` while the catalog table is absent."""
