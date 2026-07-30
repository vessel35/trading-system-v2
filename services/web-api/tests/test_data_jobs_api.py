"""Isolated contracts for collector job orchestration; no real process may start."""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from threading import Event, Timer
from typing import Any, cast

import pytest
import web_api.data_jobs as data_jobs
from fastapi.testclient import TestClient
from web_api.database import DatabaseSettings
from web_api.main import app


class FakeProcess:
    def __init__(self, *, returncode: int, output: bytes = b"") -> None:
        self.returncode = returncode
        self._output = output

    async def communicate(self) -> tuple[bytes, None]:
        return self._output, None

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9

    async def wait(self) -> int:
        return self.returncode


@pytest.fixture(autouse=True)
def block_real_collector_process(monkeypatch: pytest.MonkeyPatch) -> None:
    async def forbidden_spawn(*_args: object, **_kwargs: object) -> FakeProcess:
        raise AssertionError("tests must never start collector_service.main")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden_spawn)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def database_settings(tmp_path: Path) -> DatabaseSettings:
    return DatabaseSettings(
        host="db.example",
        port=5432,
        user="web operator",
        password="fake-db-password",
        database="backtest_db",
        config_database="config_db",
        crypto_database="crypto_data",
        signal_database="signal_db",
        evidence_root=tmp_path,
    )


def _payload(
    *,
    operation: str = "backfill",
    timeframes: list[str] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "operation": operation,
        "symbol": "ETH/USDT:USDT",
        "exchange": "binance",
        "start": "2025-01-01T00:00:00Z",
        "end": "2025-01-02T00:00:00Z",
    }
    if timeframes is not None:
        payload["timeframes"] = timeframes
    return payload


def _wait_for_terminal(client: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(200):
        response = client.get(f"/api/v1/data-jobs/{job_id}")
        assert response.status_code == 200
        body = cast(dict[str, Any], response.json())
        if body["status"] in {"SUCCEEDED", "FAILED"}:
            return body
        time.sleep(0.01)
    raise AssertionError("data job did not reach a terminal state")


@pytest.mark.parametrize(
    ("operation", "mode", "timeframes"),
    [
        ("backfill", "backfill", None),
        ("funding_backfill", "funding-backfill", None),
        ("refresh_aggregates", "refresh-aggregates", ["5m", "1h"]),
    ],
)
def test_data_job_invokes_exact_collector_argv_and_safe_environment(
    client: TestClient,
    database_settings: DatabaseSettings,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    mode: str,
    timeframes: list[str] | None,
) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def fake_spawn(*args: object, **kwargs: object) -> FakeProcess:
        calls.append((args, kwargs))
        return FakeProcess(returncode=0, output=b"collector completed")

    monkeypatch.setattr(data_jobs, "get_settings", lambda: database_settings)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_spawn)
    monkeypatch.setenv("COLLECTOR_BINANCE_API_KEY", "must-not-be-inherited")
    monkeypatch.setenv("COLLECTOR_BINANCE_API_SECRET", "must-not-be-inherited")
    monkeypatch.setenv("SERVICE_API_KEY", "must-not-be-inherited")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-be-inherited")
    monkeypatch.setenv("OAUTH_TOKEN", "must-not-be-inherited")
    monkeypatch.setenv("DATABASE_PASSWORD", "must-not-be-inherited")
    monkeypatch.setenv("FEATURE_FLAG", "not-required-by-collector")
    monkeypatch.setenv("PATH", "/safe/system/path")

    response = client.post(
        "/api/v1/data-jobs",
        json=_payload(operation=operation, timeframes=timeframes),
    )
    assert response.status_code == 202
    accepted = response.json()
    assert accepted["status"] == "QUEUED"
    assert accepted["operation"] == operation

    status = _wait_for_terminal(client, accepted["job_id"])
    assert status["status"] == "SUCCEEDED"
    assert status["started_at"] is not None
    assert status["finished_at"] is not None
    assert status["error"] is None

    assert len(calls) == 1
    arguments, options = calls[0]
    expected = [
        sys.executable,
        "-m",
        "collector_service.main",
        mode,
        "--symbol",
        "ETH/USDT:USDT",
        "--start",
        "2025-01-01T00:00:00+00:00",
        "--end",
        "2025-01-02T00:00:00+00:00",
    ]
    if timeframes is not None:
        expected.extend(("--timeframes", ",".join(timeframes)))
    assert arguments == tuple(expected)

    environment = cast(dict[str, str], options["env"])
    assert environment["COLLECTOR_CONFIG_DB_URL"] == data_jobs._database_dsn(
        database_settings,
        "config_db",
    )
    assert environment["COLLECTOR_DATA_DB_URL"] == data_jobs._database_dsn(
        database_settings,
        "crypto_data",
    )
    assert "COLLECTOR_BINANCE_API_KEY" not in environment
    assert "COLLECTOR_BINANCE_API_SECRET" not in environment
    assert "SERVICE_API_KEY" not in environment
    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert "OAUTH_TOKEN" not in environment
    assert "DATABASE_PASSWORD" not in environment
    assert "FEATURE_FLAG" not in environment
    assert environment["PATH"] == "/safe/system/path"
    assert options["cwd"] == data_jobs.COLLECTOR_WORKING_DIRECTORY
    assert options["stdout"] is asyncio.subprocess.PIPE
    assert options["stderr"] is asyncio.subprocess.STDOUT

    listed = client.get("/api/v1/data-jobs")
    assert listed.status_code == 200
    assert accepted["job_id"] in {item["job_id"] for item in listed.json()}

    with client.stream(
        "GET",
        f"/api/v1/data-jobs/{accepted['job_id']}/events",
    ) as events:
        assert events.status_code == 200
        stream = "".join(events.iter_text())
    assert "event: status" in stream
    assert '"status":"SUCCEEDED"' in stream
    assert ": keepalive" not in stream


