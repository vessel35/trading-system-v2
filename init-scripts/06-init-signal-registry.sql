\set ON_ERROR_STOP on

\connect signal_db

\ir signal-service/20260724/01-redefine-strategy-registry.sql
\ir signal-service/20260724/02-register-vessel-reference.sql
\ir signal-service/20260726/01-create-trading-signals.sql
\ir signal-service/20260810/01-create-money-management-registry.sql
\ir signal-service/20260923/01-register-supertrend-ema200-flip.sql
\ir signal-service/20260923/02-register-macd-ema200-zero-line.sql
\ir signal-service/20260923/03-register-bollinger-rsi-reversion.sql
\ir signal-service/20260923/04-register-signal-exit-atr.sql
