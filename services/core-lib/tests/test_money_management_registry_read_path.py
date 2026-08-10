"""Keep both service adapters on the one shared policy-catalog row contract."""

from __future__ import annotations

import ast
import importlib
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

import pytest
from core_lib.money_management import (
    MONEY_MANAGEMENT_CATALOG_COLUMNS,
    money_management_catalog_row_entry,
)
from core_lib.ports import MoneyManagementRegistry

_ADAPTERS = (
    (
        "backtest_service.adapters.money_management_registry",
        "BacktestMoneyManagementRegistry",
        "services/backtest-service/backtest_service/adapters/money_management_registry.py",
    ),
    (
        "signal_service.infrastructure.money_management_registry",
        "SignalMoneyManagementRegistry",
        "services/signal-service/signal_service/infrastructure/money_management_registry.py",
    ),
)


class _Result:
    def __init__(self, row: Sequence[object]) -> None:
        self._row = row

    def fetchall(self) -> list[Sequence[object]]:
        return [self._row]

    def fetchone(self) -> Sequence[object]:
        return self._row


class _Connection:
    def __init__(self, row: Sequence[object], *, query_token: str | None = None) -> None:
        self._row = row
        self._query_token = query_token

    def execute(self, query: str, params: tuple[object, ...]) -> _Result:
        del params
        assert "public.money_management_registry" in query
        if self._query_token is not None:
            assert self._query_token in query
        return _Result(self._row)


class _RegistryFactory(Protocol):
    def __call__(self, connection: _Connection) -> MoneyManagementRegistry: ...


class _TableResult:
    def __init__(self, rows: list[Sequence[object]]) -> None:
        self._rows = rows

    def fetchone(self) -> Sequence[object] | None:
        return None if not self._rows else self._rows[0]

    def fetchall(self) -> list[Sequence[object]]:
        return list(self._rows)


class _TableConnection:
    def __init__(self, relation: object, rows: list[Sequence[object]]) -> None:
        self._relation = relation
        self._rows = rows

    def execute(self, query: str, params: tuple[object, ...]) -> _TableResult:
        del params
        if "to_regclass" in query:
            return _TableResult([(self._relation,)])
        return _TableResult(self._rows)


def _row(columns: Sequence[str] = MONEY_MANAGEMENT_CATALOG_COLUMNS) -> tuple[object, ...]:
    values: dict[str, object] = {column: f"value:{column}" for column in columns}
    values.update(
        {
            "mode": "probe",
            "settings_names": ["alpha", "beta"],
            "is_active": True,
            "is_deprecated": False,
            "registered_at": datetime(2026, 8, 10, tzinfo=UTC),
            "updated_at": datetime(2026, 8, 10, tzinfo=UTC),
        }
    )
    return tuple(values[column] for column in columns)


def _factory(module_name: str, class_name: str) -> _RegistryFactory:
    module = importlib.import_module(module_name)
    return cast("_RegistryFactory", getattr(module, class_name))


def test_services_do_not_redeclare_the_money_management_catalog_contract() -> None:
    repository_root = Path(__file__).resolve().parents[3]

    for _, _, relative_path in _ADAPTERS:
        tree = ast.parse((repository_root / relative_path).read_text())
        assigned_names = {
            target.id
            for node in ast.walk(tree)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
            if isinstance(target, ast.Name)
        }
        function_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        shared_imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "core_lib.money_management"
            for alias in node.names
        }

        assert "MONEY_MANAGEMENT_CATALOG_COLUMNS" not in assigned_names
        assert "money_management_catalog_row_entry" not in function_names
        assert {
            "MONEY_MANAGEMENT_CATALOG_COLUMNS",
            "money_management_catalog_row_entry",
        } <= shared_imports


def test_both_services_return_the_same_dictionary_for_the_same_row() -> None:
    expected = money_management_catalog_row_entry(_row())

    observed = [
        _factory(module_name, class_name)(_Connection(_row())).get("probe")
        for module_name, class_name, _ in _ADAPTERS
    ]

    assert observed == [expected, expected]
    assert all(
        isinstance(entry, MoneyManagementRegistry)
        for entry in [
            _factory(module_name, class_name)(_Connection(_row()))
            for module_name, class_name, _ in _ADAPTERS
        ]
    )


@pytest.mark.parametrize(("module_name", "class_name", "_"), _ADAPTERS)
def test_policy_adapters_distinguish_a_missing_table_from_an_empty_table(
    module_name: str,
    class_name: str,
    _: str,
) -> None:
    factory = _factory(module_name, class_name)

    missing = factory(cast("_Connection", _TableConnection(None, []))).list()
    empty = factory(cast("_Connection", _TableConnection("money_management_registry", []))).list()

    assert missing is None
    assert empty == []


@pytest.mark.parametrize(("module_name", "class_name", "_"), _ADAPTERS)
def test_shared_column_extension_reaches_both_policy_adapters(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    class_name: str,
    _: str,
) -> None:
    package = importlib.import_module("core_lib.money_management")
    row_module = importlib.import_module("core_lib.money_management.catalog_row")
    registry_module = importlib.import_module(module_name)
    extended_columns = (*MONEY_MANAGEMENT_CATALOG_COLUMNS, "sentinel")

    with monkeypatch.context() as patch:
        patch.setattr(row_module, "MONEY_MANAGEMENT_CATALOG_COLUMNS", extended_columns)
        patch.setattr(package, "MONEY_MANAGEMENT_CATALOG_COLUMNS", extended_columns)
        registry_module = importlib.reload(registry_module)
        factory = cast("_RegistryFactory", getattr(registry_module, class_name))

        entry = factory(_Connection(_row(extended_columns), query_token="sentinel")).get("probe")

        assert entry["sentinel"] == "value:sentinel"

    importlib.reload(registry_module)


@pytest.mark.parametrize(("module_name", "class_name", "_"), _ADAPTERS)
@pytest.mark.parametrize(
    ("row", "error", "message"),
    [
        (_row()[:-1], ValueError, "unexpected row shape"),
        (
            (*_row()[:6], ["valid", 3], *_row()[7:]),
            TypeError,
            "list of strings",
        ),
    ],
)
def test_both_policy_adapters_reject_malformed_rows(
    module_name: str,
    class_name: str,
    _: str,
    row: tuple[object, ...],
    error: type[Exception],
    message: str,
) -> None:
    registry = _factory(module_name, class_name)(_Connection(row))

    with pytest.raises(error, match=message):
        registry.get("probe")
