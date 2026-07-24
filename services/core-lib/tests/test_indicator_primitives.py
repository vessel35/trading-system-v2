"""Verify the calculation authority's complete shared primitive layer."""

from datetime import UTC, datetime, timedelta
from math import isnan

import pytest
from core_lib.indicators.primitives import (
    cumulative,
    ema,
    hh,
    linreg,
    ll,
    rma,
    roc,
    sma,
    stdev,
    tp,
    tr,
    wma,
)
from core_lib.types import Candle


def make_candle(
    index: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> Candle:
    open_time = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=index)
    return Candle(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe="1h",
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=10.0,
        quote_volume=None,
        trade_count=None,
    )


def test_moving_average_seed_and_weight_rules() -> None:
    assert isnan(sma([1.0, 2.0, 3.0], 2)[0])
    assert sma([1.0, 2.0, 3.0], 2)[1:] == pytest.approx([1.5, 2.5])
    assert ema([1.0, 2.0, 3.0, 5.0], 3)[2:] == pytest.approx([2.0, 3.5])
    assert rma([1.0, 2.0, 3.0, 6.0], 3)[2:] == pytest.approx([2.0, 10.0 / 3.0])
    assert wma([1.0, 2.0, 3.0], 3)[2] == pytest.approx(14.0 / 6.0)


def test_price_true_range_and_typical_price() -> None:
    candles = [
        make_candle(0, open_price=9.0, high=10.0, low=8.0, close=9.0),
        make_candle(1, open_price=12.0, high=13.0, low=11.0, close=12.0),
    ]
    assert tr(candles) == pytest.approx([2.0, 4.0])
    assert tp(candles) == pytest.approx([9.0, 12.0])


def test_population_stdev_extremes_and_cumulative() -> None:
    deviations = stdev([1.0, 2.0, 3.0], 2)
    assert isnan(deviations[0])
    assert deviations[1:] == pytest.approx([0.5, 0.5])
    assert hh([1.0, 3.0, 2.0], 2)[1:] == pytest.approx([3.0, 3.0])
    assert ll([1.0, 3.0, 2.0], 2)[1:] == pytest.approx([1.0, 2.0])
    assert cumulative([1.0, -2.0, 4.0]) == pytest.approx([1.0, -1.0, 3.0])


def test_roc_and_linear_regression_forecast() -> None:
    changes = roc([10.0, 12.0, 15.0], 1)
    assert isnan(changes[0])
    assert changes[1:] == pytest.approx([20.0, 25.0])
    forecasts = linreg([1.0, 3.0, 5.0, 7.0], 3)
    assert isnan(forecasts[0]) and isnan(forecasts[1])
    assert forecasts[2:] == pytest.approx([5.0, 7.0])


def test_periods_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        ema([1.0], 0)
    with pytest.raises(ValueError, match="positive"):
        rma([1.0], 0)
