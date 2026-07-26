"""Dependency-inversion ports for the collector use case."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .models import Candle, Symbol


class ExchangeClient(Protocol):
    """Fetch confirmed exchange candles without exposing CCXT to the application."""

    async def fetch_completed_candles(
        self,
        symbol: Symbol,
        *,
        timeframe: str,
        limit: int,
    ) -> list[Candle]:
        """Return the completed prefix of a recent OHLCV response."""

    async def close(self) -> None:
        """Release the underlying exchange client."""


class CandleRepository(Protocol):
    """Persist futures candles with a database-enforced idempotent key."""

    def latest_open_time(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
    ) -> datetime | None:
        """Return the latest persisted bucket for one series."""

    def upsert_batch(self, candles: list[Candle]) -> None:
        """Insert or update every supplied confirmed candle."""


class SymbolRepository(Protocol):
    """Read the collection target from config_db."""

    def active_symbols(
        self,
        *,
        exchange: str,
        symbol: str | None,
    ) -> list[Symbol]:
        """Return at most two rows so the application can enforce singularity."""
