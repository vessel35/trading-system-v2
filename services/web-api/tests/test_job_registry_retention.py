"""The in-process job registries must not grow without bound.

Both registries live for as long as the web-api process does. Without a cap,
every submitted job would keep its state object and its asyncio.Event forever,
so a long-lived server slowly accumulates them. These tests pin the rule that
bounds the growth: finished jobs are capped, unfinished ones are never dropped.
"""

import asyncio
from datetime import UTC, datetime

from web_api.data_jobs import (
    MAX_RETAINED_FINISHED_DATA_JOBS,
    DataJobRegistry,
)
from web_api.jobs import MAX_RETAINED_FINISHED_JOBS, JobRegistry
from web_api.models import DataJobRequest


def _data_job_request() -> DataJobRequest:
    return DataJobRequest(
        operation="backfill",
        symbol="BTC/USDT:USDT",
        exchange="binance",
        start=datetime(2025, 1, 1, tzinfo=UTC),
        end=datetime(2025, 1, 2, tzinfo=UTC),
    )


def test_finished_backtest_jobs_stop_accumulating_at_the_cap() -> None:
    async def exercise() -> None:
        registry = JobRegistry()
        overshoot = 25
        for index in range(MAX_RETAINED_FINISHED_JOBS + overshoot):
            job_id = f"job-{index:04d}"
            registry.register(job_id)
            registry.update(job_id, "SUCCEEDED")

        # One more registration prunes down to the cap, plus the new job itself.
        registry.register("job-newest")
        assert len(registry._states) == MAX_RETAINED_FINISHED_JOBS + 1
        assert len(registry._events) == MAX_RETAINED_FINISHED_JOBS + 1

        assert registry.get("job-0000") is None
        assert registry.get(f"job-{overshoot - 1:04d}") is None
        assert registry.get(f"job-{overshoot:04d}") is not None
        assert registry.get(f"job-{MAX_RETAINED_FINISHED_JOBS + overshoot - 1:04d}") is not None
        assert registry.get("job-newest") is not None

    asyncio.run(exercise())


def test_queued_and_running_jobs_are_never_dropped() -> None:
    async def exercise() -> None:
        registry = JobRegistry()
        registry.register("job-queued")
        registry.register("job-running")
        registry.update("job-running", "RUNNING")

        for index in range(MAX_RETAINED_FINISHED_JOBS * 2):
            job_id = f"job-finished-{index:04d}"
            registry.register(job_id)
            registry.update(job_id, "FAILED")

        assert registry.get("job-queued") is not None
        assert registry.get("job-queued").status == "QUEUED"  # type: ignore[union-attr]
        assert registry.get("job-running") is not None
        assert len(registry._states) <= MAX_RETAINED_FINISHED_JOBS + 3

    asyncio.run(exercise())


def test_a_dropped_job_ends_its_event_stream_instead_of_hanging() -> None:
    async def exercise() -> None:
        registry = JobRegistry()
        registry.register("job-oldest")
        registry.update("job-oldest", "SUCCEEDED")
        for index in range(MAX_RETAINED_FINISHED_JOBS + 1):
            job_id = f"job-{index:04d}"
            registry.register(job_id)
            registry.update(job_id, "SUCCEEDED")

        assert registry.get("job-oldest") is None
        # No event is left behind, so a late subscriber is told the job is gone
        # rather than waiting on an Event nothing will ever set.
        assert await registry.wait_for_change("job-oldest", 0, timeout=0.01) is None

    asyncio.run(exercise())


def test_finished_data_jobs_stop_accumulating_at_the_cap() -> None:
    async def exercise() -> None:
        registry = DataJobRegistry()
        request = _data_job_request()
        for index in range(MAX_RETAINED_FINISHED_DATA_JOBS + 10):
            job_id = f"data-{index:04d}"
            registry.register(request, job_id=job_id)
            registry.update(job_id, "SUCCEEDED")

        registry.register(request, job_id="data-newest")
        assert len(registry._states) == MAX_RETAINED_FINISHED_DATA_JOBS + 1
        assert len(registry._events) == MAX_RETAINED_FINISHED_DATA_JOBS + 1
        assert len(registry.list()) == MAX_RETAINED_FINISHED_DATA_JOBS + 1
        assert registry.get("data-0000") is None
        assert registry.get("data-newest") is not None
        assert registry.list()[0].job_id == "data-newest"

    asyncio.run(exercise())


def test_running_data_jobs_survive_a_flood_of_finished_ones() -> None:
    async def exercise() -> None:
        registry = DataJobRegistry()
        request = _data_job_request()
        registry.register(request, job_id="data-running")
        registry.update("data-running", "RUNNING")

        for index in range(MAX_RETAINED_FINISHED_DATA_JOBS * 2):
            job_id = f"data-finished-{index:04d}"
            registry.register(request, job_id=job_id)
            registry.update(job_id, "SUCCEEDED")

        running = registry.get("data-running")
        assert running is not None
        assert running.status == "RUNNING"

    asyncio.run(exercise())
