"""CCXT Binance USD-M REST adapter."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast

import ccxt  # type: ignore[import-untyped]

from collector_service.domain.models import Candle, Symbol


class _SyncCcxtClient(Protocol):
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: int | None,
        limit: int,
    ) -> list[list[object]]:
        """Return normalized CCXT OHLCV rows."""

    def close(self) -> object:
        """Close the synchronous CCXT client."""


class BinanceUsdMClient:
    """Fetch only the public Binance perpetual-futures 1m kline path."""

    def __init__(self, exchange: _SyncCcxtClient) -> None:
        self._exchange = exchange
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
        open_time = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
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
