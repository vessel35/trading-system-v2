"""Prove vectorized and O(1) incremental required indicators are identical."""

import random
import statistics
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from math import isclose, isnan, sin, sqrt

import pytest
from core_lib.indicators import momentum, primitives, trend, volatility, volume
from core_lib.indicators.primitives import stdev
from core_lib.indicators.registry import (
    DEFAULT_REGISTRY,
    IndicatorSeries,
    IndicatorSpec,
    IndicatorValue,
)
from core_lib.types import Candle


def make_candles(count: int = 260) -> list[Candle]:
    candles: list[Candle] = []
    start = datetime(2025, 1, 1, tzinfo=UTC)
    previous_close = 100.0
    for index in range(count):
        open_price = previous_close
        close = 100.0 + 0.15 * index + 2.5 * sin(index / 5.0)
        high = max(open_price, close) + 1.0 + 0.1 * (index % 4)
        low = min(open_price, close) - 1.0 - 0.1 * (index % 3)
        open_time = start + timedelta(hours=index)
        candles.append(
            Candle(
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe="1h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=1000.0 + 17.0 * (index % 11) + index,
                quote_volume=None,
                trade_count=None,
            )
        )
        previous_close = close
    return candles


def make_linear_candles(count: int) -> list[Candle]:
    candles: list[Candle] = []
    start = datetime(2025, 1, 1, tzinfo=UTC)
    for index in range(count):
        close = 10.0 + index
        open_time = start + timedelta(hours=index)
        candles.append(
            Candle(
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe="1h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open=close,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=1.0 + index,
                quote_volume=None,
                trade_count=None,
            )
        )
    return candles


def make_random_candles(seed: int, count: int = 600) -> list[Candle]:
    """Build a long reproducible OHLCV stream for every warm-up length."""
    generator = random.Random(seed)
    candles: list[Candle] = []
    start = datetime(2025, 1, 1, tzinfo=UTC)
    previous_close = 100.0
    for index in range(count):
        open_price = previous_close
        close = max(1.0, open_price + generator.uniform(-2.0, 2.0))
        high = max(open_price, close) + generator.uniform(0.01, 1.5)
        low = min(open_price, close) - generator.uniform(0.01, 1.5)
        open_time = start + timedelta(hours=index)
        candles.append(
            Candle(
                symbol="BTCUSDT",
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


def make_flat_candles(count: int = 600) -> list[Candle]:
    """Build a zero-range stream that exercises flat-window branches."""
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        Candle(
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe="1h",
            open_time=start + timedelta(hours=index),
            close_time=start + timedelta(hours=index + 1),
            open=100.0,
            high=100.0,
            low=100.0,
            close=100.0,
            volume=1_000.0,
            quote_volume=None,
            trade_count=None,
        )
        for index in range(count)
    ]


def make_declining_candles(count: int = 600) -> list[Candle]:
    """Build a loss-only close stream so RSI reaches AvgGain=0."""
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        Candle(
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe="1h",
            open_time=start + timedelta(hours=index),
            close_time=start + timedelta(hours=index + 1),
            open=1_000.0 - index,
            high=1_000.5 - index,
            low=998.5 - index,
            close=999.0 - index,
            volume=1_000.0 + index,
            quote_volume=None,
            trade_count=None,
        )
        for index in range(count)
    ]


def make_large_price_candles(count: int = 120) -> list[Candle]:
    """Build large prices with representable millipoint-scale movement."""
    start = datetime(2025, 1, 1, tzinfo=UTC)
    closes = [100_000_000.0 + (index % 37) * 0.001 + index * 0.000001 for index in range(count)]
    return [
        Candle(
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe="1h",
            open_time=start + timedelta(hours=index),
            close_time=start + timedelta(hours=index + 1),
            open=close,
            high=close + 0.01,
            low=close - 0.01,
            close=close,
            volume=1_000.0,
            quote_volume=None,
            trade_count=None,
        )
        for index, close in enumerate(closes)
    ]


