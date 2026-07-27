"""Continuous-aggregate refresh orchestration without database access."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta, timezone

import pytest
from collector_service.application import AggregateRefresh

START = datetime(2021, 1, 1, tzinfo=UTC)
END = datetime(2022, 1, 1, tzinfo=UTC)
ALL_VIEWS = (
    "public.ohlcv_futures_5m",
    "public.ohlcv_futures_15m",
    "public.ohlcv_futures_1h",
    "public.ohlcv_futures_4h",
    "public.ohlcv_futures_1d",
)


class RecordingRefresher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, datetime, datetime]] = []

    def refresh_range(
        self,
        view_name: str,
        start: datetime,
        end: datetime,
    ) -> None:
        self.calls.append((view_name, start, end))


def test_default_refresh_visits_all_views_and_emits_structured_completion_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    repository = RecordingRefresher()
    service = AggregateRefresh(repository)

    with caplog.at_level(logging.INFO):
        result = asyncio.run(service.run(start=START, end=END))

    assert result.view_count == 5
    assert repository.calls == [(view, START, END) for view in ALL_VIEWS]
    view_records = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "aggregate_refresh_view_completed"
    ]
    assert [record.__dict__["view"] for record in view_records] == list(ALL_VIEWS)
    assert all(record.__dict__["service"] == "collector" for record in view_records)
    assert all(record.__dict__["start"] == START.isoformat() for record in view_records)
    assert all(record.__dict__["end"] == END.isoformat() for record in view_records)
    completed = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "aggregate_refresh_completed"
    )
    assert completed.__dict__["service"] == "collector"
    assert completed.__dict__["count"] == 5


def test_partial_refresh_preserves_requested_order_and_normalizes_range_to_utc() -> None:
    repository = RecordingRefresher()
    service = AggregateRefresh(repository)
    offset = timezone(timedelta(hours=9))
    start = START.astimezone(offset)
    end = END.astimezone(offset)

    result = asyncio.run(
        service.run(
            start=start,
            end=end,
            timeframes=("4h", "15m", "4h"),
        )
    )

    assert result.view_count == 2
    assert repository.calls == [
        ("public.ohlcv_futures_4h", START, END),
        ("public.ohlcv_futures_15m", START, END),
    ]


@pytest.mark.parametrize("timeframes", [("1m",), ("5m", "2h"), ()])
def test_invalid_timeframe_selection_is_rejected(timeframes: tuple[str, ...]) -> None:
    repository = RecordingRefresher()

    with pytest.raises(ValueError):
        asyncio.run(
            AggregateRefresh(repository).run(
                start=START,
                end=END,
                timeframes=timeframes,
            )
        )

    assert repository.calls == []


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (START.replace(tzinfo=None), END),
        (START, START),
        (END, START),
    ],
)
def test_invalid_refresh_range_uses_backfill_validation(
    start: datetime,
    end: datetime,
) -> None:
    repository = RecordingRefresher()

    with pytest.raises(ValueError):
        asyncio.run(AggregateRefresh(repository).run(start=start, end=end))

    assert repository.calls == []
