"""Consume paper signals and orchestrate the shared execution standards."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from types import TracebackType

import core_lib.execution as execution
from core_lib.costs import liquidation_price
from core_lib.sizing import size as risk_size
from core_lib.types import (
    Fill,
    MarginType,
    MarketType,
    OrderRequest,
    OrderSide,
    OrderType,
    Position,
    PositionSide,
)
from core_lib.types.money import ZERO, quantize_amount

from wallet_service.core import RiskPolicy
from wallet_service.domain import (
    AccountingSnapshot,
    PaperIntent,
    PaperSignal,
    RiskRejected,
    SignalConsumptionStatus,
    WalletExecution,
)

from .ports import PaperExecutionBroker, SignalQueue, WalletRepository
from .risk import RiskGuard


class WalletService:
    """Own paper signal ordering while delegating every standard calculation."""

    def __init__(
        self,
        wallet_id: str,
        queue: SignalQueue,
        broker: PaperExecutionBroker,
        repository: WalletRepository,
        policy: RiskPolicy,
        *,
        initial_cash: Decimal,
    ) -> None:
        if not wallet_id:
            raise ValueError("wallet_id must not be empty")
        if not isinstance(initial_cash, Decimal):
            raise TypeError("initial_cash must be Decimal")
        normalized_cash = quantize_amount(initial_cash)
        if normalized_cash <= ZERO:
            raise ValueError("initial_cash must be positive")
        self._wallet_id = wallet_id
        self._queue = queue
        self._broker = broker
        self._repository = repository
        self._policy = policy
        self._risk_guard = RiskGuard(policy)
        self._cash = normalized_cash
        self._position: Position | None = None
        self._open_risk: tuple[str, PositionSide, float] | None = None
        self._last_run_received = False

    @property
    def cash_balance(self) -> Decimal:
        """Return the committed paper cash balance."""
        return self._cash

    @property
    def current_position(self) -> Position | None:
        """Return the committed paper position, if any."""
        return self._position

    @property
    def kill_switch_engaged(self) -> bool:
        """Return the risk guard's fail-closed state."""
        return self._risk_guard.kill_switch_engaged

    @property
    def last_run_received(self) -> bool:
        """Report whether the latest ``run_once`` call received a queue message."""

        return self._last_run_received

    def engage_kill_switch(self) -> None:
        """Block every subsequent signal before sizing or Broker submission."""
        self._risk_guard.engage_kill_switch()

    def run_once(self) -> WalletExecution | None:
        """Consume one ready signal and terminally receipt every permanent outcome."""
        self._last_run_received = False
        message = self._queue.receive()
        if message is None:
            return None
        self._last_run_received = True
        try:
            execution = self.process(message)
        except RiskRejected:
            self._repository.record_consumption(
                self._wallet_id,
                message.signal_id,
                SignalConsumptionStatus.REJECTED,
                message.execution_candle.close_time,
            )
            return None
        if execution is None:
            self._repository.record_consumption(
                self._wallet_id,
                message.signal_id,
                SignalConsumptionStatus.SKIPPED,
                message.execution_candle.close_time,
            )
        return execution

    def close(self) -> None:
        """Release queue-owned read connections."""
        self._queue.close()

    def __enter__(self) -> WalletService:
        """Support bounded ownership of source read connections."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close source reads even when processing raises unexpectedly."""
        del exc_type, exc_value, traceback
        self.close()

    def process(self, message: PaperSignal) -> WalletExecution | None:
        """Simulate, account, and atomically persist one paper signal."""
        if message.wallet_id != self._wallet_id:
            raise RiskRejected("wallet_mismatch")
        self._risk_guard.validate_signal(message)

        candidate_position = None if self._position is None else deepcopy(self._position)
        book = execution.PositionBook(() if candidate_position is None else (candidate_position,))
        candidate_cash = self._cash
        candidate_risk = self._open_risk
        fills: list[Fill] = []

        if message.intent in {PaperIntent.EXIT, PaperIntent.REVERSE}:
            current = self._book_position(book, message.signal.symbol)
            if current is None:
                raise RiskRejected("position_required")
            if message.intent is PaperIntent.REVERSE and message.side is current.side:
                raise RiskRejected("reverse_requires_opposite_side")
            exit_fill, candidate_cash = self._execute_exit(
                message,
                book,
                current,
                candidate_cash,
            )
            fills.append(exit_fill)
            candidate_risk = None

        if message.intent in {PaperIntent.ENTER, PaperIntent.REVERSE}:
            if self._book_position(book, message.signal.symbol) is not None:
                raise RiskRejected("pyramiding_disabled")
            if self._any_position(book) is not None:
                raise RiskRejected("max_open_positions")
            entry_fill, candidate_cash = self._execute_entry(
                message,
                book,
                candidate_cash,
                () if candidate_risk is None else (candidate_risk,),
            )
            fills.append(entry_fill)
            assert message.side is not None
            candidate_risk = (
                message.signal.symbol,
                message.side,
                self._policy.risk_per_trade,
            )

        final_position = self._any_position(book)
        snapshot = self._snapshot(candidate_cash, final_position, tuple(fills))
        transaction = WalletExecution(
            wallet_id=self._wallet_id,
            signal_id=message.signal_id,
            symbol=message.signal.symbol,
            fills=tuple(fills),
            position=final_position,
            accounting=snapshot,
        )
        if not self._repository.store(transaction):
            return None
        self._cash = candidate_cash
        self._position = final_position
        self._open_risk = candidate_risk
        return transaction

    def _execute_entry(
        self,
        message: PaperSignal,
        book: execution.PositionBook,
        cash: Decimal,
        existing_risks: tuple[tuple[str, PositionSide, float], ...],
    ) -> tuple[Fill, Decimal]:
        stop = message.signal.stop_loss
        if stop is None:
            raise RiskRejected("protective_stop_required")
        equity = execution.recompute(cash, None)
        quantity = risk_size(
            self._policy.risk_per_trade,
            float(equity),
            abs(message.signal.price - stop),
        )
        self._risk_guard.validate_sized_entry(
            message,
            quantity,
            float(equity),
            existing_risks,
        )
        side = message.side
        if side is None:
            raise RiskRejected("direction_required")
        leverage = message.signal.leverage or 1
        self._broker.configure_execution(
            message.decision_candle,
            message.execution_candle,
            wallet_id=self._wallet_id,
            signal_id=message.signal_id,
            equity=equity,
            available_margin=cash,
            leverage=leverage,
            risk_fraction=self._policy.risk_per_trade,
        )
        fill = self._broker.submit(
            OrderRequest(
                symbol=message.signal.symbol,
                side=OrderSide.BUY if side is PositionSide.LONG else OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=float(quantity),
                price=message.signal.price,
                stop_price=stop,
                market_type=message.signal.market_type,
                position_side=side,
                reduce_only=False,
                close_position=False,
                time_in_force="GTC",
            )
        )
        self._assert_times(message, fill)
        self._risk_guard.validate_simulated_entry(fill)
        book.apply(
            fill,
            leverage=leverage,
            margin_type=MarginType.ISOLATED,
            market_type=message.signal.market_type,
            liquidation_price=self._liquidation_price(
                fill,
                leverage,
                message.signal.market_type,
            ),
        )
        position = self._book_position(book, message.signal.symbol)
        if position is None:
            raise RuntimeError("PositionBook did not create the filled position")
        next_cash = quantize_amount(cash - execution.position_value(position) - fill.fee)
        if next_cash < ZERO:
            raise RuntimeError("paper entry would make cash negative")
        self._assert_accounting(next_cash, position)
        return fill, next_cash

    def _execute_exit(
        self,
        message: PaperSignal,
        book: execution.PositionBook,
        position: Position,
        cash: Decimal,
    ) -> tuple[Fill, Decimal]:
        equity = execution.recompute(cash, position)
        self._broker.configure_execution(
            message.decision_candle,
            message.execution_candle,
            wallet_id=self._wallet_id,
            signal_id=message.signal_id,
            equity=equity,
            available_margin=cash,
            leverage=position.leverage,
            risk_fraction=None,
        )
        fill = self._broker.submit(
            OrderRequest(
                symbol=position.symbol,
                side=OrderSide.SELL if position.side is PositionSide.LONG else OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=float(position.quantity),
                price=None,
                stop_price=None,
                market_type=position.market_type,
                position_side=position.side,
                reduce_only=True,
                close_position=False,
                time_in_force="GTC",
            )
        )
        self._assert_times(message, fill)
        position.update_price(fill.price)
        equity_before_fee = execution.recompute(cash, position)
        book.apply(fill)
        remaining = self._book_position(book, position.symbol)
        next_cash = quantize_amount(
            equity_before_fee - fill.fee - execution.position_value(remaining)
        )
        if next_cash < ZERO:
            raise RuntimeError("paper exit would make cash negative")
        self._assert_accounting(next_cash, remaining)
        return fill, next_cash

    def _liquidation_price(
        self,
        fill: Fill,
        leverage: int,
        market_type: MarketType,
    ) -> Decimal:
        if fill.position_side is PositionSide.BOTH:
            raise RiskRejected("direction_required")
        if market_type is MarketType.SPOT:
            return ZERO
        params = self._broker_cost_params()
        return liquidation_price(
            fill.price,
            leverage,
            params,
            side=fill.position_side,
        )

    def _broker_cost_params(self) -> Decimal:
        params = self._broker.cost_model.liq_params()
        value = params.get("maintenance_margin_rate")
        if not isinstance(value, Decimal):
            raise TypeError("maintenance_margin_rate must be Decimal")
        return value

    def _snapshot(
        self,
        cash: Decimal,
        position: Position | None,
        fills: tuple[Fill, ...],
    ) -> AccountingSnapshot:
        position_term = execution.position_value(position)
        total_equity = execution.recompute(cash, position)
        execution.assert_identity(cash, position_term, total_equity)
        return AccountingSnapshot(
            occurred_at=fills[-1].timestamp,
            cash_balance=cash,
            position_value=position_term,
            total_equity=total_equity,
            fee_total=quantize_amount(sum((fill.fee for fill in fills), ZERO)),
            slippage_total=quantize_amount(sum((fill.slippage for fill in fills), ZERO)),
        )

    @staticmethod
    def _assert_accounting(cash: Decimal, position: Position | None) -> None:
        position_term = execution.position_value(position)
        equity = execution.recompute(cash, position)
        execution.assert_identity(cash, position_term, equity)

    @staticmethod
    def _assert_times(message: PaperSignal, fill: Fill) -> None:
        if not message.feature_time <= message.decision_time < fill.timestamp:
            raise ValueError("feature_ts <= decision_ts < execution_ts was violated")

    @staticmethod
    def _book_position(
        book: execution.PositionBook,
        symbol: str,
    ) -> Position | None:
        long_position = book.get(symbol, PositionSide.LONG)
        short_position = book.get(symbol, PositionSide.SHORT)
        if long_position is not None and short_position is not None:
            raise RuntimeError("paper wallet cannot hold both directions")
        return long_position or short_position

    def _any_position(self, book: execution.PositionBook) -> Position | None:
        positions = [
            position
            for symbol in self._policy.allowed_symbols
            for side in (PositionSide.LONG, PositionSide.SHORT)
            if (position := book.get(symbol, side)) is not None
        ]
        if len(positions) > 1:
            raise RuntimeError("paper wallet supports at most one open position")
        return None if not positions else positions[0]
