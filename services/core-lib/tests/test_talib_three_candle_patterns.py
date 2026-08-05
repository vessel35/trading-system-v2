"""Assert the TA-Lib three-candle pattern ports match captured TA-Lib bars."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from math import isnan

import pytest
from core_lib.patterns.outputs import output_keys
from core_lib.patterns.talib_raw import (
    TalibPatternPort,
    resolve_talib_penetration,
    sparse_talib_integer_signals,
)
from core_lib.patterns.talib_three_candle import (
    TALIB_THREE_CANDLE_BY_FUNCTION,
    TALIB_THREE_CANDLE_BY_NAME,
    TALIB_THREE_CANDLE_PATTERNS,
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


def _warmup_candles(count: int = 10) -> list[Candle]:
    candles: list[Candle] = []
    for index in range(count):
        open_price = 80.0 + index * 0.2
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


def _with_replacement(candles: list[Candle], index: int, candle: Candle) -> list[Candle]:
    updated = list(candles)
    updated[index] = candle
    return updated


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


def _captured_total(talib_function: str) -> int:
    return sum(len(SIGNALS[regime][talib_function]) for regime in REGIME_NAMES)


def _captured_values(talib_function: str) -> set[int]:
    values: set[int] = set()
    for regime in REGIME_NAMES:
        values.update(SIGNALS[regime][talib_function].values())
    return values


def _two_crows_candles() -> list[Candle]:
    candles = _warmup_candles()
    candles.append(_make_candle(10, 100.0, 105.5, 99.5, 105.0))
    candles.append(_make_candle(11, 108.0, 108.5, 105.5, 106.0))
    candles.append(_make_candle(12, 107.0, 107.5, 102.5, 103.0))
    return candles


def _three_black_crows_candles() -> list[Candle]:
    candles = _warmup_candles()
    candles.append(_make_candle(10, 100.0, 110.0, 99.5, 105.0))
    candles.append(_make_candle(11, 104.0, 104.1, 99.99, 100.0))
    candles.append(_make_candle(12, 103.0, 103.1, 98.99, 99.0))
    candles.append(_make_candle(13, 102.0, 102.1, 97.99, 98.0))
    return candles


def _three_stars_in_the_south_candles() -> list[Candle]:
    candles = _warmup_candles()
    candles.append(_make_candle(10, 100.0, 101.0, 87.0, 94.0))
    candles.append(_make_candle(11, 96.0, 97.0, 92.5, 93.0))
    candles.append(_make_candle(12, 95.0, 95.1, 94.1, 94.2))
    return candles


def _three_white_soldiers_candles() -> list[Candle]:
    candles = _warmup_candles()
    candles.append(_make_candle(10, 100.0, 103.05, 99.5, 103.0))
    candles.append(_make_candle(11, 101.5, 104.05, 101.0, 104.0))
    candles.append(_make_candle(12, 102.5, 105.55, 102.0, 105.5))
    return candles


def _abandoned_baby_top_candles() -> list[Candle]:
    candles = _warmup_candles()
    candles.append(_make_candle(10, 100.0, 110.5, 99.5, 110.0))
    candles.append(_make_candle(11, 113.0, 113.5, 112.5, 113.0))
    candles.append(_make_candle(12, 111.0, 112.0, 105.5, 106.0))
    return candles


def _identical_three_crows_candles() -> list[Candle]:
    candles = _warmup_candles()
    candles.append(_make_candle(10, 105.0, 105.5, 99.99, 100.0))
    candles.append(_make_candle(11, 100.0, 100.5, 94.99, 95.0))
    candles.append(_make_candle(12, 95.0, 95.5, 89.99, 90.0))
    return candles


def _upside_gap_two_crows_candles() -> list[Candle]:
    candles = _warmup_candles()
    candles.append(_make_candle(10, 100.0, 105.5, 99.5, 105.0))
    candles.append(_make_candle(11, 108.0, 108.5, 107.0, 107.3))
    candles.append(_make_candle(12, 109.0, 109.5, 106.0, 106.5))
    return candles


@_NEEDS_CAPTURE
@pytest.mark.parametrize(
    "pattern", TALIB_THREE_CANDLE_PATTERNS, ids=lambda item: item.talib_function
)
@pytest.mark.parametrize("regime", REGIME_NAMES)
def test_talib_three_candle_port_matches_capture(
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


def test_talib_three_candle_outputs_keep_four_key_warmup_contract() -> None:
    candles = candles_for("quiet_small_bodies")
    for pattern in TALIB_THREE_CANDLE_PATTERNS:
        keys = set(output_keys(pattern.name))
        values = pattern.compute_vectorized(candles)
        assert len(values) == len(candles)
        for index, value in enumerate(values):
            assert set(value) == keys
            if index < pattern.lookback:
                assert all(isnan(number) for number in value.values())
            else:
                assert all(not isnan(number) for number in value.values())


def test_talib_three_candle_lookbacks_match_source() -> None:
    assert TALIB_THREE_CANDLE_BY_FUNCTION["CDL3BLACKCROWS"].lookback == 13
    assert TALIB_THREE_CANDLE_BY_FUNCTION["CDL3OUTSIDE"].lookback == 3

    for talib_function, pattern in TALIB_THREE_CANDLE_BY_FUNCTION.items():
        if talib_function not in {"CDL3BLACKCROWS", "CDL3OUTSIDE"}:
            assert pattern.lookback == 12


def test_three_candle_penetration_defaults_stay_pattern_specific() -> None:
    assert resolve_talib_penetration("CDLDARKCLOUDCOVER") == 0.5
    for talib_function in (
        "CDLABANDONEDBABY",
        "CDLEVENINGDOJISTAR",
        "CDLEVENINGSTAR",
        "CDLMORNINGDOJISTAR",
        "CDLMORNINGSTAR",
    ):
        assert resolve_talib_penetration(talib_function) == 0.3


@_NEEDS_CAPTURE
def test_three_candle_capture_sparse_branches_are_explicit() -> None:
    assert _captured_total("CDL3BLACKCROWS") == 0
    assert _captured_total("CDL3STARSINSOUTH") == 0
    assert _captured_total("CDL3WHITESOLDIERS") == 0

    assert _captured_total("CDLABANDONEDBABY") == 3
    assert _captured_values("CDLABANDONEDBABY") == {100}

    assert _captured_total("CDL2CROWS") == 12
    assert _captured_total("CDLIDENTICAL3CROWS") == 1
    assert _captured_total("CDLUPSIDEGAP2CROWS") == 8


@pytest.mark.parametrize(
    ("pattern_name", "candles", "expected"),
    (
        ("pat_three_black_crows", _three_black_crows_candles(), -100),
        ("pat_three_stars_in_the_south", _three_stars_in_the_south_candles(), 100),
        ("pat_three_white_soldiers", _three_white_soldiers_candles(), 100),
        ("pat_abandoned_baby", _abandoned_baby_top_candles(), -100),
        ("pat_two_crows", _two_crows_candles(), -100),
        ("pat_identical_three_crows", _identical_three_crows_candles(), -100),
        ("pat_upside_gap_two_crows", _upside_gap_two_crows_candles(), -100),
    ),
)
def test_handmade_three_candle_inputs_cover_sparse_positive_branches(
    pattern_name: str,
    candles: list[Candle],
    expected: int,
) -> None:
    pattern = TALIB_THREE_CANDLE_BY_NAME[pattern_name]

    assert len(candles) >= pattern.min_history
    assert pattern.compute_integers(candles)[-1] == expected


def test_three_black_crows_handmade_input_reads_the_prior_white_candle() -> None:
    candles = _three_black_crows_candles()
    prior = candles[10]
    broken = _with_replacement(
        candles,
        10,
        replace(prior, open=105.0, high=110.0, low=99.5, close=100.0),
    )

    assert TALIB_THREE_CANDLE_BY_NAME["pat_three_black_crows"].compute_integers(broken)[-1] == 0


def test_three_stars_in_south_handmade_input_uses_shadow_long_zero_period() -> None:
    candles = _three_stars_in_the_south_candles()
    first = candles[10]
    broken = _with_replacement(candles, 10, replace(first, low=91.0))

    assert (
        TALIB_THREE_CANDLE_BY_NAME["pat_three_stars_in_the_south"].compute_integers(broken)[-1] == 0
    )


def test_three_white_soldiers_handmade_input_requires_short_upper_shadows() -> None:
    candles = _three_white_soldiers_candles()
    third = candles[12]
    broken = _with_replacement(candles, 12, replace(third, high=107.0))

    assert TALIB_THREE_CANDLE_BY_NAME["pat_three_white_soldiers"].compute_integers(broken)[-1] == 0


def test_abandoned_baby_handmade_input_covers_negative_penetration_branch() -> None:
    candles = _abandoned_baby_top_candles()
    third = candles[12]
    broken = _with_replacement(candles, 12, replace(third, low=107.5, close=108.0))

    pattern = TALIB_THREE_CANDLE_BY_NAME["pat_abandoned_baby"]
    assert pattern.compute_integers(candles)[-1] == -100
    assert pattern.compute_integers(broken)[-1] == 0
