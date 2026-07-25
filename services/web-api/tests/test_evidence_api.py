"""Real seeded-Evidence contract tests for every P1a HTTP surface."""

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from web_api.database import connect_catalog, get_settings
from web_api.main import app

pytestmark = pytest.mark.integration

SEED_RUN_ID = "BT_20260725_000976_p1-seed-btc-60d"
MISSING_EVIDENCE_RUN_ID = "BT_20260724_000974_m10-real-data-feed"
EXPECTED_COUNTS = {
    "trades": 105,
    "executions": 210,
    "funding-settlements": 182,
    "equity": 1488,
    "chart-summaries": 2976,
    "positions": 1488,
    "integrity-checks": 6,
    "outcome-buckets": 105,
    "drawdown-episodes": 78,
    "trade-features": 420,
    "candidate-events": 106,
}


@pytest.fixture(scope="module")
def evidence_client() -> Iterator[TestClient]:
    path = get_settings().evidence_root / f"{SEED_RUN_ID}.sqlite"
    if not path.is_file():
        pytest.skip(f"seed Evidence is unavailable: {path}")
    try:
        with connect_catalog() as connection:
            seed = connection.execute(
                "SELECT evidence_path FROM public.backtest_run WHERE run_id = %s",
                (SEED_RUN_ID,),
            ).fetchone()
    except (OSError, RuntimeError, psycopg.Error) as exc:
        pytest.skip(f"development backtest_db is unavailable: {type(exc).__name__}")
    if seed is None:
        pytest.skip(f"seed run is absent from the catalog: {SEED_RUN_ID}")
    assert Path(str(seed["evidence_path"])).name == path.name
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(("endpoint", "expected"), EXPECTED_COUNTS.items())
def test_seed_evidence_endpoint_counts_and_cursor_contract(
    evidence_client: TestClient,
    endpoint: str,
    expected: int,
) -> None:
    response = evidence_client.get(
        f"/api/v1/runs/{SEED_RUN_ID}/{endpoint}",
        params={"limit": 17},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["page"]["total"] == expected
    assert body["page"]["limit"] == 17
    assert body["page"]["after_seq"] == 0
    assert len(body["data"]) == min(expected, 17)
    assert body["page"]["has_more"] is (expected > 17)
    assert body["page"]["next_after_seq"] is not None

    if expected > 17:
        following = evidence_client.get(
            f"/api/v1/runs/{SEED_RUN_ID}/{endpoint}",
            params={
                "limit": 17,
                "after_seq": body["page"]["next_after_seq"],
            },
        )
        assert following.status_code == 200
        following_body = following.json()
        assert following_body["page"]["after_seq"] == body["page"]["next_after_seq"]
        assert following_body["data"] != body["data"]


def test_scaled_decimals_timestamps_json_and_real_values_are_typed(
    evidence_client: TestClient,
) -> None:
    trade = evidence_client.get(
        f"/api/v1/runs/{SEED_RUN_ID}/trades",
        params={"limit": 1},
    ).json()["data"][0]
    for field in (
        "entry_price",
        "entry_quantity",
        "gross_pnl",
        "total_fee",
        "net_pnl",
        "r0",
    ):
        assert isinstance(trade[field], str)
        Decimal(trade[field])
        assert "E" not in trade[field].upper()
    assert trade["entry_time"].endswith(("Z", "+00:00"))
    assert isinstance(trade["r_multiple"], float)
    assert isinstance(trade["liquidated"], bool)

    integrity = evidence_client.get(
        f"/api/v1/runs/{SEED_RUN_ID}/integrity-checks",
        params={"limit": 1},
    ).json()["data"][0]
    assert isinstance(integrity["passed"], bool)
    assert isinstance(integrity["detail_json"], dict)
    assert integrity["checked_at"].endswith(("Z", "+00:00"))

    episode = evidence_client.get(
        f"/api/v1/runs/{SEED_RUN_ID}/drawdown-episodes",
        params={"limit": 1},
    ).json()["data"][0]
    assert isinstance(episode["peak_equity"], str)
    assert isinstance(episode["contributing_trades_json"], list)


def test_filters_support_core_tabs_and_trade_drawer(
    evidence_client: TestClient,
) -> None:
    trade_id = 1
    cases = (
        ("trades", {"side": "SHORT", "exit_reason": "TAKE_PROFIT"}, 12),
        ("executions", {"trade_id": trade_id}, 2),
        ("funding-settlements", {"trade_id": trade_id}, 2),
        ("positions", {"trade_id": trade_id}, 14),
        ("trade-features", {"trade_id": trade_id}, 4),
        ("candidate-events", {"linked_trade_id": trade_id}, 1),
        ("chart-summaries", {"series_name": "equity"}, 1488),
        (
            "outcome-buckets",
            {"subject_kind": "trade", "subject_id": trade_id},
            1,
        ),
        ("drawdown-episodes", {"kind": "drawdown"}, 11),
    )
    for endpoint, params, expected in cases:
        response = evidence_client.get(
            f"/api/v1/runs/{SEED_RUN_ID}/{endpoint}",
            params=params,
        )
        assert response.status_code == 200
        assert response.json()["page"]["total"] == expected


def test_missing_run_and_missing_artifact_have_distinct_errors(
    evidence_client: TestClient,
) -> None:
    missing_run = evidence_client.get("/api/v1/runs/BT_00000000_000000_missing/trades")
    assert missing_run.status_code == 404
    assert missing_run.json()["error"]["code"] == "run_not_found"

    unavailable = evidence_client.get(f"/api/v1/runs/{MISSING_EVIDENCE_RUN_ID}/trades")
    assert unavailable.status_code == 409
    assert unavailable.json()["error"]["code"] == "evidence_unavailable"
    assert unavailable.json()["error"]["details"]["reason"] == "evidence_file_missing"


def test_openapi_exposes_p1a_and_decimal_formats(
    evidence_client: TestClient,
) -> None:
    document = evidence_client.get("/openapi.json").json()
    paths = document["paths"]
    for endpoint in EXPECTED_COUNTS:
        assert f"/api/v1/runs/{{run_id}}/{endpoint}" in paths
    schemas = document["components"]["schemas"]
    assert schemas["Trade"]["properties"]["entry_price"]["format"] == "decimal"
    assert schemas["EquityPoint"]["properties"]["total_equity"]["format"] == "decimal"
