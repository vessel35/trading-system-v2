"""Verify signal-to-ledger orchestration and fail-closed risk guards."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal

import core_lib.execution as core_execution
import pytest
import wallet_service.application.risk as risk_module
import wallet_service.application.service as service_module
from core_lib.sizing import MAX_RISK_PER_TRADE
from core_lib.sizing import exposure_limit as core_exposure_limit
from core_lib.sizing import one_r as core_one_r
from core_lib.sizing import size as core_risk_size
from core_lib.types import PositionSide
from wallet_service.application import WalletService
from wallet_service.core import RiskPolicy
from wallet_service.domain import PaperIntent, RiskRejected
from wallet_service.infrastructure import PaperBroker, PaperCostModel

from tests.conftest import QueueDouble, RepositoryDouble, paper_signal


def test_mock_queue_runs_core_sizing_matcher_book_costs_and_accounting(
    monkeypatch: pytest.MonkeyPatch,
    queue: QueueDouble,
    repository: RepositoryDouble,
    service: WalletService,
) -> None:
    calls: dict[str, int] = {
        "risk_size": 0,
        "position_value": 0,
        "recompute": 0,
        "assert_identity": 0,
        "single_market": 0,
    }

    def spy(
        name: str,
        target: Callable[..., object],
    ) -> Callable[..., object]:
        def wrapped(*args: object, **kwargs: object) -> object:
            calls[name] += 1
            return target(*args, **kwargs)

        return wrapped

    monkeypatch.setattr(
        service_module,
        "risk_size",
        spy("risk_size", core_risk_size),
    )
    monkeypatch.setattr(
        core_execution,
        "position_value",
        spy("position_value", core_execution.position_value),
    )
    monkeypatch.setattr(
        core_execution,
        "recompute",
        spy("recompute", core_execution.recompute),
    )
    monkeypatch.setattr(
        core_execution,
        "assert_identity",
        spy("assert_identity", core_execution.assert_identity),
    )
    monkeypatch.setattr(
        core_exposure_limit,
        "single_market",
        spy("single_market", core_exposure_limit.single_market),
    )
    queue.messages.append(paper_signal())

    result = service.run_once()

    assert result is not None
    assert result == repository.executions[0]
    assert len(result.fills) == 1
    fill = result.fills[0]
    assert fill.timestamp > result.accounting.occurred_at.replace(microsecond=0)
    assert fill.price == Decimal("102.05100000")
    assert fill.quantity == Decimal("2.00000000")
    assert fill.fee > Decimal("0")
    assert fill.slippage > Decimal("0")
    assert result.position is not None
    assert result.position.quantity == fill.quantity
    assert (
        result.accounting.cash_balance + result.accounting.position_value
        == result.accounting.total_equity
    )
    assert calls["risk_size"] == 1
    assert calls["single_market"] == 1
    assert calls["position_value"] >= 2
    assert calls["recompute"] >= 2
    assert calls["assert_identity"] >= 2


def test_exit_is_matched_and_flattened_through_the_same_accounting_path(
    service: WalletService,
) -> None:
    entered = service.process(paper_signal())
    assert entered is not None
    exit_message = paper_signal(
        "signal-2",
        decision_index=1,
        intent=PaperIntent.EXIT,
        side=None,
        execution_open=110.0,
        stop_loss=None,
        take_profit=None,
    )

    exited = service.process(exit_message)

    assert exited is not None
    assert exited.fills[0].reduce_only is True
    assert exited.position is None
    assert exited.accounting.position_value == Decimal("0E-8")
    assert service.current_position is None
    assert service.cash_balance == exited.accounting.total_equity
    assert service.cash_balance > Decimal("1000")


def test_reverse_closes_before_opening_the_opposite_paper_position(
    service: WalletService,
) -> None:
    assert service.process(paper_signal()) is not None
    reverse = paper_signal(
        "signal-2",
        decision_index=1,
        intent=PaperIntent.REVERSE,
        side=PositionSide.SHORT,
        execution_open=98.0,
        stop_loss=105.0,
        take_profit=90.0,
    )

    result = service.process(reverse)

    assert result is not None
    assert [fill.reduce_only for fill in result.fills] == [True, False]
    assert result.position is not None
    assert result.position.side is PositionSide.SHORT
    assert result.accounting.total_equity == (
        result.accounting.cash_balance + result.accounting.position_value
    )


@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        (
            RiskPolicy(frozenset({"ETHUSDT"})),
            "symbol_not_allowed",
        ),
        (
            RiskPolicy(frozenset({"BTCUSDT"}), max_order_quantity=1.0),
            "max_order_quantity",
        ),
        (
            RiskPolicy(frozenset({"BTCUSDT"}), max_order_notional=100.0),
            "max_order_notional",
        ),
        (
            RiskPolicy(frozenset({"BTCUSDT"}), single_market_limit=0.005),
            "exposure_limit",
        ),
    ],
)
def test_risk_guards_reject_before_fill_or_write(
    policy: RiskPolicy,
    expected: str,
) -> None:
    repository = RepositoryDouble()
    broker = PaperBroker(PaperCostModel())
    service = WalletService(
        "wallet-1",
        QueueDouble(),
        broker,
        repository,
        policy,
        initial_cash=Decimal("1000"),
    )

    with pytest.raises(RiskRejected, match=expected):
        service.process(paper_signal())

    assert repository.executions == []
    assert broker.open_orders() == []
    assert service.cash_balance == Decimal("1000.00000000")
    assert service.current_position is None


def test_kill_switch_is_one_way_and_blocks_before_sizing(
    monkeypatch: pytest.MonkeyPatch,
    service: WalletService,
    repository: RepositoryDouble,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("sizing must not run after kill switch")

    monkeypatch.setattr(service_module, "risk_size", forbidden)
    service.engage_kill_switch()

    with pytest.raises(RiskRejected, match="kill_switch"):
        service.process(paper_signal())

    assert service.kill_switch_engaged is True
    assert repository.executions == []


def test_actual_simulated_notional_is_rechecked_before_book_or_write() -> None:
    repository = RepositoryDouble()
    service = WalletService(
        "wallet-1",
        QueueDouble(),
        PaperBroker(PaperCostModel()),
        repository,
        RiskPolicy(frozenset({"BTCUSDT"}), max_order_notional=200.05),
        initial_cash=Decimal("1000"),
    )

    with pytest.raises(RiskRejected, match="max_order_notional"):
        service.process(paper_signal())

    assert repository.executions == []
    assert service.current_position is None
    assert service.cash_balance == Decimal("1000.00000000")


def test_one_r_float_roundoff_does_not_reject_core_sized_entry() -> None:
    equity = 89104.93
    price = 98049.54
    stop = 92359.77
    sized_quantity = core_risk_size(
        MAX_RISK_PER_TRADE,
        equity,
        abs(price - stop),
    )
    assert core_one_r(price, stop, sized_quantity) > equity * MAX_RISK_PER_TRADE

    repository = RepositoryDouble()
    service = WalletService(
        "wallet-1",
        QueueDouble(),
        PaperBroker(PaperCostModel()),
        repository,
        RiskPolicy(frozenset({"BTCUSDT"})),
        initial_cash=Decimal("89104.93"),
    )

    result = service.process(
        paper_signal(
            decision_price=price,
            execution_open=price,
            stop_loss=stop,
            take_profit=109429.08,
        )
    )

    assert result is not None
    assert result.position is not None
    assert result.position.quantity == Decimal("0.15660550")
    assert repository.executions == [result]


def test_one_r_tolerance_remains_fail_closed_for_material_overshoot(
    monkeypatch: pytest.MonkeyPatch,
    service: WalletService,
    repository: RepositoryDouble,
) -> None:
    monkeypatch.setattr(
        risk_module,
        "calculate_one_r",
        lambda entry, stop, quantity: 10.0000001,
    )

    with pytest.raises(RiskRejected, match="one_r_limit"):
        service.process(paper_signal())

    assert repository.executions == []
    assert service.current_position is None


def test_repository_replay_does_not_commit_candidate_memory_state() -> None:
    repository = RepositoryDouble(accept=False)
    service = WalletService(
        "wallet-1",
        QueueDouble(),
        PaperBroker(PaperCostModel()),
        repository,
        RiskPolicy(frozenset({"BTCUSDT"})),
        initial_cash=Decimal("1000"),
    )

    assert service.process(paper_signal()) is None
    assert service.current_position is None
    assert service.cash_balance == Decimal("1000.00000000")


def test_envelope_rejects_non_paper_mode_and_non_contiguous_execution() -> None:
    with pytest.raises(ValueError, match="paper signals only"):
        replace(paper_signal(), mode="not-paper")
    with pytest.raises(ValueError, match="contiguous"):
        replace(
            paper_signal(),
            execution_candle=paper_signal(decision_index=2).execution_candle,
        )
