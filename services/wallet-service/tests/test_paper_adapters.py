"""Verify paper Broker conformance, repository transactions, and safety surface."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Sequence
from decimal import Decimal
from pathlib import Path
from typing import cast

import core_lib.execution as core_execution
import pytest
import wallet_service.infrastructure.paper_broker as broker_module
from core_lib.ports import Broker, CostModel
from wallet_service.application import WalletService
from wallet_service.core import RiskPolicy
from wallet_service.domain import WalletExecution
from wallet_service.infrastructure import (
    PaperBroker,
    PaperCostModel,
    PostgresWalletRepository,
)

from tests.conftest import QueueDouble, RepositoryDouble, paper_signal


class _Result:
    def __init__(self, row: Sequence[object] | None = None) -> None:
        self._row = row

    def fetchone(self) -> Sequence[object] | None:
        return self._row


class _Connection:
    def __init__(
        self,
        handler: Callable[[str, tuple[object, ...]], _Result],
    ) -> None:
        self._handler = handler
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.commit_calls = 0
        self.rollback_calls = 0

    def execute(self, query: str, params: tuple[object, ...]) -> _Result:
        self.calls.append((query, params))
        return self._handler(query, params)

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


def _execution() -> WalletExecution:
    capture = RepositoryDouble()
    service = WalletService(
        "wallet-1",
        QueueDouble(),
        PaperBroker(PaperCostModel()),
        capture,
        RiskPolicy(frozenset({"BTCUSDT"})),
        initial_cash=Decimal("1000"),
    )
    result = service.process(paper_signal())
    assert result is not None
    return result


def test_paper_broker_is_shared_broker_and_uses_normalizer_then_matcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    normalize = cast(Callable[..., object], core_execution.normalize_order)
    match = cast(Callable[..., object], core_execution.match)

    def normalize_spy(*args: object, **kwargs: object) -> object:
        calls.append("normalize")
        return normalize(*args, **kwargs)

    def match_spy(*args: object, **kwargs: object) -> object:
        calls.append("match")
        return match(*args, **kwargs)

    monkeypatch.setattr(core_execution, "normalize_order", normalize_spy)
    monkeypatch.setattr(core_execution, "match", match_spy)
    broker = PaperBroker(PaperCostModel())
    service = WalletService(
        "wallet-1",
        QueueDouble(),
        broker,
        RepositoryDouble(),
        RiskPolicy(frozenset({"BTCUSDT"})),
        initial_cash=Decimal("1000"),
    )

    result = service.process(paper_signal())

    assert result is not None
    assert calls == ["normalize", "match"]
    assert isinstance(broker, Broker)
    assert isinstance(broker.cost_model, CostModel)


def test_repository_commits_fill_position_accounting_and_balance_together() -> None:
    def succeed(query: str, params: tuple[object, ...]) -> _Result:
        assert query.count("%s") == len(params)
        return _Result((1,)) if "RETURNING" in query else _Result()

    connection = _Connection(succeed)
    repository = PostgresWalletRepository(connection)

    inserted = repository.store(_execution())

    assert inserted is True
    assert connection.commit_calls == 1
    assert connection.rollback_calls == 0
    assert len(connection.calls) == 6
    statements = [query.lstrip().split(maxsplit=1)[0] for query, _ in connection.calls]
    assert statements == ["INSERT", "INSERT", "DELETE", "INSERT", "INSERT", "INSERT"]
    relations = "\n".join(query for query, _ in connection.calls)
    assert '"public".wallet_signal_consumption' in relations
    assert '"public".fills' in relations
    assert '"public".positions' in relations
    assert '"public".accounting_snapshots' in relations
    assert '"public".wallet_accounts' in relations


def test_repository_rolls_back_every_statement_on_failure() -> None:
    def fail_on_position(query: str, params: tuple[object, ...]) -> _Result:
        del params
        if '"public".positions' in query and query.lstrip().startswith("INSERT"):
            raise RuntimeError("disposable failure")
        return _Result((1,)) if "RETURNING" in query else _Result()

    connection = _Connection(fail_on_position)
    repository = PostgresWalletRepository(connection)

    with pytest.raises(RuntimeError, match="disposable failure"):
        repository.store(_execution())

    assert connection.commit_calls == 0
    assert connection.rollback_calls == 1


def test_repository_idempotency_replay_rolls_back_without_partial_write() -> None:
    connection = _Connection(lambda query, params: _Result())
    repository = PostgresWalletRepository(connection)

    inserted = repository.store(_execution())

    assert inserted is False
    assert connection.commit_calls == 0
    assert connection.rollback_calls == 1
    assert len(connection.calls) == 1


def test_service_contains_no_remote_trading_dependency_or_runner() -> None:
    root = Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text()
    sources = "\n".join(
        path.read_text() for path in sorted((root / "wallet_service").rglob("*.py"))
    )
    banned_imports = (
        "ccxt",
        "requests",
        "httpx",
        "aiohttp",
        "websocket",
        "urllib.request",
    )
    assert all(name not in pyproject for name in banned_imports)
    assert all(f"import {name}" not in sources for name in banned_imports)
    broker_classes = [
        value
        for _, value in inspect.getmembers(broker_module, inspect.isclass)
        if value.__module__ == broker_module.__name__ and issubclass(value, Broker)
    ]
    assert broker_classes == [PaperBroker]
    assert not (root / "wallet_service" / "runner.py").exists()


def test_wallet_schema_is_paper_only_and_contains_the_atomic_ledger_tables() -> None:
    root = Path(__file__).resolve().parents[3]
    migration_directory = (
        root / "init-scripts" / "wallet-service" / "20260726" / "01-create-paper-wallet-ledger.sql"
    ).parent
    migration = "\n".join(path.read_text() for path in sorted(migration_directory.glob("*.sql")))
    assert migration.count("CREATE TABLE IF NOT EXISTS") == 5
    for table in (
        "wallet_accounts",
        "fills",
        "positions",
        "accounting_snapshots",
        "wallet_signal_consumption",
    ):
        assert f"public.{table}" in migration
    assert migration.count("CHECK (mode = 'paper')") == 5
    assert "BEGIN;" in migration
    assert "COMMIT;" in migration
    assert "api_key" not in migration
    assert "secret_key" not in migration
    assert "exchange_order_id" not in migration
