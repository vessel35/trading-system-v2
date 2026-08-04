"""Assert the first TA-Lib single-candle pattern ports match captured TA-Lib bars."""

from datetime import UTC, datetime, timedelta
from math import isnan

import pytest
from core_lib.patterns.outputs import output_keys
from core_lib.patterns.talib_single_candle import (
    TALIB_SINGLE_CANDLE_BY_NAME,
    TALIB_SINGLE_CANDLE_PATTERNS,
    TalibPatternPort,
    sparse_talib_integer_signals,
    talib_integer_from_outputs,
)
from core_lib.types import Candle

from pattern_reference import (
    CAPTURE_INSTRUCTIONS,
    CAPTURED,
    REGIME_NAMES,
    REGIMES_BY_NAME,
    SIGNALS,
    candles_for,
)

_NEEDS_CAPTURE = pytest.mark.skipif(not CAPTURED, reason=CAPTURE_INSTRUCTIONS)


def _make_candle(index: int, open_price: float, high: float, low: float, close: float) -> Candle:
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
        volume=1000.0,
        quote_volume=None,
        trade_count=None,
    )


def _first_mismatch(
    actual: dict[int, int],
    expected: dict[int, int],
    bar_count: int,
) -> tuple[int, int, int] | None:
    for index in range(bar_count):
        actual_value = actual.get(index, 0)
        expected_value = expected.get(index, 0)
        if actual_value != expected_value:
            return index, actual_value, expected_value
    return None


@_NEEDS_CAPTURE
@pytest.mark.parametrize(
    "pattern", TALIB_SINGLE_CANDLE_PATTERNS, ids=lambda item: item.talib_function
)
@pytest.mark.parametrize("regime", REGIME_NAMES)
def test_talib_single_candle_port_matches_capture(
    pattern: TalibPatternPort,
    regime: str,
) -> None:
    """Every captured TA-Lib value matches on the same bar with the same sign and size."""
    actual = sparse_talib_integer_signals(
        pattern.name,
        pattern.compute_vectorized(candles_for(regime)),
    )
    expected = dict(SIGNALS[regime][pattern.talib_function])

    mismatch = _first_mismatch(actual, expected, REGIMES_BY_NAME[regime].bar_count)
    assert mismatch is None, (
        f"{pattern.talib_function} diverged on {regime} at bar {mismatch[0]}: "
        f"actual={mismatch[1]}, expected={mismatch[2]}"
    )
    assert actual == expected


def test_talib_single_candle_outputs_keep_four_key_warmup_contract() -> None:
    """The TA-Lib ports still expose the repository's four-key output shape."""
    candles = candles_for("quiet_small_bodies")
    for pattern in TALIB_SINGLE_CANDLE_PATTERNS:
        keys = set(output_keys(pattern.name))
        values = pattern.compute_vectorized(candles)
        assert len(values) == len(candles)
        for index, value in enumerate(values):
            assert set(value) == keys
            if index < pattern.lookback:
                assert all(isnan(number) for number in value.values())
            else:
                assert all(not isnan(number) for number in value.values())


def test_talib_color_treats_equal_open_close_as_white() -> None:
    """TA-Lib's candle color is white when close equals open."""
    warmup = [
        _make_candle(index, open_price=100.0, high=102.0, low=99.0, close=101.0)
        for index in range(10)
    ]
    target = _make_candle(10, open_price=100.0, high=102.0, low=98.0, close=100.0)
    pattern = TALIB_SINGLE_CANDLE_BY_NAME["pat_spinning_top"]
    output = pattern.compute_vectorized([*warmup, target])[-1]

    assert output["pat_spinning_top"] == 1.0
    assert output["pat_spinning_top_dir"] == 1.0
    assert talib_integer_from_outputs("pat_spinning_top", output) == 100
