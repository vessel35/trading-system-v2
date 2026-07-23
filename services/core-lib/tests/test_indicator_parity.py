"""Prove vectorized and O(1) incremental required indicators are identical."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from math import isclose, isnan, sin, sqrt

import pytest
from core_lib.indicators import momentum, volatility, volume
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


@pytest.mark.parametrize("period", [9, 21, 55, 200])
def test_ema_vectorized_incremental_parity(period: int) -> None:
    assert_parity(DEFAULT_REGISTRY.get("EMA", {"period": period}), make_candles())


def test_rsi_vectorized_incremental_parity() -> None:
    assert_parity(DEFAULT_REGISTRY.get("RSI", {"period": 14}), make_candles())


def test_stochastic_vectorized_incremental_parity() -> None:
    assert_parity(
        DEFAULT_REGISTRY.get("Stochastic", {"period": 14, "smooth_period": 3}),
        make_candles(),
    )


def test_atr_vectorized_incremental_parity() -> None:
    assert_parity(DEFAULT_REGISTRY.get("ATR", {"period": 14}), make_candles())


def test_bollinger_vectorized_incremental_parity() -> None:
    assert_parity(
        DEFAULT_REGISTRY.get("Bollinger Bands", {"period": 20, "multiplier": 2.0}),
        make_candles(),
    )


def test_volume_sma_vectorized_incremental_parity() -> None:
    assert_parity(DEFAULT_REGISTRY.get("Volume SMA", {"period": 20}), make_candles())


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
    ("name", "params"),
    [
        ("EMA", {"period": 9}),
        ("EMA", {"period": 21}),
        ("EMA", {"period": 55}),
        ("EMA", {"period": 200}),
        ("RSI", {"period": 14}),
        ("Stochastic", {"period": 14, "smooth_period": 3}),
        ("ATR", {"period": 14}),
        ("Bollinger Bands", {"period": 20, "multiplier": 2.0}),
        ("Volume SMA", {"period": 20}),
    ],
)
def test_min_history_and_seed_warmup(
    name: str,
    params: dict[str, int | float],
) -> None:
    spec = DEFAULT_REGISTRY.get(name, params)
    candles = make_candles(spec.min_history + 1)
    state = spec.make_state()
    state.seed(candles[: spec.min_history - 1])
    assert not bool(state.warmed_up)
    state.update(candles[spec.min_history - 1])
    assert bool(state.warmed_up)
    expected = spec.compute_vectorized(candles[: spec.min_history])[-1]
    assert_value_equal(expected, state.current())
