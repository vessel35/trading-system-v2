"""FastAPI application for the P0 research catalog."""

import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from itertools import product
from math import prod
from typing import Annotated, Any, NoReturn, cast
from uuid import uuid4

import psycopg
from backtest_service.adapters.catalog_store import (
    BacktestCatalogStore,
    WriteConnection,
    validate_catalog_run_name,
)
from backtest_service.config import RunConfig
from core_lib import __version__ as core_lib_version
from fastapi import Body, Depends, FastAPI, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import SkipValidation, ValidationError

from web_api import __version__ as web_api_version
from web_api.data_jobs import (
    TERMINAL_DATA_JOB_STATES,
    shutdown_data_jobs,
    submit_data_job,
)
from web_api.data_jobs import (
    registry as data_job_registry,
)
from web_api.database import (
    CatalogConfigurationError,
    CatalogConnection,
    CryptoConnection,
    SignalConnection,
    catalog_connection,
    connect_catalog_writer,
    crypto_connection,
    signal_connection,
)
from web_api.evidence import (
    EvidenceRepository,
    EvidenceUnavailableError,
    open_evidence,
)
from web_api.jobs import (
    TERMINAL_JOB_STATES,
    SweepPlan,
    shutdown_executor,
    start_executor,
    submit_job,
    submit_sweep_job,
)
from web_api.jobs import (
    registry as job_registry,
)
from web_api.models import (
    CandidateEvent,
    CandleCollection,
    ChartSummary,
    ConditionalExpectancy,
    DataJobRequest,
    DataJobStatus,
    DataSourceCoverage,
    DataSourceInventory,
    Decision,
    DrawdownEpisode,
    EquityPoint,
    ErrorResponse,
    EvidenceCollection,
    Execution,
    FindingsCollection,
    FundingSettlement,
    HealthResponse,
    IndicatorSnapshot,
    IntegrityCheck,
    JobStatus,
    MissedOpportunity,
    OutcomeBucket,
    Position,
    PreregistrationResponse,
    RunAccepted,
    RunComparisonResponse,
    RunHeader,
    RunListResponse,
    RunSubmission,
    RunSummaryResponse,
    RunTagsResponse,
    Signal,
    StrategyListResponse,
    SweepResponse,
    SweepSubmission,
    TagDeleteResponse,
    TagFacetsResponse,
    TagInput,
    TagMutationResponse,
    TagType,
    Trade,
    TradeFeature,
)
from web_api.repository import (
    CatalogRepository,
    MarketDataRepository,
    RunListQuery,
    StrategyRepository,
)


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


@asynccontextmanager
async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
    start_executor()
    try:
        yield
    finally:
        await shutdown_data_jobs()
        await shutdown_executor()


