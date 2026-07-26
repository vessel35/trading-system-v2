"""Read paper signals and confirmed candles without writing either source database."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from core_lib.candles import resample_confirmed_ohlcv, timeframe_duration
from core_lib.types import MarketType, PositionSide, TradingSignal

from wallet_service.application import SignalQueue
from wallet_service.domain import PaperIntent, PaperSignal

_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
_SIGNALS_SQL = """
SELECT
    signal_id,
    source_mode,
    symbol,
    exchange,
    timeframe,
    candle_open_time,
    candle_close_time,
    signal_time,
    derived_intent,
    derived_side,
    price,
    confidence,
    stop_loss,
    take_profit,
    market_type,
    leverage,
    reason,
    metadata_json
FROM {signals}
WHERE source_mode = 'paper'
  AND signal_id > %s
ORDER BY signal_id
LIMIT %s
"""
_CANDLES_SQL = """
SELECT time, open, high, low, close, volume, quote_volume, trade_count
FROM {candles}
WHERE symbol = %s
  AND exchange = %s
  AND timeframe = '1m'
  AND time >= %s
  AND time < %s
ORDER BY time
"""


class QueryResult(Protocol):
    """The SELECT result shared by psycopg cursors and isolated doubles."""

    def fetchall(self) -> list[Sequence[object]]:
        """Return selected rows."""


class ReadConnection(Protocol):
    """The parameterized, SELECT-only surface used for source databases."""

    def execute(
        self,
        query: str,
        params: tuple[object, ...],
    ) -> QueryResult:
        """Execute one read query."""


@dataclass(frozen=True, slots=True)
class _SignalRow:
    signal_id: int
    symbol: str
    exchange: str
    timeframe: str
    candle_open_time: datetime
    candle_close_time: datetime
    signal_time: datetime
    intent: PaperIntent
    side: PositionSide | None
    price: Decimal
    confidence: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    market_type: MarketType
    leverage: int | None
    reason: str
    metadata: dict[str, object]


class PostgresSignalQueue(SignalQueue):
    """Poll paper-only signal rows and assemble next-candle envelopes."""

    def __init__(
        self,
        signal_reader: ReadConnection,
        crypto_reader: ReadConnection,
        wallet_reader: ReadConnection,
        *,
        wallet_id: str,
        signal_schema: str = "public",
        crypto_schema: str = "public",
        wallet_schema: str = "public",
        batch_size: int = 100,
    ) -> None:
        if not wallet_id:
            raise ValueError("wallet_id must not be empty")
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
            raise ValueError("batch_size must be a positive int")
        self._signal_reader = signal_reader
        self._crypto_reader = crypto_reader
        self._wallet_reader = wallet_reader
        self._wallet_id = wallet_id
        self._batch_size = batch_size
        self._signals_sql = _SIGNALS_SQL.format(signals=_relation(signal_schema, "trading_signals"))
        self._candles_sql = _CANDLES_SQL.format(candles=_relation(crypto_schema, "ohlcv_futures"))
        self._consumption = _relation(wallet_schema, "wallet_signal_consumption")

    def receive(self) -> PaperSignal | None:
        """Return the first ready, unconsumed signal without claiming it early."""
        after_signal_id = 0
        while True:
            raw_rows = self._signal_reader.execute(
                self._signals_sql,
                (after_signal_id, self._batch_size),
            ).fetchall()
            if not raw_rows:
                return None
            rows = tuple(_signal_row(row) for row in raw_rows)
            after_signal_id = rows[-1].signal_id
            unconsumed = self._unconsumed_signal_ids(tuple(row.signal_id for row in rows))
            for row in rows:
                if row.signal_id not in unconsumed:
                    continue
                message = self._assemble(row)
                if message is not None:
                    return message

    def _unconsumed_signal_ids(self, signal_ids: tuple[int, ...]) -> frozenset[int]:
        values = ", ".join("(%s::varchar)" for _ in signal_ids)
        query = f"""
SELECT candidate.signal_id
FROM (VALUES {values}) AS candidate(signal_id)
LEFT JOIN {self._consumption} AS consumed
  ON consumed.signal_id = candidate.signal_id
 AND consumed.wallet_id = %s
