"""Contracts for hiding a catalog run without removing anything stored."""

from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from web_api.database import connect_catalog
from web_api.main import app


@pytest.fixture(scope="module")
def visible_run_id() -> str:
    """Return one run that the catalog currently lists, or skip."""

    try:
        with connect_catalog() as connection:
            row = connection.execute(
                """
                SELECT run_id
                FROM public.backtest_run
                WHERE deleted_at IS NULL
                ORDER BY run_seq DESC
                LIMIT 1
                """
            ).fetchone()
    except (OSError, RuntimeError, psycopg.Error) as exc:
        pytest.skip(f"development backtest_db is unavailable: {type(exc).__name__}")
    if row is None:
        pytest.skip("development backtest_db has no listed run to exercise")
    return str(row["run_id"])


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def restored(client: TestClient, visible_run_id: str) -> Iterator[str]:
    """Hand out the run id and put its delete marker back however the test ends."""

    try:
        yield visible_run_id
    finally:
        client.post(f"/api/v1/runs/{visible_run_id}:restore")


def _run_ids(client: TestClient, deleted: str) -> set[str]:
    response = client.get("/api/v1/runs", params={"deleted": deleted, "limit": 200})
    assert response.status_code == 200
    return {item["run_id"] for item in response.json()["data"]}


def test_delete_hides_the_run_from_the_default_listing_and_restore_returns_it(
    client: TestClient,
    restored: str,
) -> None:
    run_id = restored
    assert run_id in _run_ids(client, "exclude")

    deletion = client.delete(f"/api/v1/runs/{run_id}")
    assert deletion.status_code == 200
    body = deletion.json()
    assert body["deleted"] is True
    assert body["changed"] is True
    assert body["deleted_at"] is not None

    assert run_id not in _run_ids(client, "exclude")
    assert run_id in _run_ids(client, "only")
    assert run_id in _run_ids(client, "include")

    restore = client.post(f"/api/v1/runs/{run_id}:restore")
    assert restore.status_code == 200
    assert restore.json() == {
        "run_id": run_id,
        "deleted": False,
        "deleted_at": None,
        "changed": True,
    }
    assert run_id in _run_ids(client, "exclude")


def test_deleting_keeps_the_run_and_its_summary_readable_by_run_id(
    client: TestClient,
    restored: str,
) -> None:
    run_id = restored
    before = client.get(f"/api/v1/runs/{run_id}/summary").json()

    assert client.delete(f"/api/v1/runs/{run_id}").status_code == 200

    header = client.get(f"/api/v1/runs/{run_id}")
    assert header.status_code == 200
    assert header.json()["deleted_at"] is not None
    assert client.get(f"/api/v1/runs/{run_id}/summary").json() == before


def test_repeated_delete_and_restore_are_idempotent(
    client: TestClient,
    restored: str,
) -> None:
    run_id = restored
    first = client.delete(f"/api/v1/runs/{run_id}").json()
    second = client.delete(f"/api/v1/runs/{run_id}").json()
    assert second["changed"] is False
    assert second["deleted_at"] == first["deleted_at"]

    assert client.post(f"/api/v1/runs/{run_id}:restore").json()["changed"] is True
    repeated = client.post(f"/api/v1/runs/{run_id}:restore").json()
    assert repeated["changed"] is False
    assert repeated["deleted"] is False


def test_unknown_run_is_not_found_for_both_directions(client: TestClient) -> None:
    missing = "BT_20990101_000001_absent"
    assert client.delete(f"/api/v1/runs/{missing}").status_code == 404
    assert client.post(f"/api/v1/runs/{missing}:restore").status_code == 404


def test_default_listing_matches_the_explicit_exclude_filter(
    client: TestClient,
    visible_run_id: str,
) -> None:
    del visible_run_id
    default = client.get("/api/v1/runs", params={"limit": 200})
    explicit = client.get("/api/v1/runs", params={"deleted": "exclude", "limit": 200})
    assert default.status_code == 200
    assert default.json()["page"]["total"] == explicit.json()["page"]["total"]


def test_unknown_deleted_filter_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/runs", params={"deleted": "sometimes"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_query"
