"""Exercise generated registration statements inside an owned PostgreSQL schema."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from trading_plugins import facts

pytestmark = pytest.mark.integration

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_STRATEGY_REGISTRY_SCRIPT = (
    _REPOSITORY_ROOT / "init-scripts/signal-service/20260724/01-redefine-strategy-registry.sql"
)
_MONEY_MANAGEMENT_REGISTRY_SCRIPT = (
    _REPOSITORY_ROOT
    / "init-scripts/signal-service/20260810/01-create-money-management-registry.sql"
)


@dataclass(frozen=True, slots=True)
class _DisposableRegistry:
    connection: psycopg.Connection[tuple[object, ...]]
    schema: str


def _env() -> dict[str, str]:
    path = _REPOSITORY_ROOT / ".env"
    if not path.exists():
        pytest.skip("repository .env is unavailable")
    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    required = {"PGHOST", "PGPORT", "PGUSER", "PGPASSWORD"}
    if not required <= values.keys():
        pytest.skip("repository .env lacks PostgreSQL connection keys")
    return values


def _connect_writer() -> psycopg.Connection[tuple[object, ...]]:
    values = _env()
    return psycopg.connect(
        host=values["PGHOST"],
        port=int(values["PGPORT"]),
        user=values["PGUSER"],
        password=values["PGPASSWORD"],
        dbname="signal_db",
        autocommit=True,
    )


def _table_definition(path: Path, table: str) -> str:
    source = path.read_text()
    marker = f"CREATE TABLE IF NOT EXISTS public.{table} ("
    start = source.index(marker)
    end = source.index("\n);", start) + len("\n);")
    return source[start:end]


def _money_management_function_definition() -> str:
    source = _MONEY_MANAGEMENT_REGISTRY_SCRIPT.read_text()
    marker = "CREATE OR REPLACE FUNCTION public.money_management_settings_names_are_canonical("
    start = source.index(marker)
    end = source.index("$function$;", start) + len("$function$;")
    return source[start:end]


def _in_schema(
    statement: str,
    registry: _DisposableRegistry,
) -> str:
    schema = sql.Identifier(registry.schema).as_string(registry.connection)
    return statement.replace("public.", f"{schema}.")


@pytest.fixture(scope="module")
def disposable_registry() -> Iterator[_DisposableRegistry]:
    connection = _connect_writer()
    schema = f"facts_registry_{uuid4().hex}"
    registry = _DisposableRegistry(connection=connection, schema=schema)
    try:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        connection.execute(
            _in_schema(
                _table_definition(_STRATEGY_REGISTRY_SCRIPT, "strategy_registry"),
                registry,
            )
        )
        connection.execute(_in_schema(_money_management_function_definition(), registry))
        connection.execute(
            _in_schema(
                _table_definition(
                    _MONEY_MANAGEMENT_REGISTRY_SCRIPT,
                    "money_management_registry",
                ),
                registry,
            )
        )
        yield registry
    finally:
        try:
            connection.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
            )
        finally:
            connection.close()


def _read_generated_columns(
    registry: _DisposableRegistry,
    table: str,
    key_column: str,
    key: str,
    expected: Mapping[str, object],
) -> dict[str, object]:
    columns = tuple(expected)
    query = sql.SQL("SELECT {} FROM {}.{} WHERE {} = %s").format(
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        sql.Identifier(registry.schema),
        sql.Identifier(table),
        sql.Identifier(key_column),
    )
    row = registry.connection.execute(query, (key,)).fetchone()
    assert row is not None
    return dict(zip(columns, row, strict=True))


def test_strategy_registration_round_trips_and_preserves_lifecycle(
    disposable_registry: _DisposableRegistry,
) -> None:
    display_name = "Vessel 등록 검증"
    description = "Generated registration with an operator's quoted value."
    default_params = {"operator_note": "O'Brien"}
    statement = facts.registration_sql(
        "strategy",
        "vessel-reference",
        display_name,
        description,
        True,
        default_params,
    )
    expected = facts._strategy_registration_row(
        "vessel-reference",
        display_name,
        description,
        True,
        default_params,
    )
    executable = _in_schema(statement, disposable_registry)

    inserted = disposable_registry.connection.execute(executable)

    assert inserted.rowcount == 1
    assert (
        _read_generated_columns(
            disposable_registry,
            "strategy_registry",
            "strategy_id",
            "vessel-reference",
            expected,
        )
        == expected
    )

    unchanged = disposable_registry.connection.execute(executable)
    assert unchanged.rowcount == 0

    disposable_registry.connection.execute(
        sql.SQL(
            "UPDATE {}.strategy_registry "
            "SET description = %s, is_active = false, is_deprecated = true "
            "WHERE strategy_id = %s"
        ).format(sql.Identifier(disposable_registry.schema)),
        ("stale declaration", "vessel-reference"),
    )
    reapplied = disposable_registry.connection.execute(executable)
    lifecycle = disposable_registry.connection.execute(
        sql.SQL(
            "SELECT description, is_active, is_deprecated "
            "FROM {}.strategy_registry WHERE strategy_id = %s"
        ).format(sql.Identifier(disposable_registry.schema)),
        ("vessel-reference",),
    ).fetchone()

    assert reapplied.rowcount == 1
    assert lifecycle == (description, False, True)


def test_policy_registration_round_trips_canonical_settings_and_is_idempotent(
    disposable_registry: _DisposableRegistry,
) -> None:
    display_name = "Manual 정책 검증"
    description = "Generated policy registration."
    statement = facts.registration_sql(
        "money_management",
        "manual",
        display_name,
        description,
        True,
    )
    expected = facts._policy_registration_row(
        "manual",
        display_name,
        description,
        True,
    )
    executable = _in_schema(statement, disposable_registry)

    inserted = disposable_registry.connection.execute(executable)
    actual = _read_generated_columns(
        disposable_registry,
        "money_management_registry",
        "mode",
        "manual",
        expected,
    )

    assert inserted.rowcount == 1
    assert actual == expected
    settings_names = actual["settings_names"]
    assert isinstance(settings_names, list)
    assert settings_names == sorted(set(settings_names))
    assert None not in settings_names

    unchanged = disposable_registry.connection.execute(executable)
    assert unchanged.rowcount == 0
