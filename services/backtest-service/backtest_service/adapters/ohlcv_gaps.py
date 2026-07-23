"""Encode the explicit, non-interpolating OHLCV gap Evidence contract."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from core_lib.types import Candle

from .evidence_schema import canonical_json

OHLCV_GAP_CONTRACT: Final = "ohlcv-gap-v1"
_TIMEFRAME: Final = re.compile(r"^(?P<count>[1-9]\d*)(?P<unit>[mhd])$")
_TIMEFRAME_MS: Final = {"m": 60_000, "h": 3_600_000, "d": 86_400_000}
_NOTE_KEYS: Final = {
    "contract",
    "normal_gap_count",
    "normal_gap_close_times",
    "evaluation_grid_gap_count",
    "evaluation_grid_gap_close_times",
}


def timeframe_milliseconds(timeframe: str) -> int:
    """Return the exact duration for a supported Evidence candle timeframe."""
    match = _TIMEFRAME.fullmatch(timeframe)
    if match is None:
        raise ValueError(f"unsupported timeframe: {timeframe!r}")
    return _TIMEFRAME_MS[match.group("unit")] * int(match.group("count"))


def _epoch_milliseconds(value: datetime, *, name: str) -> int:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return int(value.astimezone(UTC).timestamp() * 1_000)


def _strict_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _strict_timestamp_tuple(value: object, *, name: str) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    result = tuple(
        _strict_int(item, name=f"{name} item")
        for item in value
    )
    if any(left >= right for left, right in zip(result, result[1:], strict=False)):
        raise ValueError(f"{name} must be strictly increasing")
    return result


@dataclass(frozen=True, slots=True)
class OhlcvGapContract:
    """Exact source gaps and the subset omitted from the evaluation grid."""

    normal_gap_close_times: tuple[int, ...]
    evaluation_grid_gap_close_times: tuple[int, ...]

    @property
    def normal_gap_count(self) -> int:
        """Return the number of absent source candles in the snapshot range."""
        return len(self.normal_gap_close_times)

    @property
    def evaluation_grid_gap_count(self) -> int:
        """Return the number of declared gaps inside the evaluation grid."""
        return len(self.evaluation_grid_gap_close_times)

    def encode(self) -> str:
        """Return canonical JSON suitable for SOURCE_DATA_SNAPSHOT.note."""
        return canonical_json(
            {
                "contract": OHLCV_GAP_CONTRACT,
                "normal_gap_count": self.normal_gap_count,
                "normal_gap_close_times": list(self.normal_gap_close_times),
                "evaluation_grid_gap_count": self.evaluation_grid_gap_count,
                "evaluation_grid_gap_close_times": list(
                    self.evaluation_grid_gap_close_times
                ),
            }
        )


def build_ohlcv_gap_contract(
    candles: Sequence[Candle],
    *,
    timeframe: str,
    range_start: datetime,
    range_end: datetime,
    evaluation_start: datetime,
    evaluation_end: datetime,
) -> OhlcvGapContract:
    """Derive absent candle closes without manufacturing candle values."""
    duration = timeframe_milliseconds(timeframe)
    range_start_ms = _epoch_milliseconds(range_start, name="range_start")
    range_end_ms = _epoch_milliseconds(range_end, name="range_end")
    evaluation_start_ms = _epoch_milliseconds(
        evaluation_start,
        name="evaluation_start",
    )
    evaluation_end_ms = _epoch_milliseconds(evaluation_end, name="evaluation_end")
    span = range_end_ms - range_start_ms
    evaluation_span = evaluation_end_ms - evaluation_start_ms
    if span <= 0 or span % duration:
        raise ValueError("OHLCV snapshot range must align to its timeframe")
    if evaluation_span <= 0 or evaluation_span % duration:
        raise ValueError("OHLCV evaluation range must align to its timeframe")
    if not (
        range_start_ms <= evaluation_start_ms
        and evaluation_end_ms <= range_end_ms
    ):
        raise ValueError("OHLCV snapshot range must cover the evaluation range")

    actual: set[int] = set()
    for candle in candles:
        if candle.timeframe != timeframe:
            raise ValueError("OHLCV snapshot contains a different timeframe")
        close_time = _epoch_milliseconds(candle.close_time, name="candle.close_time")
        if not range_start_ms < close_time <= range_end_ms:
            raise ValueError("OHLCV snapshot candle falls outside its declared range")
        if (close_time - range_start_ms) % duration:
            raise ValueError("OHLCV snapshot candle is off the declared grid")
        if close_time in actual:
            raise ValueError("OHLCV snapshot contains a duplicate close time")
        actual.add(close_time)

    normal_gaps = tuple(
        close_time
        for close_time in range(range_start_ms + duration, range_end_ms + 1, duration)
        if close_time not in actual
    )
    evaluation_gaps = tuple(
        close_time
        for close_time in range(
            evaluation_start_ms + duration,
            evaluation_end_ms + 1,
            duration,
        )
        if close_time not in actual
    )
    return OhlcvGapContract(normal_gaps, evaluation_gaps)


def decode_ohlcv_gap_contract(note: str) -> OhlcvGapContract:
    """Parse and validate a canonical OHLCV gap note fail-closed."""
    try:
        raw = json.loads(note)
    except json.JSONDecodeError as error:
        raise ValueError("OHLCV gap note must be valid JSON") from error
    if not isinstance(raw, dict) or set(raw) != _NOTE_KEYS:
        raise ValueError("OHLCV gap note has an unexpected shape")
    if raw["contract"] != OHLCV_GAP_CONTRACT:
        raise ValueError("OHLCV gap note has an unsupported contract")
    normal_gaps = _strict_timestamp_tuple(
        raw["normal_gap_close_times"],
        name="normal_gap_close_times",
    )
    evaluation_gaps = _strict_timestamp_tuple(
        raw["evaluation_grid_gap_close_times"],
        name="evaluation_grid_gap_close_times",
    )
    normal_count = _strict_int(raw["normal_gap_count"], name="normal_gap_count")
    evaluation_count = _strict_int(
        raw["evaluation_grid_gap_count"],
        name="evaluation_grid_gap_count",
    )
    if normal_count != len(normal_gaps) or normal_count < 0:
        raise ValueError("OHLCV normal gap count does not match its timestamps")
    if evaluation_count != len(evaluation_gaps) or evaluation_count < 0:
        raise ValueError("OHLCV evaluation gap count does not match its timestamps")
    if not set(evaluation_gaps) <= set(normal_gaps):
        raise ValueError("OHLCV evaluation gaps must be normal source gaps")
    contract = OhlcvGapContract(normal_gaps, evaluation_gaps)
    if contract.encode() != note:
        raise ValueError("OHLCV gap note must use canonical JSON")
    return contract
