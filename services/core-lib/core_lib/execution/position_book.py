"""Define position updates, reductions, liquidation, and first-fill self-check rules."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar

from core_lib.costs.liquidation import is_triggered, price_from_margin
from core_lib.types import Fill, MarginType, MarketType, Position, PositionSide
from core_lib.types.money import ZERO, quantize_amount, quantize_price

PositionKey = tuple[str, PositionSide]


@dataclass(frozen=True, slots=True)
class FundingMarginResult:
    """The theoretical and actually collectible isolated-margin funding costs."""

    theoretical_cost: Decimal
    applied_cost: Decimal
    exhausted: bool


class PositionBook:
    """Coordinate Fill application across keyed mutable Position values."""

    skip_first_sl_check: ClassVar[bool] = True

    def __init__(self, positions: Iterable[Position] = ()) -> None:
        self._positions: dict[PositionKey, Position] = {}
        for position in positions:
            key = self._key(position.symbol, position.side)
            if key in self._positions:
                raise ValueError(f"duplicate initial position: {key}")
            self._positions[key] = position

    @staticmethod
    def _key(symbol: str, side: PositionSide) -> PositionKey:
        return symbol, PositionSide(side)

    def get(self, symbol: str, side: PositionSide) -> Position | None:
        """Return one position without exposing the mutable book mapping."""
        return self._positions.get(self._key(symbol, side))

    def apply(
        self,
        fill: Fill,
        *,
        leverage: int | None = None,
        margin_type: MarginType | None = None,
        market_type: MarketType = MarketType.FUTURES,
        liquidation_price: Decimal = ZERO,
    ) -> None:
        """Apply entry, increase, reduction, or close through one entry point."""
        key = self._key(fill.symbol, fill.position_side)
        position = self._positions.get(key)
        if fill.reduce_only:
            if position is None:
                raise KeyError(f"no position to reduce: {key}")
            self.reduce(fill)
            return

        if position is not None:
            self.weighted_average(fill)
            return

        if leverage is None or margin_type is None:
            raise ValueError(
                "leverage and margin_type are required when opening a position"
            )
        if isinstance(leverage, bool) or not isinstance(leverage, int) or leverage <= 0:
            raise ValueError("leverage must be a positive int")
        normalized_market_type = MarketType(market_type)
        normalized_margin_type = MarginType(margin_type)
        notional = quantize_amount(fill.quantity * fill.price)
        margin = (
            quantize_amount(notional / Decimal(leverage))
            if normalized_market_type is MarketType.FUTURES
            else notional
        )
        self._positions[key] = Position(
            wallet_id=None,
            symbol=fill.symbol,
            quantity=fill.quantity,
            average_price=fill.price,
            total_cost=notional,
            current_price=fill.price,
            unrealized_pnl=quantize_amount(ZERO),
            side=fill.position_side,
            market_type=normalized_market_type,
            leverage=leverage,
            margin_type=normalized_margin_type,
            margin=margin,
            entry_price=fill.price,
            mark_price=fill.price,
            liquidation_price=quantize_price(liquidation_price),
            funding_fee_total=quantize_amount(ZERO),
        )

    def weighted_average(self, fill: Fill) -> Decimal:
        """Increase an existing position and return its new weighted average."""
        key = self._key(fill.symbol, fill.position_side)
        try:
            position = self._positions[key]
        except KeyError as error:
            raise KeyError(f"no position to increase: {key}") from error
        if fill.reduce_only:
            raise ValueError("reduce-only fill cannot increase a position")
        position.add_quantity(fill.quantity, fill.price)
        added_margin = (
            fill.quantity * fill.price / Decimal(position.leverage)
            if position.market_type is MarketType.FUTURES
            else fill.quantity * fill.price
        )
        position.margin = quantize_amount(position.margin + added_margin)
        return position.average_price

    def reduce(self, fill: Fill) -> Decimal:
        """Reduce a position, remove it when flat, and return released margin."""
        if not fill.reduce_only:
            raise ValueError("position reductions require a reduce-only fill")
        key = self._key(fill.symbol, fill.position_side)
        try:
            position = self._positions[key]
        except KeyError as error:
            raise KeyError(f"no position to reduce: {key}") from error
        released_margin = position.reduce_quantity(fill.quantity)
        if position.quantity == ZERO:
            del self._positions[key]
        return released_margin

    def apply_funding(
        self,
        position: Position,
        theoretical_cost: Decimal,
        *,
        maintenance_margin_rate: Decimal,
    ) -> FundingMarginResult:
        """Apply funding to isolated margin and refresh its liquidation threshold."""
        key = self._key(position.symbol, position.side)
        if self._positions.get(key) is not position:
            raise ValueError("funding position must be the active book value")
        if position.market_type is not MarketType.FUTURES:
            raise ValueError("funding applies to futures positions only")
        if position.margin_type is not MarginType.ISOLATED:
            raise ValueError("funding margin application supports ISOLATED only")
        if not isinstance(theoretical_cost, Decimal):
            raise TypeError("theoretical_cost must be Decimal")
        normalized_cost = quantize_amount(theoretical_cost)
        applied_cost = (
            min(normalized_cost, position.margin)
            if normalized_cost > ZERO
            else normalized_cost
        )
        position.margin = quantize_amount(position.margin - applied_cost)
        if position.margin < ZERO:
            raise RuntimeError("funding must not make isolated margin negative")
        position.funding_fee_total = quantize_amount(
            position.funding_fee_total + applied_cost
        )
        position.liquidation_price = price_from_margin(
            position,
            maintenance_margin_rate,
        )
        return FundingMarginResult(
            theoretical_cost=normalized_cost,
            applied_cost=applied_cost,
            exhausted=normalized_cost > ZERO and position.margin == ZERO,
        )

    @staticmethod
    def check_liquidation(position: Position, market_price: Decimal) -> bool:
        """Delegate the one liquidation comparison to ``costs.liquidation``."""
        return is_triggered(position, market_price)
