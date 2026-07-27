"""Dependency-inversion ports for the collector use case."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .models import Candle, FundingRate, Symbol


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


class HistoricalExchangeClient(Protocol):
    """Fetch bounded pages of confirmed historical futures candles."""

    async def fetch_ohlcv_page(
        self,
        symbol: Symbol,
        *,
        timeframe: str,
        since: datetime,
        limit: int,
    ) -> list[Candle]:
        """Return one ascending page from ``since``, excluding open candles."""


class FundingExchangeClient(Protocol):
    """Fetch observed funding settlements without numeric normalization."""

    async def fetch_funding_rate_page(
        self,
        symbol: Symbol,
        *,
        since: datetime,
        limit: int,
    ) -> list[FundingRate]:
        """Return one ascending funding-history page from ``since``."""


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


class FundingRepository(Protocol):
    """Persist observed funding rates with their source precision."""

    def upsert_batch(self, rates: list[FundingRate]) -> None:
        """Insert or update every supplied settlement."""


class AggregateRefreshRepository(Protocol):
    """Refresh bounded continuous-aggregate materialization ranges."""

    def refresh_range(
        self,
        view_name: str,
        start: datetime,
        end: datetime,
    ) -> None:
        """Materialize one aggregate view over the supplied range."""


class SymbolRepository(Protocol):
    """Read the collection target from config_db."""

    def active_symbols(
        self,
        *,
        exchange: str,
        symbol: str | None,
    ) -> list[Symbol]:
        """Return at most two rows so the application can enforce singularity."""
