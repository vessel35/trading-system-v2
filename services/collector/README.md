# Binance futures source collector

This service reads one active Binance futures symbol from `config_db.symbols`, polls
`ccxt.binanceusdm.fetch_ohlcv(..., "1m", limit=3)` on minute boundaries plus two seconds,
drops the final in-progress candle, and upserts only confirmed 1m candles into
`ohlcv_futures`.

Two bounded one-shot modes use the same adapters:

- `backfill` pages Binance USD-M 1m OHLCV with `since` and `limit=1000`, excludes any
  still-open candle, and batch-upserts the half-open range into `ohlcv_futures`.
- `funding-backfill` pages CCXT funding history and upserts observed
  `funding_rate`/`mark_price` rows into `funding_rates`. It parses the raw exchange decimal
  strings and does not interpolate missing settlements or apply application rounding.

All price, quantity, and funding values cross the CCXT boundary through
`Decimal(str(value))` and remain `Decimal` through persistence. The service has no spot,
indicator-generation, higher-timeframe refresh, signal, or wallet path.

## Modes

`collect` remains the default:

```bash
../../.venv/bin/python main.py
../../.venv/bin/python main.py collect
```

Bounded modes require timezone-aware ISO-8601 values. Start is inclusive and end is
exclusive. `--symbol` is an optional selector; when omitted the service still requires
exactly one active Binance symbol from `config_db.symbols`.

```bash
../../.venv/bin/python main.py backfill \
  --symbol ETH/USDT:USDT \
  --start 2025-01-01T00:00:00Z \
  --end 2025-02-01T00:00:00Z

../../.venv/bin/python main.py funding-backfill \
  --symbol ETH/USDT:USDT \
  --start 2025-01-01T00:00:00Z \
  --end 2025-02-01T00:00:00Z
```

## Safety

Do not start the service during tests. Unit tests inject a fake CCXT client and never make
network calls. The opt-in integration test accepts only `COLLECTOR_TEST_DATABASE_URL`,
requires a local host and a database name ending in `_test`, creates a random disposable
schema, and drops that schema afterward; it never accesses live `ohlcv_futures` or
`funding_rates` tables.

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
