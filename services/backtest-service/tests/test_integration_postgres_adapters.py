"""Read-only integration checks against the local development PostgreSQL."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

import psycopg
import pytest
from backtest_service.adapters.data_feed import BacktestDataFeed, ReadConnection
from backtest_service.adapters.strategy_registry import BacktestStrategyRegistry

pytestmark = pytest.mark.integration


def _env() -> dict[str, str]:
    path = Path(__file__).parents[3] / ".env"
    if not path.exists():
        pytest.skip("repository .env is unavailable")
    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    required = {"PGHOST", "PGPORT", "PGUSER", "PGPASSWORD"}
    if not required <= values.keys():
        pytest.skip("repository .env lacks PostgreSQL connection keys")
    return values


def _connect(database: str) -> psycopg.Connection[tuple[object, ...]]:
    values = _env()
    return psycopg.connect(
        host=values["PGHOST"],
        port=int(values["PGPORT"]),
        user=values["PGUSER"],
        password=values["PGPASSWORD"],
        dbname=database,
        options="-c default_transaction_read_only=on",
    )


def test_crypto_data_adapter_reads_only_contract_tables() -> None:
    with _connect("crypto_data") as connection:
        sample = connection.execute(
            """
            SELECT symbol, exchange, time
            FROM public.ohlcv_futures
            WHERE volume IS NOT NULL
            ORDER BY time
            LIMIT 1
            """
        ).fetchone()
        if sample is None:
            pytest.skip("crypto_data.ohlcv_futures is empty")
        symbol, exchange, open_time = sample
        assert isinstance(symbol, str)
        assert isinstance(exchange, str)
        assert isinstance(open_time, datetime)
        up_to = open_time + timedelta(minutes=1)
        feed = BacktestDataFeed(
            cast(ReadConnection, connection),
            exchange=exchange,
        )
        candles = feed.candles(symbol, "1m", up_to)
        assert candles
        assert all(candle.close_time <= up_to for candle in candles)

        funding_sample = connection.execute(
            """
            SELECT symbol, exchange, time
            FROM public.funding_rates
            WHERE mark_price IS NOT NULL
            ORDER BY time
            LIMIT 1
            """
        ).fetchone()
        if funding_sample is not None:
            funding_symbol, funding_exchange, at = funding_sample
            assert isinstance(funding_symbol, str)
            assert isinstance(funding_exchange, str)
            assert isinstance(at, datetime)
            funding_feed = BacktestDataFeed(
                cast(ReadConnection, connection),
                exchange=funding_exchange,
            )
            assert funding_feed.funding(funding_symbol, at).is_finite()
            assert funding_feed.mark_price(funding_symbol, at).is_finite()


def test_signal_registry_adapter_reads_only_registry_table() -> None:
    with _connect("signal_db") as connection:
        registry = BacktestStrategyRegistry(cast(ReadConnection, connection))
        entries = registry.list()
        assert all("strategy_id" in entry for entry in entries)
        if entries:
            strategy_id = entries[0]["strategy_id"]
            assert isinstance(strategy_id, str)
            assert registry.get(strategy_id)["strategy_id"] == strategy_id
