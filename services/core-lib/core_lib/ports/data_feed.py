"""Define the candle, funding, and mark-price DataFeed port."""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

from core_lib.types import Candle


class DataFeed(ABC):
    """Supply market facts without exposing data after the requested boundary."""

    @abstractmethod
    def candles(self, symbol: str, tf: str, up_to: datetime) -> list[Candle]:
        """Return only confirmed candles whose close time is at most ``up_to``."""

    @abstractmethod
    def funding(self, symbol: str, at: datetime) -> Decimal:
        """Return the observed funding rate available at ``at``."""

    @abstractmethod
    def mark_price(self, symbol: str, at: datetime) -> Decimal:
        """Return the mark price available at ``at``."""
