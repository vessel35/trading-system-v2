"""Define the record and finalize EvidenceSink port."""

from abc import ABC, abstractmethod


class EvidenceSink(ABC):
    """Persist run evidence and produce a deterministic normalized hash."""

    @abstractmethod
    def record(self, entity: object) -> None:
        """Record one time-scoped evidence entity."""

    @abstractmethod
    def finalize(self, run_id: str) -> str:
        """Finalize a run and return its normalized evidence hash."""
