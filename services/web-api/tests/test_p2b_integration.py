"""Real P2b grid sweep, tag CRUD, facets, and coverage round trip."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from web_api.database import connect_catalog, connect_crypto, get_settings
from web_api.main import app

pytestmark = pytest.mark.integration


def _require_databases() -> None:
    try:
        with connect_catalog() as catalog, connect_crypto() as crypto:
            for connection in (catalog, crypto):
                row = connection.execute(
                    "SELECT current_setting('transaction_read_only') AS value"
                ).fetchone()
                assert row is not None
                assert row["value"] == "on"
    except (OSError, RuntimeError, psycopg.Error) as exc:
        pytest.skip(f"development PostgreSQL preset is unavailable: {type(exc).__name__}")


def test_grid_sweep_tag_crud_facets_and_coverage_round_trip(tmp_path: Path) -> None:
    _require_databases()
    previous_root = os.environ.get("WEBAPI_EVIDENCE_ROOT")
    os.environ["WEBAPI_EVIDENCE_ROOT"] = str(tmp_path)
    get_settings.cache_clear()
    try:
        run_name = f"p2b-{uuid4().hex[:12]}"
        tag_value = f"p2b-{uuid4().hex[:10]}"
        payload: dict[str, Any] = {
            "type": "grid",
            "config": {
                "run_name": run_name,
                "strategy_id": "vessel-reference",
                "params": {},
                "symbol": "BTC/USDT:USDT",
                "exchange": "binance",
                "timeframe": "1h",
                "market_type": "futures",
                "data_source": "crypto_data.ohlcv_futures",
                "start": "2025-07-01T00:00:00Z",
                "end": "2025-07-01T06:00:00Z",
                "initial_capital": "10000",
                "seed": 976,
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
            },
            "axes": [{"parameter": "reward_risk", "values": [1.5, 2.5]}],
            "prereg": {
                "hypothesis": "P2b real grid sweep",
                "primary_metric": "pf",
                "success_threshold": 1.3,
                "failure_threshold": 1.0,
                "higher_is_better": True,
                "declared_by": "web-api-p2b-integration-test",
            },
        }
        with TestClient(app) as client:
            coverage = client.get(
                "/api/v1/data-sources/crypto_data.ohlcv_futures/coverage",
                params={"symbol": "BTC/USDT:USDT", "exchange": "binance"},
            )
            assert coverage.status_code == 200
            coverage_body = coverage.json()
            assert coverage_body["row_count"] > 0
            assert coverage_body["available_from"] < payload["config"]["start"]
            assert coverage_body["available_to"] > payload["config"]["end"]

            accepted = client.post("/api/v1/sweeps", json=payload)
            assert accepted.status_code == 202
            job_id = accepted.json()["job_id"]

            deadline = time.monotonic() + 180
            status: dict[str, object] = {}
            while time.monotonic() < deadline:
                response = client.get(f"/api/v1/jobs/{job_id}/status")
                assert response.status_code == 200
                status = response.json()
                if status["status"] in {"SUCCEEDED", "FAILED"}:
                    break
                time.sleep(0.1)
            assert status["status"] == "SUCCEEDED", status
            assert status["run_count"] == 2
            sweep_id = str(status["sweep_id"])
            representative_run_id = str(status["run_id"])

            sweep = client.get(f"/api/v1/sweeps/{sweep_id}")
            assert sweep.status_code == 200
            sweep_body = sweep.json()
            assert sweep_body["representative_run_id"] == representative_run_id
            assert len(sweep_body["runs"]) == 2
            assert sweep_body["oos_degradation_limit"] == 0.5
            assert sweep_body["psr_minimum"] == 0.95
            assert {item["run"]["params_json"]["reward_risk"] for item in sweep_body["runs"]} == {
                1.5,
                2.5,
            }
            assert all(item["summary_status"] == "available" for item in sweep_body["runs"])

            tag_payload = {"tag_type": "purpose", "tag_value": tag_value}
            created = client.post(
                f"/api/v1/runs/{representative_run_id}/tags",
                json=tag_payload,
            )
            assert created.status_code == 200
            assert created.json()["created"] is True
            duplicate = client.post(
                f"/api/v1/runs/{representative_run_id}/tags",
                json=tag_payload,
            )
            assert duplicate.status_code == 200
            assert duplicate.json()["created"] is False

            listed = client.get(f"/api/v1/runs/{representative_run_id}/tags")
            assert listed.status_code == 200
            assert listed.json()["data"][0]["tag_value"] == tag_value
            facets = client.get("/api/v1/tags/facets")
            assert facets.status_code == 200
            purpose = next(item for item in facets.json()["data"] if item["tag_type"] == "purpose")
            assert any(value["tag_value"] == tag_value for value in purpose["values"])
            filtered = client.get(
                "/api/v1/runs",
                params={"tag_type": "purpose", "tag_value": tag_value},
            )
            assert filtered.status_code == 200
            assert [item["run_id"] for item in filtered.json()["data"]] == [representative_run_id]

            removed = client.request(
                "DELETE",
                f"/api/v1/runs/{representative_run_id}/tags",
                json=tag_payload,
            )
            assert removed.status_code == 200
            assert removed.json()["removed"] is True
            idempotent_delete = client.request(
                "DELETE",
                f"/api/v1/runs/{representative_run_id}/tags",
                json=tag_payload,
            )
            assert idempotent_delete.status_code == 200
            assert idempotent_delete.json()["removed"] is False

            print(
                "P2B_SWEEP_RESULT "
                f"sweep_id={sweep_id} run_count=2 "
                f"representative_run_id={representative_run_id}"
            )
    finally:
        if previous_root is None:
            os.environ.pop("WEBAPI_EVIDENCE_ROOT", None)
        else:
            os.environ["WEBAPI_EVIDENCE_ROOT"] = previous_root
        get_settings.cache_clear()