app = FastAPI(
    title="Backtest Research Web API",
    version=web_api_version,
    description=(
        "Research backend-for-frontend. Read endpoints remain physically read-only. "
        "Data-job endpoints deliberately launch collector subprocesses with Binance "
        "network access and crypto_data write capability."
    ),
    lifespan=lifespan,
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
        validation_paths = {
            "/api/v1/run-config:validate",
            "/api/v1/runs",
            "/api/v1/sweeps",
        }
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                if not isinstance(operation, dict):
                    continue
                responses = operation.get("responses")
                keep_validation = path in validation_paths and method == "post"
                if isinstance(responses, dict) and not keep_validation:
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
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    run_request = request.method == "POST" and request.url.path in {
        "/api/v1/run-config:validate",
        "/api/v1/runs",
        "/api/v1/sweeps",
    }
    data_job_request = request.method == "POST" and request.url.path == "/api/v1/data-jobs"
    return JSONResponse(
        status_code=422 if run_request else 400,
        content={
            "error": {
                "code": (
                    "invalid_run_config"
                    if run_request
                    else "invalid_data_job"
                    if data_job_request
                    else "invalid_query"
                ),
                "message": (
                    "The run request is invalid."
                    if run_request
                    else "The data job request is invalid."
                    if data_job_request
                    else "The request query is invalid."
                ),
                "details": _validation_details(exc),
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


@app.exception_handler(CatalogConfigurationError)
async def runtime_configuration_error_handler(
    _request: Request,
    _exc: CatalogConfigurationError,
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


@app.exception_handler(EvidenceUnavailableError)
async def evidence_unavailable_error_handler(
    _request: Request,
    exc: EvidenceUnavailableError,
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "evidence_unavailable",
                "message": "Detailed Evidence for this run is unavailable.",
                "details": {"reason": exc.reason},
            }
        },
    )


@app.exception_handler(sqlite3.Error)
async def evidence_database_error_handler(
    _request: Request,
    _exc: sqlite3.Error,
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "evidence_unavailable",
                "message": "Detailed Evidence for this run is unavailable.",
                "details": {"reason": "evidence_query_failed"},
            }
        },
    )


def repository(
    connection: Annotated[CatalogConnection, Depends(catalog_connection)],
) -> CatalogRepository:
    return CatalogRepository(connection)


def market_repository(
    connection: Annotated[CryptoConnection, Depends(crypto_connection)],
) -> MarketDataRepository:
    return MarketDataRepository(connection)


def strategy_repository(
    connection: Annotated[SignalConnection, Depends(signal_connection)],
) -> StrategyRepository:
    return StrategyRepository(connection)


def _validation_details(exc: ValidationError | RequestValidationError) -> list[dict[str, str]]:
    return [
        {
            "field": ".".join(str(part) for part in error["loc"]),
            "message": str(error["msg"]),
            "type": str(error["type"]),
        }
        for error in exc.errors()
    ]


def _validated_run_config(value: object) -> RunConfig:
    try:
        config = RunConfig.model_validate(value)
        validate_catalog_run_name(config.run_name)
        return config
    except ValidationError as exc:
        raise ApiError(
            status_code=422,
            code="invalid_run_config",
            message="The run configuration is invalid.",
            details=_validation_details(exc),
        ) from exc
    except ValueError as exc:
        raise ApiError(
            status_code=422,
            code="invalid_run_config",
            message="The run configuration is invalid.",
            details=[
                {
                    "field": "run_name",
                    "message": str(exc),
                    "type": "catalog_run_name",
                }
            ],
        ) from exc
    except NotImplementedError as exc:
        raise ApiError(
            status_code=422,
            code="invalid_run_config",
            message="The run configuration is invalid.",
            details=[
                {
                    "field": "trigger_feed",
                    "message": str(exc),
                    "type": "not_implemented",
                }
            ],
        ) from exc


def _sweep_error(message: str, *, field: str = "axes") -> NoReturn:
    raise ApiError(
        status_code=422,
        code="invalid_run_config",
        message="The sweep configuration is invalid.",
        details=[{"field": field, "message": message, "type": "sweep_contract"}],
    )


def _sweep_run_name(base_name: str, index: int) -> str:
    suffix = f"g{index + 1}"
    prefix = base_name[: 24 - len(suffix) - 1].rstrip("-")
    return f"{prefix}-{suffix}"


def _assign_axis(params: dict[str, object], parameter: str, value: object) -> None:
    path = parameter.removeprefix("params.").split(".")
    current = params
    for part in path[:-1]:
        nested = current.get(part)
        if nested is None:
            replacement: dict[str, object] = {}
            current[part] = replacement
            current = replacement
        elif isinstance(nested, dict):
            current = cast(dict[str, object], nested)
        else:
            _sweep_error(
                f"axis '{parameter}' crosses a non-object parameter",
                field=f"axes.{parameter}",
            )
    current[path[-1]] = value


def _validate_sweep_boundaries(config: RunConfig, payload: SweepSubmission) -> None:
    if payload.type == "grid":
        return
    duration = config.end - config.start
    if payload.type == "is_oos":
        if payload.split is None:
            raise RuntimeError("validated is_oos sweep is missing split")
        boundaries = [config.start + duration * payload.split]
        field = "split"
    else:
        if payload.folds is None:
            raise RuntimeError("validated walk_forward sweep is missing folds")
        boundaries = [
            config.start + duration * (index / payload.folds) for index in range(1, payload.folds)
        ]
        field = "folds"
    timeframe = MarketDataRepository._timeframe_duration(config.timeframe)
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    misaligned = [
        boundary.isoformat()
        for boundary in boundaries
        if (boundary - epoch) % timeframe != timedelta(0)
    ]
    if misaligned:
        _sweep_error(
            (
                f"{payload.type} boundaries must align to the {config.timeframe} "
                f"timeframe grid: {misaligned}"
            ),
            field=field,
        )


def _prepare_sweep(payload: SweepSubmission) -> SweepPlan:
    base = _validated_run_config(payload.config)
    _validate_sweep_boundaries(base, payload)
    sweep_id = f"S-{uuid4().hex}"
    sweep_meta = {
        **({} if base.sweep is None else base.sweep),
        "sweep_id": sweep_id,
    }
    base_payload = base.model_dump()
    base_payload["sweep"] = sweep_meta

    if payload.type != "grid":
        config = _validated_run_config(base_payload)
        return SweepPlan(
            sweep_id=sweep_id,
            type=payload.type,
            config=config,
            folds=payload.folds,
            split=payload.split,
        )

    names = [axis.parameter.removeprefix("params.") for axis in payload.axes]
    if len(names) != len(set(names)):
        _sweep_error("grid axis parameters must be unique")
    cell_count = prod(len(axis.values) for axis in payload.axes)
    if cell_count > 100:
        _sweep_error("grid sweeps are limited to 100 cells")
    configs: list[RunConfig] = []
    value_sets = [axis.values for axis in payload.axes]
    for index, combination in enumerate(product(*value_sets)):
        cell = deepcopy(base_payload)
        params = cast(dict[str, object], cell["params"])
        for axis, value in zip(payload.axes, combination, strict=True):
            _assign_axis(params, axis.parameter, value)
        cell["run_name"] = _sweep_run_name(base.run_name, index)
        cell["sweep"] = {
            **sweep_meta,
            "fold_label": f"grid-{index + 1}",
        }
        configs.append(_validated_run_config(cell))
    return SweepPlan(
        sweep_id=sweep_id,
        type="grid",
        config=configs[0],
        configs=tuple(configs),
    )


def not_found(run_id: str) -> NoReturn:
    raise ApiError(
        status_code=404,
        code="run_not_found",
        message=f"Backtest run '{run_id}' does not exist.",
        details={"run_id": run_id},
    )


@contextmanager
def evidence_repository(
    catalog: CatalogRepository,
    run_id: str,
) -> Iterator[EvidenceRepository]:
    found, evidence_path = catalog.get_evidence_path(run_id)
    if not found:
        not_found(run_id)
    with open_evidence(evidence_path) as connection:
        yield EvidenceRepository(connection)


def _utc_datetime(value: datetime | None) -> datetime | None:
    """Normalize temporal filters, treating offset-free ISO input as UTC."""

    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _epoch_ms(value: datetime | None) -> int | None:
    normalized = _utc_datetime(value)
    return int(normalized.timestamp() * 1000) if normalized is not None else None


@app.post(
    "/api/v1/run-config:validate",
    response_model=RunConfig,
    responses={422: {"model": ErrorResponse}},
)
def validate_run_config(
    payload: Annotated[SkipValidation[RunConfig], Body()],
) -> RunConfig:
    return _validated_run_config(payload)


@app.post(
    "/api/v1/runs",
    response_model=RunAccepted,
    status_code=202,
    responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def trigger_run(payload: RunSubmission) -> RunAccepted:
    config = _validated_run_config(payload.config)
    prereg = payload.prereg.model_dump(exclude_none=True) if payload.prereg is not None else {}
    state = submit_job(config, prereg)
    base = f"/api/v1/jobs/{state.job_id}"
    return RunAccepted(
        job_id=state.job_id,
        status="QUEUED",
        events_url=f"{base}/events",
        status_url=f"{base}/status",
    )


@app.post(
    "/api/v1/sweeps",
    response_model=RunAccepted,
    status_code=202,
    responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def trigger_sweep(payload: SweepSubmission) -> RunAccepted:
    plan = _prepare_sweep(payload)
    prereg = payload.prereg.model_dump(exclude_none=True) if payload.prereg is not None else {}
    state = submit_sweep_job(plan, prereg)
    base = f"/api/v1/jobs/{state.job_id}"
    return RunAccepted(
        job_id=state.job_id,
        status="QUEUED",
        events_url=f"{base}/events",
        status_url=f"{base}/status",
    )


def _job_not_found(job_id: str) -> NoReturn:
    raise ApiError(
        status_code=404,
        code="job_not_found",
        message=f"Dry-run job '{job_id}' does not exist.",
        details={"job_id": job_id},
    )


@app.get(
    "/api/v1/jobs/{job_id}/status",
    response_model=JobStatus,
    responses={404: {"model": ErrorResponse}},
)
def get_job_status(job_id: str) -> JobStatus:
    state = job_registry.get(job_id)
    if state is None:
        _job_not_found(job_id)
    return state.public_status()


@app.get(
    "/api/v1/jobs/{job_id}/events",
    response_class=StreamingResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_job_events(job_id: str) -> StreamingResponse:
    if job_registry.get(job_id) is None:
        _job_not_found(job_id)

    async def stream() -> AsyncIterator[str]:
        revision = -1
        while True:
            state = job_registry.get(job_id)
            if state is None:
                return
            if state.revision != revision:
                revision = state.revision
                payload = state.public_status().model_dump_json(exclude_none=True)
                yield f"event: status\ndata: {payload}\n\n"
                if state.status in TERMINAL_JOB_STATES:
                    return
            try:
                await job_registry.wait_for_change(job_id, revision, timeout=15.0)
            except TimeoutError:
                yield ": keepalive\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _data_job_not_found(job_id: str) -> NoReturn:
    raise ApiError(
        status_code=404,
        code="data_job_not_found",
        message=f"Data job '{job_id}' does not exist.",
        details={"job_id": job_id},
    )


@app.post(
    "/api/v1/data-jobs",
    response_model=DataJobStatus,
    status_code=202,
    responses={400: {"model": ErrorResponse}},
    summary="Queue a collector data job",
    description=(
        "Launches a collector subprocess with external Binance network access and "
        "crypto_data write capability after validation."
    ),
)
async def trigger_data_job(payload: DataJobRequest) -> DataJobStatus:
    if payload.exchange != "binance":
        raise ApiError(
            status_code=400,
            code="unsupported_exchange",
            message=f"Exchange '{payload.exchange}' is not supported for data jobs.",
            details={"exchange": payload.exchange},
        )
    state = submit_data_job(payload)
    return state.public_status()


@app.get(
    "/api/v1/data-jobs",
    response_model=list[DataJobStatus],
)
def list_data_jobs() -> list[DataJobStatus]:
    return [state.public_status() for state in data_job_registry.list()]


@app.get(
    "/api/v1/data-jobs/{job_id}",
    response_model=DataJobStatus,
    responses={404: {"model": ErrorResponse}},
)
def get_data_job(job_id: str) -> DataJobStatus:
    state = data_job_registry.get(job_id)
    if state is None:
        _data_job_not_found(job_id)
    return state.public_status()


@app.get(
    "/api/v1/data-jobs/{job_id}/events",
    response_class=StreamingResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_data_job_events(job_id: str) -> StreamingResponse:
    if data_job_registry.get(job_id) is None:
        _data_job_not_found(job_id)

    async def stream() -> AsyncIterator[str]:
        revision = -1
        while True:
            state = data_job_registry.get(job_id)
            if state is None:
                return
            if state.revision != revision:
                revision = state.revision
                payload = state.public_status().model_dump_json(exclude_none=True)
                yield f"event: status\ndata: {payload}\n\n"
                if state.status in TERMINAL_DATA_JOB_STATES:
                    return
            try:
                await data_job_registry.wait_for_change(job_id, revision, timeout=15.0)
            except TimeoutError:
                yield ": keepalive\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get(
    "/api/v1/strategies",
    response_model=StrategyListResponse,
    responses={503: {"model": ErrorResponse}},
)
def list_strategies(
    repo: Annotated[StrategyRepository, Depends(strategy_repository)],
) -> StrategyListResponse:
    return repo.list()


@app.get(
    "/api/v1/sweeps/{sweep_id}",
    response_model=SweepResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_sweep(
    sweep_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
) -> SweepResponse:
    sweep = repo.get_sweep(sweep_id)
    if sweep is None:
        raise ApiError(
            status_code=404,
            code="sweep_not_found",
            message=f"Backtest sweep '{sweep_id}' does not exist.",
            details={"sweep_id": sweep_id},
        )
    return sweep


@app.get(
    "/api/v1/tags/facets",
    response_model=TagFacetsResponse,
    responses={503: {"model": ErrorResponse}},
)
def get_tag_facets(
    repo: Annotated[CatalogRepository, Depends(repository)],
) -> TagFacetsResponse:
    return repo.tag_facets()


@app.get(
    "/api/v1/data-sources/{data_source}/coverage",
    response_model=DataSourceCoverage,
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_data_source_coverage(
    data_source: str,
    market: Annotated[MarketDataRepository, Depends(market_repository)],
    symbol: Annotated[str, Query(min_length=1, max_length=30)],
    exchange: Annotated[str, Query(min_length=1, max_length=20)],
) -> DataSourceCoverage:
    try:
        return market.coverage(
            data_source=data_source,
            symbol=symbol,
            exchange=exchange,
        )
    except ValueError as exc:
        raise ApiError(
            status_code=400,
            code="unsupported_data_source",
            message=str(exc),
            details={"data_source": data_source},
        ) from exc


@app.get(
    "/api/v1/data-sources/{data_source}/inventory",
    response_model=DataSourceInventory,
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_data_source_inventory(
    data_source: str,
    market: Annotated[MarketDataRepository, Depends(market_repository)],
) -> DataSourceInventory:
    try:
        return market.inventory(data_source=data_source)
    except ValueError as exc:
        raise ApiError(
            status_code=400,
            code="unsupported_data_source",
            message=str(exc),
            details={"data_source": data_source},
        ) from exc


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
    tag_type: TagType | None = None,
    tag_value: str | None = None,
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
        tag_type=tag_type,
        tag_value=tag_value,
        created_at_from=_utc_datetime(created_at_from),
        created_at_to=_utc_datetime(created_at_to),
        period_start_from=_utc_datetime(period_start_from),
        period_start_to=_utc_datetime(period_start_to),
        period_end_from=_utc_datetime(period_end_from),
        period_end_to=_utc_datetime(period_end_to),
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
    "/api/v1/runs:compare",
    response_model=RunComparisonResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def compare_runs(
    repo: Annotated[CatalogRepository, Depends(repository)],
    run_ids: Annotated[list[str] | None, Query()] = None,
    sweep_id: str | None = None,
) -> RunComparisonResponse:
    if (run_ids is None) == (sweep_id is None):
        raise ApiError(
            status_code=400,
            code="invalid_query",
            message="Provide exactly one of run_ids or sweep_id.",
        )
    normalized_ids: list[str] | None = None
    if run_ids is not None:
        normalized_ids = [
            item
            for value in run_ids
            for item in (part.strip() for part in value.split(","))
            if item
        ]
        normalized_ids = list(dict.fromkeys(normalized_ids))
        if not 2 <= len(normalized_ids) <= 12:
            raise ApiError(
                status_code=400,
                code="invalid_query",
                message="run_ids must contain between 2 and 12 unique run IDs.",
            )
    try:
        response = repo.compare_runs(run_ids=normalized_ids, sweep_id=sweep_id)
    except KeyError as exc:
        missing = str(exc.args[0]).split(",")
        raise ApiError(
            status_code=404,
            code="run_not_found",
            message="One or more comparison runs do not exist.",
            details={"run_ids": missing},
        ) from exc
    if not response.data:
        raise ApiError(
            status_code=404,
            code="comparison_not_found",
            message="No runs were found for the requested comparison.",
            details={"sweep_id": sweep_id},
        )
    return response


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
    "/api/v1/runs/{run_id}/prereg",
    response_model=PreregistrationResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_run_prereg(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
) -> PreregistrationResponse:
    prereg = repo.get_prereg(run_id)
    if prereg is None:
        not_found(run_id)
    return prereg


@app.get(
    "/api/v1/runs/{run_id}/tags",
    response_model=RunTagsResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_run_tags(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
) -> RunTagsResponse:
    tags = repo.get_tags(run_id)
    if tags is None:
        not_found(run_id)
    return tags


@app.post(
    "/api/v1/runs/{run_id}/tags",
    response_model=TagMutationResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def add_run_tag(
    run_id: str,
    payload: TagInput,
    repo: Annotated[CatalogRepository, Depends(repository)],
) -> TagMutationResponse:
    if repo.get_run(run_id) is None:
        not_found(run_id)
    with connect_catalog_writer() as connection:
        store = BacktestCatalogStore(cast(WriteConnection, connection))
        created = store.add_tag(run_id, payload.tag_type, payload.tag_value)
    tag = repo.get_tag(run_id, payload.tag_type, payload.tag_value)
    if tag is None:
        raise RuntimeError("tag mutation committed without a readable tag row")
    return TagMutationResponse(tag=tag, created=created)


@app.delete(
    "/api/v1/runs/{run_id}/tags",
    response_model=TagDeleteResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def remove_run_tag(
    run_id: str,
    payload: Annotated[TagInput, Body()],
    repo: Annotated[CatalogRepository, Depends(repository)],
) -> TagDeleteResponse:
    if repo.get_run(run_id) is None:
        not_found(run_id)
    with connect_catalog_writer() as connection:
        store = BacktestCatalogStore(cast(WriteConnection, connection))
        removed = store.remove_tag(run_id, payload.tag_type, payload.tag_value)
    return TagDeleteResponse(
        run_id=run_id,
        tag_type=payload.tag_type,
        tag_value=payload.tag_value,
        removed=removed,
    )


@app.get(
    "/api/v1/runs/{run_id}/candles",
    response_model=CandleCollection,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_candles(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
    market: Annotated[MarketDataRepository, Depends(market_repository)],
    from_ts: Annotated[datetime | None, Query(alias="from")] = None,
    to_ts: Annotated[datetime | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 5000,
) -> CandleCollection:
    run = repo.get_run(run_id)
    if run is None:
        not_found(run_id)
    with evidence_repository(repo, run_id) as evidence:
        source_from, source_to = evidence.source_range(run.timeframe)
    requested_start = _utc_datetime(from_ts) or source_from
    requested_end = _utc_datetime(to_ts) or source_to
    if requested_start >= requested_end:
        raise ApiError(
            status_code=400,
            code="invalid_query",
            message="'from' must be earlier than 'to'.",
        )
    explicit_window = from_ts is not None or to_ts is not None
    if explicit_window:
        allowed_start = max(run.period_start, source_from)
        allowed_end = min(run.period_end, source_to)
        start = max(requested_start, allowed_start)
        end = min(requested_end, allowed_end)
        if start >= end:
            raise ApiError(
                status_code=400,
                code="candle_window_outside_run",
                message="The requested candle window does not overlap this run.",
                details={
                    "requested_from": requested_start,
                    "requested_to": requested_end,
                    "allowed_from": allowed_start,
                    "allowed_to": allowed_end,
                },
            )
    else:
        start, end = source_from, source_to
    try:
        collection = market.candles(
            symbol=run.symbol,
            exchange=run.exchange,
            timeframe=run.timeframe,
            data_source=run.data_source,
            from_ts=start,
            to_ts=end,
            limit=limit,
        )
    except ValueError as exc:
        raise ApiError(
            status_code=400,
            code="unsupported_candle_source",
            message=str(exc),
        ) from exc
    return collection.model_copy(
        update={
            "page": collection.page.model_copy(
                update={"window_clamped": (start != requested_start or end != requested_end)}
            )
        }
    )


@app.get(
    "/api/v1/runs/{run_id}/trades",
    response_model=EvidenceCollection[Trade],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_trades(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    exit_reason: str | None = None,
    side: str | None = None,
    liquidated: bool | None = None,
    entry_time_from: datetime | None = None,
    entry_time_to: datetime | None = None,
) -> EvidenceCollection[Trade]:
    with evidence_repository(repo, run_id) as evidence:
        return evidence.trades(
            after_seq=after_seq,
            limit=limit,
            exit_reason=exit_reason,
            side=side,
            liquidated=liquidated,
            entry_time_from=_epoch_ms(entry_time_from),
            entry_time_to=_epoch_ms(entry_time_to),
        )


@app.get(
    "/api/v1/runs/{run_id}/executions",
    response_model=EvidenceCollection[Execution],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_executions(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    trade_id: Annotated[int | None, Query(ge=1)] = None,
) -> EvidenceCollection[Execution]:
    with evidence_repository(repo, run_id) as evidence:
        return evidence.executions(
            after_seq=after_seq,
            limit=limit,
            trade_id=trade_id,
        )


@app.get(
    "/api/v1/runs/{run_id}/funding-settlements",
    response_model=EvidenceCollection[FundingSettlement],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_funding_settlements(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    trade_id: Annotated[int | None, Query(ge=1)] = None,
) -> EvidenceCollection[FundingSettlement]:
    with evidence_repository(repo, run_id) as evidence:
        return evidence.funding_settlements(
            after_seq=after_seq,
            limit=limit,
            trade_id=trade_id,
        )


@app.get(
    "/api/v1/runs/{run_id}/equity",
    response_model=EvidenceCollection[EquityPoint],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_equity(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
) -> EvidenceCollection[EquityPoint]:
    with evidence_repository(repo, run_id) as evidence:
        return evidence.equity(after_seq=after_seq, limit=limit)


@app.get(
    "/api/v1/runs/{run_id}/chart-summaries",
    response_model=EvidenceCollection[ChartSummary],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_chart_summaries(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    series_name: str | None = None,
) -> EvidenceCollection[ChartSummary]:
    with evidence_repository(repo, run_id) as evidence:
        return evidence.chart_summaries(
            after_seq=after_seq,
            limit=limit,
            series_name=series_name,
        )


@app.get(
    "/api/v1/runs/{run_id}/positions",
    response_model=EvidenceCollection[Position],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_positions(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    trade_id: Annotated[int | None, Query(ge=1)] = None,
) -> EvidenceCollection[Position]:
    with evidence_repository(repo, run_id) as evidence:
        return evidence.positions(
            after_seq=after_seq,
            limit=limit,
            trade_id=trade_id,
        )


@app.get(
    "/api/v1/runs/{run_id}/integrity-checks",
    response_model=EvidenceCollection[IntegrityCheck],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_integrity_checks(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
) -> EvidenceCollection[IntegrityCheck]:
    with evidence_repository(repo, run_id) as evidence:
        return evidence.integrity_checks(after_seq=after_seq, limit=limit)


@app.get(
    "/api/v1/runs/{run_id}/outcome-buckets",
    response_model=EvidenceCollection[OutcomeBucket],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_outcome_buckets(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    subject_kind: str | None = None,
    subject_id: Annotated[int | None, Query(ge=1)] = None,
    bucket_name: str | None = None,
) -> EvidenceCollection[OutcomeBucket]:
    with evidence_repository(repo, run_id) as evidence:
        return evidence.outcome_buckets(
            after_seq=after_seq,
            limit=limit,
            subject_kind=subject_kind,
            subject_id=subject_id,
            bucket_name=bucket_name,
        )


@app.get(
    "/api/v1/runs/{run_id}/drawdown-episodes",
    response_model=EvidenceCollection[DrawdownEpisode],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_drawdown_episodes(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    kind: str | None = None,
) -> EvidenceCollection[DrawdownEpisode]:
    with evidence_repository(repo, run_id) as evidence:
        return evidence.drawdown_episodes(
            after_seq=after_seq,
            limit=limit,
            kind=kind,
        )


@app.get(
    "/api/v1/runs/{run_id}/trade-features",
    response_model=EvidenceCollection[TradeFeature],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_trade_features(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    trade_id: Annotated[int | None, Query(ge=1)] = None,
    phase: str | None = None,
) -> EvidenceCollection[TradeFeature]:
    with evidence_repository(repo, run_id) as evidence:
        return evidence.trade_features(
            after_seq=after_seq,
            limit=limit,
            trade_id=trade_id,
            phase=phase,
        )


@app.get(
    "/api/v1/runs/{run_id}/candidate-events",
    response_model=EvidenceCollection[CandidateEvent],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_candidate_events(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    linked_trade_id: Annotated[int | None, Query(ge=1)] = None,
    realized: bool | None = None,
    blocked_by: str | None = None,
) -> EvidenceCollection[CandidateEvent]:
    with evidence_repository(repo, run_id) as evidence:
        return evidence.candidate_events(
            after_seq=after_seq,
            limit=limit,
            linked_trade_id=linked_trade_id,
            realized=realized,
            blocked_by=blocked_by,
        )


@app.get(
    "/api/v1/runs/{run_id}/signals",
    response_model=EvidenceCollection[Signal],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_signals(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    derived_intent: str | None = None,
    derived_side: str | None = None,
    is_warmup: bool | None = None,
    decision_time_from: datetime | None = None,
    decision_time_to: datetime | None = None,
) -> EvidenceCollection[Signal]:
    with evidence_repository(repo, run_id) as evidence:
        return evidence.signals(
            after_seq=after_seq,
            limit=limit,
            derived_intent=derived_intent,
            derived_side=derived_side,
            is_warmup=is_warmup,
            decision_time_from=_epoch_ms(decision_time_from),
            decision_time_to=_epoch_ms(decision_time_to),
        )


@app.get(
    "/api/v1/runs/{run_id}/decisions",
    response_model=EvidenceCollection[Decision],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_decisions(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    action: str | None = None,
    skip_reason: str | None = None,
    signal_id: Annotated[int | None, Query(ge=1)] = None,
    decision_time_from: datetime | None = None,
    decision_time_to: datetime | None = None,
) -> EvidenceCollection[Decision]:
    with evidence_repository(repo, run_id) as evidence:
        return evidence.decisions(
            after_seq=after_seq,
            limit=limit,
            action=action,
            skip_reason=skip_reason,
            signal_id=signal_id,
            decision_time_from=_epoch_ms(decision_time_from),
            decision_time_to=_epoch_ms(decision_time_to),
        )


@app.get(
    "/api/v1/runs/{run_id}/indicator-snapshots",
    response_model=EvidenceCollection[IndicatorSnapshot],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_indicator_snapshots(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    indicator_key: str | None = None,
    is_warmup: bool | None = None,
    feature_time_from: datetime | None = None,
    feature_time_to: datetime | None = None,
) -> EvidenceCollection[IndicatorSnapshot]:
    with evidence_repository(repo, run_id) as evidence:
        return evidence.indicator_snapshots(
            after_seq=after_seq,
            limit=limit,
            indicator_key=indicator_key,
            is_warmup=is_warmup,
            feature_time_from=_epoch_ms(feature_time_from),
            feature_time_to=_epoch_ms(feature_time_to),
        )


@app.get(
    "/api/v1/runs/{run_id}/missed-opportunities",
    response_model=EvidenceCollection[MissedOpportunity],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_missed_opportunities(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    missing_reason: str | None = None,
    time_from: datetime | None = None,
    time_to: datetime | None = None,
) -> EvidenceCollection[MissedOpportunity]:
    with evidence_repository(repo, run_id) as evidence:
        return evidence.missed_opportunities(
            after_seq=after_seq,
            limit=limit,
            missing_reason=missing_reason,
            time_from=_epoch_ms(time_from),
            time_to=_epoch_ms(time_to),
        )


@app.get(
    "/api/v1/runs/{run_id}/conditional-expectancy",
    response_model=EvidenceCollection[ConditionalExpectancy],
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_conditional_expectancy(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    subject_kind: str | None = None,
    is_significant: bool | None = None,
    min_sample_count: Annotated[int | None, Query(ge=1)] = None,
) -> EvidenceCollection[ConditionalExpectancy]:
    with evidence_repository(repo, run_id) as evidence:
        return evidence.conditional_expectancy(
            after_seq=after_seq,
            limit=limit,
            subject_kind=subject_kind,
            is_significant=is_significant,
            min_sample_count=min_sample_count,
        )


@app.get(
    "/api/v1/runs/{run_id}/findings",
    response_model=FindingsCollection,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_findings(
    run_id: str,
    repo: Annotated[CatalogRepository, Depends(repository)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    confidence: str | None = None,
) -> FindingsCollection:
    with evidence_repository(repo, run_id) as evidence:
        return evidence.findings(
            after_seq=after_seq,
            limit=limit,
            confidence=confidence,
        )


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
