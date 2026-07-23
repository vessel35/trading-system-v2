# Backtest v2 services

## Bootstrap

Run these commands from the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install \
  -e './services/core-lib[dev]' \
  -e './services/backtest-service[dev]'
```

`backtest-service` declares `core-lib` as a project dependency, and its uv source
configuration keeps the sibling package editable.

## Quality checks

```bash
.venv/bin/pytest services/core-lib/tests services/backtest-service/tests
.venv/bin/ruff check services/core-lib services/backtest-service
(cd services/core-lib && ../../.venv/bin/mypy)
(cd services/backtest-service && ../../.venv/bin/mypy)
```

PostgreSQL integration tests are opt-in and use the repository `.env`. They set
each session to read-only; the crypto test selects only `ohlcv_futures` and
`funding_rates`, and the signal test selects only `strategy_registry`.

```bash
.venv/bin/pytest \
  services/backtest-service/tests/test_integration_postgres_adapters.py \
  -m integration
```
