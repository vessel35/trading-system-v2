"""Mode dispatch keeps collect as the default and selects bounded jobs explicitly."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import collector_service.main as collector_main
import pytest
from collector_service.core import Settings
from service_commons.observability import RunnerLogFormatter


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


class StubAggregateAction:
    def __init__(self) -> None:
        self.calls: list[tuple[datetime | None, datetime | None, tuple[str, ...] | None]] = []

    async def run(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        timeframes: tuple[str, ...] | None = None,
    ) -> None:
        self.calls.append((start, end, timeframes))


class StubRuntime:
    def __init__(self) -> None:
        self.collector = StubAction()
        self.backfill = StubAction()
        self.funding_backfill = StubAction()
        self.aggregate_refresh = StubAggregateAction()
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
    assert runtime.aggregate_refresh.calls == []
    assert runtime.closed


def test_main_configures_info_logging_with_structured_formatter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = StubRuntime()
    monkeypatch.setattr(collector_main, "Settings", lambda **_: settings())
    monkeypatch.setattr(collector_main, "build_runtime", lambda configured: runtime)

    collector_main.main([])

    assert runtime.collector.calls == [(None, None)]
    assert runtime.closed is True
    assert logging.getLogger().level == logging.INFO
    assert all(
        isinstance(handler.formatter, RunnerLogFormatter)
        for handler in logging.getLogger().handlers
    )


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
    assert runtime.aggregate_refresh.calls == []
    assert runtime.closed


def test_refresh_aggregates_cli_dispatches_range_and_selected_timeframes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = StubRuntime()
    monkeypatch.setattr(collector_main, "Settings", lambda **_: settings())
    monkeypatch.setattr(collector_main, "build_runtime", lambda configured: runtime)

    collector_main.main(
        [
            "refresh-aggregates",
            "--start",
            "2021-01-01T00:00:00Z",
            "--end",
            "2022-01-01T00:00:00+00:00",
            "--timeframes",
            "5m, 1h",
        ]
    )

    assert runtime.collector.calls == []
    assert runtime.backfill.calls == []
    assert runtime.funding_backfill.calls == []
    assert runtime.aggregate_refresh.calls == [
        (
            datetime(2021, 1, 1, tzinfo=UTC),
            datetime(2022, 1, 1, tzinfo=UTC),
            ("5m", "1h"),
        )
    ]
    assert runtime.closed


@pytest.mark.parametrize(
    "arguments",
    [
        ["refresh-aggregates"],
        ["refresh-aggregates", "--start", "2021-01-01T00:00:00Z"],
        ["refresh-aggregates", "--end", "2022-01-01T00:00:00Z"],
    ],
)
def test_refresh_aggregates_requires_start_and_end(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        collector_main.main(arguments)

    assert raised.value.code == 2
