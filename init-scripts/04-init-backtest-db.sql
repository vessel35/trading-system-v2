\set ON_ERROR_STOP on

-- This deployment-root script intentionally contains no passwords.
-- Set role passwords from an untracked environment file after initialization.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'backtest_writer') THEN
        CREATE ROLE backtest_writer
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOREPLICATION;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'backtest_reader') THEN
        CREATE ROLE backtest_reader
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOREPLICATION;
    END IF;
END
$$;

SELECT 'CREATE DATABASE backtest_db OWNER backtest_writer'
WHERE NOT EXISTS (
    SELECT 1
    FROM pg_database
    WHERE datname = 'backtest_db'
)
\gexec

GRANT ALL PRIVILEGES ON DATABASE backtest_db TO backtest_writer;
GRANT CONNECT ON DATABASE backtest_db TO backtest_reader;

\connect backtest_db

GRANT USAGE, CREATE ON SCHEMA public TO backtest_writer;
GRANT USAGE ON SCHEMA public TO backtest_reader;

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM backtest_reader;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM backtest_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO backtest_reader;

ALTER DEFAULT PRIVILEGES FOR ROLE backtest_writer IN SCHEMA public
    GRANT SELECT ON TABLES TO backtest_reader;
