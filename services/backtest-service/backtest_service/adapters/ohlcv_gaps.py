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

OHLCV_GAP_CONTRACT: Final = "ohlcv-gap-v2"
_TIMEFRAME: Final = re.compile(r"^(?P<count>[1-9]\d*)(?P<unit>[mhd])$")
_TIMEFRAME_MS: Final = {"m": 60_000, "h": 3_600_000, "d": 86_400_000}
_MINUTE_MS: Final = 60_000
_ORIGIN_STATUSES: Final = {"verified", "fixture_unverified"}
_NOTE_KEYS: Final = {
    "contract",
    "timeframe_ms",
    "normal_gap_count",
    "normal_gap_ranges",
    "partial_bucket_count",
    "partial_bucket_ranges",
    "evaluation_grid_gap_count",
    "evaluation_grid_gap_ranges",
    "origin_validation_status",
    "origin_minute_row_count",
    "origin_timestamp_hash",
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


def _encode_ranges(values: tuple[int, ...], duration: int) -> list[list[int]]:
    ranges: list[list[int]] = []
    for value in values:
        if ranges and value == ranges[-1][0] + ranges[-1][1] * duration:
            ranges[-1][1] += 1
        else:
            ranges.append([value, 1])
    return ranges


def _decode_ranges(value: object, *, name: str, duration: int) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    result: list[int] = []
    for index, item in enumerate(value):
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError(f"{name}[{index}] must be [first_timestamp, count]")
        first = _strict_int(item[0], name=f"{name}[{index}][0]")
        count = _strict_int(item[1], name=f"{name}[{index}][1]")
        if count <= 0:
            raise ValueError(f"{name}[{index}] count must be positive")
        result.extend(first + offset * duration for offset in range(count))
    if any(left >= right for left, right in zip(result, result[1:], strict=False)):
        raise ValueError(f"{name} must encode strictly increasing timestamps")
    return tuple(result)


@dataclass(frozen=True, slots=True)
class OhlcvGapContract:
    """Classify source absence separately from incomplete resampling buckets."""

    timeframe_ms: int
    normal_gap_close_times: tuple[int, ...]
    partial_bucket_close_times: tuple[int, ...]
    evaluation_grid_gap_close_times: tuple[int, ...]
    origin_validation_status: str
    origin_minute_row_count: int
    origin_timestamp_hash: str | None

    @property
    def normal_gap_count(self) -> int:
        """Return buckets for which every underlying minute is absent."""
        return len(self.normal_gap_close_times)

    @property
    def partial_bucket_count(self) -> int:
        """Return discarded buckets with only some underlying minutes present."""
        return len(self.partial_bucket_close_times)

    @property
    def snapshot_gap_count(self) -> int:
        """Return all omitted buckets in the snapshot range."""
        return self.normal_gap_count + self.partial_bucket_count

    @property
    def evaluation_grid_gap_count(self) -> int:
        """Return all omitted buckets inside the evaluation grid."""
        return len(self.evaluation_grid_gap_close_times)

    def encode(self) -> str:
        """Return compact canonical JSON suitable for SOURCE_DATA_SNAPSHOT.note."""
        return canonical_json(
            {
                "contract": OHLCV_GAP_CONTRACT,
                "timeframe_ms": self.timeframe_ms,
                "normal_gap_count": self.normal_gap_count,
                "normal_gap_ranges": _encode_ranges(
                    self.normal_gap_close_times, self.timeframe_ms
                ),
                "partial_bucket_count": self.partial_bucket_count,
                "partial_bucket_ranges": _encode_ranges(
                    self.partial_bucket_close_times, self.timeframe_ms
                ),
                "evaluation_grid_gap_count": self.evaluation_grid_gap_count,
                "evaluation_grid_gap_ranges": _encode_ranges(
                    self.evaluation_grid_gap_close_times, self.timeframe_ms
                ),
                "origin_validation_status": self.origin_validation_status,
                "origin_minute_row_count": self.origin_minute_row_count,
                "origin_timestamp_hash": self.origin_timestamp_hash,
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
    minute_gap_close_times: Sequence[int] | None = None,
    origin_validation_status: str = "fixture_unverified",
    origin_minute_row_count: int = 0,
    origin_timestamp_hash: str | None = None,
) -> OhlcvGapContract:
    """Derive gaps and classify them without manufacturing candle values."""
    duration = timeframe_milliseconds(timeframe)
    range_start_ms = _epoch_milliseconds(range_start, name="range_start")
    range_end_ms = _epoch_milliseconds(range_end, name="range_end")
    evaluation_start_ms = _epoch_milliseconds(evaluation_start, name="evaluation_start")
    evaluation_end_ms = _epoch_milliseconds(evaluation_end, name="evaluation_end")
    span = range_end_ms - range_start_ms
    evaluation_span = evaluation_end_ms - evaluation_start_ms
    if span <= 0 or span % duration:
        raise ValueError("OHLCV snapshot range must align to its timeframe")
    if evaluation_span <= 0 or evaluation_span % duration:
        raise ValueError("OHLCV evaluation range must align to its timeframe")
    if not (range_start_ms <= evaluation_start_ms and evaluation_end_ms <= range_end_ms):
        raise ValueError("OHLCV snapshot range must cover the evaluation range")
    if origin_validation_status not in _ORIGIN_STATUSES:
        raise ValueError("unsupported origin validation status")
    if origin_minute_row_count < 0:
        raise ValueError("origin minute row count must be non-negative")
    if (origin_validation_status == "verified") != (origin_timestamp_hash is not None):
        raise ValueError("verified origin requires a timestamp hash, fixtures must omit it")

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

    omitted = tuple(
        close_time
        for close_time in range(range_start_ms + duration, range_end_ms + 1, duration)
        if close_time not in actual
    )
    if duration == _MINUTE_MS:
        normal_gaps = omitted
        partial_buckets: tuple[int, ...] = ()
    else:
        if minute_gap_close_times is None:
            raise ValueError("resampled OHLCV gaps require the 1m gap contract")
        minute_gaps = set(minute_gap_close_times)
        normal: list[int] = []
        partial: list[int] = []
        minute_count = duration // _MINUTE_MS
        for close_time in omitted:
            missing = sum(
                close_time - duration + offset * _MINUTE_MS in minute_gaps
                for offset in range(1, minute_count + 1)
            )
            if missing == minute_count:
                normal.append(close_time)
            elif missing:
                partial.append(close_time)
            else:
                raise ValueError(
                    "resampler omitted a bucket whose complete 1m origin exists"
                )
        normal_gaps = tuple(normal)
        partial_buckets = tuple(partial)

    evaluation_omitted = tuple(
        close_time
        for close_time in omitted
        if evaluation_start_ms < close_time <= evaluation_end_ms
    )
    return OhlcvGapContract(
        duration,
        normal_gaps,
        partial_buckets,
        evaluation_omitted,
        origin_validation_status,
        origin_minute_row_count,
        origin_timestamp_hash,
    )


def decode_ohlcv_gap_contract(note: str) -> OhlcvGapContract:
    """Parse and validate a compact canonical OHLCV gap note fail-closed."""
    try:
        raw = json.loads(note)
    except json.JSONDecodeError as error:
        raise ValueError("OHLCV gap note must be valid JSON") from error
    if not isinstance(raw, dict) or set(raw) != _NOTE_KEYS:
        raise ValueError("OHLCV gap note has an unexpected shape")
    if raw["contract"] != OHLCV_GAP_CONTRACT:
        raise ValueError("OHLCV gap note has an unsupported contract")
    duration = _strict_int(raw["timeframe_ms"], name="timeframe_ms")
    if duration <= 0 or duration % _MINUTE_MS:
        raise ValueError("timeframe_ms must be a positive whole minute")
    normal = _decode_ranges(raw["normal_gap_ranges"], name="normal_gap_ranges", duration=duration)
    partial = _decode_ranges(
        raw["partial_bucket_ranges"], name="partial_bucket_ranges", duration=duration
    )
    evaluation = _decode_ranges(
        raw["evaluation_grid_gap_ranges"],
        name="evaluation_grid_gap_ranges",
        duration=duration,
    )
    if _strict_int(raw["normal_gap_count"], name="normal_gap_count") != len(normal):
        raise ValueError("OHLCV normal gap count does not match its ranges")
    if _strict_int(raw["partial_bucket_count"], name="partial_bucket_count") != len(partial):
        raise ValueError("OHLCV partial bucket count does not match its ranges")
    if _strict_int(
        raw["evaluation_grid_gap_count"], name="evaluation_grid_gap_count"
    ) != len(evaluation):
        raise ValueError("OHLCV evaluation gap count does not match its ranges")
    if set(normal) & set(partial):
        raise ValueError("normal and partial OHLCV gaps must be disjoint")
    if not set(evaluation) <= set(normal) | set(partial):
        raise ValueError("evaluation gaps must be classified snapshot gaps")
    status = raw["origin_validation_status"]
    if not isinstance(status, str) or status not in _ORIGIN_STATUSES:
        raise ValueError("unsupported origin validation status")
    row_count = _strict_int(raw["origin_minute_row_count"], name="origin_minute_row_count")
    origin_hash = raw["origin_timestamp_hash"]
    if origin_hash is not None and (
        not isinstance(origin_hash, str)
        or len(origin_hash) != 64
        or any(character not in "0123456789abcdef" for character in origin_hash)
    ):
        raise ValueError("origin timestamp hash must be lowercase SHA-256")
    contract = OhlcvGapContract(
        duration, normal, partial, evaluation, status, row_count, origin_hash
    )
    if row_count < 0 or (status == "verified") != (origin_hash is not None):
        raise ValueError("invalid origin verification facts")
    if contract.encode() != note:
        raise ValueError("OHLCV gap note must use canonical JSON")
    return contract
