"""FastAPI application for the P0 research catalog."""

from datetime import datetime
from typing import Annotated, Any, NoReturn

import psycopg
from core_lib import __version__ as core_lib_version
from fastapi import Depends, FastAPI, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from web_api import __version__ as web_api_version
from web_api.database import CatalogConnection, catalog_connection
from web_api.models import (
    ErrorResponse,
    HealthResponse,
    RunHeader,
    RunListResponse,
    RunSummaryResponse,
)
from web_api.repository import CatalogRepository, RunListQuery


class ApiError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: object | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


app = FastAPI(
    title="Backtest Research Web API",
    version=web_api_version,
    description=(
        "Read-only P0 backend-for-frontend. Stored catalog summaries are returned "
        "without metric or decision recomputation."
    ),
)


def custom_openapi() -> dict[str, Any]:
    """Keep generated responses aligned with the runtime 400 validation policy."""

    if app.openapi_schema is not None:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    paths = schema.get("paths")
    if isinstance(paths, dict):
        for path_item in paths.values():
            if not isinstance(path_item, dict):
                continue
            for operation in path_item.values():
                if not isinstance(operation, dict):
                    continue
                responses = operation.get("responses")
                if isinstance(responses, dict):
                    responses.pop("422", None)
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi  # type: ignore[method-assign]


@app.exception_handler(ApiError)
async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": jsonable_encoder(exc.details),
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "invalid_query",
                "message": "The request query is invalid.",
                "details": jsonable_encoder(exc.errors()),
            }
        },
    )


@app.exception_handler(psycopg.Error)
async def database_error_handler(_request: Request, _exc: psycopg.Error) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "catalog_unavailable",
                "message": "The backtest catalog is unavailable.",
                "details": None,
            }
        },
    )


@app.exception_handler(RuntimeError)
async def runtime_configuration_error_handler(
    _request: Request,
    _exc: RuntimeError,
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "catalog_unavailable",
                "message": "The backtest catalog is unavailable.",
                "details": None,
            }
        },
    )


def repository(
    connection: Annotated[CatalogConnection, Depends(catalog_connection)],
) -> CatalogRepository:
    return CatalogRepository(connection)


def not_found(run_id: str) -> NoReturn:
    raise ApiError(
        status_code=404,
        code="run_not_found",
        message=f"Backtest run '{run_id}' does not exist.",
        details={"run_id": run_id},
    )


@app.get(
    "/api/v1/runs",
    response_model=RunListResponse,
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def list_runs(
    repo: Annotated[CatalogRepository, Depends(repository)],
    strategy_id: str | None = None,
    symbol: str | None = None,
    timeframe: str | None = None,
    exchange: str | None = None,
    market_type: str | None = None,
    status: str | None = None,
    decision_route: str | None = None,
    gate_passed: bool | None = None,
    sweep_id: str | None = None,
    config_hash: str | None = None,
    created_at_from: datetime | None = None,
    created_at_to: datetime | None = None,
    period_start_from: datetime | None = None,
    period_start_to: datetime | None = None,
    period_end_from: datetime | None = None,
    period_end_to: datetime | None = None,
    sort: str = "-created_at",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RunListResponse:
    query = RunListQuery(
        strategy_id=strategy_id,
        symbol=symbol,
        timeframe=timeframe,
        exchange=exchange,
        market_type=market_type,
        status=status,
        decision_route=decision_route,
        gate_passed=gate_passed,
        sweep_id=sweep_id,
        config_hash=config_hash,
        created_at_from=created_at_from,
        created_at_to=created_at_to,
        period_start_from=period_start_from,
        period_start_to=period_start_to,
        period_end_from=period_end_from,
        period_end_to=period_end_to,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    try:
        return repo.list_runs(query)
    except ValueError as exc:
        raise ApiError(
            status_code=400,
            code="invalid_sort",
            message=str(exc),
            details={"sort": sort},
        ) from exc


@app.get(
    "/api/v1/runs/{run_id}",
    response_model=RunHeader,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_run(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
) -> RunHeader:
    run = repo.get_run(run_id)
    if run is None:
        not_found(run_id)
    return run


@app.get(
    "/api/v1/runs/{run_id}/summary",
    response_model=RunSummaryResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_run_summary(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
) -> RunSummaryResponse:
    summary = repo.get_summary(run_id)
    if summary is None:
        not_found(run_id)
    return summary


@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    responses={503: {"model": ErrorResponse}},
)
def health(repo: Annotated[CatalogRepository, Depends(repository)]) -> HealthResponse:
    return repo.health(
        core_lib_version=core_lib_version,
        web_api_version=web_api_version,
    )
