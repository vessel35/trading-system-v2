"""FastAPI application for the P0 research catalog."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Annotated, Any, NoReturn

import psycopg
from core_lib import __version__ as core_lib_version
from fastapi import Depends, FastAPI, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from web_api import __version__ as web_api_version
from web_api.database import (
    CatalogConfigurationError,
    CatalogConnection,
    CryptoConnection,
    catalog_connection,
    crypto_connection,
)
from web_api.evidence import (
    EvidenceRepository,
    EvidenceUnavailableError,
    open_evidence,
)
from web_api.models import (
    CandidateEvent,
    CandleCollection,
    ChartSummary,
    ConditionalExpectancy,
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
    MissedOpportunity,
    OutcomeBucket,
    Position,
    PreregistrationResponse,
    RunComparisonResponse,
    RunHeader,
    RunListResponse,
    RunSummaryResponse,
    Signal,
    Trade,
    TradeFeature,
)
from web_api.repository import CatalogRepository, MarketDataRepository, RunListQuery


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
        "Read-only backend-for-frontend. Stored catalog summaries and immutable "
        "Evidence are returned without metric or decision recomputation."
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
    if from_ts is None or to_ts is None:
        with evidence_repository(repo, run_id) as evidence:
            default_from, default_to = evidence.source_range(run.timeframe)
    else:
        default_from, default_to = run.period_start, run.period_end
    start = _utc_datetime(from_ts) or default_from
    end = _utc_datetime(to_ts) or default_to
    if start >= end:
        raise ApiError(
            status_code=400,
            code="invalid_query",
            message="'from' must be earlier than 'to'.",
        )
    try:
        return market.candles(
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
