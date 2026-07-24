"""Verify bounded inputs, deterministic clock, costs, and read-only registry."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from backtest_service.adapters import cost_model as cost_model_module
from backtest_service.adapters.clock import BacktestClock
from backtest_service.adapters.cost_model import BacktestCostModel
from backtest_service.adapters.data_feed import BacktestDataFeed
from backtest_service.adapters.ohlcv_gaps import (
    build_ohlcv_gap_contract,
    decode_ohlcv_gap_contract,
)
from backtest_service.adapters.strategy_registry import BacktestStrategyRegistry
from core_lib.costs import SlippageParams
from core_lib.execution import normalize_order
from core_lib.ports import Clock, CostModel, DataFeed, StrategyRegistry
from core_lib.types import (
    Candle,
    MarketType,
    Order,
    OrderRequest,
    OrderSide,
    OrderType,
    PositionSide,
)


class StubResult:
    """Small DB-API result stub."""

    def __init__(self, rows: list[Sequence[object]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[Sequence[object]]:
        return list(self._rows)

    def fetchone(self) -> Sequence[object] | None:
        return None if not self._rows else self._rows[0]


class StubConnection:
    """Record every query and delegate row construction to a test handler."""

    def __init__(
        self,
        handler: Callable[[str, tuple[object, ...]], list[Sequence[object]]],
    ) -> None:
        self._handler = handler
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, query: str, params: tuple[object, ...]) -> StubResult:
        self.calls.append((query, params))
        return StubResult(self._handler(query, params))


def _minute_row(
    at: datetime,
    price: int,
    *,
    volume: Decimal | None = Decimal("1"),
) -> tuple[object, ...]:
    value = Decimal(price)
    return (
        at,
        value,
        value + 2,
        value - 1,
        value + 1,
        volume,
        Decimal("10"),
        2,
    )


def test_data_feed_resamples_complete_1m_rows_and_enforces_up_to() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows: list[Sequence[object]] = [
        _minute_row(base + timedelta(minutes=index), 100 + index) for index in range(6)
    ]
    connection = StubConnection(lambda query, params: rows)
    feed = BacktestDataFeed(connection)
    assert isinstance(feed, DataFeed)

    candles = feed.candles("BTCUSDT", "5m", base + timedelta(minutes=5))

    assert len(candles) == 1
    candle = candles[0]
    assert candle.open_time == base
    assert candle.close_time == base + timedelta(minutes=5)
    assert candle.close_time <= base + timedelta(minutes=5)
    assert candle.open == 100.0
    assert candle.high == 106.0
    assert candle.low == 99.0
    assert candle.close == 105.0
    assert candle.volume == 5.0
    assert candle.quote_volume == 50.0
    assert candle.trade_count == 10
    query, params = connection.calls[0]
    assert query.lstrip().startswith("SELECT")
    assert "public.ohlcv_futures" in query
    assert params == ("BTCUSDT", "binance", base + timedelta(minutes=5))

    minute_candles = feed.candles(
        "BTCUSDT",
        "1m",
        base + timedelta(minutes=5),
    )
    assert len(minute_candles) == 5
    assert len(connection.calls) == 1


def test_data_feed_discards_and_counts_absent_source_buckets(
    caplog: pytest.LogCaptureFixture,
) -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows: list[Sequence[object]] = [
        _minute_row(base + timedelta(minutes=index), 100 + index) for index in range(5)
    ]
    del rows[2]
    feed = BacktestDataFeed(StubConnection(lambda query, params: rows))

    with caplog.at_level(logging.WARNING):
        candles = feed.candles("BTCUSDT", "5m", base + timedelta(minutes=5))

    assert candles == []
    assert feed.dropped_bucket_count == 1
    assert "discarded 1 incomplete OHLCV bucket" in caplog.text


def test_gap_contract_classifies_partial_resample_and_is_compact() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    candle = Candle(
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="1h",
        open_time=base,
        close_time=base + timedelta(hours=1),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1.0,
        quote_volume=None,
        trade_count=None,
    )
    missing_minutes = [
        int((base + timedelta(hours=1, minutes=index)).timestamp() * 1_000)
        for index in range(1, 13)
    ]
    contract = build_ohlcv_gap_contract(
        [candle],
        timeframe="1h",
        range_start=base,
        range_end=base + timedelta(hours=3),
        evaluation_start=base,
        evaluation_end=base + timedelta(hours=3),
        minute_gap_close_times=missing_minutes
        + [
            int((base + timedelta(hours=2, minutes=index)).timestamp() * 1_000)
            for index in range(1, 61)
        ],
        origin_validation_status="verified",
        origin_minute_row_count=108,
        origin_timestamp_hash="a" * 64,
    )

    assert contract.partial_bucket_count == 1
    assert contract.normal_gap_count == 1
    assert contract.evaluation_grid_gap_count == 2
    assert decode_ohlcv_gap_contract(contract.encode()) == contract
    assert len(contract.encode()) < 600
    unverified = replace(contract, origin_validation_status="fixture_unverified")
    with pytest.raises(ValueError, match="independently verified"):
        decode_ohlcv_gap_contract(unverified.encode())


def test_source_candles_use_an_independent_bounded_value_query() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows: list[Sequence[object]] = [
        _minute_row(base, 100),
        _minute_row(base + timedelta(minutes=1), 101),
    ]
    connection = StubConnection(lambda query, params: rows)
    feed = BacktestDataFeed(connection)

    source = feed.source_candles("BTCUSDT", base, base + timedelta(minutes=2))
    assert [candle.open_time for candle in source] == [row[0] for row in rows]
    assert [candle.close for candle in source] == [101.0, 102.0]
    query, params = connection.calls[0]
    assert "open, high, low, close, volume" in query
    assert "time >= %s" in query and "time < %s" in query
    assert params == ("BTCUSDT", "binance", base, base + timedelta(minutes=2))


def test_data_feed_rejects_present_but_incomplete_source_rows() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows: list[Sequence[object]] = [
        _minute_row(base + timedelta(minutes=index), 100 + index) for index in range(5)
    ]
    rows[2] = _minute_row(base + timedelta(minutes=2), 102, volume=None)
    feed = BacktestDataFeed(StubConnection(lambda query, params: rows))

    with pytest.raises(TypeError, match="volume must be returned as Decimal"):
        feed.candles("BTCUSDT", "5m", base + timedelta(minutes=5))

    assert feed.dropped_bucket_count == 0


def test_data_feed_normalizes_symbol_and_one_second_collection_jitter() -> None:
    at = datetime(2026, 1, 1, 8, tzinfo=UTC)
    observed_at = at + timedelta(milliseconds=2)

    def handler(query: str, params: tuple[object, ...]) -> list[Sequence[object]]:
        assert params == (
            "BTCUSDT",
            "binance",
            at,
            at + timedelta(seconds=1),
        )
        assert "ORDER BY time" in query
        if query.lstrip().startswith("SELECT time, funding_rate"):
            return [(observed_at, Decimal("0.0000875000"))]
        if query.lstrip().startswith("SELECT time, mark_price"):
            return [(observed_at, Decimal("101234.12345678"))]
        raise AssertionError(query)

    feed = BacktestDataFeed(StubConnection(handler))
    assert feed.funding("BTC/USDT:USDT", at) == Decimal("0.0000875000")
    assert feed.mark_price("BTC/USDT:USDT", at) == Decimal("101234.12345678")
    assert feed.funding_diagnostics() == {
        "exact_count": 0,
        "normalized_count": 1,
        "missing_count": 0,
        "mark_exact_count": 0,
        "mark_normalized_count": 1,
        "mark_missing_count": 0,
    }


def test_data_feed_funding_fails_closed_outside_jitter_window() -> None:
    at = datetime(2026, 1, 1, 8, tzinfo=UTC)

    outside = BacktestDataFeed(
        StubConnection(
            lambda query, params: [
                (at + timedelta(seconds=1, milliseconds=1), Decimal("0.0001"))
            ]
        )
    )
    with pytest.raises(ValueError, match="outside the collection window"):
        outside.funding("BTC/USDT:USDT", at)

    missing = BacktestDataFeed(StubConnection(lambda query, params: []))
    with pytest.raises(LookupError, match="no measured funding rate"):
        missing.funding("BTC/USDT:USDT", at)
    with pytest.raises(LookupError, match="no measured mark price"):
        missing.mark_price("BTC/USDT:USDT", at)
    assert missing.funding_diagnostics() == {
        "exact_count": 0,
        "normalized_count": 0,
        "missing_count": 1,
        "mark_exact_count": 0,
        "mark_normalized_count": 0,
        "mark_missing_count": 1,
    }


def test_clock_uses_only_its_strict_simulation_schedule() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    clock = BacktestClock([start, start + timedelta(hours=1)])
    assert isinstance(clock, Clock)
    assert clock.now() == start
    clock.advance()
    assert clock.now() == start + timedelta(hours=1)
    with pytest.raises(StopIteration, match="exhausted"):
        clock.advance()
    with pytest.raises(ValueError, match="strictly increasing"):
        BacktestClock([start, start])


def test_clock_builds_open_close_union_across_candle_gaps() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        Candle(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe="1h",
            open_time=opened,
            close_time=opened + timedelta(hours=1),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1.0,
            quote_volume=100.0,
            trade_count=1,
        )
        for opened in (start, start + timedelta(hours=2))
    ]
    clock = BacktestClock.from_candles(candles)

    observed = [clock.now()]
    while True:
        try:
            clock.advance()
        except StopIteration:
            break
        observed.append(clock.now())

    assert observed == [
        start,
        start + timedelta(hours=1),
        start + timedelta(hours=2),
        start + timedelta(hours=3),
    ]


def _order(*, reduce_only: bool = False) -> Order:
    return normalize_order(
        OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=2.0,
            price=None,
            stop_price=None,
            market_type=MarketType.FUTURES,
            position_side=PositionSide.LONG,
            reduce_only=reduce_only,
            close_position=False,
            time_in_force="GTC",
        )
    )


def test_cost_model_injects_values_and_shared_slippage_formula() -> None:
    model = BacktestCostModel()
    assert isinstance(model, CostModel)
    order = _order()
    assert model.fee("BTCUSDT", Decimal("100")) == Decimal("0.0005")
    assert model.slippage(order, {}) == Decimal("0.0005")
    assert model.slippage(order, {"gap_filled": True}) == Decimal("0.0010")
    assert model.funding_rate(datetime(2026, 1, 1, tzinfo=UTC)) == Decimal("0.0001")
    assert model.liq_params() == {"maintenance_margin_rate": Decimal("0.004")}
    assert model.position_size_pct == Decimal("0.20")
    spot = BacktestCostModel(
        {"spot_taker_fee_rate": Decimal("0.0007")},
        market_type=MarketType.SPOT,
    )
    assert spot.fee("BTCUSDT", Decimal("100")) == Decimal("0.0007")

    standard = BacktestCostModel(
        {
            "spread_rate": Decimal("0.002"),
            "impact_coefficient": Decimal("0.1"),
            "liquidity": Decimal("100"),
        }
    )
    assert standard.slippage(order, {}) == Decimal("0.003")


def test_cost_model_delegates_effective_rate_formula(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[SlippageParams] = []

    def shared_formula(
        params: SlippageParams,
        *,
        order: Order,
        context: dict[str, object] | None = None,
    ) -> Decimal:
        del order, context
        observed.append(params)
        return Decimal("0.123")

    monkeypatch.setattr(
        cost_model_module,
        "effective_slippage_rate",
        shared_formula,
    )
    model = BacktestCostModel()
    assert model.slippage(_order(), {"gap_filled": True}) == Decimal("0.123")
    assert observed[0].gap_multiplier == Decimal("2")


def _registry_row(strategy_id: str) -> tuple[object, ...]:
    return (
        strategy_id,
        "FakeAdaptee",
        "strategies.fake",
        "Fake",
        None,
        "1.0.0",
        ["1h"],
        [{"name": "ema", "params": {"period": 20}}],
        100,
        {"period": 20},
        True,
        False,
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_strategy_registry_reads_only_its_table_and_rejects_registration() -> None:
    rows: list[Sequence[object]] = [
        _registry_row("alpha"),
        _registry_row("beta"),
    ]

    def handler(query: str, params: tuple[object, ...]) -> list[Sequence[object]]:
        assert query.lstrip().startswith("SELECT")
        assert "public.strategy_registry" in query
        if "WHERE strategy_id" in query:
            return [row for row in rows if row[0] == params[0]]
        return rows

    connection = StubConnection(handler)
    registry = BacktestStrategyRegistry(connection)
    assert isinstance(registry, StrategyRegistry)
    assert registry.get("alpha")["strategy_id"] == "alpha"
    assert [row["strategy_id"] for row in registry.list()] == ["alpha", "beta"]
    calls_before_register = len(connection.calls)
    with pytest.raises(PermissionError, match="read-only"):
        registry.register("gamma", {"class_name": "Gamma"})
    assert len(connection.calls) == calls_before_register
    with pytest.raises(KeyError):
        registry.get("missing")