WHERE consumed.signal_id IS NULL
ORDER BY candidate.signal_id::bigint
"""
        rows = self._wallet_reader.execute(query, (*signal_ids, self._wallet_id)).fetchall()
        return frozenset(_source_signal_id(row[0]) for row in rows)

    def _assemble(self, row: _SignalRow) -> PaperSignal | None:
        duration = timeframe_duration(row.timeframe)
        execution_boundary = row.candle_close_time + duration
        minute_rows = self._crypto_reader.execute(
            self._candles_sql,
            (
                row.symbol,
                row.exchange,
                row.candle_open_time,
                execution_boundary,
            ),
        ).fetchall()
        resampled = resample_confirmed_ohlcv(
            minute_rows,
            symbol=row.symbol,
            exchange=row.exchange,
            timeframe=row.timeframe,
            boundary=execution_boundary,
        )
        decision = next(
            (
                candle
                for candle in resampled.candles
                if candle.open_time == row.candle_open_time
                and candle.close_time == row.candle_close_time
            ),
            None,
        )
        execution = next(
            (candle for candle in resampled.candles if candle.open_time == row.candle_close_time),
            None,
        )
        if decision is None or execution is None:
            return None
        signal = TradingSignal(
            symbol=row.symbol,
            timestamp=row.signal_time,
            confidence=float(row.confidence),
            price=float(row.price),
            stop_loss=None if row.stop_loss is None else float(row.stop_loss),
            take_profit=None if row.take_profit is None else float(row.take_profit),
            market_type=row.market_type,
            leverage=row.leverage,
            reason=row.reason,
            metadata=row.metadata,
        )
        return PaperSignal(
            wallet_id=self._wallet_id,
            signal_id=str(row.signal_id),
            decision_candle=decision,
            execution_candle=execution,
            signal=signal,
            intent=row.intent,
            side=row.side,
        )


def _relation(schema: str, table: str) -> str:
    if _IDENTIFIER.fullmatch(schema) is None:
        raise ValueError("schema must be a lowercase PostgreSQL identifier")
    return f'"{schema}".{table}'


def _signal_row(row: Sequence[object]) -> _SignalRow:
    if len(row) != 18:
        raise ValueError("trading_signals SELECT returned an unexpected row shape")
    signal_id = _source_signal_id(row[0])
    if row[1] != "paper":
        raise ValueError("wallet-service accepts paper signal rows only")
    symbol = _string(row[2], name="symbol")
    exchange = _string(row[3], name="exchange")
    timeframe = _string(row[4], name="timeframe")
    candle_open_time = _datetime(row[5], name="candle_open_time")
    candle_close_time = _datetime(row[6], name="candle_close_time")
    signal_time = _datetime(row[7], name="signal_time")
    side = None if row[9] is None else PositionSide(_string(row[9], name="derived_side"))
    leverage = row[15]
    if leverage is not None and (isinstance(leverage, bool) or not isinstance(leverage, int)):
        raise TypeError("leverage must be int or None")
    metadata = row[17]
    if not isinstance(metadata, Mapping):
        raise TypeError("metadata_json must be a JSON object")
    return _SignalRow(
        signal_id=signal_id,
        symbol=symbol,
        exchange=exchange,
        timeframe=timeframe,
        candle_open_time=candle_open_time,
        candle_close_time=candle_close_time,
        signal_time=signal_time,
        intent=PaperIntent(_string(row[8], name="derived_intent")),
        side=side,
        price=_decimal(row[10], name="price"),
        confidence=_decimal(row[11], name="confidence"),
        stop_loss=_optional_decimal(row[12], name="stop_loss"),
        take_profit=_optional_decimal(row[13], name="take_profit"),
        market_type=MarketType(_string(row[14], name="market_type")),
        leverage=leverage,
        reason=_string(row[16], name="reason", allow_empty=True),
        metadata=dict(metadata),
    )


def _source_signal_id(value: object) -> int:
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError as error:
            raise TypeError("signal_id must be a positive integer") from error
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise TypeError("signal_id must be a positive integer")
    return value


def _string(value: object, *, name: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not allow_empty and not value:
        raise ValueError(f"{name} must not be empty")
    return value


def _datetime(value: object, *, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _decimal(value: object, *, name: str) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be Decimal")
    return value


def _optional_decimal(value: object, *, name: str) -> Decimal | None:
    return None if value is None else _decimal(value, name=name)


__all__ = ["PostgresSignalQueue", "ReadConnection"]
