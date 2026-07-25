"""Real dry-run trigger round trip through catalog and immutable Evidence."""

from __future__ import annotations

import os
import time
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from web_api.database import (
    connect_catalog,
    connect_crypto,
    connect_signal,
    get_settings,
)
from web_api.main import app

pytestmark = pytest.mark.integration


def _require_databases() -> None:
    try:
        with (
            connect_catalog() as catalog,
            connect_crypto() as crypto,
            connect_signal() as signal,
        ):
            for connection in (catalog, crypto, signal):
                row = connection.execute(
                    "SELECT current_setting('transaction_read_only') AS value"
                ).fetchone()
                assert row is not None
                assert row["value"] == "on"
    except (OSError, RuntimeError, psycopg.Error) as exc:
        pytest.skip(f"development PostgreSQL preset is unavailable: {type(exc).__name__}")


def test_dry_run_trigger_catalog_evidence_and_detail_round_trip(
    tmp_path: Path,
) -> None:
    _require_databases()
    previous_root = os.environ.get("WEBAPI_EVIDENCE_ROOT")
    os.environ["WEBAPI_EVIDENCE_ROOT"] = str(tmp_path)
    get_settings.cache_clear()
    try:
        payload = {
            "config": {
                "run_name": f"p2a-{uuid4().hex[:12]}",
                "strategy_id": "vessel-reference",
                "params": {},
                "symbol": "BTC/USDT:USDT",
                "exchange": "binance",
                "timeframe": "1h",
                "market_type": "futures",
                "data_source": "crypto_data.ohlcv_futures",
                "start": "2025-07-01T00:00:00Z",
                "end": "2025-07-04T00:00:00Z",
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
            "prereg": {
                "hypothesis": "P2a real trigger round trip",
                "primary_metric": "pf",
                "success_threshold": 1.3,
                "failure_threshold": 1.0,
                "higher_is_better": True,
                "declared_by": "web-api-integration-test",
            },
        }
        with TestClient(app) as client:
            strategies = client.get("/api/v1/strategies")
            assert strategies.status_code == 200
            vessel = next(
                item
                for item in strategies.json()["data"]
                if item["strategy_id"] == "vessel-reference"
            )
            assert vessel["source"] == "strategy_registry"
            assert vessel["supported_timeframes"] == ["1h"]

            accepted = client.post("/api/v1/runs", json=payload)
            assert accepted.status_code == 202
            job_id = accepted.json()["job_id"]

            deadline = time.monotonic() + 120
            status: dict[str, object] = {}
            while time.monotonic() < deadline:
                response = client.get(f"/api/v1/jobs/{job_id}/status")
                assert response.status_code == 200
                status = response.json()
                if status["status"] in {"SUCCEEDED", "FAILED"}:
                    break
                time.sleep(0.1)
            assert status["status"] == "SUCCEEDED", status
            run_id = str(status["run_id"])
            evidence_hash = str(status["evidence_hash"])
            assert run_id
            assert len(evidence_hash) == 64
            assert status["catalog_status"] == "EVALUATED"
            assert status["summary_present"] is True

            detail = client.get(f"/api/v1/runs/{run_id}")
            assert detail.status_code == 200
            header = detail.json()
            assert header["run_id"] == run_id
            assert header["status"] == "EVALUATED"
            assert header["evidence_hash"] == evidence_hash

            evidence_path = (tmp_path / Path(header["evidence_path"]).name).resolve()
            assert evidence_path.parent == tmp_path.resolve()
            assert evidence_path.is_file()

            summary = client.get(f"/api/v1/runs/{run_id}/summary")
            assert summary.status_code == 200
            assert summary.json()["summary_status"] == "available"
            integrity = client.get(
                f"/api/v1/runs/{run_id}/integrity-checks",
                params={"limit": 10},
            )
            assert integrity.status_code == 200
            assert integrity.json()["page"]["total"] > 0
    finally:
        if previous_root is None:
            os.environ.pop("WEBAPI_EVIDENCE_ROOT", None)
        else:
            os.environ["WEBAPI_EVIDENCE_ROOT"] = previous_root
        get_settings.cache_clear()
