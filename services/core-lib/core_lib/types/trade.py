"""Define completed trades including initial risk."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .enums import ExitReason, MarketType, OrderSide
from .money import ZERO, quantize_amount, quantize_percent, quantize_price


@dataclass(slots=True)
class Trade:
    """A completed trade record suitable for PnL and R-multiple analysis."""

    source_type: str
    symbol: str
    side: OrderSide
    market_type: MarketType
    entry_price: Decimal
    entry_quantity: Decimal
    entry_time: datetime
    exit_price: Decimal
    exit_quantity: Decimal
    exit_time: datetime
    exit_reason: ExitReason
    gross_pnl: Decimal
    total_fee: Decimal
    slippage: Decimal
    funding_cost: Decimal
    liquidation_penalty: Decimal
    net_pnl: Decimal
    return_pct: Decimal
    r0: Decimal | None
    leverage: int
    liquidated: bool
    wallet_id: str | None
    backtest_run_id: str | None
    strategy_id: str
    strategy_name: str
    hold_duration_seconds: int
    signal_confidence: float
    reason: str

    def __post_init__(self) -> None:
        self.side = OrderSide(self.side)
        self.market_type = MarketType(self.market_type)
        self.exit_reason = ExitReason(self.exit_reason)
        self.entry_price = quantize_price(self.entry_price)
        self.entry_quantity = quantize_amount(self.entry_quantity)
        self.exit_price = quantize_price(self.exit_price)
        self.exit_quantity = quantize_amount(self.exit_quantity)
        self.gross_pnl = quantize_amount(self.gross_pnl)
        self.total_fee = quantize_amount(self.total_fee)
        self.slippage = quantize_amount(self.slippage)
        self.funding_cost = quantize_amount(self.funding_cost)
        self.liquidation_penalty = quantize_amount(self.liquidation_penalty)
        self.net_pnl = quantize_amount(self.net_pnl)
        self.return_pct = quantize_percent(self.return_pct)
        if self.r0 is not None:
            self.r0 = quantize_amount(self.r0)

        if self.source_type not in {"live", "paper", "backtest"}:
            raise ValueError("source_type must be live, paper, or backtest")
        if self.entry_price <= ZERO or self.exit_price <= ZERO:
            raise ValueError("trade prices must be positive")
        if self.entry_quantity <= ZERO or self.exit_quantity <= ZERO:
            raise ValueError("trade quantities must be positive")
        if self.total_fee < ZERO or self.slippage < ZERO:
            raise ValueError("fees and slippage must be non-negative")
        if self.liquidation_penalty < ZERO:
            raise ValueError("liquidation_penalty must be non-negative")
        if self.r0 is not None and self.r0 < ZERO:
            raise ValueError("r0 must be non-negative or None")
        if isinstance(self.leverage, bool) or not isinstance(self.leverage, int):
            raise TypeError("leverage must be int")
        if self.leverage <= 0:
            raise ValueError("leverage must be positive")
        if self.liquidated is not (self.exit_reason is ExitReason.LIQUIDATION):
            raise ValueError("liquidated must pair with exit_reason LIQUIDATION")
        if not self.liquidated and self.liquidation_penalty != ZERO:
            raise ValueError("non-liquidated trades must have zero liquidation_penalty")
        expected_net_pnl = quantize_amount(
            self.gross_pnl
            - self.total_fee
            - self.slippage
            - self.funding_cost
            - self.liquidation_penalty
        )
        if self.net_pnl != expected_net_pnl:
            raise ValueError(
                "net_pnl must equal gross_pnl minus fee, slippage, funding, and penalty"
            )
        if self.exit_time < self.entry_time:
            raise ValueError("exit_time must not precede entry_time")
        if isinstance(self.hold_duration_seconds, bool) or not isinstance(
            self.hold_duration_seconds, int
        ):
            raise TypeError("hold_duration_seconds must be int")
        if self.hold_duration_seconds < 0:
            raise ValueError("hold_duration_seconds must be non-negative")
        if not isinstance(self.signal_confidence, float):
            raise TypeError("signal_confidence must be float")
        if not 0.0 <= self.signal_confidence <= 1.0:
            raise ValueError("signal_confidence must be between 0 and 1")
