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


def test_trend_values_do_not_change_when_the_candles_after_them_are_removed() -> None:
    """A value at bar t must be the same whether or not bar t+1 exists yet.

    None of the trend indicators shifts a value onto another bar, so the way a
    look-ahead would appear here is a window or a chain reaching past its own bar.
    Cutting the series at a bar and recomputing answers that directly: if anything
    later fed the value, the truncated series produces a different one. The
    incremental path is structurally causal already, so this covers the batch path
    that the parity tests compare it against.
    """

    candles = make_candles(260)
    for spec in DEFAULT_REGISTRY.list():
        if spec.category != "trend":
            continue
        full = spec.compute_vectorized(candles)
        for cut in (spec.min_history, spec.min_history + 7, len(candles)):
            if cut > len(candles):
                continue
            truncated = spec.compute_vectorized(candles[:cut])
            assert len(truncated) == cut
            assert_value_equal(full[cut - 1], truncated[cut - 1])


def test_t3_with_a_zero_volume_factor_is_the_third_link_of_its_own_chain() -> None:
    """§1.3's expanded coefficients collapse to ``c4 = 1`` when the factor is zero.

    Written out, ``c1``, ``c2`` and ``c3`` all carry a factor of the volume factor
    while ``c4`` reduces to one, so T3 must become the third EMA of its chain and
    nothing else. What that pins is the constant term of ``c4`` and which link of
    the chain the sum is anchored on; the three factor-carrying constants vanish
    here and are covered instead by the comparison against TA-Lib's T3.
    """

    candles = make_candles(120)
    period = 12
    chain = [candle.close for candle in candles]
    for _ in range(3):
        chain = primitives.ema(chain, period)

    for index, value in enumerate(trend.t3(candles, period, 0.0)):
        if isnan(value):
            continue
        assert value == pytest.approx(chain[index])


def test_hma_smooths_over_the_rounded_square_root_of_its_period() -> None:
    """§1.4 rounds the square root of the period, and nothing else pins that.

    The registered combination uses a period of 9, whose square root is exactly 3,
    so rounding, flooring and ceiling all agree there and the convention is never
    exercised by it. The periods below are chosen because they disagree, and they
    disagree in both directions: at 21, 32 and 45 the rounded window is one wider
    than a floored one, while at 20 and 50 it is one narrower than a ceiling. A
    later change to either neighbour therefore fails here.

    The direction matters in practice. Tulip Indicators truncates this window,
    which is why our HMA at period 21 sits 1.50e-01, 1.65e+00 and 4.54e-01 away
    from Tulip's at bars 100, 200 and 299 of the reference series, with the gap
    holding rather than closing. That is the standard and that library genuinely
    disagreeing, and §1.4 is the one this repository follows. It is also why the
    registered period is compared against Tulip in `indicator_reference/trend.py`
    while this test carries the convention that comparison cannot reach.
    """

    candles = make_candles(200)
    closes = [candle.close for candle in candles]

    for period, expected_window in ((20, 4), (21, 5), (32, 6), (45, 7), (50, 7)):
        assert expected_window == round(sqrt(period))
        fast = primitives.wma(closes, period // 2)
        slow = primitives.wma(closes, period)
        lead = [
            primitives.NAN if isnan(quick) or isnan(steady) else 2.0 * quick - steady
            for quick, steady in zip(fast, slow, strict=True)
        ]

        produced = trend.hma(candles, period)
        for expected, actual in zip(primitives.wma(lead, expected_window), produced, strict=True):
            assert_scalar_equal(expected, actual)

        # The warm-up is stated a second time, on the incremental state, and has to
        # round the same way the calculation does.
        assert trend.HMAState(period=period).min_history == period + expected_window - 1

        # Without this the assertion above could hold for a window the standard did
        # not ask for, if the neighbouring windows happened to produce the same
        # series. They do not, and the failure names which neighbour collided.
        for neighbour in (expected_window - 1, expected_window + 1):
            other = primitives.wma(lead, neighbour)
            assert any(
                not isnan(one) and not isnan(two) and not isclose(one, two, rel_tol=1e-12)
                for one, two in zip(produced, other, strict=True)
            ), f"period {period}: window {neighbour} is indistinguishable from {expected_window}"


def test_zlema_removes_the_whole_lag_of_a_straight_line() -> None:
    """§1.5 exists to cancel the delay, and on a straight line it cancels all of it.

    An EMA of a line settles exactly ``(n - 1) / 2`` bars behind it, which is the
    lag §1.5 subtracts. For an odd period the correction is that number exactly, so
    the average has to converge onto the current price rather than trail it.
    """

    candles = make_linear_candles(300)
    values = trend.zlema(candles, 21)
    assert values[-1] == pytest.approx(candles[-1].close, abs=1e-6)


def test_alma_leans_on_the_recent_side_of_its_window() -> None:
    """§1.6's weights are positive and its offset of 0.85 sits past the middle.

    Two things follow without recomputing the kernel. Positive weights normalized
    by their own sum cannot leave the window's range, and a peak at ``0.85 * (n-1)``
    puts more mass on the newer bars than a flat window does, so on a rising line
    the result has to sit above the simple average of the same bars. The second
    part is what fails if the weights are laid against the window backwards.
    """

    candles = make_linear_candles(60)
    closes = [candle.close for candle in candles]
    averages = primitives.sma(closes, 9)

    for index, value in enumerate(trend.alma(candles, 9, 0.85, 6.0)):
        if isnan(value):
            continue
        window = closes[index - 8 : index + 1]
        assert min(window) <= value <= max(window)
        assert value > averages[index]


def test_vidya_becomes_a_plain_ema_when_momentum_is_saturated() -> None:
    """§1.8's ``k`` reaches one exactly when §2.8's CMO reaches 100.

    A series that only rises has no losses, so CMO is 100 at every bar past its
    window and ``k`` is one. The recursion is then ``alpha * P + (1 - alpha) *
    previous``, which is §0.3's EMA over the same period and the same seed. Tying
    the two together checks the division by 100 and the alpha at once: an unscaled
    ``k`` would overshoot instead of matching.
    """

    candles = make_linear_candles(120)
    expected = trend.ema(candles, 21)

    for index, value in enumerate(trend.vidya(candles, 21, 9)):
        if isnan(value):
            continue
        assert value == pytest.approx(expected[index])


def test_mcginley_divisor_slows_the_average_when_price_runs_ahead() -> None:
    """§1.9 puts the price-to-average ratio in the divisor, which is its whole point.

    Above the average the ratio exceeds one, so the divisor exceeds the period and
    the step is smaller than a plain ``1 / N`` step; below it the divisor shrinks
    and the step is larger. Checking the direction on both sides is what an
    exponent of the wrong sign would break.
    """

    candles = make_candles(120)
    closes = [candle.close for candle in candles]
    period = 21
    values = trend.mcginley_dynamic(candles, period)

    compared = 0
    for index in range(1, len(values)):
        previous, current = values[index - 1], values[index]
        if isnan(previous) or isnan(current):
            continue
        price = closes[index]
        step = abs(current - previous)
        plain = abs(price - previous) / period
        if price > previous:
            assert step < plain
        elif price < previous:
            assert step > plain
        else:
            assert current == previous
        compared += 1
    assert compared > 0


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
