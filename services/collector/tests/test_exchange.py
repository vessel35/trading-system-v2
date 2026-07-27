"""The CCXT boundary drops the in-progress row and preserves decimals."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from collector_service.domain import Symbol
from collector_service.infrastructure.exchange import BinanceUsdMClient


class FakeCcxt:
    def __init__(
        self,
        rows: list[list[object]],
        funding_rows: list[dict[str, object]] | None = None,
    ) -> None:
        self.rows = rows
        self.funding_rows = funding_rows or []
        self.calls: list[tuple[str, str, int | None, int]] = []
        self.funding_calls: list[tuple[str, int | None, int | None]] = []
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

    def fetch_funding_rate_history(
        self,
        symbol: str,
        since: int | None,
        limit: int | None,
    ) -> list[dict[str, object]]:
        self.funding_calls.append((symbol, since, limit))
        return self.funding_rows

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


def test_historical_page_uses_since_1000_and_drops_only_an_open_candle() -> None:
    since = datetime(2025, 7, 21, 0, 0, tzinfo=UTC)
    since_ms = int(since.timestamp() * 1_000)
    fake = FakeCcxt(
        [
            [since_ms, "1", "2", "0.5", "1.5", "10"],
            [since_ms + 60_000, "1.5", "2", "1", "1.75", "11"],
            [since_ms + 120_000, "1.75", "2", "1", "1.8", "12"],
        ]
    )
    client = BinanceUsdMClient(
        fake,
        clock=lambda: datetime(2025, 7, 21, 0, 2, 30, tzinfo=UTC),
    )

    candles = asyncio.run(
        client.fetch_ohlcv_page(
            Symbol("ETH/USDT:USDT", "binance"),
            timeframe="1m",
            since=since,
            limit=1_000,
        )
    )

    assert [item.open_time for item in candles] == [
        since,
        datetime(2025, 7, 21, 0, 1, tzinfo=UTC),
    ]
    assert fake.calls == [("ETH/USDT:USDT", "1m", since_ms, 1_000)]


def test_historical_page_keeps_the_last_row_when_its_minute_is_closed() -> None:
    since = datetime(2025, 7, 21, 0, 0, tzinfo=UTC)
    since_ms = int(since.timestamp() * 1_000)
    client = BinanceUsdMClient(
        FakeCcxt(
            [
                [since_ms, "1", "2", "0.5", "1.5", "10"],
                [since_ms + 60_000, "1.5", "2", "1", "1.75", "11"],
            ]
        ),
        clock=lambda: datetime(2025, 7, 21, 0, 2, tzinfo=UTC),
    )

    candles = asyncio.run(
        client.fetch_ohlcv_page(
            Symbol("ETH/USDT:USDT", "binance"),
            timeframe="1m",
            since=since,
            limit=1_000,
        )
    )

    assert [item.open_time for item in candles] == [
        since,
        datetime(2025, 7, 21, 0, 1, tzinfo=UTC),
    ]


def test_funding_page_preserves_raw_rate_precision_and_optional_mark_price() -> None:
    since = datetime(2025, 7, 21, 0, 0, tzinfo=UTC)
    since_ms = int(since.timestamp() * 1_000)
    fake = FakeCcxt(
        [],
        funding_rows=[
            {
                "timestamp": since_ms,
                "fundingRate": 0.0000875001,
                "info": {
                    "fundingTime": str(since_ms),
                    "fundingRate": "0.0000875001",
                    "markPrice": "3765.12345678",
                },
            },
            {
                "timestamp": since_ms + 28_800_000,
                "fundingRate": -0.0000000001,
                "info": {
                    "fundingTime": str(since_ms + 28_800_000),
                    "fundingRate": "-0.0000000001",
                },
            },
        ],
    )
    client = BinanceUsdMClient(fake)

    rates = asyncio.run(
        client.fetch_funding_rate_page(
            Symbol("ETH/USDT:USDT", "binance"),
            since=since,
            limit=1_000,
        )
    )

    assert rates[0].funding_rate == Decimal("0.0000875001")
    assert rates[0].mark_price == Decimal("3765.12345678")
    assert rates[1].funding_rate == Decimal("-0.0000000001")
    assert rates[1].mark_price is None
    assert fake.funding_calls == [("ETH/USDT:USDT", since_ms, 1_000)]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fundingTime", "not-a-timestamp"),
        ("fundingRate", "not-a-rate"),
    ],
)
def test_invalid_required_funding_fields_still_fail(field: str, value: str) -> None:
    since = datetime(2025, 7, 21, 0, 0, tzinfo=UTC)
    info = {
        "fundingTime": str(int(since.timestamp() * 1_000)),
        "fundingRate": "0.0000875001",
        "markPrice": "",
    }
    info[field] = value
    client = BinanceUsdMClient(FakeCcxt([], funding_rows=[{"info": info}]))

    with pytest.raises(ValueError, match="invalid numeric value"):
        asyncio.run(
            client.fetch_funding_rate_page(
                Symbol("ETH/USDT:USDT", "binance"),
                since=since,
                limit=1_000,
            )
        )


def test_exchange_adapter_rejects_non_1m_or_large_fetches() -> None:
    client = BinanceUsdMClient(FakeCcxt([]))
    symbol = Symbol("ETH/USDT:USDT", "binance")
    with pytest.raises(ValueError, match="only 1m"):
        asyncio.run(client.fetch_completed_candles(symbol, timeframe="5m", limit=3))
    with pytest.raises(ValueError, match="2 or 3"):
        asyncio.run(client.fetch_completed_candles(symbol, timeframe="1m", limit=100))
    with pytest.raises(ValueError, match="1000"):
        asyncio.run(
            client.fetch_ohlcv_page(
                symbol,
                timeframe="1m",
                since=datetime(2025, 7, 21, tzinfo=UTC),
                limit=999,
            )
        )
    with pytest.raises(ValueError, match="1000"):
        asyncio.run(
            client.fetch_funding_rate_page(
                symbol,
                since=datetime(2025, 7, 21, tzinfo=UTC),
                limit=999,
            )
        )


def test_close_releases_only_the_injected_client() -> None:
    fake = FakeCcxt([])
    client = BinanceUsdMClient(fake)
    asyncio.run(client.close())
    assert fake.closed
