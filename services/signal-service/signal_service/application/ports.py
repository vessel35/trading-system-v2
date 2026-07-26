"""Define short-lived signal output boundaries."""

from abc import ABC, abstractmethod
from datetime import datetime

from core_lib.ports import DataFeed
from core_lib.types import Candle

from signal_service.domain import PersistedSignal


class SignalDataFeed(DataFeed):
    """Extend the shared feed with cursor-bounded reads needed by polling."""

    @abstractmethod
    def candles_after(
        self,
        symbol: str,
        tf: str,
        after: datetime,
        up_to: datetime,
    ) -> list[Candle]:
        """Return confirmed candles opening at or after the processed cursor."""


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
