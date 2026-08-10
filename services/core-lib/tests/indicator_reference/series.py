"""Shared inputs of the outside comparison: the series, the sample points, the floor.

Everything here is common to all eight categories, so no category owns it and nobody
adding an indicator has a reason to edit this file. Changing the candle builder or
the sample indices would invalidate every frozen number in the sibling modules at
once, which is exactly why the values live apart from the series that produced them.
"""

import math
import random
from datetime import UTC, datetime, timedelta

from core_lib.types import Candle

SAMPLE_INDICES = (100, 200, 299)

# Below this the remaining gap is floating-point noise rather than a seed being
# forgotten, so the test stops demanding that it keep shrinking.
CONVERGENCE_NOISE_FLOOR = 1e-9
RANDOM_SEEDS = (0, 7, 42, 2026)
RANDOM_BAR_COUNT = 600


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


def paired_reference_candles(count: int = 300) -> list[Candle]:
    """Build the reference-symbol series used by the paired TA-Lib captures."""

    candles: list[Candle] = []
    previous_close = 180.0
    start = datetime(2025, 1, 1, tzinfo=UTC)
    for index in range(count):
        drift = math.sin(index / 7.0) * 2.2 - math.cos(index / 13.0) * 1.1
        close = previous_close + drift + (index % 5) * 0.35 - 0.55
        open_time = start + timedelta(hours=index)
        candles.append(
            Candle(
                symbol="ETH/USDT:USDT",
                exchange="binance",
                timeframe="1h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open=previous_close,
                high=max(previous_close, close) + 0.9,
                low=min(previous_close, close) - 0.9,
                close=close,
                volume=150.0 + (index % 11) * 7.0,
                quote_volume=None,
                trade_count=None,
            )
        )
        previous_close = close
    return candles


def _random_candles(
    generator: random.Random,
    *,
    count: int,
    symbol: str,
    initial_close: float,
) -> list[Candle]:
    candles: list[Candle] = []
    start = datetime(2025, 1, 1, tzinfo=UTC)
    previous_close = initial_close
    for index in range(count):
        open_price = previous_close
        close = max(1.0, open_price + generator.uniform(-2.0, 2.0))
        high = max(open_price, close) + generator.uniform(0.01, 1.5)
        low = min(open_price, close) - generator.uniform(0.01, 1.5)
        open_time = start + timedelta(hours=index)
        candles.append(
            Candle(
                symbol=symbol,
                exchange="BINANCE",
                timeframe="1h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=generator.uniform(1.0, 10_000.0),
                quote_volume=None,
                trade_count=None,
            )
        )
        previous_close = close
    return candles


def random_candles(seed: int, count: int = RANDOM_BAR_COUNT) -> list[Candle]:
    """Build the seeded stream used by every single-series parity test."""
    return _random_candles(
        random.Random(seed),
        count=count,
        symbol="BTCUSDT",
        initial_close=100.0,
    )


def paired_random_candles(
    seed: int,
    count: int = RANDOM_BAR_COUNT,
) -> tuple[list[Candle], list[Candle]]:
    """Build primary/reference streams from one seeded generator."""
    generator = random.Random(seed)
    primary = _random_candles(
        generator,
        count=count,
        symbol="BTCUSDT",
        initial_close=100.0,
    )
    reference = _random_candles(
        generator,
        count=count,
        symbol="ETHUSDT",
        initial_close=180.0,
    )
    return primary, reference
