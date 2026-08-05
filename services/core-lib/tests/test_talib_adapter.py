"""Verify the TA-Lib raw-integer to four-key adapter contract."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest
from core_lib.patterns.outputs import (
    BOUNDARY_STRENGTH,
    FULL_STRENGTH,
    MATCHED,
    NOT_MATCHED,
    output_keys,
)
from core_lib.patterns.talib_hikkake import (
    TALIB_HIKKAKE_BY_FUNCTION,
    TALIB_HIKKAKE_PATTERNS,
    TalibStatefulPatternPort,
)
from core_lib.patterns.talib_multi_candle import TALIB_MULTI_CANDLE_PATTERNS
from core_lib.patterns.talib_raw import (
    TALIB_RAW_ALLOWED_VALUES,
    TalibPatternPort,
    outputs_from_talib_integer,
    talib_integer_from_outputs,
)
from core_lib.patterns.talib_single_candle import TALIB_SINGLE_CANDLE_PATTERNS
from core_lib.patterns.talib_three_candle import TALIB_THREE_CANDLE_PATTERNS
from core_lib.patterns.talib_two_candle import TALIB_TWO_CANDLE_PATTERNS
from core_lib.types import Candle

TalibDirectPort = TalibPatternPort | TalibStatefulPatternPort
Ohlc = tuple[float, float, float, float]

_ADAPTER_TEST_NAME = "pat_talib_adapter_probe"
_ALL_TALIB_PORTS: tuple[TalibDirectPort, ...] = (
    *TALIB_SINGLE_CANDLE_PATTERNS,
    *TALIB_TWO_CANDLE_PATTERNS,
    *TALIB_THREE_CANDLE_PATTERNS,
    *TALIB_MULTI_CANDLE_PATTERNS,
    *TALIB_HIKKAKE_PATTERNS,
)


def _shape(
    *,
    matched: float,
    direction: float,
    strength: float,
    confirmed: float,
) -> dict[str, float]:
    return dict(
        zip(
            output_keys(_ADAPTER_TEST_NAME),
            (matched, direction, strength, confirmed),
            strict=True,
        )
    )


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


def _candles(rows: Sequence[Ohlc]) -> list[Candle]:
    return [_make_candle(index, *row) for index, row in enumerate(rows)]


def _warmup_rows(count: int) -> list[Ohlc]:
    return [(100.0 + index, 103.0 + index, 97.0 + index, 101.0 + index) for index in range(count)]


def _hikkake_bullish_confirmation_candles() -> list[Candle]:
    return _candles(
        (
            (100.0, 120.0, 100.0, 110.0),
            (110.0, 115.0, 105.0, 111.0),
            (106.0, 114.0, 104.0, 107.0),
            (107.0, 113.0, 103.0, 110.0),
            (110.0, 114.0, 104.0, 111.0),
            (111.0, 121.0, 110.0, 121.0),
        )
    )


def _hikkake_bearish_confirmation_candles() -> list[Candle]:
    return _candles(
        (
            (100.0, 120.0, 100.0, 110.0),
            (110.0, 115.0, 105.0, 111.0),
            (116.0, 116.0, 106.0, 115.0),
            (115.0, 116.0, 106.0, 110.0),
            (110.0, 117.0, 107.0, 111.0),
            (107.0, 108.0, 103.0, 104.0),
        )
    )


def _hikkakemod_bullish_confirmation_candles() -> list[Candle]:
    return _candles(
        (
            *_warmup_rows(7),
            (110.0, 120.0, 100.0, 112.0),
            (106.0, 115.0, 105.0, 105.8),
            (107.0, 114.0, 106.0, 109.0),
            (105.0, 113.0, 104.0, 108.0),
            (114.0, 116.0, 112.0, 115.0),
        )
    )


def _hikkakemod_bearish_confirmation_candles() -> list[Candle]:
    return _candles(
        (
            *_warmup_rows(7),
            (110.0, 120.0, 100.0, 112.0),
            (114.0, 115.0, 105.0, 114.5),
            (110.0, 114.0, 106.0, 109.0),
            (112.0, 116.0, 107.0, 115.0),
            (105.0, 107.0, 104.0, 105.0),
        )
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    (
        (0, (0.0, 0.0, 0.0, 0.0)),
        (80, (1.0, 1.0, 0.5, 0.0)),
        (-80, (1.0, -1.0, 0.5, 0.0)),
        (100, (1.0, 1.0, 1.0, 0.0)),
        (-100, (1.0, -1.0, 1.0, 0.0)),
        (200, (0.0, 1.0, 0.0, 1.0)),
        (-200, (0.0, -1.0, 0.0, 1.0)),
    ),
)
def test_outputs_from_talib_integer_uses_the_adapter_table(
    raw: int,
    expected: tuple[float, float, float, float],
) -> None:
    output = outputs_from_talib_integer(_ADAPTER_TEST_NAME, raw)

    assert tuple(output[key] for key in output_keys(_ADAPTER_TEST_NAME)) == expected


def test_all_sixty_one_talib_adapter_values_round_trip_source_allowed_raw_values() -> None:
    checked = 0

    assert len(_ALL_TALIB_PORTS) == 61
    assert len(TALIB_RAW_ALLOWED_VALUES) == 7
    for pattern in _ALL_TALIB_PORTS:
        for raw in sorted(TALIB_RAW_ALLOWED_VALUES):
            output = outputs_from_talib_integer(pattern.name, raw)

            assert talib_integer_from_outputs(pattern.name, output) == raw
            checked += 1

    assert checked == 427


def test_talib_integer_from_outputs_keeps_all_nan_warmup_as_no_integer() -> None:
    warmup = _shape(
        matched=float("nan"),
        direction=float("nan"),
        strength=float("nan"),
        confirmed=float("nan"),
    )

    assert talib_integer_from_outputs(_ADAPTER_TEST_NAME, warmup) is None


@pytest.mark.parametrize(
    "value",
    (
        pytest.param(
            _shape(
                matched=MATCHED,
                direction=1.0,
                strength=FULL_STRENGTH,
                confirmed=MATCHED,
            ),
            id="match-and-confirm-together",
        ),
        pytest.param(
            _shape(
                matched=MATCHED,
                direction=NOT_MATCHED,
                strength=FULL_STRENGTH,
                confirmed=NOT_MATCHED,
            ),
            id="matched-without-direction",
        ),
        pytest.param(
            _shape(
                matched=NOT_MATCHED,
                direction=NOT_MATCHED,
                strength=NOT_MATCHED,
                confirmed=MATCHED,
            ),
            id="confirmed-without-direction",
        ),
        pytest.param(
            _shape(
                matched=NOT_MATCHED,
                direction=1.0,
                strength=NOT_MATCHED,
                confirmed=NOT_MATCHED,
            ),
            id="unmatched-with-direction",
        ),
        pytest.param(
            _shape(
                matched=MATCHED,
                direction=1.0,
                strength=NOT_MATCHED,
                confirmed=NOT_MATCHED,
            ),
            id="matched-without-strength",
        ),
        pytest.param(
            _shape(
                matched=NOT_MATCHED,
                direction=1.0,
                strength=BOUNDARY_STRENGTH,
                confirmed=MATCHED,
            ),
            id="confirmation-with-strength",
        ),
        pytest.param(
            _shape(
                matched=float("nan"),
                direction=NOT_MATCHED,
                strength=NOT_MATCHED,
                confirmed=NOT_MATCHED,
            ),
            id="partial-nan",
        ),
    ),
)
def test_talib_integer_from_outputs_rejects_non_adapter_shapes(
    value: dict[str, float],
) -> None:
    with pytest.raises(ValueError):
        talib_integer_from_outputs(_ADAPTER_TEST_NAME, value)


@pytest.mark.parametrize(
    ("talib_function", "candles", "confirmation_index", "expected"),
    (
        ("CDLHIKKAKE", _hikkake_bullish_confirmation_candles(), 5, 200),
        ("CDLHIKKAKE", _hikkake_bearish_confirmation_candles(), 5, -200),
        ("CDLHIKKAKEMOD", _hikkakemod_bullish_confirmation_candles(), 11, 200),
        ("CDLHIKKAKEMOD", _hikkakemod_bearish_confirmation_candles(), 11, -200),
    ),
)
def test_hikkake_confirmations_preserve_direction_in_adapter_outputs(
    talib_function: str,
    candles: list[Candle],
    confirmation_index: int,
    expected: int,
) -> None:
    pattern = TALIB_HIKKAKE_BY_FUNCTION[talib_function]
    match_key, direction_key, strength_key, confirm_key = output_keys(pattern.name)
    output = pattern.compute_vectorized(candles)[confirmation_index]

    assert pattern.compute_integers(candles)[confirmation_index] == expected
    assert output[match_key] == NOT_MATCHED
    assert output[direction_key] == (1.0 if expected > 0 else -1.0)
    assert output[strength_key] == NOT_MATCHED
    assert output[confirm_key] == MATCHED
    assert talib_integer_from_outputs(pattern.name, output) == expected
