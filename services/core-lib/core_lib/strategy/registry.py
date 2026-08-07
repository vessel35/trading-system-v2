"""Define in-process Adaptee registration and lookup rules."""

from .base import StrategyAdapter

AdapterClass = type[StrategyAdapter]


class InProcessStrategyRegistry:
    """Map stable strategy ids to already-imported Adaptee classes."""

    def __init__(self) -> None:
        self._adaptees: dict[str, AdapterClass] = {}

    def register(self, strategy_id: str, adaptee_class: AdapterClass) -> None:
        """Register one class without importing modules or touching a database."""
        if not strategy_id:
            raise ValueError("strategy_id must not be empty")
        if strategy_id in self._adaptees:
            raise ValueError(f"strategy is already registered in-process: {strategy_id}")
        adaptee_class.get_metadata()
        adaptee_class.get_parameter_schema()
        self._adaptees[strategy_id] = adaptee_class

    def get(self, strategy_id: str) -> AdapterClass:
        """Return the exact registered Adaptee class."""
        try:
            return self._adaptees[strategy_id]
        except KeyError as error:
            raise KeyError(f"strategy is not registered in-process: {strategy_id}") from error

    def list(self) -> list[str]:
        """Return stable strategy ids in deterministic order."""
        return sorted(self._adaptees)

    def unregister(self, strategy_id: str) -> None:
        """Remove a plugin registration, primarily for controlled lifecycle teardown."""
        try:
            del self._adaptees[strategy_id]
        except KeyError as error:
            raise KeyError(f"strategy is not registered in-process: {strategy_id}") from error