def assert_scalar_equal(expected: float, actual: float) -> None:
    if isnan(expected):
        assert isnan(actual)
    else:
        assert isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)


def assert_value_equal(expected: IndicatorValue, actual: IndicatorValue) -> None:
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        assert actual.keys() == expected.keys()
        for key, value in expected.items():
            assert_scalar_equal(value, actual[key])
    else:
        assert isinstance(actual, float)
        assert_scalar_equal(expected, actual)


def assert_parity(spec: IndicatorSpec, candles: Sequence[Candle]) -> None:
    vectorized: IndicatorSeries = spec.compute_vectorized(candles)
    state = spec.make_state()
    incremental = [state.update(candle) for candle in candles]
    assert len(vectorized) == len(incremental)
    for expected, actual in zip(vectorized, incremental, strict=True):
        assert_value_equal(expected, actual)


ALL_REGISTERED_SPECS = DEFAULT_REGISTRY.list()


@pytest.mark.parametrize("spec", ALL_REGISTERED_SPECS, ids=lambda spec: spec.identifier)
@pytest.mark.parametrize("seed", [0, 7, 42, 2026])
def test_all_registered_indicators_match_on_long_seeded_random_streams(
    spec: IndicatorSpec,
    seed: int,
) -> None:
    assert_parity(spec, make_random_candles(seed))


@pytest.mark.parametrize("spec", ALL_REGISTERED_SPECS, ids=lambda spec: spec.identifier)
def test_all_registered_indicators_match_on_flat_streams(spec: IndicatorSpec) -> None:
    assert_parity(spec, make_flat_candles())


def test_rsi_avg_gain_zero_branch_has_full_series_parity() -> None:
    candles = make_declining_candles()
    spec = DEFAULT_REGISTRY.get("RSI", {"period": 14})
    assert_parity(spec, candles)
    assert spec.compute_vectorized(candles)[-1] == 0.0


def test_large_price_tiny_variation_stdev_and_bollinger_are_stable() -> None:
    candles = make_large_price_candles()
    closes = [candle.close for candle in candles]
    period = 20
    first_window = closes[:period]
    expected_first = statistics.pstdev(first_window)
    old_one_pass_variance = (
        sum(value * value for value in first_window) / period - (sum(first_window) / period) ** 2
    )
    assert old_one_pass_variance == 0.0
    assert expected_first > 0.0

    deviations = stdev(closes, period)
    assert deviations[period - 1] == pytest.approx(expected_first, abs=1e-7)
    assert deviations[-1] == pytest.approx(
        statistics.pstdev(closes[-period:]),
        abs=1e-7,
    )

    spec = DEFAULT_REGISTRY.get(
        "Bollinger Bands",
        {"period": period, "multiplier": 2.0},
    )
    assert_parity(spec, candles)
    last = spec.compute_vectorized(candles)[-1]
    assert isinstance(last, dict)
    assert (last["upper"] - last["lower"]) / 4.0 == pytest.approx(
        statistics.pstdev(closes[-period:]),
        abs=1e-7,
    )


def test_required_indicators_match_authority_reference_values() -> None:
    candles = make_linear_candles(20)
    assert momentum.rsi(candles[:15], 14)[-1] == 100.0
    assert volatility.atr(candles[:14], 14)[-1] == pytest.approx(2.0)
    stochastic = momentum.stochastic(candles[:16], 14, 3)[-1]
    assert stochastic == pytest.approx(
        {"percent_k": 100.0 * 14.0 / 15.0, "percent_d": 100.0 * 14.0 / 15.0}
    )
    bands = volatility.bollinger_bands(candles, 20, 2.0)[-1]
    assert bands["middle"] == pytest.approx(19.5)
    assert bands["upper"] == pytest.approx(19.5 + 2.0 * sqrt(33.25))
    assert volume.volume_sma(candles, 20)[-1] == pytest.approx(10.5)


