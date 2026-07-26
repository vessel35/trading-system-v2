"""Shared deterministic paper-wallet fixtures."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from core_lib.types import Candle, MarketType, PositionSide, TradingSignal
from wallet_service.application import SignalQueue, WalletRepository, WalletService
from wallet_service.core import RiskPolicy
from wallet_service.domain import PaperIntent, PaperSignal, WalletExecution
from wallet_service.infrastructure import PaperBroker, PaperCostModel


class QueueDouble(SignalQueue):
    """Return messages in deterministic FIFO order."""

    def __init__(self, messages: list[PaperSignal] | None = None) -> None:
        self.messages = [] if messages is None else list(messages)

    def receive(self) -> PaperSignal | None:
        return None if not self.messages else self.messages.pop(0)


class RepositoryDouble(WalletRepository):
    """Capture committed application transactions."""

    def __init__(self, *, accept: bool = True) -> None:
        self.accept = accept
        self.executions: list[WalletExecution] = []

    def store(self, execution: WalletExecution) -> bool:
        if not self.accept:
            return False
        self.executions.append(execution)
        return True


def candle(index: int, *, opening: float, closing: float) -> Candle:
    """Build one contiguous hourly candle."""
    opened = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=index)
    return Candle(
        symbol="BTCUSDT",
        exchange="paper",
        timeframe="1h",
        open_time=opened,
        close_time=opened + timedelta(hours=1),
        open=opening,
        high=max(opening, closing) + 2.0,
        low=min(opening, closing) - 2.0,
        close=closing,
        volume=10.0,
        quote_volume=1_000.0,
        trade_count=10,
    )


def paper_signal(
    signal_id: str = "signal-1",
    *,
    decision_index: int = 0,
    intent: PaperIntent = PaperIntent.ENTER,
    side: PositionSide | None = PositionSide.LONG,
    decision_price: float = 100.0,
    execution_open: float = 102.0,
    stop_loss: float | None = 95.0,
    take_profit: float | None = 110.0,
    mode: str = "paper",
) -> PaperSignal:
    """Build a signal-service-compatible paper envelope."""
    decision = candle(
        decision_index,
        opening=decision_price,
        closing=decision_price,
    )
    execution_candle = candle(
        decision_index + 1,
        opening=execution_open,
        closing=execution_open + 1.0,
    )
    signal = TradingSignal(
        symbol=decision.symbol,
        timestamp=decision.close_time,
        confidence=0.9,
        price=decision.close,
        stop_loss=stop_loss,
        take_profit=take_profit,
        market_type=MarketType.FUTURES,
        leverage=2,
        reason="fixture",
        metadata={"source": "unit"},
    )
    return PaperSignal(
        wallet_id="wallet-1",
        signal_id=signal_id,
        decision_candle=decision,
        execution_candle=execution_candle,
        signal=signal,
        intent=intent,
        side=side,
        mode=mode,
    )


@pytest.fixture
def repository() -> RepositoryDouble:
    """Return a fresh in-memory persistence double."""
    return RepositoryDouble()


@pytest.fixture
def queue() -> QueueDouble:
    """Return an empty queue double."""
    return QueueDouble()


@pytest.fixture
def policy() -> RiskPolicy:
    """Return safe defaults for BTC paper execution."""
    return RiskPolicy(frozenset({"BTCUSDT"}))


@pytest.fixture
def service(
    queue: QueueDouble,
    repository: RepositoryDouble,
    policy: RiskPolicy,
) -> WalletService:
    """Assemble the paper driver with no external systems."""
    return WalletService(
        "wallet-1",
        queue,
        PaperBroker(PaperCostModel()),
        repository,
        policy,
        initial_cash=Decimal("1000"),
    )
