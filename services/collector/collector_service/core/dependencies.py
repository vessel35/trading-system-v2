"""Assemble the production adapters without starting live collection."""

from __future__ import annotations

from dataclasses import dataclass

from collector_service.application import (
    AggregateRefresh,
    FundingBackfill,
    HistoricalBackfill,
    LiveCollector,
)
from collector_service.infrastructure import (
    BinanceUsdMClient,
    ConfigSymbolRepository,
    PostgresAggregateRefresher,
    PostgresFundingRepository,
    PostgresOhlcvRepository,
    connection_provider,
)

from .config import Settings


@dataclass(frozen=True, slots=True)
class Runtime:
    """Resources owned by one collector process."""

    collector: LiveCollector
    backfill: HistoricalBackfill
    funding_backfill: FundingBackfill
    aggregate_refresh: AggregateRefresh
    exchange: BinanceUsdMClient

    async def close(self) -> None:
        """Release the exchange resource."""

        await self.exchange.close()


def build_runtime(settings: Settings) -> Runtime:
    """Wire config_db read-only and data_db write adapters."""

    exchange = BinanceUsdMClient.create(
        api_key=settings.binance_api_key.get_secret_value(),
        api_secret=settings.binance_api_secret.get_secret_value(),
    )
    symbols = ConfigSymbolRepository(
        connection_provider(
            settings.config_db_url.get_secret_value(),
            read_only=True,
            application_name="collector-config-reader",
        )
    )
    candles = PostgresOhlcvRepository(
        connection_provider(
            settings.data_db_url.get_secret_value(),
            read_only=False,
            application_name="collector-ohlcv-writer",
        )
    )
    funding = PostgresFundingRepository(
        connection_provider(
            settings.data_db_url.get_secret_value(),
            read_only=False,
            application_name="collector-funding-writer",
        )
    )
    aggregate_refresher = PostgresAggregateRefresher(
        connection_provider(
            settings.data_db_url.get_secret_value(),
            read_only=False,
            application_name="collector-aggregate-refresher",
            autocommit=True,
        )
    )
    collector = LiveCollector(
        symbols=symbols,
        exchange=exchange,
        candles=candles,
        exchange_name=settings.exchange,
        symbol_selector=settings.symbol,
        timeframe=settings.timeframe,
        fetch_limit=settings.fetch_limit,
        poll_interval_seconds=settings.poll_interval_seconds,
        poll_buffer_seconds=settings.poll_buffer_seconds,
    )
    backfill = HistoricalBackfill(
        symbols=symbols,
        exchange=exchange,
        candles=candles,
        exchange_name=settings.exchange,
        symbol_selector=settings.symbol,
        timeframe=settings.timeframe,
    )
    funding_backfill = FundingBackfill(
        symbols=symbols,
        exchange=exchange,
        funding=funding,
        exchange_name=settings.exchange,
        symbol_selector=settings.symbol,
    )
    aggregate_refresh = AggregateRefresh(aggregate_refresher)
    return Runtime(
        collector=collector,
        backfill=backfill,
        funding_backfill=funding_backfill,
        aggregate_refresh=aggregate_refresh,
        exchange=exchange,
    )
