"""Mode dispatch keeps collect as the default and selects bounded jobs explicitly."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import collector_service.main as collector_main
import pytest
from collector_service.core import Settings


class StubAction:
    def __init__(self) -> None:
        self.calls: list[tuple[datetime | None, datetime | None]] = []

    async def run(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> None:
        self.calls.append((start, end))


class StubRuntime:
    def __init__(self) -> None:
        self.collector = StubAction()
        self.backfill = StubAction()
        self.funding_backfill = StubAction()
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def settings() -> Settings:
    return Settings.model_validate(
        {
            "config_db_url": "postgresql://config",
            "data_db_url": "postgresql://data",
        }
    )


def test_default_run_keeps_collect_path_and_closes_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = StubRuntime()
    monkeypatch.setattr(
        collector_main,
        "build_runtime",
        lambda configured: runtime,
    )

    asyncio.run(collector_main._run(settings()))

    assert runtime.collector.calls == [(None, None)]
    assert runtime.backfill.calls == []
    assert runtime.funding_backfill.calls == []
    assert runtime.closed


def test_bounded_modes_dispatch_the_exact_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = StubRuntime()
    monkeypatch.setattr(
        collector_main,
        "build_runtime",
        lambda configured: runtime,
    )
    start = datetime(2025, 1, 1, tzinfo=UTC)
    end = datetime(2025, 2, 1, tzinfo=UTC)

    asyncio.run(collector_main._run(settings(), mode="backfill", start=start, end=end))
    asyncio.run(
        collector_main._run(
            settings(),
            mode="funding-backfill",
            start=start,
            end=end,
        )
    )

    assert runtime.collector.calls == []
    assert runtime.backfill.calls == [(start, end)]
    assert runtime.funding_backfill.calls == [(start, end)]
    assert runtime.closed
