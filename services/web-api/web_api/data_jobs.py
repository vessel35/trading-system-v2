"""Asynchronous orchestration for collector processes with real write capability."""

from __future__ import annotations

import asyncio
import os
import re
import sys
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import uuid4

from psycopg.conninfo import make_conninfo

from web_api.database import DatabaseSettings, get_settings
from web_api.models import (
    AggregateTimeframe,
    DataJobOperation,
    DataJobRequest,
    DataJobStatus,
    JobError,
)

DataJobStateValue = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"]
TERMINAL_DATA_JOB_STATES = frozenset({"SUCCEEDED", "FAILED"})
OPERATION_MODES: dict[DataJobOperation, str] = {
    "backfill": "backfill",
    "funding_backfill": "funding-backfill",
    "refresh_aggregates": "refresh-aggregates",
}
REPOSITORY_ROOT = Path(__file__).parents[3]
COLLECTOR_WORKING_DIRECTORY = REPOSITORY_ROOT / "services" / "web-api"
_OUTPUT_TAIL_BYTES = 4_096
_MAX_ERROR_MESSAGE = 500
_URI_CREDENTIALS = re.compile(r"(?P<scheme>[a-z][a-z0-9+.-]*://)[^\s/@]+@", re.IGNORECASE)
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class DataJobState:
    job_id: str
    operation: DataJobOperation
    symbol: str
    exchange: Literal["binance"]
    start: datetime
    end: datetime
    timeframes: tuple[AggregateTimeframe, ...] | None
    status: DataJobStateValue
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    revision: int = 0
    error: JobError | None = None

    def public_status(self) -> DataJobStatus:
        return DataJobStatus(
            job_id=self.job_id,
            operation=self.operation,
            symbol=self.symbol,
            exchange=self.exchange,
            start=self.start,
            end=self.end,
            timeframes=list(self.timeframes) if self.timeframes is not None else None,
            status=self.status,
            created_at=self.created_at,
            updated_at=self.updated_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
            error=self.error,
        )


class DataJobRegistry:
    """Thread-safe collector job snapshots with asyncio wakeups for SSE."""

    def __init__(self) -> None:
        self._states: dict[str, DataJobState] = {}
        self._events: dict[str, asyncio.Event] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = RLock()

    def register(self, request: DataJobRequest, *, job_id: str | None = None) -> DataJobState:
        now = _now()
        identifier = job_id or str(uuid4())
        state = DataJobState(
            job_id=identifier,
            operation=request.operation,
            symbol=request.symbol,
            exchange="binance",
            start=request.start,
            end=request.end,
            timeframes=tuple(request.timeframes) if request.timeframes is not None else None,
            status="QUEUED",
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            if identifier in self._states:
                raise ValueError(f"data job already exists: {identifier}")
            self._states[identifier] = state
            self._events[identifier] = asyncio.Event()
            self._loop = asyncio.get_running_loop()
        return state

    def get(self, job_id: str) -> DataJobState | None:
        with self._lock:
            return self._states.get(job_id)

    def list(self) -> list[DataJobState]:
        with self._lock:
            return sorted(
                self._states.values(),
                key=lambda state: state.created_at,
                reverse=True,
            )

    def update(
        self,
        job_id: str,
        status: DataJobStateValue,
        *,
        error: JobError | None = None,
    ) -> DataJobState:
        now = _now()
        with self._lock:
            current = self._states[job_id]
            state = replace(
                current,
                status=status,
                updated_at=now,
                started_at=(
                    now
                    if status == "RUNNING" and current.started_at is None
                    else current.started_at
                ),
                finished_at=now if status in TERMINAL_DATA_JOB_STATES else None,
                revision=current.revision + 1,
                error=error,
            )
            self._states[job_id] = state
            event = self._events[job_id]
            loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(event.set)
        return state

    async def wait_for_change(
        self,
        job_id: str,
        revision: int,
        *,
        timeout: float,
    ) -> DataJobState | None:
        with self._lock:
            event = self._events.get(job_id)
        if event is None:
            return None
        while True:
            event.clear()
            state = self.get(job_id)
            if state is None or state.revision > revision:
                return state
            await asyncio.wait_for(event.wait(), timeout=timeout)


registry = DataJobRegistry()
_tasks: set[asyncio.Task[None]] = set()


def _database_dsn(settings: DatabaseSettings, database: str) -> str:
    return make_conninfo(
        host=settings.host,
        port=settings.port,
        user=settings.user,
        password=settings.password,
        dbname=database,
    )


def _collector_environment(settings: DatabaseSettings) -> tuple[dict[str, str], tuple[str, ...]]:
    """Build a clean collector environment without inheriting exchange credentials."""

    environment = {
        key: value for key, value in os.environ.items() if not key.upper().startswith("COLLECTOR_")
    }
    config_dsn = _database_dsn(settings, settings.config_database)
    data_dsn = _database_dsn(settings, settings.crypto_database)
    environment.update(
        {
            "COLLECTOR_CONFIG_DB_URL": config_dsn,
            "COLLECTOR_DATA_DB_URL": data_dsn,
        }
    )
    return environment, (settings.password, config_dsn, data_dsn)


def _collector_argv(state: DataJobState) -> tuple[str, ...]:
    arguments = [
        sys.executable,
        "-m",
        "collector_service.main",
        OPERATION_MODES[state.operation],
        "--symbol",
        state.symbol,
        "--start",
        state.start.isoformat(),
        "--end",
        state.end.isoformat(),
    ]
    if state.timeframes is not None:
        arguments.extend(("--timeframes", ",".join(state.timeframes)))
    return tuple(arguments)


def _safe_output_tail(output: bytes | None, sensitive_values: tuple[str, ...]) -> str:
    if not output:
        return ""
    message = output[-_OUTPUT_TAIL_BYTES:].decode("utf-8", errors="replace")
    message = _ANSI_ESCAPE.sub("", message)
    for value in sensitive_values:
        if value:
            message = message.replace(value, "[redacted]")
    message = _URI_CREDENTIALS.sub(r"\g<scheme>[redacted]@", message)
    return " ".join(message.split())[-_MAX_ERROR_MESSAGE:]


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        process.terminate()
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=5.0)
    except TimeoutError:
        try:
            process.kill()
        except ProcessLookupError:
            return
        await process.wait()


