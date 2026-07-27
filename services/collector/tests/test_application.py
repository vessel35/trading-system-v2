"""Use-case tests with a fully mocked exchange and in-memory repositories."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from collector_service.application import (
    CollectorConfigurationError,
    LiveCollector,
    RunnerHealthSnapshot,
    seconds_until_next_poll,
)
from collector_service.domain import Candle, Symbol

BASE = datetime(2026, 7, 26, 0, 0, tzinfo=UTC)


def candle(minute: int, *, close: str = "100") -> Candle:
    return Candle(
        symbol="ETH/USDT:USDT",
        exchange="binance",
        timeframe="1m",
        open_time=BASE + timedelta(minutes=minute),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal(close),
        volume=Decimal("10"),
    )


class MockExchange:
    def __init__(self, completed: list[Candle]) -> None:
        self.completed = completed
        self.calls: list[tuple[Symbol, str, int]] = []

    async def fetch_completed_candles(
        self,
        symbol: Symbol,
        *,
        timeframe: str,
        limit: int,
    ) -> list[Candle]:
        self.calls.append((symbol, timeframe, limit))
        return list(self.completed)

    async def close(self) -> None:
        return None


class SecretFailingExchange(MockExchange):
    async def fetch_completed_candles(
        self,
        symbol: Symbol,
        *,
        timeframe: str,
        limit: int,
    ) -> list[Candle]:
        del symbol, timeframe, limit
        raise ValueError("postgresql://operator:fake-password@db.example/collector")


class MemoryCandleRepository:
    def __init__(self, latest: datetime | None = None) -> None:
        self.latest = latest
        self.batches: list[list[Candle]] = []

    def latest_open_time(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
    ) -> datetime | None:
        assert (symbol, exchange, timeframe) == ("ETH/USDT:USDT", "binance", "1m")
        return self.latest

    def upsert_batch(self, candles: list[Candle]) -> None:
        self.batches.append(list(candles))
        self.latest = max(item.open_time for item in candles)


class MemorySymbolRepository:
    def __init__(self, configured: list[Symbol]) -> None:
        self.configured = configured
        self.calls: list[tuple[str, str | None]] = []

    def active_symbols(
        self,
        *,
        exchange: str,
        symbol: str | None,
    ) -> list[Symbol]:
        self.calls.append((exchange, symbol))
        return list(self.configured)


def make_collector(
    completed: list[Candle],
    repository: MemoryCandleRepository,
    *,
    symbols: list[Symbol] | None = None,
) -> tuple[LiveCollector, MockExchange]:
    exchange = MockExchange(completed)
    configured = symbols if symbols is not None else [Symbol("ETH/USDT:USDT", "binance")]
    service = LiveCollector(
        symbols=MemorySymbolRepository(configured),
        exchange=exchange,
        candles=repository,
    )
    return service, exchange


def test_every_new_confirmed_candle_is_persisted_even_when_values_do_not_change() -> None:
    repository = MemoryCandleRepository(latest=BASE)
    service, exchange = make_collector([candle(1), candle(2)], repository)

    result = asyncio.run(service.collect_once(Symbol("ETH/USDT:USDT", "binance")))

    assert result.persisted_count == 2
    assert repository.batches == [[candle(1), candle(2)]]
    assert exchange.calls[0][1:] == ("1m", 3)


def test_replayed_completed_rows_are_stale_and_never_duplicate_the_series() -> None:
    repository = MemoryCandleRepository()
    service, _ = make_collector([candle(1), candle(2)], repository)
    symbol = Symbol("ETH/USDT:USDT", "binance")

    first = asyncio.run(service.collect_once(symbol))
    second = asyncio.run(service.collect_once(symbol))

    assert first.persisted_count == 2
    assert second.persisted_count == 0
    assert second.stale_count == 2
    assert len(repository.batches) == 1


def test_gap_is_logged_and_marked_without_synthesizing_a_candle(
    caplog: pytest.LogCaptureFixture,
) -> None:
    repository = MemoryCandleRepository(latest=BASE)
    service, _ = make_collector([candle(1), candle(3)], repository)

    with caplog.at_level(logging.WARNING):
        result = asyncio.run(service.collect_once(Symbol("ETH/USDT:USDT", "binance")))

    assert [item.open_time for item in repository.batches[0]] == [
        BASE + timedelta(minutes=1),
        BASE + timedelta(minutes=3),
    ]
    assert len(result.gaps) == 1
    assert result.gaps[0].missing_candles == 1
    assert "ohlcv_gap" in caplog.text


@pytest.mark.parametrize(
    "completed",
    [
        [candle(1), candle(1)],
        [candle(2), candle(1)],
    ],
)
def test_duplicate_or_regressing_exchange_batches_fail_before_write(
    completed: list[Candle],
) -> None:
    repository = MemoryCandleRepository()
    service, _ = make_collector(completed, repository)

    with pytest.raises(ValueError, match="strictly increasing"):
        asyncio.run(service.collect_once(Symbol("ETH/USDT:USDT", "binance")))
    assert repository.batches == []


def test_crossed_series_fails_before_write() -> None:
    repository = MemoryCandleRepository()
    crossed = replace(candle(1), symbol="BTC/USDT:USDT")
    service, _ = make_collector([crossed], repository)
    with pytest.raises(ValueError, match="crossed"):
        asyncio.run(service.collect_once(Symbol("ETH/USDT:USDT", "binance")))
    assert repository.batches == []


def test_symbol_is_read_from_config_and_must_be_singular() -> None:
    configured = Symbol("ETH/USDT:USDT", "binance")
    symbol_repository = MemorySymbolRepository([configured])
    service = LiveCollector(
        symbols=symbol_repository,
        exchange=MockExchange([]),
        candles=MemoryCandleRepository(),
        symbol_selector="ETH/USDT:USDT",
    )
    assert asyncio.run(service.load_symbol()) == configured
    assert symbol_repository.calls == [("binance", "ETH/USDT:USDT")]

    for invalid in ([], [configured, Symbol("BTC/USDT:USDT", "binance")]):
        broken, _ = make_collector([], MemoryCandleRepository(), symbols=invalid)
        with pytest.raises(CollectorConfigurationError, match="exactly one"):
            asyncio.run(broken.load_symbol())


def test_runner_observability_counts_persistence_gap_and_structured_events(
    caplog: pytest.LogCaptureFixture,
) -> None:
    repository = MemoryCandleRepository(latest=BASE)
    now = 15.0
    sleep_calls = 0

    def wall_clock() -> float:
        return now

    async def cancel_after_one_poll(delay: float) -> None:
        nonlocal now, sleep_calls
        now += delay
        sleep_calls += 1
        if sleep_calls == 2:
            raise asyncio.CancelledError

    service = LiveCollector(
        symbols=MemorySymbolRepository([Symbol("ETH/USDT:USDT", "binance")]),
        exchange=MockExchange([candle(1), candle(3)]),
        candles=repository,
        wall_clock=wall_clock,
        sleep=cancel_after_one_poll,
    )

    with caplog.at_level(logging.INFO), pytest.raises(asyncio.CancelledError):
        asyncio.run(service.run())

    metrics = service.metrics_snapshot()
    assert metrics.warmups == 1
    assert metrics.poll_cycles == 1
    assert metrics.poll_errors == 0
    assert metrics.records_processed == 2
    assert metrics.gaps_detected == 1
    assert metrics.last_poll_at == datetime(1970, 1, 1, 0, 1, 2, tzinfo=UTC)
    assert metrics.last_progress_at == datetime(1970, 1, 1, 0, 1, 2, tzinfo=UTC)
    events = {getattr(record, "event", None) for record in caplog.records}
    assert {
        "runner_warmup",
        "runner_poll_started",
        "records_persisted",
        "data_gap",
        "runner_poll_completed",
        "runner_shutdown",
    } <= events
    completed = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "runner_poll_completed"
    )
    assert getattr(completed, "service", None) == "collector"
    assert getattr(completed, "symbol", None) == "ETH/USDT:USDT"
    assert getattr(completed, "count", None) == 2
    assert service.health_snapshot().running is False


def test_collector_poll_error_is_secret_safe_and_staleness_is_visible(
    caplog: pytest.LogCaptureFixture,
) -> None:
    now = 15.0
    sleep_calls = 0
    snapshots: list[RunnerHealthSnapshot] = []
    service: LiveCollector

    def wall_clock() -> float:
        return now

    async def inspect_then_cancel(delay: float) -> None:
        nonlocal now, sleep_calls
        now += delay
        sleep_calls += 1
        if sleep_calls == 2:
            snapshots.append(service.health_snapshot())
            raise asyncio.CancelledError

    service = LiveCollector(
        symbols=MemorySymbolRepository([Symbol("ETH/USDT:USDT", "binance")]),
        exchange=SecretFailingExchange([]),
        candles=MemoryCandleRepository(),
        wall_clock=wall_clock,
        sleep=inspect_then_cancel,
        stale_after_seconds=30,
    )

    with caplog.at_level(logging.ERROR), pytest.raises(asyncio.CancelledError):
        asyncio.run(service.run())

    metrics = service.metrics_snapshot()
    assert metrics.warmups == 1
    assert metrics.poll_cycles == 1
    assert metrics.poll_errors == 1
    assert metrics.last_progress_at is None
    assert len(snapshots) == 1
    assert snapshots[0].running is True
    assert snapshots[0].stale is True
    assert snapshots[0].healthy is False
    error_record = next(
        record for record in caplog.records if getattr(record, "event", None) == "runner_poll_error"
    )
    assert getattr(error_record, "service", None) == "collector"
    assert getattr(error_record, "error_type", None) == "ValueError"
    assert getattr(error_record, "reason", None) == "poll_failed"
    assert "fake-password" not in caplog.text
    assert "fake-password" not in repr(metrics)
    assert "fake-password" not in repr(service.health_snapshot())


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (0.0, 2.0),
        (1.25, 0.75),
        (2.0, 60.0),
        (15.0, 47.0),
        (59.5, 2.5),
        (60.0, 2.0),
    ],
)
def test_polling_is_minute_aligned_with_two_second_buffer(
    now: float,
    expected: float,
) -> None:
    assert seconds_until_next_poll(now) == expected
