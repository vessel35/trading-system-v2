"""Validate the small environment-independent signal generation configuration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from core_lib.types import MarketType

from signal_service.domain import SignalMode


@dataclass(frozen=True, slots=True)
class SignalGenerationConfig:
    """Describe one in-memory strategy session without carrying credentials."""

    strategy_id: str
    symbol: str
    timeframe: str
    market_type: MarketType
    mode: SignalMode = SignalMode.PAPER
    params: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (
            ("strategy_id", self.strategy_id),
            ("symbol", self.symbol),
            ("timeframe", self.timeframe),
        ):
            if not value:
                raise ValueError(f"{name} must not be empty")
        object.__setattr__(self, "market_type", MarketType(self.market_type))
        object.__setattr__(self, "mode", SignalMode(self.mode))
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))
