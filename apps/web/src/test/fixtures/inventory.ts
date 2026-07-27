import { http, HttpResponse } from "msw";

export const inventoryFixture = {
  data_source: "crypto_data.ohlcv_futures",
  items: [
    {
      symbol: "BTC/USDT:USDT",
      exchange: "binance",
      timeframe: "1m",
      available_from: "2025-06-21T00:00:00Z",
      available_to: "2026-06-02T00:00:00Z",
      row_count: 470_000,
      expected_1m_rows: 498_241,
      missing_1m_rows: 28_241,
      coverage_ratio: 0.943319,
    },
    {
      symbol: "ETH/USDT:USDT",
      exchange: "binance",
      timeframe: "1m",
      available_from: "2025-06-21T00:00:00Z",
      available_to: "2026-06-02T00:00:00Z",
      row_count: 498_241,
      expected_1m_rows: 498_241,
      missing_1m_rows: 0,
      coverage_ratio: 1,
    },
  ],
};

export const inventoryHandlers = [
  http.get("http://localhost/api/v1/data-sources/:dataSource/inventory", () =>
    HttpResponse.json(inventoryFixture),
  ),
];
