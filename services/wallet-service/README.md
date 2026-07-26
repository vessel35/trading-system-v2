# wallet-service

`wallet-service` is the v2 paper-execution driver. It consumes an injected
queue, calls `core_lib` for risk-money sizing, exposure
limits, deterministic matching, costs, position-book updates, and accounting,
then commits fills, the current position, and an accounting snapshot to its
own `wallet_db`.

`PaperSignal` is the wallet-side queue delivery envelope. A process-local queue
adapter remains available for unit assembly. `PostgresSignalQueue` reads
paper-only decisions from `signal_db`, anti-joins their IDs against the
wallet-owned consumption receipts, and reads only finalized 1m rows from
`crypto_data`. Both decision and next execution candles use the shared
`core_lib.candles` resampler; an incomplete next candle yields no work until a
later poll and creates no receipt. Terminal risk rejections and non-persisted
executions are receipted as `rejected` and `skipped`, while atomic paper ledger
commits use `filled`; all three statuses advance the anti-join without turning
a rejection into a fill.

## Safety boundary

This package has one execution adapter: `PaperBroker`. It simulates a
next-candle fill from supplied candle data and has no exchange client, remote
order API, credential model, withdrawal path, or live runner. The only
float-to-`Decimal` transition is inside `PaperBroker.submit()` through
`core_lib.execution.normalizer`.

The application constructor accepts already-created read connections,
connection/repository, and queue. It never reads `.env`, discovers a database,
or starts a process by itself. Signal and candle connections issue SELECT only;
the atomic ledger transaction writes only `wallet_db`, including
`wallet_signal_consumption`. PostgreSQL integration tests are opt-in and reject
any DSN that is not local and whose database name does not end in `_test`.
Use the assembled `WalletService` as a context manager (or call `close()`) so
queue-owned `signal_db` and `crypto_data` read sessions cannot remain idle in a
transaction; the wallet connection remains repository-owned.

## Checks

```bash
cd services/wallet-service
../../.venv/bin/pytest -q
../../.venv/bin/ruff check .
../../.venv/bin/ruff format --check .
../../.venv/bin/mypy .
```

The opt-in repository integration test uses only a disposable local database:

```bash
WALLET_SERVICE_DISPOSABLE_TEST=1 \
WALLET_SERVICE_TEST_DSN='postgresql://.../wallet_db_test' \
../../.venv/bin/pytest -q -m integration
```
