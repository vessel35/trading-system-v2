"""Contracts for P2a validation, background jobs, SSE, and strategy discovery."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator
from threading import Event, Timer
from types import SimpleNamespace
from typing import Any, cast

import pytest
import web_api.jobs as jobs
from backtest_service.config import RunConfig
from backtest_service.config.run_config import (
    SELECTABLE_MONEY_MANAGEMENT_MODES,
    validate_money_management_config,
)
from core_lib.money_management import MoneyManagementFactory
from fastapi.testclient import TestClient
from web_api.database import SignalConnection
from web_api.main import app
from web_api.models import StrategyOption
from web_api.repository import (
    StrategyRepository,
    _default_money_management,
    _freeze_money_management_defaults,
    _money_management_options,
    _selectable_modes,
)


@pytest.fixture
def run_config_payload() -> dict[str, object]:
    return {
        "run_name": "p2a-contract",
        "strategy_id": "vessel-reference",
        "params": {},
        "symbol": "BTC/USDT:USDT",
        "exchange": "binance",
        "timeframe": "1h",
        "market_type": "futures",
        "data_source": "crypto_data.ohlcv_futures",
        "start": "2025-07-01T00:00:00+09:00",
        "end": "2025-07-04T00:00:00+09:00",
        "initial_capital": "10000.00",
        "seed": 0,
        "sizing_method": "risk_based",
        "risk_per_trade": 0.01,
        "cost_values": {
            "futures_taker_fee_rate": "0.0004",
            "futures_entry_slippage_rate": "0.0005",
            "exit_slippage_rate": "0.0001",
            "funding_fallback_rate": "0.0001",
        },
        "indicator_mode": "auto",
        "explicit_indicators": [],
        "trigger_feed": "tf_candle",
        "fill_timing": "next_bar",
        "profile_ref": "vessel-reference-v1",
    }


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _wait_for_terminal(client: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(200):
        response = client.get(f"/api/v1/jobs/{job_id}/status")
        assert response.status_code == 200
        body = response.json()
        if body["status"] in {"SUCCEEDED", "FAILED", "ORPHANED"}:
            return cast(dict[str, Any], body)
        time.sleep(0.01)
    raise AssertionError("job did not reach a terminal state")


def test_run_config_validation_normalizes_decimals_and_utc(
    client: TestClient,
    run_config_payload: dict[str, object],
) -> None:
    response = client.post("/api/v1/run-config:validate", json=run_config_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["initial_capital"] == "10000.00"
    assert body["cost_values"]["futures_taker_fee_rate"] == "0.0004"
    assert body["start"] == "2025-06-30T15:00:00Z"
    assert body["money_management"] == {
        "mode": "manual",
        "leverage": 1,
        "reward_risk": 2.0,
        "atr_stop_multiple": 2.0,
    }

    invalid = dict(run_config_payload, position_size_pct=0.25)
    response = client.post("/api/v1/run-config:validate", json=invalid)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_run_config"
    assert "position_size_pct" in error["details"][0]["message"]
    assert "input" not in error["details"][0]

    reserved = dict(run_config_payload, trigger_feed="m1_subcandle")
    response = client.post("/api/v1/run-config:validate", json=reserved)
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "trigger_feed"

    turtle = {
        **run_config_payload,
        "money_management": {
            "mode": "turtle",
            "n_period": 20,
            "n_timeframe": "1d",
            "stop_n_multiple": 2.0,
            "leverage_cap": 10,
        },
    }
    response = client.post("/api/v1/run-config:validate", json=turtle)
    assert response.status_code == 200
    assert response.json()["money_management"]["mode"] == "turtle"

    unknown_policy = {
        **run_config_payload,
        "money_management": {"mode": "kelly"},
    }
    response = client.post(
        "/api/v1/run-config:validate",
        json=unknown_policy,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_run_config"


@pytest.mark.parametrize(
    "run_name",
    [
        "P2A-Review",
        "p2a.review",
        "p2a-review-name-longer-than-24",
    ],
)
def test_catalog_run_name_rejected_before_trigger(
    client: TestClient,
    run_config_payload: dict[str, object],
    run_name: str,
) -> None:
    invalid = dict(run_config_payload, run_name=run_name)
    for path, payload in (
        ("/api/v1/run-config:validate", invalid),
        ("/api/v1/runs", {"config": invalid}),
    ):
        response = client.post(path, json=payload)
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "invalid_run_config"
        assert error["details"] == [
            {
                "field": "run_name",
                "message": ("run_name must be at most 24 lowercase kebab-case characters"),
                "type": "catalog_run_name",
            }
        ]


def test_trigger_tracks_success_and_closes_sse_after_terminal_event(
    client: TestClient,
    run_config_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, object] = {}

    def fake_run_backtest(config: object, prereg: object, **kwargs: object) -> object:
        received.update(config=config, prereg=prereg, kwargs=kwargs)
        return SimpleNamespace(
            run_id="BT_00000001_p2a",
            evidence_hash="a" * 64,
            integrity_status="passed",
        )

    monkeypatch.setattr(jobs, "run_backtest", fake_run_backtest)
    response = client.post(
        "/api/v1/runs",
        json={"config": run_config_payload},
    )
    assert response.status_code == 202
    accepted = response.json()
    assert accepted["status"] == "QUEUED"
    assert accepted["events_url"].endswith(f"/{accepted['job_id']}/events")
    assert accepted["status_url"].endswith(f"/{accepted['job_id']}/status")

    status = _wait_for_terminal(client, accepted["job_id"])
    assert status == {
        "job_id": accepted["job_id"],
        "status": "SUCCEEDED",
        "catalog_status": "EVALUATED",
        "updated_at": status["updated_at"],
        "run_id": "BT_00000001_p2a",
        "evidence_hash": "a" * 64,
        "integrity_status": "passed",
        "summary_present": True,
        "error": None,
    }
    assert received["prereg"] == {}

    with client.stream("GET", accepted["events_url"]) as events:
        assert events.status_code == 200
        stream = "".join(events.iter_text())
    assert "event: status" in stream
    assert '"status":"SUCCEEDED"' in stream
    assert ": keepalive" not in stream


def test_trigger_maps_prereg_and_reports_sanitized_failure(
    client: TestClient,
    run_config_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("P2A_TEST_SECRET", "do-not-expose")

    def failing_run_backtest(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("failure includes do-not-expose")

    monkeypatch.setattr(jobs, "run_backtest", failing_run_backtest)
    response = client.post(
        "/api/v1/runs",
        json={
            "config": run_config_payload,
            "prereg": {
                "hypothesis": "Short-window contract",
                "primary_metric": "pf",
                "higher_is_better": True,
            },
        },
    )
    assert response.status_code == 202
    status = _wait_for_terminal(client, response.json()["job_id"])
    assert status["status"] == "FAILED"
    assert status["catalog_status"] is None
    assert status["error"]["code"] == "backtest_failed"
    assert status["error"]["message"] == "failure includes [redacted]"

    unsupported = client.post(
        "/api/v1/runs",
        json={
            "config": run_config_payload,
            "prereg": {"primary_metric": "not-a-metric"},
        },
    )
    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "invalid_run_config"


def test_job_setup_exception_transitions_to_failed(
    client: TestClient,
    run_config_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable_environment() -> dict[str, str]:
        raise RuntimeError("repository environment unavailable")

    monkeypatch.setattr(jobs, "_repository_env", unavailable_environment)
    response = client.post("/api/v1/runs", json={"config": run_config_payload})
    assert response.status_code == 202
    status = _wait_for_terminal(client, response.json()["job_id"])
    assert status["status"] == "FAILED"
    assert status["error"] == {
        "code": "backtest_failed",
        "message": "repository environment unavailable",
    }


def test_shutdown_cancels_queued_jobs_without_blocking_event_loop(
    run_config_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = Event()
    release = Event()
    executed: list[str] = []

    def blocking_job(job_id: str, _config: RunConfig, _prereg: dict[str, object]) -> None:
        started.set()
        release.wait(timeout=2)
        executed.append(job_id)

    monkeypatch.setattr(jobs, "_run_job", blocking_job)
    config = RunConfig.model_validate(run_config_payload)

    async def exercise() -> None:
        jobs.start_executor()
        try:
            for _ in range(4):
                jobs.submit_job(config, {})
            assert await asyncio.to_thread(started.wait, 1)
            fallback_release = Timer(0.5, release.set)
            fallback_release.start()
            before = time.monotonic()
            shutdown = asyncio.create_task(jobs.shutdown_executor())
            await asyncio.sleep(0.05)
            elapsed = time.monotonic() - before
            release.set()
            await asyncio.wait_for(shutdown, timeout=1)
            fallback_release.cancel()
            assert elapsed < 0.2
        finally:
            release.set()
            await jobs.shutdown_executor()

    asyncio.run(exercise())
    assert len(executed) == 1


def test_unknown_job_and_openapi_contract(
    client: TestClient,
) -> None:
    missing = client.get("/api/v1/jobs/unknown/status")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "job_not_found"

    document = client.get("/openapi.json").json()
    paths = document["paths"]
    assert {
        "/api/v1/run-config:validate",
        "/api/v1/jobs/{job_id}/events",
        "/api/v1/jobs/{job_id}/status",
        "/api/v1/strategies",
    } <= paths.keys()
    assert "post" in paths["/api/v1/runs"]
    assert "422" in paths["/api/v1/run-config:validate"]["post"]["responses"]
    assert "422" not in paths["/api/v1/runs"]["get"]["responses"]


class _MissingTableCursor:
    def fetchone(self) -> dict[str, object]:
        return {"relation": None}


class _MissingTableConnection:
    def execute(self, _query: str) -> _MissingTableCursor:
        return _MissingTableCursor()


def test_strategy_repository_falls_back_to_code_registry() -> None:
    connection = cast(SignalConnection, _MissingTableConnection())
    response = StrategyRepository(connection).list()
    assert len(response.data) == 1
    strategy = response.data[0]
    assert strategy.strategy_id == "vessel-reference"
    assert strategy.supported_timeframes == ["1h"]
    assert strategy.default_params["reward_risk"] == 2.0
    assert strategy.supported_money_management == ["manual", "turtle"]
    assert strategy.default_money_management["mode"] == "manual"
    assert strategy.source == "code_registry"


def test_the_strategy_list_does_not_restrict_the_money_management_modes() -> None:
    """A policy is deployed as a file, so two names cannot be baked into the schema.

    While the field was a closed pair of literals, a deployed policy could never
    reach the client: the response model dropped it and the generated client type
    had no name for it.
    """
    field = StrategyOption.model_json_schema()["properties"]["supported_money_management"]

    assert "enum" not in field["items"]


def test_a_mode_default_comes_from_the_policy_rather_than_a_manual_shaped_dict() -> None:
    """The prefilled settings used to be manual's fields regardless of the mode."""
    connection = cast(SignalConnection, _MissingTableConnection())
    strategy = StrategyRepository(connection).list().data[0]

    assert strategy.default_money_management == dict(
        MoneyManagementFactory.create({"mode": "manual"}).resolved_config()
    )
    assert _default_money_management("turtle") == dict(
        MoneyManagementFactory.create({"mode": "turtle"}).resolved_config()
    )


