"""Define Adaptee construction rules."""

from collections.abc import Callable
from typing import cast

from .base import StrategyAdapter
from .config import ResolvedConfig
from .registry import AdapterClass


class AdapterFactory:
    """Instantiate a registered Adaptee with one immutable ResolvedConfig."""

    @staticmethod
    def create(
        adaptee_class: AdapterClass,
        config: ResolvedConfig,
    ) -> StrategyAdapter:
        """Construct and runtime-check one structural StrategyAdapter."""
        constructor = cast(Callable[[ResolvedConfig], StrategyAdapter], adaptee_class)
        instance = constructor(config)
        if not isinstance(instance, StrategyAdapter):
            raise TypeError("constructed Adaptee does not implement StrategyAdapter")
        return instance
