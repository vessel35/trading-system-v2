"""Define the validated unified candle value type."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

_TIMEFRAME_PATTERN = re.compile(r"^(?P<count>[1-9]\d*)(?P<unit>[mhd])$")
_TIMEFRAME_UNITS = {
    "m": timedelta(minutes=1),
    "h": timedelta(hours=1),
    "d": timedelta(days=1),
}


@dataclass(slots=True)
class Candle:
    """A confirmed OHLCV candle shared by every execution mode."""

    symbol: str
    exchange: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float | None
    trade_count: int | None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Reject a malformed individual candle."""
        match = _TIMEFRAME_PATTERN.fullmatch(self.timeframe)
        if match is None:
            raise ValueError(f"unsupported timeframe: {self.timeframe!r}")

        expected_duration = _TIMEFRAME_UNITS[match.group("unit")] * int(match.group("count"))
        if self.close_time != self.open_time + expected_duration:
            raise ValueError("close_time must equal open_time + timeframe")

        prices = (self.open, self.high, self.low, self.close)
        if any(not isinstance(price, float) for price in prices):
            raise TypeError("candle prices must be float")
        if any(price <= 0 for price in prices):
            raise ValueError("all candle prices must be positive")
        if self.high < max(self.open, self.close):
            raise ValueError("high must be at least max(open, close)")
        if self.low > min(self.open, self.close):
            raise ValueError("low must be at most min(open, close)")

        if not isinstance(self.volume, float):
            raise TypeError("volume must be float")
        if self.volume < 0:
            raise ValueError("volume must be non-negative")
        if self.quote_volume is not None:
            if not isinstance(self.quote_volume, float):
                raise TypeError("quote_volume must be float or None")
            if self.quote_volume < 0:
                raise ValueError("quote_volume must be non-negative")
        if self.trade_count is not None:
            if isinstance(self.trade_count, bool) or not isinstance(self.trade_count, int):
                raise TypeError("trade_count must be int or None")
            if self.trade_count < 0:
                raise ValueError("trade_count must be non-negative")
