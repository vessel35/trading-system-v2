"""Verify the read-only signal/candle adapter and look-ahead boundary."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from core_lib.types import MarketType, PositionSide
from wallet_service.domain import PaperIntent
from wallet_service.infrastructure import PostgresSignalQueue


class _Result:
    def __init__(self, rows: list[Sequence[object]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[Sequence[object]]:
        return list(self._rows)


class _Connection:
    def __init__(
        self,
        handler: Callable[[str, tuple[object, ...]], list[Sequence[object]]],
    ) -> None:
        self._handler = handler
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.closed = False

    def execute(self, query: str, params: tuple[object, ...]) -> _Result:
        self.calls.append((query, params))
        return _Result(self._handler(query, params))

    def close(self) -> None:
        self.closed = True


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


def _signal_row(base: datetime) -> tuple[object, ...]:
    return (
        41,
        "paper",
        "BTCUSDT",
        "binance",
        "1h",
        base,
        base + timedelta(hours=1),
        base + timedelta(hours=1),
        "enter",
        "long",
        Decimal("160"),
        Decimal("0.900000"),
        Decimal("150"),
        Decimal("180"),
        "futures",
        2,
        "fixture",
        {"source": "signal-service"},
    )


def _queue(
    *,
    minute_count: int = 120,
    consumed: bool = False,
) -> tuple[PostgresSignalQueue, _Connection, _Connection, _Connection]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    row = _signal_row(base)

    def signal_handler(
        query: str,
        params: tuple[object, ...],
    ) -> list[Sequence[object]]:
        del query
        return [row] if params[0] == 0 else []

    signal = _Connection(signal_handler)
    crypto = _Connection(
        lambda query, params: [
            _minute_row(base + timedelta(minutes=index), 100 + index)
            for index in range(minute_count)
        ]
    )
    wallet = _Connection(lambda query, params: [] if consumed else [("41",)])
    return (
        PostgresSignalQueue(
            signal,
            crypto,
            wallet,
            wallet_id="wallet-1",
            signal_schema="signal_source",
            crypto_schema="crypto_source",
            wallet_schema="wallet_owned",
        ),
        signal,
        crypto,
        wallet,
    )


def test_queue_assembles_paper_signal_from_three_read_boundaries() -> None:
    queue, signal, crypto, wallet = _queue()

    message = queue.receive()

    assert message is not None
    assert message.wallet_id == "wallet-1"
    assert message.signal_id == "41"
    assert message.intent is PaperIntent.ENTER
    assert message.side is PositionSide.LONG
    assert message.signal.market_type is MarketType.FUTURES
    assert message.signal.metadata == {"source": "signal-service"}
    assert message.decision_candle.open_time == datetime(2026, 1, 1, tzinfo=UTC)
    assert message.execution_candle.open_time == message.decision_candle.close_time
    assert message.execution_candle.open == 160.0

    signal_query, signal_params = signal.calls[0]
    assert signal_query.lstrip().startswith("SELECT")
    assert '"signal_source".trading_signals' in signal_query
    assert "source_mode = 'paper'" in signal_query
    assert signal_params == (0, 100)
    wallet_query, wallet_params = wallet.calls[0]
    assert wallet_query.lstrip().startswith("SELECT")
    assert "LEFT JOIN" in wallet_query
    assert '"wallet_owned".wallet_signal_consumption' in wallet_query
    assert wallet_params == (41, "wallet-1")
    crypto_query, crypto_params = crypto.calls[0]
    assert crypto_query.lstrip().startswith("SELECT")
    assert '"crypto_source".ohlcv_futures' in crypto_query
    assert crypto_params == (
        "BTCUSDT",
        "binance",
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, 2, tzinfo=UTC),
    )
    for query, _ in signal.calls + crypto.calls:
        assert all(token not in query.upper() for token in ("INSERT", "UPDATE", "DELETE"))


def test_queue_skips_until_the_next_execution_candle_is_confirmed() -> None:
    queue, signal, crypto, wallet = _queue(minute_count=60)

    assert queue.receive() is None
    assert len(signal.calls) == 2
    assert len(crypto.calls) == 1
    assert len(wallet.calls) == 1
    assert all(not query.lstrip().startswith("INSERT") for query, _ in wallet.calls)


def test_queue_close_releases_only_source_connections() -> None:
    queue, signal, crypto, wallet = _queue()

    queue.close()
    queue.close()

    assert signal.closed is True
    assert crypto.closed is True
    assert wallet.closed is False
    with pytest.raises(RuntimeError, match="closed"):
        queue.receive()


def test_queue_does_not_read_candles_for_an_already_consumed_signal() -> None:
    queue, signal, crypto, wallet = _queue(consumed=True)

    assert queue.receive() is None
    assert len(signal.calls) == 2
    assert crypto.calls == []
    assert len(wallet.calls) == 1
