"""Real-catalog contract tests for all P0 HTTP surfaces."""

from collections.abc import Iterator
from decimal import Decimal

import psycopg
import pytest
from fastapi.testclient import TestClient
from web_api.database import connect_catalog
from web_api.main import app
from web_api.repository import _decimal_strings


def test_decimal_serialization_uses_fixed_point_notation() -> None:
    converted = _decimal_strings(
        {
            "net_pnl_total": Decimal("0E-8"),
            "total_fee": Decimal("-1.23000000"),
        }
    )
    assert converted["net_pnl_total"] == "0.00000000"
    assert converted["total_fee"] == "-1.23000000"


@pytest.fixture(scope="module")
def catalog_rows() -> dict[str, object]:
    try:
        with connect_catalog() as connection:
            read_only = connection.execute(
                "SELECT current_setting('transaction_read_only') AS value"
            ).fetchone()
            counts = connection.execute(
                """
                SELECT
                    count(*) AS run_count,
                    count(s.run_id) AS summary_count,
                    count(*) FILTER (WHERE s.run_id IS NULL) AS summary_absent_count
                FROM public.backtest_run r
                LEFT JOIN public.backtest_summary s ON s.run_id = r.run_id
                """
            ).fetchone()
            with_summary = connection.execute(
                """
                SELECT r.run_id
                FROM public.backtest_run r
                JOIN public.backtest_summary s ON s.run_id = r.run_id
                ORDER BY r.created_at DESC
                LIMIT 1
                """
            ).fetchone()
            without_summary = connection.execute(
                """
                SELECT r.run_id
                FROM public.backtest_run r
                LEFT JOIN public.backtest_summary s ON s.run_id = r.run_id
                WHERE s.run_id IS NULL
                ORDER BY r.created_at DESC
                LIMIT 1
                """
            ).fetchone()
            with_zero_decimal = connection.execute(
                """
                SELECT run_id
                FROM public.backtest_summary
                WHERE net_pnl_total = 0
                   OR gross_pnl_total = 0
                   OR total_fee = 0
                   OR total_slippage = 0
                   OR total_funding = 0
                   OR total_liquidation_penalty = 0
                ORDER BY computed_at DESC
                LIMIT 1
                """
            ).fetchone()
    except (OSError, RuntimeError, psycopg.Error) as exc:
        pytest.skip(f"development backtest_db is unavailable: {type(exc).__name__}")
    assert read_only is not None
    assert counts is not None
    assert with_summary is not None
    assert with_zero_decimal is not None
    return {
        "read_only": read_only["value"],
        "run_count": int(counts["run_count"]),
        "summary_count": int(counts["summary_count"]),
        "summary_absent_count": int(counts["summary_absent_count"]),
        "with_summary": with_summary["run_id"],
        "without_summary": without_summary["run_id"] if without_summary else None,
        "with_zero_decimal": with_zero_decimal["run_id"],
    }


