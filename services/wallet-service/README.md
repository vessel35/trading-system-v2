# wallet-service

`wallet-service` is the v2 paper-execution driver. It consumes an injected
in-process signal queue, calls `core_lib` for risk-money sizing, exposure
limits, deterministic matching, costs, position-book updates, and accounting,
then commits fills, the current position, and an accounting snapshot to its
own `wallet_db`.

`PaperSignal` is the wallet-side queue delivery envelope. A process-local queue
adapter carries the signal-service decision plus routing identity and the next
finalized paper candle; the services remain sibling packages and do not import
one another.

## Safety boundary

This package has one execution adapter: `PaperBroker`. It simulates a
next-candle fill from supplied candle data and has no exchange client, remote
order API, credential model, withdrawal path, or live runner. The only
float-to-`Decimal` transition is inside `PaperBroker.submit()` through
`core_lib.execution.normalizer`.

The application constructor accepts an already-created connection/repository
and queue. It never reads `.env`, discovers a database, or starts a process by
itself. PostgreSQL integration tests are opt-in and reject any DSN that is not
local and whose database name does not end in `_test`.

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
