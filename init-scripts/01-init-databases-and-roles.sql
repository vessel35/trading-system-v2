\set ON_ERROR_STOP on

-- v2 owns these databases. This bootstrap creates no application data and
-- intentionally assigns no role passwords; set them from an untracked secret
-- source after initialization.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'data_writer') THEN
        CREATE ROLE data_writer
            LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'data_reader') THEN
        CREATE ROLE data_reader
            LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'config_reader') THEN
        CREATE ROLE config_reader
            LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'signal_writer') THEN
        CREATE ROLE signal_writer
            LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wallet_writer') THEN
        CREATE ROLE wallet_writer
            LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
END
$$;

SELECT 'CREATE DATABASE crypto_data'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'crypto_data')
\gexec
SELECT 'CREATE DATABASE config_db'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'config_db')
\gexec
SELECT 'CREATE DATABASE signal_db'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'signal_db')
\gexec
SELECT 'CREATE DATABASE wallet_db'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'wallet_db')
\gexec

REVOKE CONNECT ON DATABASE crypto_data FROM PUBLIC;
REVOKE CONNECT ON DATABASE config_db FROM PUBLIC;
REVOKE CONNECT ON DATABASE signal_db FROM PUBLIC;
REVOKE CONNECT ON DATABASE wallet_db FROM PUBLIC;

GRANT CONNECT ON DATABASE crypto_data TO data_writer, data_reader;
GRANT CONNECT ON DATABASE config_db TO config_reader;
GRANT CONNECT ON DATABASE signal_db TO signal_writer;
GRANT CONNECT ON DATABASE wallet_db TO wallet_writer;

-- The future signal service may read configuration and market data through
-- the same least-privilege roles; no operational signal schema is created here.
GRANT config_reader, data_reader TO signal_writer;
