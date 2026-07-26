# signal-service

`signal-service` is the paper/live driver sibling of `backtest-service`. It
accepts already-opened connections, reads confirmed 1m candles from
`crypto_data`, resamples only complete buckets, then polls with a cursor-bounded
incremental query. Missing candles are never filled; every detected gap is
returned in `SignalCycleResult.gaps` and logged. The service resolves an Adaptee
through the read-only `signal_db.strategy_registry` and runs the same shared
call path:

```text
finalized Candle
  -> core_lib IndicatorRegistry incremental state
  -> core_lib AdapterManager-created Adaptee.analyze(...)
  -> core_lib TradingSignal
  -> signal_db.trading_signals
```

The sink commits every insert (including an idempotent duplicate outcome) and
rolls back on failure. Its idempotency identity includes the core-resolved
strategy parameters and exchange, so distinct deployments cannot silently
discard each other's signals.

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
