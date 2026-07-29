"""P2b sweep, tag, facet, and coverage HTTP contracts."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest
import web_api.jobs as jobs
import web_api.main as main_module
from fastapi.testclient import TestClient
from web_api.main import app, market_repository, repository
from web_api.models import (
    BacktestTag,
    DataSourceCoverage,
    DataSourceInventory,
    InventoryItem,
    RunTagsResponse,
    SweepSubmission,
    TagFacetsResponse,
)


@pytest.fixture
def run_config_payload() -> dict[str, object]:
    return {
        "run_name": "p2b-sweep",
        "strategy_id": "vessel-reference",
        "params": {"reward_risk": 2.0},
        "symbol": "BTC/USDT:USDT",
        "exchange": "binance",
        "timeframe": "1h",
        "market_type": "futures",
        "data_source": "crypto_data.ohlcv_futures",
        "start": "2025-07-01T00:00:00Z",
        "end": "2025-07-02T00:00:00Z",
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
    }


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _wait_for_terminal(client: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(200):
        response = client.get(f"/api/v1/jobs/{job_id}/status")
        assert response.status_code == 200
        body = cast(dict[str, Any], response.json())
        if body["status"] in {"SUCCEEDED", "FAILED", "ORPHANED"}:
            return body
        time.sleep(0.01)
    raise AssertionError("job did not reach a terminal state")


def test_grid_sweep_expands_validated_configs_and_reports_completion(
    client: TestClient,
    run_config_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, object] = {}

    class FakeHarness:
        def sweep(self, configs: list[object]) -> list[object]:
            received["configs"] = configs
            return [
                SimpleNamespace(run_id="BT_grid_1"),
                SimpleNamespace(run_id="BT_grid_2"),
            ]

    @contextmanager
    def fake_build_harness(*args: object, **kwargs: object) -> Iterator[FakeHarness]:
        received["build"] = (args, kwargs)
        yield FakeHarness()

    monkeypatch.setattr(jobs, "build_harness", fake_build_harness)
    response = client.post(
        "/api/v1/sweeps",
        json={
            "type": "grid",
            "config": run_config_payload,
            "axes": [{"parameter": "reward_risk", "values": [1.5, 2.5]}],
            "prereg": {"hypothesis": "grid contract", "primary_metric": "pf"},
        },
    )
    assert response.status_code == 202
    status = _wait_for_terminal(client, response.json()["job_id"])
    assert status["status"] == "SUCCEEDED"
    assert status["run_id"] == "BT_grid_1"
    assert status["run_count"] == 2
    assert status["sweep_id"].startswith("S-")
    configs = cast(list[Any], received["configs"])
    assert [config.params["reward_risk"] for config in configs] == [1.5, 2.5]
    assert [
        config.money_management.reward_risk for config in configs
    ] == [1.5, 2.5]
    assert {config.sweep["sweep_id"] for config in configs} == {status["sweep_id"]}
    assert [config.run_name for config in configs] == ["p2b-sweep-g1", "p2b-sweep-g2"]


def test_grid_sweep_assigns_explicit_money_management_axis(
    run_config_payload: dict[str, object],
) -> None:
    payload = SweepSubmission.model_validate(
        {
            "type": "grid",
            "config": {
                **run_config_payload,
                "params": {},
                "money_management": {
                    "mode": "turtle",
                    "n_period": 20,
                    "n_timeframe": "1d",
                    "stop_n_multiple": 2.0,
                    "leverage_cap": 10,
                },
            },
            "axes": [
                {
                    "parameter": "money_management.stop_n_multiple",
                    "values": [1.5, 2.5],
                }
            ],
        }
    )
    plan = main_module._prepare_sweep(payload)
    assert plan.configs is not None
    assert [
        config.money_management.stop_n_multiple
        for config in plan.configs
    ] == [1.5, 2.5]
    assert [config.params for config in plan.configs] == [{}, {}]


@pytest.mark.parametrize(
    ("sweep_type", "extra", "method", "run_count"),
    [
        ("walk_forward", {"folds": 3}, "walk_forward", 3),
        ("is_oos", {"split": 0.5}, "is_oos", 2),
    ],
)
def test_validation_sweep_modes_use_harness_aggregate_methods(
    client: TestClient,
    run_config_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    sweep_type: str,
    extra: dict[str, object],
    method: str,
    run_count: int,
) -> None:
    calls: list[tuple[str, object]] = []

    class FakeHarness:
        def walk_forward(self, _config: object, folds: int) -> dict[str, object]:
            calls.append(("walk_forward", folds))
            return {"representative_run_id": "BT_rep"}

        def is_oos(self, _config: object, split: float) -> dict[str, object]:
            calls.append(("is_oos", split))
            return {"representative_run_id": "BT_rep"}

    @contextmanager
    def fake_build_harness(*_args: object, **_kwargs: object) -> Iterator[FakeHarness]:
        yield FakeHarness()

    monkeypatch.setattr(jobs, "build_harness", fake_build_harness)
    response = client.post(
        "/api/v1/sweeps",
        json={"type": sweep_type, "config": run_config_payload, **extra},
    )
    assert response.status_code == 202
    status = _wait_for_terminal(client, response.json()["job_id"])
    assert status["status"] == "SUCCEEDED"
    assert status["run_id"] == "BT_rep"
    assert status["run_count"] == run_count
    assert calls == [(method, extra[next(iter(extra))])]


@pytest.mark.parametrize(
    ("sweep_type", "extra", "field"),
    [
        ("is_oos", {"split": 0.7}, "split"),
        ("walk_forward", {"folds": 5}, "folds"),
    ],
)
def test_validation_sweep_rejects_misaligned_timeframe_boundaries_before_job(
    client: TestClient,
    run_config_payload: dict[str, object],
    sweep_type: str,
    extra: dict[str, object],
    field: str,
) -> None:
    response = client.post(
        "/api/v1/sweeps",
        json={"type": sweep_type, "config": run_config_payload, **extra},
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_run_config"
    assert error["details"][0]["field"] == field
    assert "timeframe grid" in error["details"][0]["message"]


def test_grid_sweep_rejects_duplicate_or_oversized_axes(
    client: TestClient,
    run_config_payload: dict[str, object],
) -> None:
    duplicate = client.post(
        "/api/v1/sweeps",
        json={
            "type": "grid",
            "config": run_config_payload,
            "axes": [
                {"parameter": "params.reward_risk", "values": [1, 2]},
                {"parameter": "reward_risk", "values": [3, 4]},
            ],
        },
    )
    assert duplicate.status_code == 422
    assert duplicate.json()["error"]["code"] == "invalid_run_config"

    oversized = client.post(
        "/api/v1/sweeps",
        json={
            "type": "grid",
            "config": run_config_payload,
            "axes": [
                {"parameter": "reward_risk", "values": list(range(11))},
                {"parameter": "atr_stop_multiple", "values": list(range(10))},
            ],
        },
    )
    assert oversized.status_code == 422
    assert "100" in oversized.json()["error"]["details"][0]["message"]


class _FakeTagRepository:
    def __init__(self) -> None:
        self.run_exists = True
        self.tag = BacktestTag(
            tag_id=7,
            run_id="BT_tag",
            tag_type="purpose",
            tag_value="review",
            created_at=datetime(2026, 7, 26, tzinfo=UTC),
        )

    def get_run(self, _run_id: str) -> object | None:
        return object() if self.run_exists else None

    def get_tags(self, run_id: str) -> RunTagsResponse | None:
        if not self.run_exists:
            return None
        return RunTagsResponse(run_id=run_id, data=[self.tag])

    def get_tag(self, _run_id: str, _tag_type: str, _tag_value: str) -> BacktestTag:
        return self.tag


def test_tag_crud_uses_idempotent_short_lived_writer(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_repo = _FakeTagRepository()
    writes: list[tuple[str, str, str]] = []

    class FakeStore:
        def __init__(self, _connection: object) -> None:
            pass

        def add_tag(self, run_id: str, tag_type: str, tag_value: str) -> bool:
            writes.append((run_id, tag_type, tag_value))
            return False

        def remove_tag(self, run_id: str, tag_type: str, tag_value: str) -> bool:
            writes.append((run_id, tag_type, tag_value))
            return True

    @contextmanager
    def fake_writer() -> Iterator[object]:
        yield object()

    app.dependency_overrides[repository] = lambda: fake_repo
    monkeypatch.setattr(main_module, "connect_catalog_writer", fake_writer)
    monkeypatch.setattr(main_module, "BacktestCatalogStore", FakeStore)
    try:
        listed = client.get("/api/v1/runs/BT_tag/tags")
        assert listed.status_code == 200
        assert listed.json()["data"][0]["tag_value"] == "review"

        added = client.post(
            "/api/v1/runs/BT_tag/tags",
            json={"tag_type": "purpose", "tag_value": " review "},
        )
        assert added.status_code == 200
        assert added.json()["created"] is False
        assert writes[-1] == ("BT_tag", "purpose", "review")

        removed = client.request(
            "DELETE",
            "/api/v1/runs/BT_tag/tags",
            json={"tag_type": "purpose", "tag_value": "review"},
        )
        assert removed.status_code == 200
        assert removed.json()["removed"] is True
        assert writes[-1] == ("BT_tag", "purpose", "review")

        fake_repo.run_exists = False
        missing = client.post(
            "/api/v1/runs/missing/tags",
            json={"tag_type": "purpose", "tag_value": "review"},
        )
        assert missing.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_facets_coverage_and_inventory_are_read_only_dependency_queries(
    client: TestClient,
) -> None:
    class FakeCatalog:
        @staticmethod
        def tag_facets() -> TagFacetsResponse:
            return TagFacetsResponse(data=[])

    class FakeMarket:
        @staticmethod
        def coverage(**kwargs: str) -> DataSourceCoverage:
            return DataSourceCoverage(
                data_source=kwargs["data_source"],
                symbol=kwargs["symbol"],
                exchange=kwargs["exchange"],
                available_from=datetime(2025, 1, 1, tzinfo=UTC),
                available_to=datetime(2025, 1, 2, tzinfo=UTC),
                row_count=1440,
                expected_1m_rows=1441,
                missing_1m_rows=1,
            )

        @staticmethod
        def inventory(**kwargs: str) -> DataSourceInventory:
            return DataSourceInventory(
                data_source=kwargs["data_source"],
                items=[
                    InventoryItem(
                        symbol="BTC/USDT:USDT",
                        exchange="binance",
                        available_from=datetime(2025, 1, 1, tzinfo=UTC),
                        available_to=datetime(2025, 1, 2, tzinfo=UTC),
                        row_count=1440,
                        expected_1m_rows=1441,
                        missing_1m_rows=1,
                        coverage_ratio=1440 / 1441,
                    )
                ],
            )

    app.dependency_overrides[repository] = FakeCatalog
    app.dependency_overrides[market_repository] = FakeMarket
    try:
        facets = client.get("/api/v1/tags/facets")
        assert facets.status_code == 200
        assert facets.json() == {"data": []}

        coverage = client.get(
            "/api/v1/data-sources/crypto_data.ohlcv_futures/coverage",
            params={"symbol": "BTC/USDT:USDT", "exchange": "binance"},
        )
        assert coverage.status_code == 200
        assert coverage.json()["missing_1m_rows"] == 1
        assert coverage.json()["source_timeframe"] == "1m"

        inventory = client.get("/api/v1/data-sources/crypto_data.ohlcv_futures/inventory")
        assert inventory.status_code == 200
        assert inventory.json()["items"][0]["timeframe"] == "1m"
        assert inventory.json()["items"][0]["missing_1m_rows"] == 1
    finally:
        app.dependency_overrides.clear()


def test_inventory_rejects_unsupported_data_source(client: TestClient) -> None:
    class FakeMarket:
        @staticmethod
        def inventory(**_kwargs: str) -> DataSourceInventory:
            raise ValueError("run data_source is not a supported OHLCV table")

    app.dependency_overrides[market_repository] = FakeMarket
    try:
        response = client.get("/api/v1/data-sources/crypto_data.trades/inventory")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "unsupported_data_source"
    finally:
        app.dependency_overrides.clear()


def test_sweep_submission_rejects_cross_mode_fields(
    run_config_payload: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        SweepSubmission.model_validate(
            {
                "type": "walk_forward",
                "config": run_config_payload,
                "folds": 3,
                "axes": [{"parameter": "reward_risk", "values": [1, 2]}],
            }
        )