def test_data_job_failure_uses_exit_code_and_redacted_output_tail(
    client: TestClient,
    database_settings: DatabaseSettings,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def fake_spawn(*_args: object, **kwargs: object) -> FakeProcess:
        environment = cast(dict[str, str], kwargs["env"])
        output = (
            f"connection failed for {environment['COLLECTOR_DATA_DB_URL']} "
            "postgresql://operator:another-secret@db.example/crypto_data"
        ).encode()
        return FakeProcess(returncode=9, output=output)

    monkeypatch.setattr(data_jobs, "get_settings", lambda: database_settings)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_spawn)
    caplog.set_level(logging.INFO, logger="web_api.data_jobs")

    accepted = client.post("/api/v1/data-jobs", json=_payload()).json()
    status = _wait_for_terminal(client, accepted["job_id"])
    assert status["status"] == "FAILED"
    assert status["error"]["code"] == "collector_failed"
    message = status["error"]["message"]
    assert "code 9" in message
    assert "[redacted]" in message
    assert database_settings.password not in message
    assert "another-secret" not in message
    assert "dbname=crypto_data" not in message
    assert status["finished_at"] is not None

    result_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "data_job_finished"
        and getattr(record, "job_id", None) == accepted["job_id"]
    )
    assert result_record.__dict__["status"] == "FAILED"
    assert result_record.__dict__["error_code"] == "collector_failed"
    error_message = cast(str, result_record.__dict__["error_message"])
    assert database_settings.password not in error_message
    assert "dbname=crypto_data" not in error_message


def test_data_job_exposes_running_and_wakes_sse_subscriber(
    client: TestClient,
    database_settings: DatabaseSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = Event()
    release = Event()

    class BlockingProcess:
        returncode: int | None = None

        async def communicate(self) -> tuple[bytes, None]:
            started.set()
            await asyncio.to_thread(release.wait, 2)
            self.returncode = 0
            return b"collector completed", None

        def terminate(self) -> None:
            self.returncode = -15
            release.set()

        def kill(self) -> None:
            self.returncode = -9
            release.set()

        async def wait(self) -> int:
            return self.returncode or 0

    async def fake_spawn(*_args: object, **_kwargs: object) -> BlockingProcess:
        return BlockingProcess()

    monkeypatch.setattr(data_jobs, "get_settings", lambda: database_settings)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_spawn)

    accepted = client.post("/api/v1/data-jobs", json=_payload()).json()
    assert started.wait(timeout=1)
    running = client.get(f"/api/v1/data-jobs/{accepted['job_id']}").json()
    assert running["status"] == "RUNNING"
    assert running["started_at"] is not None
    assert running["finished_at"] is None

    fallback_release = Timer(1, release.set)
    fallback_release.start()
    try:
        with client.stream(
            "GET",
            f"/api/v1/data-jobs/{accepted['job_id']}/events",
        ) as events:
            release.set()
            stream = "".join(events.iter_text())
    finally:
        release.set()
        fallback_release.cancel()
    assert '"status":"RUNNING"' in stream
    assert '"status":"SUCCEEDED"' in stream


