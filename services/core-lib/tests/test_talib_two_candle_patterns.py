"""Assert the TA-Lib two-candle pattern ports match captured TA-Lib bars."""

from datetime import UTC, datetime, timedelta

import pytest
from core_lib.patterns.talib_raw import (
    TalibPatternPort,
    sparse_talib_integer_signals,
)
from core_lib.patterns.talib_two_candle import (
    TALIB_TWO_CANDLE_BY_FUNCTION,
    TALIB_TWO_CANDLE_BY_NAME,
    TALIB_TWO_CANDLE_PATTERNS,
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


def _warmup_candles() -> list[Candle]:
    candles: list[Candle] = []
    for index in range(10):
        open_price = 100.0 + index * 0.1
        close = open_price + 1.0 if index % 2 == 0 else open_price - 1.0
        candles.append(
            _make_candle(
                index,
                open_price=open_price,
                high=max(open_price, close) + 0.5,
                low=min(open_price, close) - 0.5,
                close=close,
            )
        )
    return candles


def _kicking_candles(
    previous: tuple[float, float, float, float],
    current: tuple[float, float, float, float],
) -> list[Candle]:
    candles = _warmup_candles()
    candles.append(_make_candle(10, *previous))
    candles.append(_make_candle(11, *current))
    return candles


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
@pytest.mark.parametrize("pattern", TALIB_TWO_CANDLE_PATTERNS, ids=lambda item: item.talib_function)
@pytest.mark.parametrize("regime", REGIME_NAMES)
def test_talib_two_candle_port_matches_capture(
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


def test_talib_two_candle_lookbacks_match_source() -> None:
    assert TALIB_TWO_CANDLE_BY_FUNCTION["CDLENGULFING"].lookback == 2
    assert TALIB_TWO_CANDLE_BY_FUNCTION["CDLMATCHINGLOW"].lookback == 6

    for pattern in TALIB_TWO_CANDLE_PATTERNS:
        if pattern.talib_function not in {"CDLENGULFING", "CDLMATCHINGLOW"}:
            assert pattern.lookback == 11


@_NEEDS_CAPTURE
def test_kicking_captures_are_mutually_silent() -> None:
    for regime in REGIME_NAMES:
        assert SIGNALS[regime]["CDLKICKING"] == {}
        assert SIGNALS[regime]["CDLKICKINGBYLENGTH"] == {}


def test_kicking_handmade_positive_inputs_cover_both_signs() -> None:
    bullish = _kicking_candles(
        (100.0, 100.05, 94.95, 95.0),
        (106.0, 111.05, 105.95, 111.0),
    )
    bearish = _kicking_candles(
        (100.0, 105.05, 99.95, 105.0),
        (94.0, 94.05, 88.95, 89.0),
    )
    pattern = TALIB_TWO_CANDLE_BY_NAME["pat_kicking"]

    assert pattern.compute_integers(bullish)[-1] == 100
    assert pattern.compute_integers(bearish)[-1] == -100


def test_kicking_by_length_uses_longer_body_and_source_tie_break() -> None:
    current_longer = _kicking_candles(
        (100.0, 100.05, 94.95, 95.0),
        (106.0, 112.05, 105.95, 112.0),
    )
    equal_lengths = _kicking_candles(
        (100.0, 100.05, 94.95, 95.0),
        (106.0, 111.05, 105.95, 111.0),
    )
    by_length = TALIB_TWO_CANDLE_BY_NAME["pat_kicking_by_length"]
    kicking = TALIB_TWO_CANDLE_BY_NAME["pat_kicking"]

    assert by_length.compute_integers(current_longer)[-1] == 100
    assert kicking.compute_integers(equal_lengths)[-1] == 100
    assert by_length.compute_integers(equal_lengths)[-1] == -100