@pytest.mark.parametrize(
    "identifier",
    [spec.identifier for spec in DEFAULT_REGISTRY.list()],
)
def test_min_history_and_seed_warmup(identifier: str) -> None:
    """Every registered combination warms up exactly at its declared minimum.

    The list comes from the registry itself, so registering an indicator without
    a working warm-up cannot slip through by being left off a hand-written list.
    """

    spec = next(
        candidate for candidate in DEFAULT_REGISTRY.list() if candidate.identifier == identifier
    )
    candles = make_candles(spec.min_history + 1)
    state = spec.make_state()
    state.seed(candles[: spec.min_history - 1])
    assert not bool(state.warmed_up)
    state.update(candles[spec.min_history - 1])
    assert bool(state.warmed_up)
    expected = spec.compute_vectorized(candles[: spec.min_history])[-1]
    assert_value_equal(expected, state.current())


def test_wave_one_indicators_satisfy_their_standard_relations() -> None:
    """Check each new indicator against a relation its own section states.

    These are not a second implementation of the same formula; each assertion is
    a property the standard writes down separately from the calculation, so a
    transcription error shows up as a broken relation rather than as two wrong
    numbers agreeing with each other.
    """

    candles = make_candles(120)

    # §2.4: the histogram is defined as the distance between line and signal.
    for macd_value in momentum.macd(candles, 12, 26, 9):
        if isnan(macd_value["macd"]) or isnan(macd_value["signal"]):
            continue
        assert macd_value["histogram"] == pytest.approx(macd_value["macd"] - macd_value["signal"])

    # §1.1: DEMA is 2*EMA1 - EMA2 over the same period.
    closes = [candle.close for candle in candles]
    first = primitives.ema(closes, 21)
    second = primitives.ema(first, 21)
    for index, dema_value in enumerate(trend.dema(candles, 21)):
        if isnan(dema_value):
            continue
        assert dema_value == pytest.approx(2.0 * first[index] - second[index])

    # §2.12: the oscillator is the gap between two median-price averages.
    median = primitives.hl2(candles)
    fast = primitives.sma(median, 5)
    slow = primitives.sma(median, 34)
    for index, oscillator_value in enumerate(momentum.awesome_oscillator(candles, 5, 34)):
        if isnan(oscillator_value):
            continue
        assert oscillator_value == pytest.approx(fast[index] - slow[index])

    # §2.7: the index is a ratio of two smoothings of the same series, so it
    # cannot leave the range the ratio allows.
    for tsi_value in momentum.tsi(candles, 25, 13):
        if not isnan(tsi_value):
            assert -100.0 <= tsi_value <= 100.0


def test_accumulation_distribution_follows_the_stated_degenerate_rule() -> None:
    """§4.2 states H = L keeps the multiplier at zero, so the line holds still."""

    candles = make_candles(10)
    flat = Candle(
        symbol=candles[-1].symbol,
        exchange=candles[-1].exchange,
        timeframe=candles[-1].timeframe,
        open_time=candles[-1].open_time,
        close_time=candles[-1].close_time,
        open=100.0,
        high=100.0,
        low=100.0,
        close=100.0,
        volume=1_000.0,
        quote_volume=None,
        trade_count=None,
    )
    series = volume.ad_line([*candles, flat])
    assert series[-1] == pytest.approx(series[-2])


def test_cci_reads_a_deviation_free_window_as_zero() -> None:
    """§2.10 gives no substitute for a zero mean deviation; this repo reads it as 0."""

    base = make_candles(25)
    flat = [
        Candle(
            symbol=candle.symbol,
            exchange=candle.exchange,
            timeframe=candle.timeframe,
            open_time=candle.open_time,
            close_time=candle.close_time,
            open=50.0,
            high=50.0,
            low=50.0,
            close=50.0,
            volume=candle.volume,
            quote_volume=None,
            trade_count=None,
        )
        for candle in base
    ]
    assert momentum.cci(flat, 20)[-1] == 0.0
