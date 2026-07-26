"""The CCXT boundary drops the in-progress row and preserves decimals."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from collector_service.domain import Symbol
from collector_service.infrastructure.exchange import BinanceUsdMClient


class FakeCcxt:
    def __init__(self, rows: list[list[object]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, str, int | None, int]] = []
        self.closed = False

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: int | None,
        limit: int,
    ) -> list[list[object]]:
        self.calls.append((symbol, timeframe, since, limit))
        return self.rows

    def close(self) -> object:
        self.closed = True
        return None


def test_fetch_excludes_in_progress_row_and_converts_at_decimal_boundary() -> None:
    fake = FakeCcxt(
        [
            [1_753_056_000_000, 0.1, "0.2", "0.05", "0.15", 10.25],
            [1_753_056_060_000, "0.15", "0.3", "0.1", "0.25", "11.5"],
            [1_753_056_120_000, "999", "999", "999", "999", "999"],
        ]
    )
    client = BinanceUsdMClient(fake)

    candles = asyncio.run(
        client.fetch_completed_candles(
            Symbol("ETH/USDT:USDT", "binance"),
            timeframe="1m",
            limit=3,
        )
    )

    assert len(candles) == 2
    assert candles[0].open == Decimal("0.1")
    assert candles[0].volume == Decimal("10.25")
    assert all(candle.close != Decimal("999") for candle in candles)
    assert fake.calls == [("ETH/USDT:USDT", "1m", None, 3)]


def test_single_in_progress_row_yields_no_completed_candles() -> None:
    client = BinanceUsdMClient(FakeCcxt([[1_753_056_000_000, "1", "1", "1", "1", "1"]]))
    result = asyncio.run(
        client.fetch_completed_candles(
            Symbol("ETH/USDT:USDT", "binance"),
            timeframe="1m",
            limit=2,
        )
    )
    assert result == []


def test_exchange_adapter_rejects_non_1m_or_large_fetches() -> None:
    client = BinanceUsdMClient(FakeCcxt([]))
    symbol = Symbol("ETH/USDT:USDT", "binance")
    with pytest.raises(ValueError, match="only 1m"):
        asyncio.run(client.fetch_completed_candles(symbol, timeframe="5m", limit=3))
    with pytest.raises(ValueError, match="2 or 3"):
        asyncio.run(client.fetch_completed_candles(symbol, timeframe="1m", limit=100))


def test_close_releases_only_the_injected_client() -> None:
    fake = FakeCcxt([])
    client = BinanceUsdMClient(fake)
    asyncio.run(client.close())
    assert fake.closed
