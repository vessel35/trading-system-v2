"""Contracts for hiding a catalog run without removing anything stored."""

from pathlib import Path

from fastapi.testclient import TestClient


def _run_ids(client: TestClient, deleted: str) -> set[str]:
    response = client.get("/api/v1/runs", params={"deleted": deleted, "limit": 200})
    assert response.status_code == 200
    return {item["run_id"] for item in response.json()["data"]}


def test_delete_hides_the_run_from_the_default_listing_and_restore_returns_it(
    client: TestClient,
    disposable_run: tuple[str, Path],
) -> None:
    run_id, _ = disposable_run
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


def test_deleting_keeps_the_run_its_summary_and_its_evidence_file_in_place(
    client: TestClient,
    disposable_run: tuple[str, Path],
) -> None:
    run_id, artifact = disposable_run
    before = client.get(f"/api/v1/runs/{run_id}/summary").json()

    assert client.delete(f"/api/v1/runs/{run_id}").status_code == 200

    header = client.get(f"/api/v1/runs/{run_id}")
    assert header.status_code == 200
    assert header.json()["deleted_at"] is not None
    assert client.get(f"/api/v1/runs/{run_id}/summary").json() == before
    assert artifact.is_file()


def test_repeated_delete_and_restore_are_idempotent(
    client: TestClient,
    disposable_run: tuple[str, Path],
) -> None:
    run_id, _ = disposable_run
    first = client.delete(f"/api/v1/runs/{run_id}").json()
    second = client.delete(f"/api/v1/runs/{run_id}").json()
    assert second["changed"] is False
    assert second["deleted_at"] == first["deleted_at"]

    assert client.post(f"/api/v1/runs/{run_id}:restore").json()["changed"] is True
    repeated = client.post(f"/api/v1/runs/{run_id}:restore").json()
    assert repeated["changed"] is False
    assert repeated["deleted"] is False


def test_unknown_run_is_not_found_for_both_directions(
    client: TestClient,
    catalog_available: None,
) -> None:
    missing = "BT_20990101_000001_absent"
    assert client.delete(f"/api/v1/runs/{missing}").status_code == 404
    assert client.post(f"/api/v1/runs/{missing}:restore").status_code == 404


def test_default_listing_matches_the_explicit_exclude_filter(
    client: TestClient,
    catalog_available: None,
) -> None:
    default = client.get("/api/v1/runs", params={"limit": 200})
    explicit = client.get("/api/v1/runs", params={"deleted": "exclude", "limit": 200})
    assert default.status_code == 200
    assert default.json()["page"]["total"] == explicit.json()["page"]["total"]


def test_unknown_deleted_filter_is_rejected(
    client: TestClient,
    catalog_available: None,
) -> None:
    response = client.get("/api/v1/runs", params={"deleted": "sometimes"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_query"
