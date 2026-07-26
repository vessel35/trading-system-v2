# signal-service

`signal-service` is the paper/live driver sibling of `backtest-service`. It
accepts already-opened connections, reads confirmed 1m candles from
`crypto_data`, resamples only complete buckets, resolves an Adaptee through the
read-only `signal_db.strategy_registry`, and runs the same shared call path:

```text
finalized Candle
  -> core_lib IndicatorRegistry incremental state
  -> core_lib AdapterManager-created Adaptee.analyze(...)
  -> core_lib TradingSignal
  -> signal_db.trading_signals
```

The package intentionally has no executable CLI and does not load `.env`.
Opening production connections, streaming/recovery, and running the service are
deployment work outside this slice. `SignalQueue` is only the future
wallet-service boundary; there is no queue transport, exchange client, order
submission, or `wallet_db` adapter here.

## Local verification

From this directory, with the repository development environment installed:

```bash
../../.venv/bin/pytest
../../.venv/bin/ruff check .
../../.venv/bin/ruff format --check .
../../.venv/bin/mypy
```

Default tests use in-memory feeds and DB-API test doubles only. The optional
PostgreSQL test requires a separately created disposable database whose name
ends in `_test`; it never reads repository environment files.
