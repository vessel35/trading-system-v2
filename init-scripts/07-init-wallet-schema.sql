\set ON_ERROR_STOP on

GRANT data_reader, signal_reader TO wallet_writer;

\connect wallet_db

\ir wallet-service/20260726/01-create-paper-wallet-ledger.sql
\ir wallet-service/20260726/02-create-wallet-signal-consumption.sql
