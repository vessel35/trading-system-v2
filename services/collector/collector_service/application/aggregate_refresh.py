"""Operator-triggered maintenance for bounded continuous-aggregate ranges."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from collector_service.domain.aggregates import AGGREGATE_VIEWS
from collector_service.domain.ports import AggregateRefreshRepository

from .backfill import _validated_range

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AggregateRefreshResult:
    """Summary of one bounded aggregate refresh."""

    view_count: int


class AggregateRefresh:
    """Refresh allowlisted TimescaleDB continuous aggregates."""

    def __init__(self, repository: AggregateRefreshRepository) -> None:
        self._repository = repository

    async def run(
        self,
        *,
        start: datetime,
        end: datetime,
        timeframes: Sequence[str] | None = None,
    ) -> AggregateRefreshResult:
        """Refresh selected views over the normalized half-open UTC range."""

        start, end = _validated_range(start, end)
        selected_timeframes = self._selected_timeframes(timeframes)

        for timeframe in selected_timeframes:
            view_name = AGGREGATE_VIEWS[timeframe]
            await asyncio.to_thread(
                self._repository.refresh_range,
                view_name,
                start,
                end,
            )
            logger.info(
                "aggregate_refresh_view_completed view=%s start=%s end=%s",
                view_name,
                start.isoformat(),
                end.isoformat(),
                extra={
                    "event": "aggregate_refresh_view_completed",
                    "service": "collector",
                    "view": view_name,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                },
            )

        logger.info(
            "aggregate_refresh_completed start=%s end=%s views=%d",
            start.isoformat(),
            end.isoformat(),
            len(selected_timeframes),
            extra={
                "event": "aggregate_refresh_completed",
                "service": "collector",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "count": len(selected_timeframes),
            },
        )
        return AggregateRefreshResult(view_count=len(selected_timeframes))

    @staticmethod
    def _selected_timeframes(timeframes: Sequence[str] | None) -> tuple[str, ...]:
        if timeframes is None:
            return tuple(AGGREGATE_VIEWS)
        invalid = sorted(set(timeframes) - AGGREGATE_VIEWS.keys())
        if invalid:
            raise ValueError(f"unsupported aggregate timeframes: {', '.join(invalid)}")
        if not timeframes:
            raise ValueError("at least one aggregate timeframe is required")
        return tuple(dict.fromkeys(timeframes))
