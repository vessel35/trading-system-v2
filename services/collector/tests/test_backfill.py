"""Bounded backfill tests with no database or network access."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from collector_service.application import FundingBackfill, HistoricalBackfill
from collector_service.domain import Candle, FundingRate, Symbol
from collector_service.infrastructure.exchange import BinanceUsdMClient

BASE = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
TARGET = Symbol("ETH/USDT:USDT", "binance")


def candle(minute: int) -> Candle:
    return Candle(
        symbol=TARGET.value,
        exchange=TARGET.exchange,
        timeframe="1m",
        open_time=BASE + timedelta(minutes=minute),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100.5"),
        volume=Decimal("10"),
    )


def funding(hour: int, rate: str, mark: str | None = None) -> FundingRate:
    return FundingRate(
        symbol=TARGET.value,
        exchange=TARGET.exchange,
        time=BASE + timedelta(hours=hour),
        funding_rate=Decimal(rate),
        mark_price=None if mark is None else Decimal(mark),
    )


class MemorySymbols:
    def active_symbols(
        self,
        *,
        exchange: str,
        symbol: str | None,
    ) -> list[Symbol]:
        assert exchange == "binance"
        assert symbol is None
        return [TARGET]


class MockHistoricalExchange:
    def __init__(self) -> None:
        self.calls: list[tuple[datetime, int]] = []

    async def fetch_ohlcv_page(
        self,
        symbol: Symbol,
        *,
        timeframe: str,
        since: datetime,
        limit: int,
    ) -> list[Candle]:
        assert symbol == TARGET
        assert timeframe == "1m"
        self.calls.append((since, limit))
        pages = {
            BASE: [candle(0), candle(1)],
            BASE + timedelta(minutes=2): [candle(2), candle(3)],
        }
        return pages.get(since, [])


class MemoryCandles:
    def __init__(self) -> None:
        self.rows: dict[tuple[datetime, str, str, str], Candle] = {}
        self.batch_sizes: list[int] = []

    def latest_open_time(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
    ) -> datetime | None:
        return None

    def upsert_batch(self, candles: list[Candle]) -> None:
        self.batch_sizes.append(len(candles))
        for item in candles:
            self.rows[(item.open_time, item.symbol, item.exchange, item.timeframe)] = item


class MockFundingExchange:
    def __init__(self) -> None:
        self.calls: list[tuple[datetime, int]] = []

    async def fetch_funding_rate_page(
        self,
        symbol: Symbol,
        *,
        since: datetime,
        limit: int,
    ) -> list[FundingRate]:
        assert symbol == TARGET
        self.calls.append((since, limit))
        if since == BASE:
            return [
                funding(0, "0.0000875001", "3500.12345678"),
                funding(16, "-0.0000000001"),
                funding(24, "0.0001000000"),
            ]
        return []


class InvalidMarkCcxt:
    def __init__(self) -> None:
        self.rows = [
            {
                "timestamp": int(BASE.timestamp() * 1_000),
                "info": {
                    "fundingTime": str(int(BASE.timestamp() * 1_000)),
                    "fundingRate": "0.0000875001",
                    "markPrice": "",
                },
            },
            {
                "timestamp": int((BASE + timedelta(hours=8)).timestamp() * 1_000),
                "info": {
                    "fundingTime": str(int((BASE + timedelta(hours=8)).timestamp() * 1_000)),
                    "fundingRate": "-0.0000000001",
                    "markPrice": "0",
                },
            },
        ]

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: int | None,
        limit: int,
    ) -> list[list[object]]:
        return []

    def fetch_funding_rate_history(
        self,
        symbol: str,
        since: int | None,
        limit: int | None,
    ) -> list[dict[str, object]]:
        assert symbol == TARGET.value
        assert since is not None
        assert limit == 1_000
        return [row for row in self.rows if int(str(row["timestamp"])) >= since]

    def close(self) -> object:
        return None


class MemoryFunding:
    def __init__(self) -> None:
        self.rows: dict[tuple[datetime, str, str], FundingRate] = {}
        self.batch_sizes: list[int] = []

    def upsert_batch(self, rates: list[FundingRate]) -> None:
        self.batch_sizes.append(len(rates))
        for item in rates:
            self.rows[(item.time, item.symbol, item.exchange)] = item


def test_ohlcv_range_pages_in_batches_and_replay_is_idempotent() -> None:
    exchange = MockHistoricalExchange()
    repository = MemoryCandles()
    service = HistoricalBackfill(
        symbols=MemorySymbols(),
        exchange=exchange,
        candles=repository,
    )

    first = asyncio.run(
        service.run(
            start=BASE,
            end=BASE + timedelta(minutes=3),
        )
    )
    second = asyncio.run(
        service.run(
            start=BASE,
            end=BASE + timedelta(minutes=3),
        )
    )

    assert first.page_count == 2
    assert first.fetched_count == 4
    assert first.persisted_count == 3
    assert second == first
    assert len(repository.rows) == 3
    assert repository.batch_sizes == [2, 1, 2, 1]
    assert exchange.calls == [
        (BASE, 1_000),
        (BASE + timedelta(minutes=2), 1_000),
        (BASE, 1_000),
        (BASE + timedelta(minutes=2), 1_000),
    ]


def test_funding_range_keeps_precision_and_does_not_fill_missing_boundaries() -> None:
    exchange = MockFundingExchange()
    repository = MemoryFunding()
    service = FundingBackfill(
        symbols=MemorySymbols(),
        exchange=exchange,
        funding=repository,
    )

    result = asyncio.run(
        service.run(
            start=BASE,
            end=BASE + timedelta(hours=24),
        )
    )

    assert result.page_count == 1
    assert result.fetched_count == 3
    assert result.persisted_count == 2
    assert repository.batch_sizes == [2]
    assert set(item.time for item in repository.rows.values()) == {
        BASE,
        BASE + timedelta(hours=16),
    }
    assert repository.rows[(BASE, TARGET.value, TARGET.exchange)].funding_rate == Decimal(
        "0.0000875001"
    )
    assert repository.rows[(BASE, TARGET.value, TARGET.exchange)].mark_price == Decimal(
        "3500.12345678"
    )
    assert exchange.calls == [(BASE, 1_000)]


def test_invalid_marks_become_null_without_blocking_funding_backfill(
    caplog: pytest.LogCaptureFixture,
) -> None:
    repository = MemoryFunding()
    service = FundingBackfill(
        symbols=MemorySymbols(),
        exchange=BinanceUsdMClient(InvalidMarkCcxt()),
        funding=repository,
    )

    with caplog.at_level(logging.WARNING):
        result = asyncio.run(
            service.run(
                start=BASE,
                end=BASE + timedelta(hours=9),
            )
        )

    assert result.persisted_count == 2
    persisted = sorted(repository.rows.values(), key=lambda item: item.time)
    assert [item.funding_rate for item in persisted] == [
        Decimal("0.0000875001"),
        Decimal("-0.0000000001"),
    ]
    assert [item.mark_price for item in persisted] == [None, None]
    assert caplog.text.count("funding_mark_price_dropped") == 2
    assert "reason=parse_error" in caplog.text
    assert "reason=non_positive_or_non_finite" in caplog.text


def test_funding_domain_lowers_nonpositive_decimal_mark_to_none() -> None:
    assert funding(0, "0.0001", "0").mark_price is None
    assert funding(0, "0.0001", "-1").mark_price is None