def test_data_jobs_run_serially_and_leave_second_job_queued(
    client: TestClient,
    database_settings: DatabaseSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_started = Event()
    release_first = Event()
    second_spawned = Event()
    spawn_count = 0

    class SequencedProcess:
        returncode = 0

        def __init__(self, sequence: int) -> None:
            self.sequence = sequence

        async def communicate(self) -> tuple[bytes, None]:
            if self.sequence == 1:
                first_started.set()
                await asyncio.to_thread(release_first.wait, 2)
            return b"collector completed", None

        def terminate(self) -> None:
            self.returncode = -15
            release_first.set()

        def kill(self) -> None:
            self.returncode = -9
            release_first.set()

        async def wait(self) -> int:
            return self.returncode

    async def fake_spawn(*_args: object, **_kwargs: object) -> SequencedProcess:
        nonlocal spawn_count
        spawn_count += 1
        if spawn_count == 2:
            second_spawned.set()
        return SequencedProcess(spawn_count)

    monkeypatch.setattr(data_jobs, "get_settings", lambda: database_settings)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_spawn)

    first = client.post("/api/v1/data-jobs", json=_payload()).json()
    assert first_started.wait(timeout=1)
    second = client.post(
        "/api/v1/data-jobs",
        json={
            **_payload(),
            "symbol": "BTC/USDT:USDT",
        },
    ).json()

    try:
        assert not second_spawned.wait(timeout=0.1)
        waiting = client.get(f"/api/v1/data-jobs/{second['job_id']}").json()
        assert waiting["status"] == "QUEUED"
        assert waiting["started_at"] is None
    finally:
        release_first.set()

    assert _wait_for_terminal(client, first["job_id"])["status"] == "SUCCEEDED"
    assert _wait_for_terminal(client, second["job_id"])["status"] == "SUCCEEDED"
    assert spawn_count == 2


def test_data_job_acceptance_and_completion_emit_safe_structured_audit_logs(
    client: TestClient,
    database_settings: DatabaseSettings,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def fake_spawn(*_args: object, **_kwargs: object) -> FakeProcess:
        return FakeProcess(returncode=0)

    monkeypatch.setattr(data_jobs, "get_settings", lambda: database_settings)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_spawn)
    caplog.set_level(logging.INFO, logger="web_api.data_jobs")

    accepted = client.post("/api/v1/data-jobs", json=_payload()).json()
    assert _wait_for_terminal(client, accepted["job_id"])["status"] == "SUCCEEDED"

    accepted_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "data_job_accepted"
        and getattr(record, "job_id", None) == accepted["job_id"]
    )
    assert accepted_record.__dict__["operation"] == "backfill"
    assert accepted_record.__dict__["symbol"] == "ETH/USDT:USDT"
    assert accepted_record.__dict__["exchange"] == "binance"
    assert accepted_record.__dict__["start"] == "2025-01-01T00:00:00+00:00"
    assert accepted_record.__dict__["end"] == "2025-01-02T00:00:00+00:00"
    accepted_at = cast(str, accepted_record.__dict__["accepted_at"])
    assert accepted_at.endswith("+00:00")

    result_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "data_job_finished"
        and getattr(record, "job_id", None) == accepted["job_id"]
    )
    assert result_record.__dict__["status"] == "SUCCEEDED"
    assert result_record.__dict__["error_code"] is None
    safe_log_fields = " ".join(
        str(getattr(record, field, ""))
        for record in (accepted_record, result_record)
        for field in (
            "operation",
            "symbol",
            "exchange",
            "start",
            "end",
            "job_id",
            "accepted_at",
            "status",
            "error_code",
            "error_message",
        )
    )
    assert database_settings.password not in safe_log_fields
    assert "COLLECTOR_CONFIG_DB_URL" not in safe_log_fields
    assert "COLLECTOR_DATA_DB_URL" not in safe_log_fields