def test_a_mode_the_run_config_would_refuse_is_not_offered() -> None:
    """A policy can be registered and still be missing from the run configuration.

    Offering it showed a choice that was rejected the moment it was submitted.
    """
    assert _selectable_modes(["manual", "turtle", "never-registered"]) == ["manual", "turtle"]
    assert set(_selectable_modes(["manual", "turtle"])) <= SELECTABLE_MONEY_MANAGEMENT_MODES


def test_one_policy_that_fails_to_build_does_not_break_the_strategy_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A policy construction fault is isolated while defaults are frozen."""

    def explode(*args: object, **kwargs: object) -> object:
        raise RuntimeError("a deployed policy raised while being built")

    monkeypatch.setattr("web_api.repository.MoneyManagementFactory.create", staticmethod(explode))

    assert dict(_freeze_money_management_defaults({}, ["turtle"])) == {}


def test_a_rejected_declared_default_does_not_invent_another_default() -> None:
    modes, default = _money_management_options(
        ["manual", "not-in-the-run-union"],
        "not-in-the-run-union",
    )

    assert modes == ["manual"]
    assert default == {}


def test_all_rejected_modes_leave_both_the_list_and_default_empty() -> None:
    assert _money_management_options(["not-in-the-run-union"], "not-in-the-run-union") == (
        [],
        {},
    )


@pytest.mark.parametrize(
    ("supported", "declared_default"),
    [
        (["manual", "turtle"], "manual"),
        (["manual", "turtle"], "turtle"),
        (["manual", "not-in-the-run-union"], "not-in-the-run-union"),
    ],
)
def test_projected_default_is_empty_or_valid_for_a_selectable_mode(
    supported: list[str],
    declared_default: str,
) -> None:
    modes, default = _money_management_options(supported, declared_default)

    if not default:
        return
    assert default["mode"] in modes
    assert validate_money_management_config(default) == default


@pytest.mark.parametrize(
    "resolved",
    [
        {"mode": "manual"},
        {"mode": "turtle", "not_in_the_schema": True},
    ],
)
def test_a_policy_default_with_the_wrong_mode_or_shape_is_not_projected(
    monkeypatch: pytest.MonkeyPatch,
    resolved: dict[str, object],
) -> None:
    policy = SimpleNamespace(resolved_config=lambda: resolved)
    monkeypatch.setattr(
        "web_api.repository.MoneyManagementFactory.create",
        staticmethod(lambda *args, **kwargs: policy),
    )

    assert dict(_freeze_money_management_defaults({}, ["turtle"])) == {}
