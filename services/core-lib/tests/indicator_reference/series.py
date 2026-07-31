"""Shared inputs of the outside comparison: the series, the sample points, the floor.

Everything here is common to all six categories, so no category owns it and nobody
adding an indicator has a reason to edit this file. Changing the candle builder or
the sample indices would invalidate every frozen number in the sibling modules at
once, which is exactly why the values live apart from the series that produced them.
"""

import math
from datetime import UTC, datetime, timedelta

from core_lib.types import Candle

SAMPLE_INDICES = (100, 200, 299)

# Below this the remaining gap is floating-point noise rather than a seed being
# forgotten, so the test stops demanding that it keep shrinking.
CONVERGENCE_NOISE_FLOOR = 1e-9


def reference_candles(count: int = 300) -> list[Candle]:
    """Build the exact series the frozen reference values were produced from."""

    candles: list[Candle] = []
    previous_close = 100.0
    start = datetime(2025, 1, 1, tzinfo=UTC)
    for index in range(count):
        drift = math.sin(index / 5.0) * 3.0 + math.cos(index / 11.0) * 1.5
        close = previous_close + drift + (index % 7) * 0.25 - 0.75
        open_price = previous_close
        high = max(open_price, close) + 1.25 + (index % 3) * 0.4
        low = min(open_price, close) - 1.25 - (index % 5) * 0.3
        open_time = start + timedelta(hours=index)
        candles.append(
            Candle(
                symbol="BTC/USDT:USDT",
                exchange="binance",
                timeframe="1h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=100.0 + (index % 13) * 5.0,
                quote_volume=None,
                trade_count=None,
            )
        )
        previous_close = close
    return candles
