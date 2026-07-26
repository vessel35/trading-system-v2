"""CCXT Binance USD-M REST adapter."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast

import ccxt  # type: ignore[import-untyped]

from collector_service.domain.models import ONE_MINUTE, Candle, FundingRate, Symbol

_PAGE_LIMIT = 1_000
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
logger = logging.getLogger(__name__)


class _SyncCcxtClient(Protocol):
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: int | None,
        limit: int,
    ) -> list[list[object]]:
        """Return normalized CCXT OHLCV rows."""

    def fetch_funding_rate_history(
        self,
        symbol: str,
        since: int | None,
        limit: int | None,
    ) -> list[dict[str, object]]:
        """Return normalized CCXT funding rows with their raw ``info`` payload."""

    def close(self) -> object:
        """Close the synchronous CCXT client."""


class BinanceUsdMClient:
    """Fetch only the public Binance perpetual-futures 1m kline path."""

    def __init__(
        self,
        exchange: _SyncCcxtClient,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._exchange = exchange
        self._clock = clock
        self._rest_lock = asyncio.Lock()

    @classmethod
    def create(
        cls,
        *,
        api_key: str = "",
        api_secret: str = "",
    ) -> BinanceUsdMClient:
        """Construct ccxt.binanceusdm without making a network request."""

        exchange_type = ccxt.binanceusdm
        exchange = exchange_type(
            {
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
            }
        )
        return cls(cast(_SyncCcxtClient, exchange))

    async def fetch_completed_candles(
        self,
        symbol: Symbol,
        *,
        timeframe: str,
        limit: int,
    ) -> list[Candle]:
        """Fetch 2-3 rows and exclude the final, potentially in-progress row."""

        if timeframe != "1m":
            raise ValueError("Binance collector may request only 1m candles")
        if limit not in {2, 3}:
            raise ValueError("Binance collector fetch limit must be 2 or 3")

        async with self._rest_lock:
            ohlcv_list = await asyncio.to_thread(
                self._exchange.fetch_ohlcv,
                symbol.value,
                timeframe,
                None,
                limit,
            )

        completed = ohlcv_list[:-1]
        return [self._to_candle(symbol, timeframe, row) for row in completed]

    async def fetch_ohlcv_page(
        self,
        symbol: Symbol,
        *,
        timeframe: str,
        since: datetime,
        limit: int,
    ) -> list[Candle]:
        """Fetch one 1000-row historical page and discard any still-open bucket."""

        if timeframe != "1m":
            raise ValueError("Binance backfill may request only 1m candles")
        if limit != _PAGE_LIMIT:
            raise ValueError("Binance backfill page limit must be 1000")
        since_ms = self._timestamp_ms(since, name="since")

        async with self._rest_lock:
            ohlcv_list = await asyncio.to_thread(
                self._exchange.fetch_ohlcv,
                symbol.value,
                timeframe,
                since_ms,
                limit,
            )

        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("exchange clock must be timezone-aware")
        completed_before = now.astimezone(UTC)
        candles = [self._to_candle(symbol, timeframe, row) for row in ohlcv_list]
        return [candle for candle in candles if candle.open_time + ONE_MINUTE <= completed_before]

    async def fetch_funding_rate_page(
        self,
        symbol: Symbol,
        *,
        since: datetime,
        limit: int,
    ) -> list[FundingRate]:
        """Fetch one funding-history page, preserving raw decimal strings."""

        if limit != _PAGE_LIMIT:
            raise ValueError("Binance funding page limit must be 1000")
        since_ms = self._timestamp_ms(since, name="since")

        async with self._rest_lock:
            history = await asyncio.to_thread(
                self._exchange.fetch_funding_rate_history,
                symbol.value,
                since_ms,
                limit,
            )
        return [self._to_funding_rate(symbol, row) for row in history]

    async def close(self) -> None:
        """Close the sync client without blocking the event loop."""

        await asyncio.to_thread(self._exchange.close)

    @staticmethod
    def _to_candle(symbol: Symbol, timeframe: str, row: list[object]) -> Candle:
        if len(row) < 6:
            raise ValueError("CCXT OHLCV row must contain timestamp and five values")
        try:
            timestamp_ms = int(str(row[0]))
            values = [Decimal(str(value)) for value in row[1:6]]
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("CCXT OHLCV row contains an invalid numeric value") from exc
        open_time = _EPOCH + timedelta(milliseconds=timestamp_ms)
        return Candle(
            symbol=symbol.value,
            exchange=symbol.exchange,
            timeframe=timeframe,
            open_time=open_time,
            open=values[0],
            high=values[1],
            low=values[2],
            close=values[3],
            volume=values[4],
        )

    @staticmethod
    def _to_funding_rate(
        symbol: Symbol,
        row: Mapping[str, object],
    ) -> FundingRate:
        info_value = row.get("info")
        info = info_value if isinstance(info_value, Mapping) else {}
        timestamp_value = info.get("fundingTime", row.get("timestamp"))
        rate_value = info.get("fundingRate", row.get("fundingRate"))
        mark_value = info.get("markPrice", row.get("markPrice"))
        try:
            timestamp_ms = int(str(timestamp_value))
            funding_rate = Decimal(str(rate_value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("CCXT funding row contains an invalid numeric value") from exc
        mark_price = BinanceUsdMClient._optional_mark_price(
            symbol=symbol,
            timestamp_ms=timestamp_ms,
            value=mark_value,
        )
        return FundingRate(
            symbol=symbol.value,
            exchange=symbol.exchange,
            time=_EPOCH + timedelta(milliseconds=timestamp_ms),
            funding_rate=funding_rate,
            mark_price=mark_price,
        )

    @staticmethod
    def _optional_mark_price(
        *,
        symbol: Symbol,
        timestamp_ms: int,
        value: object,
    ) -> Decimal | None:
        if value is None:
            return None
        try:
            mark_price = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            logger.warning(
                "funding_mark_price_dropped symbol=%s exchange=%s funding_time_ms=%d "
                "reason=parse_error",
                symbol.value,
                symbol.exchange,
                timestamp_ms,
            )
            return None
        if not mark_price.is_finite() or mark_price <= 0:
            logger.warning(
                "funding_mark_price_dropped symbol=%s exchange=%s funding_time_ms=%d "
                "reason=non_positive_or_non_finite",
                symbol.value,
                symbol.exchange,
                timestamp_ms,
            )
            return None
        return mark_price

    @staticmethod
    def _timestamp_ms(value: datetime, *, name: str) -> int:
        if value.tzinfo is None:
            raise ValueError(f"{name} must be timezone-aware")
        elapsed = value.astimezone(UTC) - _EPOCH
        return elapsed.days * 86_400_000 + elapsed.seconds * 1_000 + elapsed.microseconds // 1_000
