"""Self-seeded Evidence contract tests for every P1a HTTP surface."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from web_api.database import get_settings
from web_api.main import _epoch_ms, _utc_datetime, app

pytestmark = pytest.mark.integration

REPOSITORY_ROOT = Path(__file__).parents[3]
ENDPOINT_TABLES = {
    "trades": "TRADE",
    "executions": "EXECUTION",
    "funding-settlements": "FUNDING_SETTLEMENT",
    "equity": "PORTFOLIO_PNL",
    "chart-summaries": "CHART_SUMMARY",
    "positions": "POSITION",
    "integrity-checks": "INTEGRITY_CHECK",
    "outcome-buckets": "OUTCOME_BUCKET",
    "drawdown-episodes": "DRAWDOWN_RUNUP_EPISODE",
    "trade-features": "TRADE_FEATURE_SNAPSHOT",
    "candidate-events": "CANDIDATE_EVENT",
}


@dataclass(frozen=True)
class SeededEvidence:
    client: TestClient
    run_id: str
    path: Path
    counts: dict[str, int]


def _seed_with_script(evidence_root: Path) -> tuple[str, Path]:
    """Run the public seed command with its documented deterministic defaults."""

    completed = subprocess.run(
        [
            sys.executable,
            str(REPOSITORY_ROOT / "scripts" / "seed_evidence.py"),
            "--evidence-root",
            str(evidence_root),
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Evidence seed command failed with exit {completed.returncode}")
    result: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            result[key] = value
    run_id = result.get("run_id")
    evidence_path = result.get("evidence_path")
    if run_id is None or evidence_path is None:
        raise RuntimeError("Evidence seed command did not report its run and artifact")
    if result.get("integrity_status") != "passed":
        raise RuntimeError("Evidence seed command did not pass integrity checks")
    path = Path(evidence_path).resolve()
    if path.parent != evidence_root.resolve() or not path.is_file():
        raise RuntimeError("Evidence seed command wrote outside the requested root")
    return run_id, path


@pytest.fixture(scope="module")
def seeded_evidence(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SeededEvidence]:
    evidence_root = tmp_path_factory.mktemp("webapi-evidence")
    run_id, path = _seed_with_script(evidence_root)
    with sqlite3.connect(path) as connection:
        counts = {
            endpoint: int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
            for endpoint, table in ENDPOINT_TABLES.items()
        }

    previous_root = os.environ.get("WEBAPI_EVIDENCE_ROOT")
    os.environ["WEBAPI_EVIDENCE_ROOT"] = str(evidence_root)
    get_settings.cache_clear()
    try:
        assert Path(get_settings().evidence_root).resolve() == evidence_root.resolve()
        with TestClient(app) as client:
            yield SeededEvidence(client=client, run_id=run_id, path=path, counts=counts)
    finally:
        if previous_root is None:
            os.environ.pop("WEBAPI_EVIDENCE_ROOT", None)
        else:
            os.environ["WEBAPI_EVIDENCE_ROOT"] = previous_root
        get_settings.cache_clear()


@pytest.mark.parametrize("endpoint", ENDPOINT_TABLES)
def test_seed_evidence_endpoint_counts_and_cursor_contract(
    seeded_evidence: SeededEvidence,
    endpoint: str,
) -> None:
    expected = seeded_evidence.counts[endpoint]
    response = seeded_evidence.client.get(
        f"/api/v1/runs/{seeded_evidence.run_id}/{endpoint}",
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
        following = seeded_evidence.client.get(
            f"/api/v1/runs/{seeded_evidence.run_id}/{endpoint}",
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
    seeded_evidence: SeededEvidence,
) -> None:
    trade = seeded_evidence.client.get(
        f"/api/v1/runs/{seeded_evidence.run_id}/trades",
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

    integrity = seeded_evidence.client.get(
        f"/api/v1/runs/{seeded_evidence.run_id}/integrity-checks",
        params={"limit": 1},
    ).json()["data"][0]
    assert isinstance(integrity["passed"], bool)
    assert isinstance(integrity["detail_json"], dict)
    assert integrity["checked_at"].endswith(("Z", "+00:00"))

    episode = seeded_evidence.client.get(
        f"/api/v1/runs/{seeded_evidence.run_id}/drawdown-episodes",
        params={"limit": 1},
    ).json()["data"][0]
    assert isinstance(episode["peak_equity"], str)
    assert isinstance(episode["contributing_trades_json"], list)


def test_filters_support_core_tabs_and_trade_drawer(
    seeded_evidence: SeededEvidence,
) -> None:
    with sqlite3.connect(seeded_evidence.path) as connection:
        trade_id = int(connection.execute("SELECT min(trade_id) FROM TRADE").fetchone()[0])
        side, exit_reason = connection.execute(
            """
            SELECT side, exit_reason
            FROM TRADE
            WHERE exit_reason IS NOT NULL
            ORDER BY trade_id
            LIMIT 1
            """
        ).fetchone()
        series_name = str(
            connection.execute(
                "SELECT series_name FROM CHART_SUMMARY ORDER BY summary_seq LIMIT 1"
            ).fetchone()[0]
        )
        outcome_subject = connection.execute(
            """
            SELECT subject_kind, subject_id
            FROM OUTCOME_BUCKET
            ORDER BY bucket_id
            LIMIT 1
            """
        ).fetchone()
        episode_kind = str(
            connection.execute(
                "SELECT kind FROM DRAWDOWN_RUNUP_EPISODE ORDER BY episode_id LIMIT 1"
            ).fetchone()[0]
        )
        cases = (
            (
                "trades",
                {"side": side, "exit_reason": exit_reason},
                connection.execute(
                    "SELECT count(*) FROM TRADE WHERE side = ? AND exit_reason = ?",
                    (side, exit_reason),
                ).fetchone()[0],
            ),
            (
                "executions",
                {"trade_id": trade_id},
                connection.execute(
                    """
                    SELECT count(*)
                    FROM EXECUTION AS e
                    WHERE EXISTS (
                        SELECT 1
                        FROM TRADE AS t
                        WHERE t.trade_id = ?
                          AND (
                              t.entry_execution_id = e.execution_id
                              OR t.exit_execution_id = e.execution_id
                          )
                    )
                    """,
                    (trade_id,),
                ).fetchone()[0],
            ),
            (
                "funding-settlements",
                {"trade_id": trade_id},
                connection.execute(
                    "SELECT count(*) FROM FUNDING_SETTLEMENT WHERE trade_id = ?",
                    (trade_id,),
                ).fetchone()[0],
            ),
            (
                "positions",
                {"trade_id": trade_id},
                connection.execute(
                    "SELECT count(*) FROM POSITION WHERE trade_id = ?",
                    (trade_id,),
                ).fetchone()[0],
            ),
            (
                "trade-features",
                {"trade_id": trade_id},
                connection.execute(
                    "SELECT count(*) FROM TRADE_FEATURE_SNAPSHOT WHERE trade_id = ?",
                    (trade_id,),
                ).fetchone()[0],
            ),
            (
                "candidate-events",
                {"linked_trade_id": trade_id},
                connection.execute(
                    "SELECT count(*) FROM CANDIDATE_EVENT WHERE linked_trade_id = ?",
                    (trade_id,),
                ).fetchone()[0],
            ),
            (
                "chart-summaries",
                {"series_name": series_name},
                connection.execute(
                    "SELECT count(*) FROM CHART_SUMMARY WHERE series_name = ?",
                    (series_name,),
                ).fetchone()[0],
            ),
            (
                "outcome-buckets",
                {
                    "subject_kind": outcome_subject[0],
                    "subject_id": outcome_subject[1],
                },
                connection.execute(
                    """
                    SELECT count(*)
                    FROM OUTCOME_BUCKET
                    WHERE subject_kind = ? AND subject_id = ?
                    """,
                    outcome_subject,
                ).fetchone()[0],
            ),
            (
                "drawdown-episodes",
                {"kind": episode_kind},
                connection.execute(
                    "SELECT count(*) FROM DRAWDOWN_RUNUP_EPISODE WHERE kind = ?",
                    (episode_kind,),
                ).fetchone()[0],
            ),
        )

    for endpoint, params, expected in cases:
        response = seeded_evidence.client.get(
            f"/api/v1/runs/{seeded_evidence.run_id}/{endpoint}",
            params=params,
        )
        assert response.status_code == 200
        assert response.json()["page"]["total"] == expected


def test_offset_free_temporal_filters_are_utc(
    seeded_evidence: SeededEvidence,
) -> None:
    naive = datetime(2025, 8, 1)
    explicit_utc = datetime(2025, 8, 1, tzinfo=UTC)
    assert _utc_datetime(naive) == explicit_utc
    assert _epoch_ms(naive) == _epoch_ms(explicit_utc)

    for parameter in ("entry_time_from", "entry_time_to"):
        offset_free = seeded_evidence.client.get(
            f"/api/v1/runs/{seeded_evidence.run_id}/trades",
            params={parameter: "2025-08-01T00:00:00", "limit": 200},
        )
        with_utc = seeded_evidence.client.get(
            f"/api/v1/runs/{seeded_evidence.run_id}/trades",
            params={parameter: "2025-08-01T00:00:00Z", "limit": 200},
        )
        assert offset_free.status_code == 200
        assert offset_free.json() == with_utc.json()


def test_execution_join_deduplicates_shared_reversal_fill(
    seeded_evidence: SeededEvidence,
) -> None:
    with sqlite3.connect(seeded_evidence.path) as connection:
        first_trade_id, shared_execution_id, second_trade_id, original_entry_id = (
            connection.execute(
                """
                SELECT first.trade_id,
                       first.exit_execution_id,
                       second.trade_id,
                       second.entry_execution_id
                FROM TRADE AS first
                JOIN TRADE AS second ON second.trade_id > first.trade_id
                WHERE first.exit_execution_id IS NOT NULL
                  AND first.exit_execution_id <> second.entry_execution_id
                ORDER BY first.trade_id, second.trade_id
                LIMIT 1
                """
            ).fetchone()
        )
        execution_count = int(connection.execute("SELECT count(*) FROM EXECUTION").fetchone()[0])
        connection.execute(
            "UPDATE TRADE SET entry_execution_id = ? WHERE trade_id = ?",
            (shared_execution_id, second_trade_id),
        )
        connection.commit()

    try:
        execution_ids: list[int] = []
        after_seq = 0
        while True:
            response = seeded_evidence.client.get(
                f"/api/v1/runs/{seeded_evidence.run_id}/executions",
                params={"after_seq": after_seq, "limit": 17},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["page"]["total"] == execution_count
            execution_ids.extend(row["execution_id"] for row in body["data"])
            if not body["page"]["has_more"]:
                break
            next_after_seq = body["page"]["next_after_seq"]
            assert isinstance(next_after_seq, int)
            assert next_after_seq > after_seq
            after_seq = next_after_seq

        assert len(execution_ids) == execution_count
        assert len(execution_ids) == len(set(execution_ids))
        assert execution_ids.count(shared_execution_id) == 1
        assert first_trade_id != second_trade_id
    finally:
        with sqlite3.connect(seeded_evidence.path) as connection:
            connection.execute(
                "UPDATE TRADE SET entry_execution_id = ? WHERE trade_id = ?",
                (original_entry_id, second_trade_id),
            )
            connection.commit()


def test_missing_run_and_missing_artifact_have_distinct_errors(
    seeded_evidence: SeededEvidence,
) -> None:
    missing_run = seeded_evidence.client.get("/api/v1/runs/BT_00000000_000000_missing/trades")
    assert missing_run.status_code == 404
    assert missing_run.json()["error"]["code"] == "run_not_found"

    parked = seeded_evidence.path.with_suffix(".parked")
    seeded_evidence.path.replace(parked)
    try:
        unavailable = seeded_evidence.client.get(f"/api/v1/runs/{seeded_evidence.run_id}/trades")
        assert unavailable.status_code == 409
        assert unavailable.json()["error"]["code"] == "evidence_unavailable"
        assert unavailable.json()["error"]["details"]["reason"] == "evidence_file_missing"
    finally:
        parked.replace(seeded_evidence.path)


def test_openapi_exposes_p1a_and_decimal_formats(
    seeded_evidence: SeededEvidence,
) -> None:
    document = seeded_evidence.client.get("/openapi.json").json()
    paths = document["paths"]
    for endpoint in ENDPOINT_TABLES:
        assert f"/api/v1/runs/{{run_id}}/{endpoint}" in paths
    schemas = document["components"]["schemas"]
    assert schemas["Trade"]["properties"]["entry_price"]["format"] == "decimal"
    assert schemas["EquityPoint"]["properties"]["total_equity"]["format"] == "decimal"
