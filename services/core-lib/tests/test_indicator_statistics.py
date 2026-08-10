"""Pin the paired statistics registrations and their TA-Lib input order."""

from dataclasses import replace

import pytest
from core_lib.indicators import statistics
from core_lib.indicators.registry import DEFAULT_REGISTRY
from core_lib.series import PairedSeriesState
from core_lib.types import Candle

from indicator_reference import (
    RANDOM_BAR_COUNT,
    RANDOM_SEEDS,
    paired_random_candles,
    paired_reference_candles,
    reference_candles,
)
from indicator_reference.statistics_talib import (
    BAR_COUNT,
    LOOKBACKS,
    OUTPUTS,
    TA_LIB_VERSION,
)


def _flat_reference_candles(count: int) -> list[Candle]:
    return [
        replace(
            candle,
            symbol="ETH/USDT:USDT",
            open=180.0,
            high=180.0,
            low=180.0,
            close=180.0,
        )
        for candle in reference_candles(count)
    ]


def test_beta_and_correl_are_registered_as_paired_statistics() -> None:
    expected = {
        "BETA(period=5)": (6, statistics.BetaState),
        "CORREL(period=30)": (30, statistics.CorrelState),
    }

    assert len(DEFAULT_REGISTRY.list()) == 93
    for identifier, (min_history, state_type) in expected.items():
        name = identifier.split("(", 1)[0]
        period = 5 if name == "BETA" else 30
        spec = DEFAULT_REGISTRY.get(name, {"period": period})
        state = spec.make_paired_state()
        assert spec.identifier == identifier
        assert spec.category == "statistics"
        assert spec.needs_reference_series is True
        assert spec.min_history == min_history
        assert isinstance(state, state_type)
        assert isinstance(state, PairedSeriesState)


def test_beta_uses_reference_as_x_and_primary_as_y() -> None:
    primary = reference_candles()
    reference = paired_reference_candles()

    expected = -2.7042317660836295
    actual = statistics.beta(primary, reference, period=5)[299]
    swapped = statistics.beta(reference, primary, period=5)[299]

    assert actual == pytest.approx(expected, rel=1e-9, abs=1e-9)
    assert swapped == pytest.approx(-0.368444721906708, rel=1e-9, abs=1e-9)
    assert swapped != pytest.approx(expected, rel=1e-9, abs=1e-9)


def test_correl_is_symmetric_even_though_the_engine_order_is_fixed() -> None:
    primary = reference_candles()
    reference = paired_reference_candles()

    actual = statistics.correl(primary, reference, period=30)[299]
    swapped = statistics.correl(reference, primary, period=30)[299]

    assert actual == pytest.approx(0.4588834235110546, rel=1e-9, abs=1e-9)
    assert swapped == pytest.approx(actual, rel=1e-12, abs=1e-12)


def test_beta_returns_talib_zero_when_reference_returns_have_zero_variance() -> None:
    primary = reference_candles(6)
    reference = _flat_reference_candles(6)
    reference_returns = [
        (current.close - previous.close) / previous.close
        for previous, current in zip(reference[:-1], reference[1:], strict=True)
    ]
    denominator = len(reference_returns) * sum(value * value for value in reference_returns)
    denominator -= sum(reference_returns) ** 2

    assert denominator == 0.0
    # TA-Lib 0.7.1 returns 0.0 for this zero-denominator input.
    assert statistics.beta(primary, reference, period=5)[-1] == 0.0


def test_correl_returns_talib_zero_when_reference_prices_have_zero_variance() -> None:
    primary = reference_candles(30)
    reference = _flat_reference_candles(30)
    reference_mean = sum(candle.close for candle in reference) / len(reference)
    reference_variance = sum((candle.close - reference_mean) ** 2 for candle in reference)
    primary_mean = sum(candle.close for candle in primary) / len(primary)
    primary_variance = sum((candle.close - primary_mean) ** 2 for candle in primary)

    assert reference_variance * primary_variance == 0.0
    # TA-Lib 0.7.1 returns 0.0 for this zero-denominator input.
    assert statistics.correl(primary, reference, period=30)[-1] == 0.0


@pytest.mark.parametrize(("name", "period"), (("BETA", 5), ("CORREL", 30)))
@pytest.mark.parametrize("seed", RANDOM_SEEDS)
def test_paired_statistics_match_talib_over_entire_seeded_stream(
    name: str,
    period: int,
    seed: int,
) -> None:
    assert TA_LIB_VERSION.startswith("0.7.1 ")
    assert BAR_COUNT == RANDOM_BAR_COUNT
    assert set(OUTPUTS) == {"BETA", "CORREL"}
    assert set(OUTPUTS[name]) == set(RANDOM_SEEDS)

    primary, reference = paired_random_candles(seed)
    state = DEFAULT_REGISTRY.get(name, {"period": period}).make_paired_state()
    actual = [
        state.update(candle, reference_candle)
        for candle, reference_candle in zip(primary, reference, strict=True)
    ]
    lookback = LOOKBACKS[name]
    expected = OUTPUTS[name][seed]

    assert len(actual[lookback:]) == len(expected)
    for index, (actual_value, expected_value) in enumerate(
        zip(actual[lookback:], expected, strict=True),
        start=lookback,
    ):
        assert actual_value == pytest.approx(expected_value, rel=1e-12, abs=1e-11), (
            f"{name} seed {seed} differs from TA-Lib 0.7.1 at candle {index}"
        )


@pytest.mark.parametrize("name,period", (("BETA", 5), ("CORREL", 30)))
def test_paired_statistics_reject_the_single_series_batch_path(name: str, period: int) -> None:
    spec = DEFAULT_REGISTRY.get(name, {"period": period})

    with pytest.raises(TypeError, match="requires a reference series"):
        spec.compute_vectorized(reference_candles())