async def _run_data_job(job_id: str) -> None:
    state = registry.get(job_id)
    if state is None:
        return
    process: asyncio.subprocess.Process | None = None
    sensitive_values: tuple[str, ...] = ()
    try:
        registry.update(job_id, "RUNNING")
        settings = get_settings()
        environment, sensitive_values = _collector_environment(settings)
        process = await asyncio.create_subprocess_exec(
            *_collector_argv(state),
            cwd=COLLECTOR_WORKING_DIRECTORY,
            env=environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output, _ = await process.communicate()
        if process.returncode == 0:
            registry.update(job_id, "SUCCEEDED")
            return
        tail = _safe_output_tail(output, sensitive_values)
        message = f"Collector exited with code {process.returncode}."
        if tail:
            message = f"{message} Output: {tail}"
        registry.update(
            job_id,
            "FAILED",
            error=JobError(code="collector_failed", message=message[:_MAX_ERROR_MESSAGE]),
        )
    except asyncio.CancelledError:
        if process is not None:
            await _stop_process(process)
        registry.update(
            job_id,
            "FAILED",
            error=JobError(
                code="collector_cancelled",
                message="The collector job was cancelled during web API shutdown.",
            ),
        )
        raise
    except Exception:
        registry.update(
            job_id,
            "FAILED",
            error=JobError(
                code="collector_launch_failed",
                message="The collector process could not be started.",
            ),
        )


def _job_done(job_id: str, task: asyncio.Task[None]) -> None:
    _tasks.discard(task)
    if task.cancelled():
        return
    error = task.exception()
    state = registry.get(job_id)
    if error is None or state is None or state.status in TERMINAL_DATA_JOB_STATES:
        return
    registry.update(
        job_id,
        "FAILED",
        error=JobError(
            code="collector_launch_failed",
            message="The collector task terminated unexpectedly.",
        ),
    )


def submit_data_job(request: DataJobRequest) -> DataJobState:
    """Queue a subprocess that can access Binance and write the crypto_data database."""

    state = registry.register(request)
    task = asyncio.create_task(_run_data_job(state.job_id), name=f"data-job-{state.job_id}")
    _tasks.add(task)
    task.add_done_callback(lambda completed: _job_done(state.job_id, completed))
    return state


async def shutdown_data_jobs() -> None:
    """Cancel and reap collector subprocess tasks owned by this web API process."""

    tasks = tuple(_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


__all__ = [
    "DataJobRegistry",
    "DataJobState",
    "TERMINAL_DATA_JOB_STATES",
    "registry",
    "shutdown_data_jobs",
    "submit_data_job",
]
