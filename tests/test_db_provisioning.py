"""Opt-in assertions for the disposable v2 docker-compose database."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DATABASES = {
    "backtest_db",
    "config_db",
    "crypto_data",
    "signal_db",
    "wallet_db",
}
EXPECTED_ROLES = {
    "backtest_reader",
    "backtest_writer",
    "config_reader",
    "data_reader",
    "data_writer",
    "signal_reader",
    "signal_writer",
    "wallet_writer",
}
EXPECTED_AGGREGATES = {
    "ohlcv_futures_5m",
    "ohlcv_futures_15m",
    "ohlcv_futures_1h",
    "ohlcv_futures_4h",
    "ohlcv_futures_1d",
}
EXPECTED_BACKTEST_TABLES = {
    "backtest_prereg",
    "backtest_run",
    "backtest_summary",
    "backtest_tag",
}
EXPECTED_WALLET_TABLES = {
    "accounting_snapshots",
    "fills",
    "positions",
    "wallet_accounts",
    "wallet_signal_consumption",
}
EXPECTED_SIGNAL_REGISTRY_COLUMNS = {
    "strategy_id",
    "class_name",
    "module_path",
    "display_name",
    "description",
    "strategy_version",
    "supported_timeframes",
    "required_indicators_json",
    "min_history",
    "default_params_json",
    "is_active",
    "is_deprecated",
    "registered_at",
    "updated_at",
}
EXPECTED_TRADING_SIGNAL_COLUMNS = {
    "signal_id",
    "strategy_id",
    "params_json",
    "source_mode",
    "symbol",
    "exchange",
    "timeframe",
    "candle_open_time",
    "candle_close_time",
    "signal_time",
    "signal_type",
    "derived_intent",
    "derived_side",
    "price",
    "confidence",
    "stop_loss",
    "take_profit",
    "market_type",
    "leverage",
    "reason",
    "metadata_json",
    "created_at",
}
EXPECTED_CRYPTO_COLUMNS = {
    "ohlcv_futures": {
        "time": ("timestamp with time zone", None, None, None, "NO"),
        "symbol": ("character varying", 30, None, None, "NO"),
        "exchange": ("character varying", 20, None, None, "NO"),
        "timeframe": ("character varying", 10, None, None, "NO"),
        "open": ("numeric", None, 20, 8, "NO"),
        "high": ("numeric", None, 20, 8, "NO"),
        "low": ("numeric", None, 20, 8, "NO"),
        "close": ("numeric", None, 20, 8, "NO"),
        "volume": ("numeric", None, 30, 8, "YES"),
        "quote_volume": ("numeric", None, 30, 8, "YES"),
        "trade_count": ("integer", None, 32, 0, "YES"),
        "ingest_time": ("timestamp with time zone", None, None, None, "YES"),
    },
    "funding_rates": {
        "time": ("timestamp with time zone", None, None, None, "NO"),
        "symbol": ("character varying", 30, None, None, "NO"),
        "exchange": ("character varying", 20, None, None, "NO"),
        "funding_rate": ("numeric", None, 20, 10, "NO"),
        "mark_price": ("numeric", None, 20, 8, "YES"),
        "created_at": ("timestamp with time zone", None, None, None, "YES"),
    },
}


if os.environ.get("V2_DB_PROVISIONING_TEST") != "1":
    pytest.skip(
        "set V2_DB_PROVISIONING_TEST=1 after starting the disposable v2 compose stack",
        allow_module_level=True,
    )


def _compose_command() -> list[str]:
    command = shlex.split(os.environ.get("V2_COMPOSE_COMMAND", "docker-compose"))
    if not command:
        raise RuntimeError("V2_COMPOSE_COMMAND must not be empty")
    project = os.environ.get("V2_COMPOSE_PROJECT_NAME", "trading-system-v2-db")
    environment_file = os.environ.get("V2_COMPOSE_ENV_FILE", os.devnull)
    return [
        *command,
        "--env-file",
        environment_file,
        "--project-name",
        project,
    ]


def _container_id() -> str:
    result = subprocess.run(
        [*_compose_command(), "ps", "--quiet", "timescaledb"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    container_id = result.stdout.strip()
    if not container_id:
        raise RuntimeError("the disposable v2 timescaledb service is not running")
    return container_id


def _assert_disposable_compose_target() -> None:
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            (
                '{{ index .Config.Labels "com.docker.compose.service" }}|'
                '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}'
            ),
            _container_id(),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    service, working_directory = result.stdout.strip().split("|", maxsplit=1)
    assert service == "timescaledb"
    assert Path(working_directory).resolve() == REPOSITORY_ROOT


def _query(database: str, sql: str) -> list[str]:
    _assert_disposable_compose_target()
    result = subprocess.run(
        [
            *_compose_command(),
            "exec",
            "--no-TTY",
            "timescaledb",
            "sh",
            "-ceu",
            (
                'exec psql --username "$POSTGRES_USER" --dbname "$1" '
                "--no-align --tuples-only --set ON_ERROR_STOP=on"
            ),
            "sh",
            database,
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        input=sql,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _crypto_column_contract(
    table: str,
) -> dict[str, tuple[str, int | None, int | None, int | None, str]]:
    rows = _query(
        "crypto_data",
        f"""
        SELECT concat_ws(
            '|',
            column_name,
            data_type,
            coalesce(character_maximum_length::text, ''),
            coalesce(numeric_precision::text, ''),
            coalesce(numeric_scale::text, ''),
            is_nullable
        )
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = '{table}'
        ORDER BY ordinal_position;
        """,
    )
    contract: dict[str, tuple[str, int | None, int | None, int | None, str]] = {}
    for row in rows:
        name, data_type, length, precision, scale, nullable = row.split("|")
        contract[name] = (
            data_type,
            int(length) if length else None,
            int(precision) if precision else None,
            int(scale) if scale else None,
            nullable,
        )
    return contract


def test_expected_databases_and_passwordless_application_roles_exist() -> None:
    databases = set(
        _query(
            "postgres",
            """
            SELECT datname
            FROM pg_database
            WHERE datname = ANY (
                ARRAY[
                    'backtest_db',
                    'config_db',
                    'crypto_data',
                    'signal_db',
                    'wallet_db'
                ]
            )
            ORDER BY datname;
            """,
        )
    )
    roles = set(
        _query(
            "postgres",
            """
            SELECT rolname
            FROM pg_authid
            WHERE rolname = ANY (
                ARRAY[
                    'backtest_reader',
                    'backtest_writer',
                    'config_reader',
                    'data_reader',
                    'data_writer',
                    'signal_reader',
                    'signal_writer',
                    'wallet_writer'
                ]
            )
              AND rolpassword IS NULL
            ORDER BY rolname;
            """,
        )
    )
    assert databases == EXPECTED_DATABASES
    assert roles == EXPECTED_ROLES


def test_application_roles_have_expected_least_privilege_access() -> None:
    memberships = _query(
        "postgres",
        """
        SELECT
            pg_has_role('backtest_writer', 'data_reader', 'member'),
            pg_has_role('backtest_writer', 'signal_reader', 'member'),
            pg_has_role('signal_writer', 'config_reader', 'member'),
            pg_has_role('wallet_writer', 'data_reader', 'member'),
            pg_has_role('wallet_writer', 'signal_reader', 'member');
        """,
    )
    crypto_access = _query(
        "crypto_data",
        """
        SELECT
            has_table_privilege(
                'data_writer',
                'public.ohlcv_futures',
                'INSERT,UPDATE'
            ),
            has_table_privilege(
                'data_reader',
                'public.ohlcv_futures',
                'SELECT'
            ),
            NOT has_table_privilege(
                'data_reader',
                'public.ohlcv_futures',
                'INSERT'
            );
        """,
    )
    config_access = _query(
        "config_db",
        """
        SELECT
            has_table_privilege('config_reader', 'public.symbols', 'SELECT'),
            NOT has_table_privilege('config_reader', 'public.symbols', 'INSERT');
        """,
    )
    signal_access = _query(
        "signal_db",
        """
        SELECT
            has_table_privilege(
                'signal_reader',
                'public.strategy_registry',
                'SELECT'
            ),
            NOT has_table_privilege(
                'signal_reader',
                'public.strategy_registry',
                'INSERT'
            ),
            has_table_privilege(
                'signal_writer',
                'public.trading_signals',
                'SELECT,INSERT'
            ),
            NOT has_table_privilege(
                'signal_writer',
                'public.trading_signals',
                'UPDATE,DELETE'
            ),
            has_table_privilege(
                'signal_reader',
                'public.trading_signals',
                'SELECT'
            ),
            NOT has_table_privilege(
                'signal_reader',
                'public.trading_signals',
                'SELECT,INSERT'
            );
        """,
    )
    wallet_access = _query(
        "wallet_db",
        """
        SELECT
            has_table_privilege(
                'wallet_writer',
                'public.wallet_accounts',
                'SELECT,INSERT,UPDATE'
            ),
            has_table_privilege(
                'wallet_writer',
                'public.fills',
                'SELECT,INSERT'
            ),
            NOT has_table_privilege(
                'wallet_writer',
                'public.fills',
                'UPDATE,DELETE'
            ),
            has_table_privilege(
                'wallet_writer',
                'public.positions',
                'SELECT,INSERT,UPDATE,DELETE'
            ),
            has_table_privilege(
                'wallet_writer',
                'public.accounting_snapshots',
                'SELECT,INSERT'
            ),
            has_table_privilege(
                'wallet_writer',
                'public.wallet_signal_consumption',
                'SELECT,INSERT'
            ),
            NOT has_table_privilege(
                'wallet_writer',
                'public.wallet_signal_consumption',
                'UPDATE,DELETE'
            );
        """,
    )
    assert memberships == ["t|t|t|t|t"]
    assert crypto_access == ["t|t|t"]
    assert config_access == ["t|t"]
    assert signal_access == ["t|t|t|t|t|t"]
    assert wallet_access == ["t|t|t|t|t|t|t"]


def test_crypto_columns_precision_nullability_and_primary_keys_match_design() -> None:
    for table, expected in EXPECTED_CRYPTO_COLUMNS.items():
        assert _crypto_column_contract(table) == expected
    primary_keys = set(
        _query(
            "crypto_data",
            """
            SELECT concat_ws(
                '|',
                relation.relname,
                string_agg(
                    attribute.attname,
                    ','
                    ORDER BY array_position(index.indkey, attribute.attnum)
                )
            )
            FROM pg_index AS index
            JOIN pg_class AS relation
              ON relation.oid = index.indrelid
            JOIN pg_namespace AS namespace
              ON namespace.oid = relation.relnamespace
            JOIN pg_attribute AS attribute
              ON attribute.attrelid = relation.oid
             AND attribute.attnum = ANY(index.indkey)
            WHERE index.indisprimary
              AND namespace.nspname = 'public'
              AND relation.relname IN ('ohlcv_futures', 'funding_rates')
            GROUP BY relation.relname
            ORDER BY relation.relname;
            """,
        )
    )
    assert primary_keys == {
        "funding_rates|time,symbol,exchange",
        "ohlcv_futures|time,symbol,exchange,timeframe",
    }


def test_crypto_contract_has_compression_before_2000_day_retention() -> None:
    hypertables = set(
        _query(
            "crypto_data",
            """
            SELECT hypertable_name
            FROM timescaledb_information.hypertables
            WHERE hypertable_schema = 'public'
              AND hypertable_name IN ('ohlcv_futures', 'funding_rates')
              AND compression_enabled
            ORDER BY hypertable_name;
            """,
        )
    )
    compression_tables = set(
        _query(
            "crypto_data",
            """
            SELECT hypertable_name
            FROM timescaledb_information.jobs
            WHERE proc_name = 'policy_compression'
              AND hypertable_schema = 'public'
              AND hypertable_name IN ('ohlcv_futures', 'funding_rates')
              AND (config ->> 'compress_after')::interval = INTERVAL '7 days'
            ORDER BY hypertable_name;
            """,
        )
    )
    retention_tables = set(
        _query(
            "crypto_data",
            """
            SELECT hypertable_name
            FROM timescaledb_information.jobs
            WHERE proc_name = 'policy_retention'
              AND hypertable_schema = 'public'
              AND hypertable_name IN ('ohlcv_futures', 'funding_rates')
              AND (config ->> 'drop_after')::interval = INTERVAL '2000 days'
            ORDER BY hypertable_name;
            """,
        )
    )
    assert hypertables == {"funding_rates", "ohlcv_futures"}
    assert compression_tables == hypertables
    assert retention_tables == hypertables


def test_crypto_contract_has_five_continuous_aggregates_and_refresh_jobs() -> None:
    aggregates = set(
        _query(
            "crypto_data",
            """
            SELECT view_name
            FROM timescaledb_information.continuous_aggregates
            WHERE view_schema = 'public'
              AND hypertable_name = 'ohlcv_futures'
            ORDER BY view_name;
            """,
        )
    )
    refresh_job_count = _query(
        "crypto_data",
        """
        SELECT count(*)
        FROM timescaledb_information.jobs
        WHERE proc_name = 'policy_refresh_continuous_aggregate';
        """,
    )
    assert aggregates == EXPECTED_AGGREGATES
    assert refresh_job_count == ["5"]


def test_service_catalogs_and_paper_wallet_schema_exist_without_legacy_data() -> None:
    crypto_table_count = _query(
        "crypto_data",
        """
        SELECT count(*)
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE';
        """,
    )
    config_state = _query(
        "config_db",
        """
        SELECT
            to_regclass('public.symbols') IS NOT NULL,
            (SELECT count(*) FROM public.symbols);
        """,
    )
    backtest_tables = set(
        _query(
            "backtest_db",
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name LIKE 'backtest_%'
            ORDER BY table_name;
            """,
        )
    )
    signal_state = _query(
        "signal_db",
        """
        SELECT
            to_regclass('public.strategy_registry') IS NOT NULL,
            (SELECT count(*) FROM public.strategy_registry),
            to_regclass('public.trading_strategies') IS NULL,
            to_regclass('public.trading_signals') IS NOT NULL,
            (SELECT strategy_id FROM public.strategy_registry);
        """,
    )
    signal_registry_columns = set(
        _query(
            "signal_db",
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'strategy_registry'
            ORDER BY ordinal_position;
            """,
        )
    )
    trading_signal_columns = set(
        _query(
            "signal_db",
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'trading_signals'
            ORDER BY ordinal_position;
            """,
        )
    )
    trading_signal_unique_columns = _query(
        "signal_db",
        """
        SELECT column_name
        FROM information_schema.key_column_usage
        WHERE table_schema = 'public'
          AND table_name = 'trading_signals'
          AND constraint_name = 'uq_trading_signals_decision'
        ORDER BY ordinal_position;
        """,
    )
    wallet_tables = set(
        _query(
            "wallet_db",
            """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name;
        """,
        )
    )
    assert crypto_table_count == ["2"]
    assert config_state == ["t|0"]
    assert backtest_tables == EXPECTED_BACKTEST_TABLES
    assert signal_state == ["t|1|t|t|vessel-reference"]
    assert signal_registry_columns == EXPECTED_SIGNAL_REGISTRY_COLUMNS
    assert trading_signal_columns == EXPECTED_TRADING_SIGNAL_COLUMNS
    assert trading_signal_unique_columns == [
        "strategy_id",
        "params_json",
        "source_mode",
        "symbol",
        "exchange",
        "timeframe",
        "candle_close_time",
    ]
    assert wallet_tables == EXPECTED_WALLET_TABLES
