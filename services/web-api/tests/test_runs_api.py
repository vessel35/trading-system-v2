"""Contracts for P2a validation, background jobs, SSE, and strategy discovery."""

from __future__ import annotations

import time
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, cast

import pytest
import web_api.jobs as jobs
from fastapi.testclient import TestClient
from web_api.database import SignalConnection
from web_api.main import app
from web_api.repository import StrategyRepository


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
    assert strategy.source == "code_registry"
