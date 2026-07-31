"""Hold the volatility indicators to the substitute each one names for a zero divisor.

Three sections of the standard divide by a quantity that a perfectly flat window drives
to zero, and none of the three names what to return there. §0.11 says the choice belongs
to the indicator, so each of them states one in its `pinned_impl`, and the value has to
follow from what that indicator measures rather than from one number applied to all
three. Because these outputs are single numbers rather than named sets, the backtest
engine cannot be told to tolerate a NaN in them: `_assert_finite_indicator` skips only
named keys, so a NaN here would stop a run. That is what makes the substitute part of
the contract rather than a detail, and what this file exists to hold in place.

The registered combinations are read from the registry so that this checks what a run
would actually execute, and both execution paths are checked, since a substitute that
lived in only one of them would be a parity failure waiting for a flat market.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest
from core_lib.indicators.registry import DEFAULT_REGISTRY, IndicatorValue
from core_lib.types import Candle


def flat_candles(count: int) -> list[Candle]:
    """Build a stream whose high, low, and close never move."""
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


def both_paths(name: str, params: dict[str, float | int], count: int) -> list[IndicatorValue]:
    """Return the last value from the batch path and from the incremental one."""
    spec = DEFAULT_REGISTRY.get(name, params)
    candles: Sequence[Candle] = flat_candles(count)
    state = spec.make_state()
    for candle in candles:
        state.update(candle)
    return [spec.compute_vectorized(candles)[-1], state.current()]


def test_relative_volatility_index_reads_a_still_market_as_the_midpoint() -> None:
    """§3.7 is a 0-100 oscillator, and no volatility either way leans neither way.

    Both smoothed deviations reach zero together, so the share §3.7 asks for has a zero
    denominator. The indicator is bounded, and the balanced reading of a bounded share
    is its midpoint, which is the same answer §2.2 Stochastic already gives a collapsed
    range in this repository.
    """

    for value in both_paths(
        "Relative Volatility Index", {"period": 14, "deviation_period": 10}, 80
    ):
        assert value == pytest.approx(50.0)


def test_chaikin_volatility_reads_a_still_market_as_no_change() -> None:
    """§3.8 is a rate of change, and no volatility to no volatility is no change."""

    for value in both_paths("Chaikin Volatility", {"period": 10}, 60):
        assert value == pytest.approx(0.0)


def test_mass_index_reads_a_still_market_as_its_own_window_length() -> None:
    """§3.9 sums a ratio of two smoothings of one quantity, and that ratio is one here.

    Numerator and denominator are smoothings of the same range series, so a window of
    zero ranges makes them equal rather than merely both zero. Summing a ratio of one
    over twenty-five bars gives twenty-five, which is where the reversal thresholds §3.9
    names, 27 and 26.5, sit relative to.
    """

    for value in both_paths("Mass Index", {"period": 9, "sum_period": 25}, 100):
        assert value == pytest.approx(25.0)


def test_ulcer_index_reads_a_still_market_as_no_drawdown() -> None:
    """§3.6 measures depth below the window's highest close, and there is none."""

    for value in both_paths("Ulcer Index", {"period": 14}, 60):
        assert value == pytest.approx(0.0)


def test_every_volatility_output_stays_finite_on_a_flat_stream() -> None:
    """No volatility output may go non-finite where the registry has not said it may.

    This is the engine's own rule, stated once here over the whole category: a value
    the registry has not listed in `undefined_outputs` must be finite after warm-up, and
    a flat market is where these indicators come closest to breaking it.
    """

    candles = flat_candles(120)
    for spec in DEFAULT_REGISTRY.list():
        if spec.category != "volatility":
            continue
        state = spec.make_state()
        for candle in candles:
            state.update(candle)
        value = state.current()
        named = value.items() if isinstance(value, dict) else ((None, value),)
        for key, item in named:
            if key is not None and key in spec.undefined_outputs:
                continue
            assert item == item, f"{spec.identifier}{'' if key is None else '.' + key} is NaN"
            assert abs(item) != float("inf"), f"{spec.identifier} is infinite"
