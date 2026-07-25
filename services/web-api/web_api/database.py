"""Read-only PostgreSQL connection boundary for the backtest catalog."""

import os
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

CatalogConnection = Connection[dict[str, Any]]
CryptoConnection = Connection[dict[str, Any]]
SignalConnection = Connection[dict[str, Any]]


class CatalogConfigurationError(RuntimeError):
    """The catalog reader preset is missing or malformed."""


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    user: str
    password: str
    database: str
    crypto_database: str
    signal_database: str
    evidence_root: Path


def _repository_env() -> dict[str, str]:
    """Load repository .env without mutating or logging the process environment."""

    values = dict(os.environ)
    path = Path(__file__).parents[3] / ".env"
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        # Match the existing integration-test contract: repository .env is the
        # canonical local preset and wins over incidental shell PG* variables.
        values[key.strip()] = value.strip().strip("'\"")
    return values


@lru_cache(maxsize=1)
def get_settings() -> DatabaseSettings:
    values = _repository_env()
    missing = [key for key in ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD") if not values.get(key)]
    if missing:
        names = ", ".join(missing)
        raise CatalogConfigurationError(f"PostgreSQL connection settings are incomplete: {names}")
    try:
        port = int(values["PGPORT"])
    except ValueError as exc:
        raise CatalogConfigurationError("PGPORT must be an integer") from exc
    return DatabaseSettings(
        host=values["PGHOST"],
        port=port,
        user=values["PGUSER"],
        password=values["PGPASSWORD"],
        database=values.get("BACKTEST_DB_NAME", "backtest_db"),
        crypto_database=values.get("CRYPTO_DB_NAME", "crypto_data"),
        signal_database=values.get("SIGNAL_DB_NAME", "signal_db"),
        evidence_root=Path(
            values.get(
                "WEBAPI_EVIDENCE_ROOT",
                str(Path(__file__).parents[3] / "var" / "evidence"),
            )
        ).expanduser(),
    )


@contextmanager
def connect_catalog() -> Iterator[CatalogConnection]:
    """Open a physically read-only catalog transaction."""

    settings = get_settings()
    with psycopg.connect(
        host=settings.host,
        port=settings.port,
        user=settings.user,
        password=settings.password,
        dbname=settings.database,
        options="-c default_transaction_read_only=on",
        connect_timeout=5,
        application_name="web-api-p0-reader",
        row_factory=dict_row,
    ) as connection:
        yield connection


def catalog_connection() -> Generator[CatalogConnection]:
    with connect_catalog() as connection:
        yield connection


@contextmanager
def connect_crypto() -> Iterator[CryptoConnection]:
    """Open a physically read-only market-data transaction."""

    settings = get_settings()
    with psycopg.connect(
        host=settings.host,
        port=settings.port,
        user=settings.user,
        password=settings.password,
        dbname=settings.crypto_database,
        options="-c default_transaction_read_only=on",
        connect_timeout=5,
        application_name="web-api-p1-crypto-reader",
        row_factory=dict_row,
    ) as connection:
        yield connection


def crypto_connection() -> Generator[CryptoConnection]:
    with connect_crypto() as connection:
        yield connection


@contextmanager
def connect_signal() -> Iterator[SignalConnection]:
    """Open a physically read-only strategy-registry transaction."""

    settings = get_settings()
    with psycopg.connect(
        host=settings.host,
        port=settings.port,
        user=settings.user,
        password=settings.password,
        dbname=settings.signal_database,
        options="-c default_transaction_read_only=on",
        connect_timeout=5,
        application_name="web-api-p2-strategy-reader",
        row_factory=dict_row,
    ) as connection:
        yield connection


def signal_connection() -> Generator[SignalConnection]:
    with connect_signal() as connection:
        yield connection
