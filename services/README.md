# Backtest v2 services

## Bootstrap

Run these commands from the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r services/requirements-dev.txt
```

`requirements-dev.txt` contains editable paths relative to the repository root,
so the pip command must keep the repository root as its working directory.
`backtest-service` pins the compatible `core-lib` release. The pip requirements
file supplies both sibling projects in one resolver transaction, while the uv
source configuration keeps the same sibling package editable. Do not install
`backtest-service` alone from the repository: the requirements file is the
index-confusion guard for local development.

## Quality checks

The following repository-root command is the standard combined pytest invocation.
Both package configurations register the same marker contract, so swapping the two
test-path arguments produces the same result. Integration tests are excluded unless
explicitly selected.

```bash
.venv/bin/pytest services/core-lib/tests services/backtest-service/tests
.venv/bin/ruff check services/core-lib services/backtest-service
.venv/bin/ruff format --check services/core-lib services/backtest-service
(cd services/core-lib && ../../.venv/bin/mypy)
(cd services/backtest-service && ../../.venv/bin/mypy)
```

PostgreSQL integration tests are opt-in and use the repository `.env`. The
default pytest invocation cannot bind the real-data matrix axes because those
checks require the development databases. They set the crypto and signal
sessions to read-only: crypto selects only `ohlcv_futures` and `funding_rates`,
and signal selects only `strategy_registry`. The catalog integration check
writes permanent initialization-test metadata only to
`backtest_db.backtest_run`, `backtest_prereg`, and `backtest_summary`.

```bash
# Short integration tier, excluding long-window real-data cells:
.venv/bin/pytest \
  services/backtest-service/tests/test_integration_postgres_adapters.py \
  -m "integration and not real_data_long"

# Complete matrix, including every real_data_long cell and axis-binding gate:
.venv/bin/pytest \
  services/backtest-service/tests/test_integration_postgres_adapters.py \
  -m integration
```
