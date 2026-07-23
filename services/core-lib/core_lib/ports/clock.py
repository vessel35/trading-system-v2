"""Define the deterministic Clock port."""

from abc import ABC, abstractmethod
from datetime import datetime


class Clock(ABC):
    """Expose simulation time without consulting wall-clock time."""

    @abstractmethod
    def now(self) -> datetime:
        """Return the current simulation timestamp."""

    @abstractmethod
    def advance(self) -> None:
        """Advance to the next simulation timestamp."""
