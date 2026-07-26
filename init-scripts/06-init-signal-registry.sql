\set ON_ERROR_STOP on

\connect signal_db

\ir signal-service/20260724/01-redefine-strategy-registry.sql
\ir signal-service/20260724/02-register-vessel-reference.sql
\ir signal-service/20260726/01-create-trading-signals.sql
