"""Advance deterministic simulated candle time without wall-clock access."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from itertools import pairwise
from typing import Self

from core_lib.ports import Clock
from core_lib.types import Candle


class BacktestClock(Clock):
    """Advance over one immutable, strictly increasing simulation schedule."""

    @classmethod
    def from_candles(cls, candles: Iterable[Candle]) -> Self:
        """Build the canonical union of every candle open and close instant."""
        schedule = sorted(
            {
                instant
                for candle in candles
                for instant in (candle.open_time, candle.close_time)
            }
        )
        return cls(schedule)

    def __init__(self, schedule: Iterable[datetime]) -> None:
        normalized: list[datetime] = []
        for value in schedule:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("simulation schedule timestamps must be timezone-aware")
            normalized.append(value.astimezone(UTC))
        if not normalized:
            raise ValueError("simulation schedule must not be empty")
        if any(left >= right for left, right in pairwise(normalized)):
            raise ValueError("simulation schedule must be strictly increasing")
        self._schedule = tuple(normalized)
        self._index = 0

    def now(self) -> datetime:
        """Return the current simulation timestamp without consulting wall-clock."""
        return self._schedule[self._index]

    def advance(self) -> None:
        """Advance one deterministic point or raise at the end of the schedule."""
        if self._index + 1 >= len(self._schedule):
            raise StopIteration("simulation schedule is exhausted")
        self._index += 1
