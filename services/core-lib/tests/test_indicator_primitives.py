"""Verify the calculation authority's complete shared primitive layer."""

from datetime import UTC, datetime, timedelta
from math import isnan

import pytest
from core_lib.indicators.primitives import (
    CumulativeState,
    EmaState,
    RmaState,
    RocState,
    RollingExtremeState,
    SmaState,
    StdevState,
    cumulative,
    ema,
    hh,
    hl2,
    hlcc4,
    linreg,
    ll,
    mom,
    ohlc4,
    rma,
    roc,
    safe_divide,
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


def test_price_inputs_follow_the_standard_definitions() -> None:
    """§0.1 fixes four price derivations; each is exactly one formula."""

    candles = [make_candle(0, open_price=10.0, high=14.0, low=6.0, close=12.0)]
    assert hl2(candles) == [10.0]
    assert tp(candles) == [pytest.approx((14.0 + 6.0 + 12.0) / 3.0)]
    assert hlcc4(candles) == [pytest.approx((14.0 + 6.0 + 2.0 * 12.0) / 4.0)]
    assert ohlc4(candles) == [pytest.approx((10.0 + 14.0 + 6.0 + 12.0) / 4.0)]


def test_momentum_is_the_raw_difference_and_roc_is_its_percentage() -> None:
    """§0.10 defines ROC as a percentage and MOM as the same span unscaled."""

    values = [10.0, 11.0, 12.0, 15.0]
    assert isnan(mom(values, 2)[1])
    assert mom(values, 2)[2] == pytest.approx(2.0)
    assert mom(values, 2)[3] == pytest.approx(4.0)
    assert roc(values, 2)[2] == pytest.approx(100.0 * 2.0 / 10.0)


def test_safe_divide_requires_the_caller_to_name_the_zero_substitute() -> None:
    """§0.11 leaves the substitute to each indicator, so it stays explicit."""

    assert safe_divide(1.0, 2.0, on_zero=0.0) == pytest.approx(0.5)
    assert safe_divide(5.0, 0.0, on_zero=100.0) == 100.0
    assert isnan(safe_divide(float("nan"), 2.0, on_zero=0.0))
    with pytest.raises(ValueError, match="reserved for warm-up"):
        safe_divide(1.0, 0.0, on_zero=float("nan"))


def _feed(state: object, values: list[float]) -> list[float]:
    return [state.update(value) for value in values]  # type: ignore[attr-defined]


def test_incremental_primitives_match_their_vectorized_form() -> None:
    """The two paths of every primitive must agree value for value.

    This is the same contract the indicator parity test enforces one layer up.
    Holding it at the primitive layer is what makes it safe for indicator states
    to compose these instead of restating each recursion.
    """

    values = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0, 5.0, 3.0, 5.0, 8.0]
    period = 4

    for state, expected in (
        (SmaState(period), sma(values, period)),
        (EmaState(period), ema(values, period)),
        (RmaState(period), rma(values, period)),
        (StdevState(period), stdev(values, period)),
        (RollingExtremeState(period, highest=True), hh(values, period)),
        (RollingExtremeState(period, highest=False), ll(values, period)),
        (CumulativeState(), cumulative(values)),
        (RocState(period), roc(values, period)),
    ):
        produced = _feed(state, values)
        assert len(produced) == len(expected)
        for index, (left, right) in enumerate(zip(produced, expected, strict=True)):
            if isnan(right):
                assert isnan(left), f"{type(state).__name__} index {index} should be NaN"
            else:
                assert left == pytest.approx(right), f"{type(state).__name__} index {index}"


def test_incremental_primitives_reset_returns_them_to_warm_up() -> None:
    """A reset state must behave exactly like a fresh one."""

    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    for state in (
        SmaState(3),
        EmaState(3),
        RmaState(3),
        StdevState(3),
        RollingExtremeState(3, highest=True),
        CumulativeState(),
        RocState(3),
    ):
        _feed(state, values)
        state.reset()
        assert not state.warmed_up
        assert isnan(state.current())


def test_incremental_momentum_state_can_drop_the_percentage() -> None:
    """RocState carries the raw MOM form the standard names as a part."""

    values = [10.0, 11.0, 12.0, 15.0]
    state = RocState(2, percentage=False)
    assert _feed(state, values)[3] == pytest.approx(4.0)
