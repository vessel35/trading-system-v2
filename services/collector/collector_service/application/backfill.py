"""Bounded historical OHLCV and funding ingestion use cases."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from collector_service.domain.models import (
    ONE_MINUTE,
    Candle,
    FundingRate,
    Symbol,
    require_strictly_increasing,
)
from collector_service.domain.ports import (
    CandleRepository,
    FundingExchangeClient,
    FundingRepository,
    HistoricalExchangeClient,
    SymbolRepository,
)

from .service import CollectorConfigurationError

logger = logging.getLogger(__name__)

PAGE_LIMIT = 1_000
ONE_MILLISECOND = timedelta(milliseconds=1)


@dataclass(frozen=True, slots=True)
class BackfillResult:
    """Progress summary for one bounded OHLCV backfill."""

    page_count: int
    fetched_count: int
    persisted_count: int


@dataclass(frozen=True, slots=True)
class FundingBackfillResult:
    """Progress summary for one bounded funding-history backfill."""

    page_count: int
    fetched_count: int
    persisted_count: int


class _SingleSymbolUseCase:
    def __init__(
        self,
        *,
        symbols: SymbolRepository,
        exchange_name: str,
        symbol_selector: str | None,
    ) -> None:
        self._symbols = symbols
        self._exchange_name = exchange_name
        self._symbol_selector = symbol_selector

    async def load_symbol(self) -> Symbol:
        configured = await asyncio.to_thread(
            self._symbols.active_symbols,
            exchange=self._exchange_name,
            symbol=self._symbol_selector,
        )
        if len(configured) != 1:
            raise CollectorConfigurationError(
                "backfill requires exactly one active Binance futures symbol; "
                f"config_db returned {len(configured)}"
            )
        return configured[0]


class HistoricalBackfill(_SingleSymbolUseCase):
    """Page confirmed Binance 1m futures candles into ``ohlcv_futures``."""

    def __init__(
        self,
        *,
        symbols: SymbolRepository,
        exchange: HistoricalExchangeClient,
        candles: CandleRepository,
        exchange_name: str = "binance",
        symbol_selector: str | None = None,
        timeframe: str = "1m",
    ) -> None:
        super().__init__(
            symbols=symbols,
            exchange_name=exchange_name,
            symbol_selector=symbol_selector,
        )
        if timeframe != "1m":
            raise ValueError("historical backfill supports only 1m ingestion")
        self._exchange = exchange
        self._candles = candles
        self._timeframe = timeframe

    async def run(self, *, start: datetime, end: datetime) -> BackfillResult:
        """Upsert the half-open range ``[start, end)`` in 1000-candle pages."""

        start, end = _validated_range(start, end)
        if not _minute_aligned(start) or not _minute_aligned(end):
            raise ValueError("OHLCV backfill range must align to UTC minute boundaries")
        symbol = await self.load_symbol()
        cursor = start
        page_count = 0
        fetched_count = 0
        persisted_count = 0

        while cursor < end:
            page = await self._exchange.fetch_ohlcv_page(
                symbol,
                timeframe=self._timeframe,
                since=cursor,
                limit=PAGE_LIMIT,
            )
            self._validate_page(symbol, cursor, page)
            if not page:
                break

            page_count += 1
            fetched_count += len(page)
            in_range = [candle for candle in page if start <= candle.open_time < end]
            if in_range:
                await asyncio.to_thread(self._candles.upsert_batch, in_range)
                persisted_count += len(in_range)

            next_cursor = page[-1].open_time + ONE_MINUTE
            if next_cursor <= cursor:
                raise ValueError("OHLCV backfill page did not advance the since cursor")
            logger.info(
                "ohlcv_backfill_progress symbol=%s exchange=%s page=%d "
                "fetched=%d persisted=%d next_since=%s",
                symbol.value,
                symbol.exchange,
                page_count,
                fetched_count,
                persisted_count,
                next_cursor.isoformat(),
            )
            cursor = next_cursor

        logger.info(
            "ohlcv_backfill_completed symbol=%s exchange=%s start=%s end=%s "
            "pages=%d fetched=%d persisted=%d",
            symbol.value,
            symbol.exchange,
            start.isoformat(),
            end.isoformat(),
            page_count,
            fetched_count,
            persisted_count,
        )
        return BackfillResult(
            page_count=page_count,
            fetched_count=fetched_count,
            persisted_count=persisted_count,
        )

    def _validate_page(
        self,
        symbol: Symbol,
        cursor: datetime,
        page: list[Candle],
    ) -> None:
        require_strictly_increasing(page)
        for candle in page:
            if (
                candle.symbol != symbol.value
                or candle.exchange != symbol.exchange
                or candle.timeframe != self._timeframe
            ):
                raise ValueError("exchange response crossed the configured candle series")
            if candle.open_time < cursor:
                raise ValueError("OHLCV backfill page contains a row before since")


class FundingBackfill(_SingleSymbolUseCase):
    """Page observed settlements into ``funding_rates`` without interpolation."""

    def __init__(
        self,
        *,
        symbols: SymbolRepository,
        exchange: FundingExchangeClient,
        funding: FundingRepository,
        exchange_name: str = "binance",
        symbol_selector: str | None = None,
    ) -> None:
        super().__init__(
            symbols=symbols,
            exchange_name=exchange_name,
            symbol_selector=symbol_selector,
        )
        self._exchange = exchange
        self._funding = funding

    async def run(self, *, start: datetime, end: datetime) -> FundingBackfillResult:
        """Upsert the half-open range ``[start, end)`` without filling missing rows."""

        start, end = _validated_range(start, end)
        symbol = await self.load_symbol()
        cursor = start
        page_count = 0
        fetched_count = 0
        persisted_count = 0

        while cursor < end:
            page = await self._exchange.fetch_funding_rate_page(
                symbol,
                since=cursor,
                limit=PAGE_LIMIT,
            )
            self._validate_page(symbol, cursor, page)
            if not page:
                break

            page_count += 1
            fetched_count += len(page)
            in_range = [rate for rate in page if start <= rate.time < end]
            if in_range:
                await asyncio.to_thread(self._funding.upsert_batch, in_range)
                persisted_count += len(in_range)

            next_cursor = page[-1].time + ONE_MILLISECOND
            if next_cursor <= cursor:
                raise ValueError("funding backfill page did not advance the since cursor")
            logger.info(
                "funding_backfill_progress symbol=%s exchange=%s page=%d "
                "fetched=%d persisted=%d next_since=%s",
                symbol.value,
                symbol.exchange,
                page_count,
                fetched_count,
                persisted_count,
                next_cursor.isoformat(),
            )
            cursor = next_cursor

        logger.info(
            "funding_backfill_completed symbol=%s exchange=%s start=%s end=%s "
            "pages=%d fetched=%d persisted=%d",
            symbol.value,
            symbol.exchange,
            start.isoformat(),
            end.isoformat(),
            page_count,
            fetched_count,
            persisted_count,
        )
        return FundingBackfillResult(
            page_count=page_count,
            fetched_count=fetched_count,
            persisted_count=persisted_count,
        )

    @staticmethod
    def _validate_page(
        symbol: Symbol,
        cursor: datetime,
        page: list[FundingRate],
    ) -> None:
        for previous, current in zip(page, page[1:], strict=False):
            if current.time <= previous.time:
                raise ValueError("funding times must be strictly increasing")
        for rate in page:
            if rate.symbol != symbol.value or rate.exchange != symbol.exchange:
                raise ValueError("exchange response crossed the configured funding series")
            if rate.time < cursor:
                raise ValueError("funding backfill page contains a row before since")


def _validated_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("range must be timezone-aware")
    normalized_start = start.astimezone(UTC)
    normalized_end = end.astimezone(UTC)
    if normalized_start >= normalized_end:
        raise ValueError("start must precede end")
    return normalized_start, normalized_end


def _minute_aligned(value: datetime) -> bool:
    return value.second == 0 and value.microsecond == 0
