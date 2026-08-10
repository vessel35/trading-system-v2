"""Verify query boundaries and the operational signal sink with DB-API doubles."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

import pytest
from core_lib.ports import DataFeed, StrategyRegistry
from core_lib.types import Candle, MarketType, PositionSide, SignalType, TradingSignal
from signal_service.application import SignalSink
from signal_service.core import SignalGenerationConfig
from signal_service.domain import PersistedSignal, SignalIntent, SignalMode
from signal_service.infrastructure import (
    CryptoDataFeed,
    PostgresSignalSink,
    SignalStrategyRegistry,
)
from signal_service.main import build_signal_generator


class _Result:
    def __init__(self, rows: list[Sequence[object]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[Sequence[object]]:
        return list(self._rows)

    def fetchone(self) -> Sequence[object] | None:
        return None if not self._rows else self._rows[0]


class _Connection:
    def __init__(
        self,
        handler: Callable[[str, tuple[object, ...]], list[Sequence[object]]],
    ) -> None:
        self._handler = handler
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.commit_calls = 0
        self.rollback_calls = 0

    def execute(self, query: str, params: tuple[object, ...]) -> _Result:
        self.calls.append((query, params))
        return _Result(self._handler(query, params))

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


def _minute_row(at: datetime, price: int) -> tuple[object, ...]:
    value = Decimal(price)
    return (
        at,
        value,
        value + 2,
        value - 1,
        value + 1,
        Decimal("1"),
        Decimal("10"),
        2,
    )


def _registry_row(strategy_id: str) -> tuple[object, ...]:
    return (
        strategy_id,
        "Probe",
        "strategies.probe",
        "Probe",
        None,
        "2.0.0",
        ["1h"],
        [{"name": "EMA", "params": {"period": 9}}],
        9,
        {},
        True,
        False,
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, tzinfo=UTC),
    )


def _vessel_registry_row() -> tuple[object, ...]:
    return (
        "vessel-reference",
        "VesselReference",
        "trading_plugins.strategies.vessel_reference",
        "Vessel Reference",
        None,
        "3.0.0",
        ["1h"],
        [
            {"name": "EMA", "params": {"period": 9}},
            {"name": "EMA", "params": {"period": 21}},
        ],
        1,
        {},
        True,
        False,
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, tzinfo=UTC),
    )


def _persisted() -> PersistedSignal:
    opened = datetime(2026, 1, 1, tzinfo=UTC)
    candle = Candle(
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="1h",
        open_time=opened,
        close_time=opened + timedelta(hours=1),
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=10.0,
        quote_volume=1_000.0,
        trade_count=5,
    )
    decision = TradingSignal(
        symbol=candle.symbol,
        timestamp=candle.close_time,
        confidence=0.8,
        price=candle.close,
        stop_loss=95.0,
        take_profit=111.0,
        market_type=MarketType.FUTURES,
        leverage=2,
        reason="fixture",
        metadata={"source": "unit"},
    )
    return PersistedSignal(
        strategy_id="probe",
        params={"threshold": 2},
        mode=SignalMode.PAPER,
        timeframe="1h",
        candle=candle,
        signal=decision,
        signal_type=SignalType.BUY,
        intent=SignalIntent.ENTER,
        side=PositionSide.LONG,
    )


def test_crypto_data_feed_reads_and_returns_only_complete_confirmed_buckets() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows: list[Sequence[object]] = [
        _minute_row(base + timedelta(minutes=index), 100 + index) for index in range(6)
    ]
    connection = _Connection(lambda query, params: rows)
    feed = CryptoDataFeed(connection)

    candles = feed.candles("BTCUSDT", "5m", base + timedelta(minutes=5))

    assert isinstance(feed, DataFeed)
    assert len(candles) == 1
    assert candles[0].open_time == base
    assert candles[0].close_time == base + timedelta(minutes=5)
    assert candles[0].close_time <= base + timedelta(minutes=5)
    assert candles[0].open == 100.0
    assert candles[0].close == 105.0
    query, params = connection.calls[0]
    assert query.lstrip().startswith("SELECT")
    assert "public.ohlcv_futures" in query
    assert all(token not in query.upper() for token in ("INSERT", "UPDATE", "DELETE"))
    assert params == ("BTCUSDT", "binance", base + timedelta(minutes=5))


def test_crypto_data_feed_drops_an_incomplete_bucket() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows: list[Sequence[object]] = [
        _minute_row(base + timedelta(minutes=index), 100 + index) for index in range(5)
    ]
    del rows[2]
    feed = CryptoDataFeed(_Connection(lambda query, params: rows))

    assert feed.candles("BTCUSDT", "5m", base + timedelta(minutes=5)) == []
    assert feed.dropped_bucket_count == 1


def test_crypto_data_feed_incremental_read_starts_at_processed_cursor() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    cursor = base + timedelta(minutes=5)
    boundary = base + timedelta(minutes=10)
    rows: list[Sequence[object]] = [
        _minute_row(base + timedelta(minutes=index), 100 + index) for index in range(5, 10)
    ]
    connection = _Connection(lambda query, params: rows)
    feed = CryptoDataFeed(connection)

    candles = feed.candles_after("BTCUSDT", "5m", cursor, boundary)

    assert len(candles) == 1
    assert candles[0].open_time == cursor
    query, params = connection.calls[0]
    assert "time >= %s" in query
    assert params == ("BTCUSDT", "binance", cursor, boundary)


def test_signal_strategy_registry_reads_only_catalog_and_rejects_writes() -> None:
    rows: list[Sequence[object]] = [_registry_row("alpha"), _registry_row("beta")]

    def handler(query: str, params: tuple[object, ...]) -> list[Sequence[object]]:
        assert query.lstrip().startswith("SELECT")
        assert "public.strategy_registry" in query
        if "WHERE strategy_id" in query:
            return [row for row in rows if row[0] == params[0]]
        return rows

    connection = _Connection(handler)
    registry = SignalStrategyRegistry(connection)

    assert isinstance(registry, StrategyRegistry)
    assert registry.get("alpha")["strategy_id"] == "alpha"
    assert [entry["strategy_id"] for entry in registry.list()] == ["alpha", "beta"]
    calls_before = len(connection.calls)
    with pytest.raises(PermissionError, match="read-only"):
        registry.register("gamma", {})
    assert len(connection.calls) == calls_before


def test_signal_sink_writes_only_owned_table_and_is_idempotent() -> None:
    connection = _Connection(lambda query, params: [(42,)])
    sink = PostgresSignalSink(connection)
    persisted = _persisted()

    inserted = sink.store(persisted)

    assert isinstance(sink, SignalSink)
    assert inserted is True
    query, params = connection.calls[0]
    assert query.lstrip().startswith("INSERT")
    assert '"public".trading_signals' in query
    assert "ON CONFLICT" in query
    assert "strategy_registry" not in query
    assert "wallet" not in query.casefold()
    assert params[0] == "probe"
    assert params[1] == '{"threshold":2}'
    assert params[2] == "paper"
    assert params[9:12] == ("BUY", "enter", "long")
    assert params[-1] == '{"source":"unit"}'
    assert connection.commit_calls == 1
    assert connection.rollback_calls == 0

    duplicate_connection = _Connection(lambda query, params: [])
    assert PostgresSignalSink(duplicate_connection).store(persisted) is False
    assert duplicate_connection.commit_calls == 1
    assert duplicate_connection.rollback_calls == 0


def test_signal_sink_rolls_back_when_insert_fails() -> None:
    def fail(query: str, params: tuple[object, ...]) -> list[Sequence[object]]:
        del query, params
        raise RuntimeError("insert failed")

    connection = _Connection(fail)

    with pytest.raises(RuntimeError, match="insert failed"):
        PostgresSignalSink(connection).store(_persisted())

    assert connection.commit_calls == 0
    assert connection.rollback_calls == 1


def test_signal_sink_rejects_an_untrusted_schema_identifier() -> None:
    with pytest.raises(ValueError, match="schema"):
        PostgresSignalSink(_Connection(lambda query, params: []), schema="public; DROP")


def test_main_wires_confirmed_crypto_rows_through_core_vessel_to_signal_db() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    minute_rows: list[Sequence[object]] = [
        _minute_row(base + timedelta(minutes=index), 100 + index) for index in range(22 * 60)
    ]
    crypto = _Connection(lambda query, params: minute_rows)
    registry = _Connection(lambda query, params: [_vessel_registry_row()])
    writer = _Connection(lambda query, params: [(1,)])
    service = build_signal_generator(
        crypto_reader=crypto,
        registry_reader=registry,
        signal_writer=writer,
    )

    cycle = service.start(
        SignalGenerationConfig(
            strategy_id="vessel-reference",
            symbol="BTCUSDT",
            timeframe="1h",
            market_type=MarketType.FUTURES,
            mode=SignalMode.PAPER,
        ),
        base + timedelta(hours=22),
    )
    persisted = cycle.signal

    assert persisted is not None
    assert dict(persisted.params) == {}
    assert persisted.signal.metadata["adaptee"] == "vessel-reference"
    assert persisted.signal.metadata["decision_action"] == "ENTER_LONG"
    money_management = cast(dict[str, object], persisted.signal.metadata["money_management"])
    assert money_management["policy_id"] == "manual"
    assert persisted.signal.stop_loss is not None
    assert persisted.signal.take_profit is not None
    assert persisted.signal.stop_loss < persisted.signal.price < persisted.signal.take_profit
    assert persisted.signal.leverage == 1
    assert persisted.signal_type is SignalType.BUY
    assert crypto.calls[0][0].lstrip().startswith("SELECT")
    assert registry.calls[0][0].lstrip().startswith("SELECT")
    assert writer.calls[0][0].lstrip().startswith("INSERT")
    assert '"public".trading_signals' in writer.calls[0][0]
    assert writer.commit_calls == 1
