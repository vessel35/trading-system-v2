"""Asynchronous orchestration for collector processes with real write capability."""

from __future__ import annotations

import asyncio
import logging
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
DATA_JOB_MAX_RANGE_DAYS = 730
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
_SENSITIVE_ENVIRONMENT_KEY = re.compile(
    r"(?:API_KEY|SECRET|TOKEN|PASSWORD|COLLECTOR_)",
    re.IGNORECASE,
)
_SYSTEM_ENVIRONMENT_KEYS = frozenset(
    {
        "COMSPEC",
        "CURL_CA_BUNDLE",
        "LANG",
        "PATH",
        "PATHEXT",
        "PYTHONHOME",
        "PYTHONPATH",
        "REQUESTS_CA_BUNDLE",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "TZ",
        "VIRTUAL_ENV",
        "WINDIR",
    }
)
logger = logging.getLogger(__name__)


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
_execution_semaphore: asyncio.Semaphore | None = None
_execution_loop: asyncio.AbstractEventLoop | None = None


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
        key: value
        for key, value in os.environ.items()
        if (key.upper() in _SYSTEM_ENVIRONMENT_KEYS or key.upper().startswith("LC_"))
        and _SENSITIVE_ENVIRONMENT_KEY.search(key) is None
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
    for value in sorted({value for value in sensitive_values if value}, key=len, reverse=True):
        message = message.replace(value, "[redacted]")
    message = _URI_CREDENTIALS.sub(r"\g<scheme>[redacted]@", message)
    return " ".join(message.split())[-_MAX_ERROR_MESSAGE:]


def _execution_limit() -> asyncio.Semaphore:
    """Return a loop-local gate that permits exactly one collector process."""

    global _execution_loop, _execution_semaphore
    loop = asyncio.get_running_loop()
    if _execution_semaphore is None or _execution_loop is not loop:
        _execution_loop = loop
        _execution_semaphore = asyncio.Semaphore(1)
    return _execution_semaphore


def _audit_fields(state: DataJobState) -> dict[str, object]:
    return {
        "operation": state.operation,
        "symbol": state.symbol,
        "exchange": state.exchange,
        "start": state.start.isoformat(),
        "end": state.end.isoformat(),
        "job_id": state.job_id,
        "accepted_at": state.created_at.isoformat(),
    }


def _log_data_job_accepted(state: DataJobState) -> None:
    fields = _audit_fields(state)
    fields["event"] = "data_job_accepted"
    logger.info("data_job_accepted", extra=fields)


def _log_data_job_result(state: DataJobState) -> None:
    fields = _audit_fields(state)
    fields.update(
        {
            "event": "data_job_finished",
            "status": state.status,
            "finished_at": (
                state.finished_at.isoformat() if state.finished_at is not None else None
            ),
            "error_code": state.error.code if state.error is not None else None,
            "error_message": state.error.message if state.error is not None else None,
        }
    )
    log_method = logger.warning if state.status == "FAILED" else logger.info
    log_method("data_job_finished", extra=fields)


def _finish_data_job(
    job_id: str,
    status: Literal["SUCCEEDED", "FAILED"],
    *,
    error: JobError | None = None,
) -> DataJobState:
    state = registry.update(job_id, status, error=error)
    _log_data_job_result(state)
    return state


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
        async with _execution_limit():
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
                _finish_data_job(job_id, "SUCCEEDED")
                return
            tail = _safe_output_tail(output, sensitive_values)
            message = f"Collector exited with code {process.returncode}."
            if tail:
                message = f"{message} Output: {tail}"
            _finish_data_job(
                job_id,
                "FAILED",
                error=JobError(code="collector_failed", message=message[:_MAX_ERROR_MESSAGE]),
            )
    except asyncio.CancelledError:
        if process is not None:
            await _stop_process(process)
        current = registry.get(job_id)
        if current is not None and current.status not in TERMINAL_DATA_JOB_STATES:
            _finish_data_job(
                job_id,
                "FAILED",
                error=JobError(
                    code="collector_cancelled",
                    message="The collector job was cancelled during web API shutdown.",
                ),
            )
        raise
    except Exception:
        current = registry.get(job_id)
        if current is not None and current.status not in TERMINAL_DATA_JOB_STATES:
            _finish_data_job(
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
    _finish_data_job(
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
    _log_data_job_accepted(state)
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
    "DATA_JOB_MAX_RANGE_DAYS",
    "DataJobRegistry",
    "DataJobState",
    "TERMINAL_DATA_JOB_STATES",
    "registry",
    "shutdown_data_jobs",
    "submit_data_job",
]
