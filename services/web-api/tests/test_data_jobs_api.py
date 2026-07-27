"""Isolated contracts for collector job orchestration; no real process may start."""

from __future__ import annotations

import asyncio
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

    accepted = client.post("/api/v1/data-jobs", json=_payload()).json()
    status = _wait_for_terminal(client, accepted["job_id"])
    assert status["status"] == "FAILED"
    assert status["error"]["code"] == "collector_failed"
    message = status["error"]["message"]
    assert "code 9" in message
    assert "[redacted]" in message
    assert database_settings.password not in message
    assert "another-secret" not in message
    assert status["finished_at"] is not None


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
