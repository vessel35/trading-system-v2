"""Unit contracts for read-only market-data inventory queries."""

from datetime import UTC, datetime
from typing import cast

from web_api.database import CryptoConnection
from web_api.repository import MarketDataRepository


class FakeCursor:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[dict[str, object]]:
        return self._rows


class FakeConnection:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows
        self.queries: list[tuple[str, object | None]] = []

    def execute(self, query: str, params: object | None = None) -> FakeCursor:
        self.queries.append((query, params))
        return FakeCursor(self._rows)


def test_inventory_groups_all_1m_symbols_and_calculates_coverage_ratio() -> None:
    connection = FakeConnection(
        [
            {
                "symbol": "BTC/USDT:USDT",
                "exchange": "binance",
                "available_from": datetime(2025, 1, 1, tzinfo=UTC),
                "available_to": datetime(2025, 1, 1, 0, 3, tzinfo=UTC),
                "row_count": 3,
            },
            {
                "symbol": "ETH/USDT:USDT",
                "exchange": "binance",
                "available_from": None,
                "available_to": None,
                "row_count": 0,
            },
            {
                "symbol": "SOL/USDT:USDT",
                "exchange": "binance",
                "available_from": datetime(2025, 1, 1, tzinfo=UTC),
                "available_to": datetime(2025, 1, 1, tzinfo=UTC),
                "row_count": 2,
            },
        ]
    )

    result = MarketDataRepository(cast(CryptoConnection, connection)).inventory(
        data_source="crypto_data.ohlcv_futures"
    )

    assert result.data_source == "crypto_data.ohlcv_futures"
    assert [item.symbol for item in result.items] == [
        "BTC/USDT:USDT",
        "ETH/USDT:USDT",
        "SOL/USDT:USDT",
    ]
    assert result.items[0].timeframe == "1m"
    assert result.items[0].row_count == 3
    assert result.items[0].expected_1m_rows == 4
    assert result.items[0].missing_1m_rows == 1
    assert result.items[0].coverage_ratio == 0.75
    assert result.items[1].coverage_ratio == 0
    assert result.items[2].missing_1m_rows == 0
    assert result.items[2].coverage_ratio == 1

    query, params = connection.queries[0]
    normalized_query = " ".join(query.split())
    # Holdings come from the maintained summary, so the reader must not aggregate the
    # base table: that cost grew with retained history rather than with what is shown.
    assert "FROM public.ohlcv_futures_inventory" in normalized_query
    assert "WHERE timeframe = '1m'" in normalized_query
    assert "GROUP BY" not in normalized_query
    assert "ORDER BY symbol, exchange" in normalized_query
    assert params is None
