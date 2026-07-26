"""In-process dry-run job execution outside the FastAPI event loop."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import uuid4

from backtest_service.config import RunConfig
from backtest_service.runner import build_harness, run_backtest

from web_api.database import _repository_env
from web_api.models import JobError, JobStatus, SweepType

JobStateValue = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "ORPHANED"]
TERMINAL_JOB_STATES = frozenset({"SUCCEEDED", "FAILED", "ORPHANED"})
REPOSITORY_ROOT = Path(__file__).parents[3]


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class JobState:
    job_id: str
    status: JobStateValue
    created_at: datetime
    updated_at: datetime
    revision: int = 0
    run_id: str | None = None
    sweep_id: str | None = None
    run_count: int | None = None
    evidence_hash: str | None = None
    integrity_status: str | None = None
    summary_present: bool | None = None
    error: JobError | None = None

    def public_status(self) -> JobStatus:
        catalog_status = {
            "RUNNING": "RUNNING",
            "SUCCEEDED": "EVALUATED",
            "ORPHANED": "ORPHANED",
        }.get(self.status)
        return JobStatus(
            job_id=self.job_id,
            status=self.status,
            catalog_status=catalog_status,
            updated_at=self.updated_at,
            run_id=self.run_id,
            sweep_id=self.sweep_id,
            run_count=self.run_count,
            evidence_hash=self.evidence_hash,
            integrity_status=self.integrity_status,
            summary_present=self.summary_present,
            error=self.error,
        )


class JobRegistry:
    """Thread-safe job snapshots with asyncio wakeups for SSE subscribers."""

    def __init__(self) -> None:
        self._states: dict[str, JobState] = {}
        self._events: dict[str, asyncio.Event] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = RLock()

    def register(self, job_id: str) -> JobState:
        now = _now()
        state = JobState(
            job_id=job_id,
            status="QUEUED",
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            if job_id in self._states:
                raise ValueError(f"job already exists: {job_id}")
            self._states[job_id] = state
            self._events[job_id] = asyncio.Event()
            self._loop = asyncio.get_running_loop()
        return state

    def get(self, job_id: str) -> JobState | None:
        with self._lock:
            return self._states.get(job_id)

    def update(
        self,
        job_id: str,
        status: JobStateValue,
        *,
        run_id: str | None = None,
        sweep_id: str | None = None,
        run_count: int | None = None,
        evidence_hash: str | None = None,
        integrity_status: str | None = None,
        summary_present: bool | None = None,
        error: JobError | None = None,
    ) -> JobState:
        with self._lock:
            current = self._states[job_id]
            state = replace(
                current,
                status=status,
                updated_at=_now(),
                revision=current.revision + 1,
                run_id=run_id,
                sweep_id=sweep_id,
                run_count=run_count,
                evidence_hash=evidence_hash,
                integrity_status=integrity_status,
                summary_present=summary_present,
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
    ) -> JobState | None:
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


registry = JobRegistry()
_executor: ThreadPoolExecutor | None = None


@dataclass(frozen=True, slots=True)
class SweepPlan:
    sweep_id: str
    type: SweepType
    config: RunConfig
    configs: tuple[RunConfig, ...] = ()
    folds: int | None = None
    split: float | None = None


def start_executor() -> None:
    """Create the one permitted worker for serial dry-run execution."""

    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="webapi-dry-run")


async def shutdown_executor() -> None:
    """Cancel queued work and drain only the running job without blocking the loop."""

    global _executor
    executor, _executor = _executor, None
    if executor is not None:
        await asyncio.to_thread(
            executor.shutdown,
            wait=True,
            cancel_futures=True,
        )


def _safe_error_message(error: Exception, env: dict[str, str]) -> str:
    message = str(error).strip() or type(error).__name__
    for key, value in env.items():
        if value and any(token in key.upper() for token in ("PASSWORD", "SECRET", "TOKEN", "KEY")):
            message = message.replace(value, "[redacted]")
    return message[:500]


def _run_job(job_id: str, config: RunConfig, prereg: dict[str, object]) -> None:
    env: dict[str, str] = {}
    try:
        registry.update(job_id, "RUNNING")
        env = _repository_env()
        evidence_root = Path(
            env.get("WEBAPI_EVIDENCE_ROOT", str(REPOSITORY_ROOT / "var" / "evidence"))
        ).expanduser()
        result = run_backtest(
            config,
            prereg,
            evidence_root=evidence_root,
            env=env,
        )
        registry.update(
            job_id,
            "SUCCEEDED",
            run_id=result.run_id,
            evidence_hash=result.evidence_hash,
            integrity_status=result.integrity_status,
            summary_present=True,
        )
    except Exception as error:
        registry.update(
            job_id,
            "FAILED",
            error=JobError(
                code="backtest_failed",
                message=_safe_error_message(error, env),
            ),
        )


def _run_sweep_job(job_id: str, plan: SweepPlan, prereg: dict[str, object]) -> None:
    env: dict[str, str] = {}
    try:
        registry.update(job_id, "RUNNING", sweep_id=plan.sweep_id)
        env = _repository_env()
        evidence_root = Path(
            env.get("WEBAPI_EVIDENCE_ROOT", str(REPOSITORY_ROOT / "var" / "evidence"))
        ).expanduser()
        with build_harness(
            plan.config,
            prereg,
            evidence_root=evidence_root,
            env=env,
            seed=plan.config.seed,
        ) as harness:
            if plan.type == "grid":
                results = harness.sweep(list(plan.configs))
                representative_run_id = results[0].run_id
                run_count = len(results)
            elif plan.type == "walk_forward":
                if plan.folds is None:
                    raise RuntimeError("walk-forward sweep is missing folds")
                evidence = harness.walk_forward(plan.config, plan.folds)
                representative_run_id = str(evidence["representative_run_id"])
                run_count = plan.folds
            else:
                if plan.split is None:
                    raise RuntimeError("in/out-of-sample sweep is missing split")
                evidence = harness.is_oos(plan.config, plan.split)
                representative_run_id = str(evidence["representative_run_id"])
                run_count = 2
        registry.update(
            job_id,
            "SUCCEEDED",
            run_id=representative_run_id,
            sweep_id=plan.sweep_id,
            run_count=run_count,
            summary_present=True,
        )
    except Exception as error:
        registry.update(
            job_id,
            "FAILED",
            sweep_id=plan.sweep_id,
            error=JobError(
                code="sweep_failed",
                message=_safe_error_message(error, env),
            ),
        )


def _job_done(job_id: str, future: asyncio.Future[None]) -> None:
    """Retrieve executor failures and make an unexpected escape terminal."""

    if future.cancelled():
        return
    error = future.exception()
    if error is None:
        return
    state = registry.get(job_id)
    if state is None or state.status in TERMINAL_JOB_STATES:
        return
    registry.update(
        job_id,
        "FAILED",
        sweep_id=state.sweep_id,
        run_count=state.run_count,
        error=JobError(
            code="backtest_failed",
            message="The dry-run worker terminated unexpectedly.",
        ),
    )


def submit_job(config: RunConfig, prereg: dict[str, object]) -> JobState:
    """Register a QUEUED job and submit its blocking runner to the executor."""

    if _executor is None:
        raise RuntimeError("dry-run executor is not started")
    job_id = str(uuid4())
    state = registry.register(job_id)
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(_executor, _run_job, job_id, config, prereg)
    future.add_done_callback(lambda completed: _job_done(job_id, completed))
    return state


def submit_sweep_job(plan: SweepPlan, prereg: dict[str, object]) -> JobState:
    """Register a QUEUED multi-run job on the same serial dry-run executor."""

    if _executor is None:
        raise RuntimeError("dry-run executor is not started")
    job_id = str(uuid4())
    state = registry.register(job_id)
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(_executor, _run_sweep_job, job_id, plan, prereg)
    future.add_done_callback(lambda completed: _job_done(job_id, completed))
    return state


__all__ = [
    "JobRegistry",
    "JobState",
    "SweepPlan",
    "TERMINAL_JOB_STATES",
    "registry",
    "shutdown_executor",
    "start_executor",
    "submit_job",
    "submit_sweep_job",
]
