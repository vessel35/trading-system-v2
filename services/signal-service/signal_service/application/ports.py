"""Define short-lived signal output boundaries."""

from abc import ABC, abstractmethod

from signal_service.domain import PersistedSignal


class SignalSink(ABC):
    """Persist signals owned by this service without exposing a database."""

    @abstractmethod
    def store(self, signal: PersistedSignal) -> bool:
        """Store one signal, returning false when idempotency rejected a duplicate."""


class SignalQueue(ABC):
    """Reserved wallet-service queue boundary; no transport exists in this slice."""

    @abstractmethod
    def publish(self, signal: PersistedSignal) -> None:
        """Publish one already-persisted signal to the future wallet-service queue."""
