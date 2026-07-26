# OHLCV collector

This service reads one active Binance futures symbol from `config_db.symbols`, polls
`ccxt.binanceusdm.fetch_ohlcv(..., "1m", limit=3)` on minute boundaries plus two seconds,
drops the final in-progress candle, and upserts only confirmed 1m candles into
`ohlcv_futures`.

It deliberately contains no indicator, spot, backfill, macro, funding, higher-timeframe,
or Docker path. Monetary and quantity values cross the CCXT boundary through
`Decimal(str(value))` and remain `Decimal` through persistence.

## Safety

Do not start the service during tests. Unit tests inject a fake CCXT client and never make
network calls. The opt-in integration test accepts only `COLLECTOR_TEST_DATABASE_URL`,
requires a local host and a non-production database name, creates a random disposable
schema, and drops that schema afterward; it never accesses the live `ohlcv_futures` table.

## Checks

Install and check from this directory:

```bash
../../.venv/bin/python -m pip install -e '.[dev]'
../../.venv/bin/pytest
../../.venv/bin/ruff check .
../../.venv/bin/ruff format --check .
../../.venv/bin/mypy
```

To opt into the disposable PostgreSQL check:

```bash
COLLECTOR_TEST_DATABASE_URL=postgresql://... ../../.venv/bin/pytest -m integration
```