@pytest.fixture(scope="module")
def client(catalog_rows: dict[str, object]) -> Iterator[TestClient]:
    del catalog_rows
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.integration
def test_runs_lists_real_rows_filters_sorts_and_pages(
    client: TestClient,
    catalog_rows: dict[str, object],
) -> None:
    response = client.get("/api/v1/runs", params={"limit": 5, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["page"]["total"] == catalog_rows["run_count"]
    assert body["page"]["limit"] == 5
    assert len(body["data"]) == 5
    run_count = catalog_rows["run_count"]
    assert isinstance(run_count, int)
    # The catalog is provisioned per environment and starts empty, so this asserts only
    # what the paging assertions above consume rather than an accumulated run history.
    assert run_count >= 5
    assert [row["created_at"] for row in body["data"]] == sorted(
        [row["created_at"] for row in body["data"]],
        reverse=True,
    )

    sample = body["data"][0]
    filtered = client.get(
        "/api/v1/runs",
        params={
            "strategy_id": sample["strategy_id"],
            "symbol": sample["symbol"],
            "timeframe": sample["timeframe"],
            "limit": 2,
            "sort": "-pf",
        },
    )
    assert filtered.status_code == 200
    filtered_body = filtered.json()
    assert len(filtered_body["data"]) <= 2
    assert all(row["strategy_id"] == sample["strategy_id"] for row in filtered_body["data"])
    assert all(row["symbol"] == sample["symbol"] for row in filtered_body["data"])

    invalid = client.get("/api/v1/runs", params={"sort": "drop_table"})
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_sort"
    invalid_limit = client.get("/api/v1/runs", params={"limit": 201})
    assert invalid_limit.status_code == 400
    assert invalid_limit.json()["error"]["code"] == "invalid_query"


@pytest.mark.integration
def test_run_header_returns_every_reproducibility_field_and_decimal_strings(
    client: TestClient,
    catalog_rows: dict[str, object],
) -> None:
    run_id = str(catalog_rows["with_summary"])
    response = client.get(f"/api/v1/runs/{run_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert isinstance(body["initial_capital"], str)
    Decimal(body["initial_capital"])
    for optional_decimal in ("risk_per_trade", "position_size_pct"):
        assert body[optional_decimal] is None or isinstance(body[optional_decimal], str)
    assert body["created_at"].endswith(("Z", "+00:00"))
    assert "resolved_indicators_json" in body
    assert "source_data_hash" in body

    missing = client.get("/api/v1/runs/BT_00000000_000000_missing")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "run_not_found"


@pytest.mark.integration
def test_run_summary_supports_one_and_zero_rows_with_decimal_strings(
    client: TestClient,
    catalog_rows: dict[str, object],
) -> None:
    run_id = str(catalog_rows["with_summary"])
    response = client.get(f"/api/v1/runs/{run_id}/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["summary_status"] == "available"
    assert body["summary"] is not None
    for field in (
        "initial_capital",
        "final_equity",
        "net_pnl_total",
        "gross_pnl_total",
        "total_fee",
        "total_slippage",
        "total_funding",
        "total_liquidation_penalty",
    ):
        value = body["summary"][field]
        assert value is None or isinstance(value, str)
        if value is not None:
            Decimal(value)
            assert "E" not in value.upper()

    without_summary = catalog_rows["without_summary"]
    if without_summary is not None:
        absent = client.get(f"/api/v1/runs/{without_summary}/summary")
        assert absent.status_code == 200
        absent_body = absent.json()
        assert absent_body["summary"] is None
        assert absent_body["summary_status"] != "available"


@pytest.mark.integration
def test_decimal_zeroes_use_fixed_point_notation(
    client: TestClient,
    catalog_rows: dict[str, object],
) -> None:
    run_id = str(catalog_rows["with_zero_decimal"])
    response = client.get(f"/api/v1/runs/{run_id}/summary")
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary is not None
    money_fields = (
        "initial_capital",
        "final_equity",
        "net_pnl_total",
        "gross_pnl_total",
        "total_fee",
        "total_slippage",
        "total_funding",
        "total_liquidation_penalty",
    )
    values = [summary[field] for field in money_fields if summary[field] is not None]
    assert any(Decimal(value).is_zero() for value in values)
    assert all("E" not in value.upper() for value in values)


@pytest.mark.integration
def test_health_proves_read_only_real_catalog_connection(
    client: TestClient,
    catalog_rows: dict[str, object],
) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["catalog"]["run_count"] == catalog_rows["run_count"]
    assert body["catalog"]["read_only"] is True
    assert catalog_rows["read_only"] == "on"
    assert body["core_lib_version"]
    assert body["catalog"]["schema_version"] == "20260724"


@pytest.mark.integration
def test_openapi_exposes_five_surfaces_and_decimal_formats(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    document = response.json()
    paths = document["paths"]
    assert {
        "/api/v1/runs",
        "/api/v1/runs/{run_id}",
        "/api/v1/runs/{run_id}/summary",
        "/api/v1/health",
    } <= paths.keys()
    assert "422" not in paths["/api/v1/runs"]["get"]["responses"]
    schemas = document["components"]["schemas"]
    assert schemas["RunSummary"]["properties"]["net_pnl_total"]["anyOf"][0]["format"] == "decimal"
    assert schemas["RunHeader"]["properties"]["initial_capital"]["format"] == "decimal"
