"""Orchestrate one strictly monotonic confirmed-candle series."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from collector_service.domain.models import (
    Candle,
    CandleGap,
    Symbol,
    detect_gaps,
    require_strictly_increasing,
)
from collector_service.domain.ports import (
    CandleRepository,
    ExchangeClient,
    SymbolRepository,
)

logger = logging.getLogger(__name__)


class CollectorConfigurationError(RuntimeError):
    """The config database did not identify exactly one collection target."""


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Observable facts from one REST poll."""

    fetched_completed_count: int
    persisted_count: int
    stale_count: int
    gaps: tuple[CandleGap, ...]


def seconds_until_next_poll(
    now: float,
    *,
    poll_interval_seconds: int = 60,
    poll_buffer_seconds: int = 2,
) -> float:
    """Align polling to each wall-clock minute boundary plus the close buffer."""

    if poll_interval_seconds <= 0:
        raise ValueError("poll interval must be positive")
    if not 0 <= poll_buffer_seconds < poll_interval_seconds:
        raise ValueError("poll buffer must be within the polling interval")
    seconds_into_period = now % poll_interval_seconds
    if seconds_into_period < poll_buffer_seconds:
        return poll_buffer_seconds - seconds_into_period
    return poll_interval_seconds - seconds_into_period + poll_buffer_seconds


class LiveCollector:
    """Load one config-driven futures symbol and persist its confirmed 1m candles."""

    def __init__(
        self,
        *,
        symbols: SymbolRepository,
        exchange: ExchangeClient,
        candles: CandleRepository,
        exchange_name: str = "binance",
        symbol_selector: str | None = None,
        timeframe: str = "1m",
        fetch_limit: int = 3,
        poll_interval_seconds: int = 60,
        poll_buffer_seconds: int = 2,
        wall_clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if timeframe != "1m":
            raise ValueError("live collector supports only 1m ingestion")
        if fetch_limit not in {2, 3}:
            raise ValueError("fetch_limit must be 2 or 3")
        self._symbols = symbols
        self._exchange = exchange
        self._candles = candles
        self._exchange_name = exchange_name
        self._symbol_selector = symbol_selector
        self._timeframe = timeframe
        self._fetch_limit = fetch_limit
        self._poll_interval_seconds = poll_interval_seconds
        self._poll_buffer_seconds = poll_buffer_seconds
        self._wall_clock = wall_clock
        self._sleep = sleep
        self._ingestion_lock = asyncio.Lock()

    async def load_symbol(self) -> Symbol:
        """Read, rather than seed, the single active Binance target."""

        configured = await asyncio.to_thread(
            self._symbols.active_symbols,
            exchange=self._exchange_name,
            symbol=self._symbol_selector,
        )
        if len(configured) != 1:
            raise CollectorConfigurationError(
                "collector requires exactly one active Binance futures symbol; "
                f"config_db returned {len(configured)}"
            )
        return configured[0]

    async def collect_once(self, symbol: Symbol) -> IngestionResult:
        """Fetch, validate, gap-check, and upsert every newly confirmed candle."""

        async with self._ingestion_lock:
            completed = await self._exchange.fetch_completed_candles(
                symbol,
                timeframe=self._timeframe,
                limit=self._fetch_limit,
            )
            self._validate_series_identity(symbol, completed)
            require_strictly_increasing(completed)

            latest = await asyncio.to_thread(
                self._candles.latest_open_time,
                symbol.value,
                symbol.exchange,
                self._timeframe,
            )
            new_candles = [
                candle for candle in completed if latest is None or candle.open_time > latest
            ]
            gaps = detect_gaps(latest, new_candles)
            for gap in gaps:
                logger.warning(
                    "ohlcv_gap symbol=%s exchange=%s expected=%s observed=%s missing=%d",
                    symbol.value,
                    symbol.exchange,
                    gap.expected_open_time.isoformat(),
                    gap.observed_open_time.isoformat(),
                    gap.missing_candles,
                )

            if new_candles:
                await asyncio.to_thread(self._candles.upsert_batch, new_candles)
                logger.info(
                    "persisted_confirmed_ohlcv symbol=%s exchange=%s timeframe=1m rows=%d",
                    symbol.value,
                    symbol.exchange,
                    len(new_candles),
                )
            return IngestionResult(
                fetched_completed_count=len(completed),
                persisted_count=len(new_candles),
                stale_count=len(completed) - len(new_candles),
                gaps=gaps,
            )

    async def run(self) -> None:
        """Poll forever at minute boundary +2s; cancellation remains cooperative."""

        symbol = await self.load_symbol()
        logger.info(
            "collector_started symbol=%s exchange=%s timeframe=1m",
            symbol.value,
            symbol.exchange,
        )
        while True:
            delay = seconds_until_next_poll(
                self._wall_clock(),
                poll_interval_seconds=self._poll_interval_seconds,
                poll_buffer_seconds=self._poll_buffer_seconds,
            )
            await self._sleep(delay)
            try:
                await self.collect_once(symbol)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "collector_poll_failed symbol=%s exchange=%s",
                    symbol.value,
                    symbol.exchange,
                )

    def _validate_series_identity(
        self,
        symbol: Symbol,
        candles: list[Candle],
    ) -> None:
        for candle in candles:
            if (
                candle.symbol != symbol.value
                or candle.exchange != symbol.exchange
                or candle.timeframe != self._timeframe
            ):
                raise ValueError("exchange response crossed the configured candle series")