@pytest.mark.parametrize(
    ("operation", "timeframes"),
    [
        ("backfill", None),
        ("refresh_aggregates", ["5m"]),
    ],
)
def test_data_job_rejects_ranges_over_the_configured_limit(
    client: TestClient,
    operation: str,
    timeframes: list[str] | None,
) -> None:
    existing_job_ids = {state.job_id for state in data_jobs.registry.list()}
    payload = _payload(operation=operation, timeframes=timeframes)
    # 기본 start 2025-01-01 기준 약 2191일 → 2000일 상한 초과.
    payload["end"] = "2031-01-01T00:00:00Z"

    response = client.post("/api/v1/data-jobs", json=payload)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "range_too_large"
    assert error["details"] == {
        "max_range_days": data_jobs.DATA_JOB_MAX_RANGE_DAYS,
        "range_semantics": "[start, end)",
    }
    assert {state.job_id for state in data_jobs.registry.list()} == existing_job_ids


def test_data_job_accepts_range_at_the_configured_limit(
    client: TestClient,
    database_settings: DatabaseSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_spawn(*_args: object, **_kwargs: object) -> FakeProcess:
        return FakeProcess(returncode=0)

    monkeypatch.setattr(data_jobs, "get_settings", lambda: database_settings)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_spawn)
    payload = _payload()
    payload["end"] = "2027-01-01T00:00:00Z"

    response = client.post("/api/v1/data-jobs", json=payload)

    assert response.status_code == 202
    assert _wait_for_terminal(client, response.json()["job_id"])["status"] == "SUCCEEDED"


def test_shutdown_terminates_and_reaps_running_collector(
    database_settings: DatabaseSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = Event()
    terminated = Event()
    release = Event()

    class ShutdownProcess:
        returncode: int | None = None

        async def communicate(self) -> tuple[bytes, None]:
            started.set()
            await asyncio.to_thread(release.wait, 2)
            return b"", None

        def terminate(self) -> None:
            self.returncode = -15
            terminated.set()
            release.set()

        def kill(self) -> None:
            self.returncode = -9
            release.set()

        async def wait(self) -> int:
            return self.returncode or 0

    process = ShutdownProcess()

    async def fake_spawn(*_args: object, **_kwargs: object) -> ShutdownProcess:
        return process

    monkeypatch.setattr(data_jobs, "get_settings", lambda: database_settings)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_spawn)

    with TestClient(app) as shutdown_client:
        accepted = shutdown_client.post("/api/v1/data-jobs", json=_payload()).json()
        assert started.wait(timeout=1)

    assert terminated.is_set()
    state = data_jobs.registry.get(accepted["job_id"])
    assert state is not None
    assert state.status == "FAILED"
    assert state.error is not None
    assert state.error.code == "collector_cancelled"


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({**_payload(), "operation": "collect"}, "invalid_data_job"),
        ({**_payload(), "exchange": "upbit"}, "unsupported_exchange"),
        (
            {
                **_payload(),
                "start": "2025-01-02T00:00:00Z",
                "end": "2025-01-01T00:00:00Z",
            },
            "invalid_data_job",
        ),
        ({**_payload(), "start": "2025-01-01T00:00:00"}, "invalid_data_job"),
        ({**_payload(), "symbol": "ETH-USDT"}, "invalid_data_job"),
        (
            _payload(operation="refresh_aggregates", timeframes=["5m", "2h"]),
            "invalid_data_job",
        ),
        ({**_payload(), "timeframes": ["5m"]}, "invalid_data_job"),
    ],
)
def test_data_job_rejects_invalid_requests_without_spawning(
    client: TestClient,
    payload: dict[str, object],
    code: str,
) -> None:
    response = client.post("/api/v1/data-jobs", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == code


def test_unknown_data_job_returns_standard_error(client: TestClient) -> None:
    response = client.get("/api/v1/data-jobs/unknown")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "data_job_not_found"


def test_data_job_rejection_reports_the_collector_reason_without_the_log_frame(
    client: TestClient,
    database_settings: DatabaseSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reason = (
        "binance does not list NOPE/USDT:USDT as a USD-margined perpetual, so it was not registered"
    )

    async def fake_spawn(*_args: object, **_kwargs: object) -> FakeProcess:
        output = (f"2026-07-29 21:40:53,122 ERROR __main__ collector_rejected {reason}").encode()
        return FakeProcess(returncode=2, output=output)

    monkeypatch.setattr(data_jobs, "get_settings", lambda: database_settings)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_spawn)

    accepted = client.post("/api/v1/data-jobs", json=_payload()).json()
    status = _wait_for_terminal(client, accepted["job_id"])

    assert status["status"] == "FAILED"
    assert status["error"]["code"] == "request_rejected"
    assert status["error"]["message"] == reason
    assert "exited with code" not in status["error"]["message"]
    assert "ERROR" not in status["error"]["message"]
