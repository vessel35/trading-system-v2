"""Wire wallet safety policy to the shared sizing and exposure standards."""

from __future__ import annotations

from collections.abc import Iterable

from core_lib.sizing import exposure_limit
from core_lib.sizing import one_r as calculate_one_r
from core_lib.types import Fill, MarketType, PositionSide

from wallet_service.core import RiskPolicy
from wallet_service.domain import PaperSignal, RiskRejected


class RiskGuard:
    """Reject unsafe paper candidates before they reach Broker.submit."""

    def __init__(self, policy: RiskPolicy) -> None:
        self._policy = policy
        self._kill_switch_engaged = policy.kill_switch_engaged

    @property
    def kill_switch_engaged(self) -> bool:
        """Return the fail-closed switch state."""
        return self._kill_switch_engaged

    def engage_kill_switch(self) -> None:
        """Engage the one-way process-local kill switch."""
        self._kill_switch_engaged = True

    def validate_signal(self, message: PaperSignal) -> None:
        """Apply mode, switch, symbol, and market-direction guards."""
        if self._kill_switch_engaged:
            raise RiskRejected("kill_switch")
        if message.mode != "paper":
            raise RiskRejected("paper_only")
        if message.signal.symbol != message.signal.symbol.upper():
            raise RiskRejected("symbol_not_canonical")
        if message.signal.symbol.upper() not in self._policy.allowed_symbols:
            raise RiskRejected("symbol_not_allowed")
        if message.signal.market_type is MarketType.SPOT and message.side is PositionSide.SHORT:
            raise RiskRejected("spot_short_not_supported")

    def validate_sized_entry(
        self,
        message: PaperSignal,
        quantity: float,
        equity: float,
        existing_risks: Iterable[tuple[str, PositionSide, float]],
    ) -> None:
        """Apply order-size, 1R, and aggregate shared exposure-limit guards."""
        if quantity > self._policy.max_order_quantity:
            raise RiskRejected("max_order_quantity")
        if quantity * message.signal.price > self._policy.max_order_notional:
            raise RiskRejected("max_order_notional")
        stop = message.signal.stop_loss
        if stop is None:
            raise RiskRejected("protective_stop_required")
        one_r = calculate_one_r(message.signal.price, stop, quantity)
        if one_r > equity * 0.01:
            raise RiskRejected("one_r_limit")

        normalized_symbol = message.signal.symbol.upper()
        side = message.side
        if side is None:
            raise RiskRejected("direction_required")
        risks = list(existing_risks)
        market_risks = [risk for symbol, _, risk in risks if symbol.upper() == normalized_symbol]
        direction_risks = [risk for _, existing_side, risk in risks if existing_side is side]
        candidate = self._policy.risk_per_trade
        checks = (
            exposure_limit.single_market(
                [*market_risks, candidate],
                self._policy.single_market_limit,
            ),
            exposure_limit.correlation_group(
                [*[risk for _, _, risk in risks], candidate],
                self._policy.correlation_group_limit,
            ),
            exposure_limit.single_direction(
                [*direction_risks, candidate],
                self._policy.single_direction_limit,
            ),
        )
        if not all(checks):
            raise RiskRejected("exposure_limit")

    def validate_simulated_entry(self, fill: Fill) -> None:
        """Recheck hard size caps against the actual simulated fill."""
        if float(fill.quantity) > self._policy.max_order_quantity:
            raise RiskRejected("max_order_quantity")
        if float(fill.price * fill.quantity) > self._policy.max_order_notional:
            raise RiskRejected("max_order_notional")
