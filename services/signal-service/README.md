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

The package intentionally has no environment-driven executable CLI and does not
load `.env`. Operators inject the configuration and already-opened connections,
then may call `run_signal_generator()` to warm once and poll each wall-clock
minute boundary plus the close buffer. The runner accepts an injected clock,
sleep function, and stop event; its default wait is interruptible and the main
wiring translates SIGINT/SIGTERM into a cooperative stop. `SignalQueue` remains
an injected wallet-service boundary; there is no exchange client, order
submission, or `wallet_db` adapter here.

If polling observes multiple unprocessed candles or a finalized-series gap, the
runner performs a full warm-up from the latest available history before
continuing. Other feed or strategy failures remain ordinary poll errors and do
not reset indicator state.

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
