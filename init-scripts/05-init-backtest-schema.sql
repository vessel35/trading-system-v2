\set ON_ERROR_STOP on

\connect backtest_db

\ir backtest-service/20260724/01-create-backtest-catalog.sql
\ir backtest-service/20260724/02-add-resolved-indicators.sql
\ir backtest-service/20260724/03-add-gap-coverage-summary.sql
\ir backtest-service/20260724/04-add-source-data-hash.sql
\ir backtest-service/20260731/01-add-run-soft-delete.sql
\ir backtest-service/20260805/01-add-evidence-schema-version.sql
