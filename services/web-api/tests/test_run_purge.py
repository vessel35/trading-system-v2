"""Contracts for the irreversible purge of a run and its Evidence artifact."""

from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient


def test_purge_removes_the_row_its_tags_and_the_evidence_file(
    client: TestClient,
    disposable_run: tuple[str, Path],
    tag_count: Callable[[str], int],
) -> None:
    run_id, artifact = disposable_run
    assert artifact.is_file()
    assert tag_count(run_id) == 1

    response = client.delete(f"/api/v1/runs/{run_id}:purge")
    assert response.status_code == 200
    assert response.json() == {
        "run_id": run_id,
        "run_removed": True,
        "evidence_removed": True,
        "evidence_path": f"{run_id}.sqlite",
    }

    assert not artifact.is_file()
    assert not Path(f"{artifact}-wal").is_file()
    assert tag_count(run_id) == 0
    assert client.get(f"/api/v1/runs/{run_id}").status_code == 404
    listed = client.get("/api/v1/runs", params={"deleted": "include", "limit": 200})
    assert run_id not in {item["run_id"] for item in listed.json()["data"]}


def test_a_soft_deleted_run_can_still_be_purged(
    client: TestClient,
    disposable_run: tuple[str, Path],
) -> None:
    run_id, artifact = disposable_run
    assert client.delete(f"/api/v1/runs/{run_id}").json()["deleted"] is True
    assert run_id in {
        item["run_id"]
        for item in client.get(
            "/api/v1/runs",
            params={"deleted": "only", "limit": 200},
        ).json()["data"]
    }

    response = client.delete(f"/api/v1/runs/{run_id}:purge")
    assert response.status_code == 200
    assert response.json()["run_removed"] is True
    assert not artifact.is_file()
    assert client.get(f"/api/v1/runs/{run_id}").status_code == 404


def test_purge_completes_when_the_evidence_file_is_already_absent(
    client: TestClient,
    disposable_run: tuple[str, Path],
) -> None:
    run_id, artifact = disposable_run
    artifact.unlink()

    response = client.delete(f"/api/v1/runs/{run_id}:purge")
    assert response.status_code == 200
    assert response.json()["evidence_removed"] is False
    assert response.json()["run_removed"] is True
    assert client.get(f"/api/v1/runs/{run_id}").status_code == 404


def test_purge_leaves_other_runs_and_their_artifacts_alone(
    client: TestClient,
    disposable_run: tuple[str, Path],
) -> None:
    run_id, artifact = disposable_run
    neighbour = artifact.parent / "BT_20200101_000001_neighbour.sqlite"
    neighbour.write_bytes(b"another run's artifact")
    try:
        assert client.delete(f"/api/v1/runs/{run_id}:purge").status_code == 200
        assert neighbour.is_file()
    finally:
        neighbour.unlink(missing_ok=True)


def test_purging_an_unknown_run_is_not_found(
    client: TestClient,
    catalog_available: None,
) -> None:
    response = client.delete("/api/v1/runs/BT_20990101_000001_absent:purge")
    assert response.status_code == 404
    assert response.json()["error"]["details"]["run_id"] == "BT_20990101_000001_absent"
