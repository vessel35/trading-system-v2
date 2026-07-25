"""Define preregistration, run registration, and summary CatalogStore operations."""

from abc import ABC, abstractmethod


class CatalogStore(ABC):
    """Persist preregistration and lightweight backtest run metadata."""

    @abstractmethod
    def save_prereg(self, prereg: object) -> None:
        """Persist and lock a preregistration before the first decision."""

    @abstractmethod
    def register(self, run: object) -> str:
        """Register a run and return the catalog-issued run id."""

    @abstractmethod
    def upsert_summary(self, summary: object) -> None:
        """Insert or update one run summary."""

    @abstractmethod
    def record_harness_aggregate(
        self,
        run_id: str,
        *,
        oos_degradation: float | None,
        psr: float | None,
        harness_json: object,
    ) -> None:
        """Stamp cross-run overfitting aggregates onto one representative run summary."""
