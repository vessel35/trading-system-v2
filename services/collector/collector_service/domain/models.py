"""Validated values at the confirmed-candle ingestion boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

ONE_MINUTE = timedelta(minutes=1)


@dataclass(frozen=True, slots=True)
class Symbol:
    """One configured perpetual-futures market."""

    value: str
    exchange: str

    def __post_init__(self) -> None:
        if "/" not in self.value:
            raise ValueError("symbol must use CCXT BASE/QUOTE notation")
        if not self.exchange:
            raise ValueError("exchange is required")


@dataclass(frozen=True, slots=True)
class Candle:
    """One confirmed 1m futures candle, represented without binary floats."""

    symbol: str
    exchange: str
    timeframe: str
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Decimal | None = None
    trade_count: int | None = None

    def __post_init__(self) -> None:
        if self.timeframe != "1m":
            raise ValueError("collector accepts only the 1m timeframe")
        if self.open_time.tzinfo is None:
            raise ValueError("open_time must be timezone-aware")
        normalized = self.open_time.astimezone(UTC)
        if normalized.second != 0 or normalized.microsecond != 0:
            raise ValueError("open_time must be aligned to a UTC minute boundary")
        if not self.symbol or not self.exchange:
            raise ValueError("symbol and exchange are required")

        prices = (self.open, self.high, self.low, self.close)
        if any(not isinstance(value, Decimal) for value in prices):
            raise TypeError("prices must be Decimal")
        if any(value <= 0 for value in prices):
            raise ValueError("prices must be positive")
        if self.high < max(self.open, self.close):
            raise ValueError("high must be at least max(open, close)")
        if self.low > min(self.open, self.close):
            raise ValueError("low must be at most min(open, close)")
        if not isinstance(self.volume, Decimal):
            raise TypeError("volume must be Decimal")
        if self.volume < 0:
            raise ValueError("volume must be non-negative")
        if self.quote_volume is not None:
            if not isinstance(self.quote_volume, Decimal):
                raise TypeError("quote_volume must be Decimal or None")
            if self.quote_volume < 0:
                raise ValueError("quote_volume must be non-negative")
        if self.trade_count is not None:
            if isinstance(self.trade_count, bool) or not isinstance(self.trade_count, int):
                raise TypeError("trade_count must be int or None")
            if self.trade_count < 0:
                raise ValueError("trade_count must be non-negative")


@dataclass(frozen=True, slots=True)
class CandleGap:
    """A missing 1m range that is reported but never synthesized."""

    expected_open_time: datetime
    observed_open_time: datetime
    missing_candles: int

    def __post_init__(self) -> None:
        if self.observed_open_time <= self.expected_open_time:
            raise ValueError("gap end must follow its expected start")
        if self.missing_candles < 1:
            raise ValueError("a gap must contain at least one missing candle")


def require_strictly_increasing(candles: list[Candle]) -> None:
    """Reject duplicate or regressing exchange batches before any write."""

    for previous, current in zip(candles, candles[1:], strict=False):
        if current.open_time <= previous.open_time:
            raise ValueError("completed candle open_time must be strictly increasing")


def detect_gaps(
    previous_open_time: datetime | None,
    candles: list[Candle],
) -> tuple[CandleGap, ...]:
    """Describe missing minutes without manufacturing replacement rows."""

    gaps: list[CandleGap] = []
    previous = previous_open_time
    for candle in candles:
        if previous is not None:
            expected = previous + ONE_MINUTE
            if candle.open_time > expected:
                missing = int((candle.open_time - expected) / ONE_MINUTE)
                gaps.append(
                    CandleGap(
                        expected_open_time=expected,
                        observed_open_time=candle.open_time,
                        missing_candles=missing,
                    )
                )
        previous = candle.open_time
    return tuple(gaps)
