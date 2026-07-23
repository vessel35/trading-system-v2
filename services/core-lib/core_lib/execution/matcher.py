"""Define deterministic bar-trigger and fill matching rules."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from uuid import NAMESPACE_URL, uuid5

from core_lib.costs import fee as fee_cost
from core_lib.costs import liquidation, slippage
from core_lib.ports import CostModel
from core_lib.types import (
    Candle,
    ExitReason,
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSide,
)
from core_lib.types.money import Q_AMOUNT, ZERO, quantize_amount, quantize_price

from .normalizer import to_decimal
from .position_book import PositionBook

FILL_TIMINGS = frozenset({"immediate", "next_bar"})


def _price(value: float) -> Decimal:
    return to_decimal(value, quantizer=quantize_price)


def _execution_candle(
    candle: Candle,
    history: Sequence[Candle],
    fill_timing: str,
) -> tuple[Candle, Decimal, datetime]:
    if fill_timing not in FILL_TIMINGS:
        raise ValueError(f"unsupported fill_timing: {fill_timing}")
    if fill_timing == "immediate":
        return candle, _price(candle.close), candle.close_time

    candidates = sorted(
        (
            candidate
            for candidate in history
            if candidate is not candle and candidate.open_time >= candle.close_time
        ),
        key=lambda candidate: candidate.open_time,
    )
    if not candidates:
        raise ValueError("next_bar matching requires a candle after the decision candle")
    next_candle = candidates[0]
    execution_time = max(
        next_candle.open_time,
        candle.close_time + timedelta(milliseconds=1),
    )
    return next_candle, _price(next_candle.open), execution_time


def _trigger_reference(order: Order, candle: Candle) -> tuple[Decimal, bool] | None:
    open_price = _price(candle.open)
    high = _price(candle.high)
    low = _price(candle.low)
    if order.order_type is OrderType.MARKET:
        return open_price, False

    if order.order_type is OrderType.LIMIT:
        if order.price is None:
            raise ValueError("limit order requires price")
        if order.side is OrderSide.BUY and low <= order.price:
            return min(open_price, order.price), open_price < order.price
        if order.side is OrderSide.SELL and high >= order.price:
            return max(open_price, order.price), open_price > order.price
        return None

    if order.stop_price is None:
        raise ValueError("trigger order requires stop_price")
    if order.order_type is OrderType.STOP_MARKET:
        if order.side is OrderSide.BUY and high >= order.stop_price:
            return max(open_price, order.stop_price), open_price > order.stop_price
        if order.side is OrderSide.SELL and low <= order.stop_price:
            return min(open_price, order.stop_price), open_price < order.stop_price
        return None
    if order.order_type is OrderType.TAKE_PROFIT_MARKET:
        if order.side is OrderSide.BUY and low <= order.stop_price:
            return min(open_price, order.stop_price), False
        if order.side is OrderSide.SELL and high >= order.stop_price:
            return max(open_price, order.stop_price), False
        return None
    raise NotImplementedError("trailing-stop matching is reserved")


def _fill(
    order: Order,
    reference_price: Decimal,
    quantity: Decimal,
    timestamp: datetime,
    cost_model: CostModel,
    *,
    gap_filled: bool,
    qty_truncated: bool,
    exit_reason: ExitReason | None,
) -> Fill:
    actual_price, signed_slippage = _execution_price(
        order,
        reference_price,
        quantity,
        cost_model,
        gap_filled=gap_filled,
    )
    fee = fee_cost.calc(
        quantize_amount(actual_price * quantity),
        cost_model.fee(
            order.symbol,
            quantize_amount(actual_price * quantity),
        ),
    )
    cumulative_quantity = quantize_amount(order.filled_quantity + quantity)
    previous_notional = (
        ZERO
        if order.average_filled_price is None
        else order.average_filled_price * order.filled_quantity
    )
    cumulative_average = quantize_price(
        (previous_notional + actual_price * quantity) / cumulative_quantity
    )
    order.mark_as_filled(order.quantity, cumulative_average)
    order.fee = quantize_amount(order.fee + fee)
    return Fill(
        order_id=order.id,
        symbol=order.symbol,
        side=order.side,
        position_side=order.position_side,
        reference_price=reference_price,
        price=actual_price,
        quantity=quantity,
        fee=fee,
        slippage=abs(signed_slippage),
        liquidity="taker",
        timestamp=timestamp,
        reduce_only=order.reduce_only or order.close_position,
        exit_reason=exit_reason,
        gap_filled=gap_filled,
        qty_truncated=qty_truncated,
    )


def _execution_price(
    order: Order,
    reference_price: Decimal,
    quantity: Decimal,
    cost_model: CostModel,
    *,
    gap_filled: bool,
) -> tuple[Decimal, Decimal]:
    priced_order = replace(
        order,
        quantity=quantize_amount(order.filled_quantity + quantity),
    )
    context: dict[str, object] = {
        "gap_filled": gap_filled,
        "reference_price": reference_price,
    }
    reference_notional = quantize_amount(reference_price * quantity)
    signed_slippage = slippage.apply(
        reference_notional,
        order.side,
        cost_model,
        order=priced_order,
        context=context,
    )
    actual_price = quantize_price(reference_price + signed_slippage / quantity)
    if actual_price <= ZERO:
        raise ValueError("slippage produced a non-positive execution price")
    return actual_price, signed_slippage


def _truncate_amount(value: Decimal) -> Decimal:
    """Round a quantity toward zero so a hard upper bound is never exceeded."""
    return value.quantize(Q_AMOUNT, rounding=ROUND_DOWN)


def _entry_cash_requirement(
    order: Order,
    fill_price: Decimal,
    quantity: Decimal,
    cost_model: CostModel,
    leverage: int,
    expected_cost_rate: Decimal,
) -> Decimal:
    """Return entry margin, charged fee, and the declared future-cost reserve."""
    notional = quantize_amount(fill_price * quantity)
    margin = quantize_amount(notional / Decimal(leverage))
    fee = fee_cost.calc(notional, cost_model.fee(order.symbol, notional))
    reserve = quantize_amount(notional * expected_cost_rate)
    return quantize_amount(margin + fee + reserve)


def _affordable_entry_quantity(
    order: Order,
    fill_price: Decimal,
    maximum: Decimal,
    available_margin: Decimal,
    cost_model: CostModel,
    leverage: int,
    expected_cost_rate: Decimal,
) -> Decimal:
    """Find the largest eight-decimal quantity whose margin and fee fit cash."""
    upper_units = int(_truncate_amount(maximum) / Q_AMOUNT)
    low = 0
    high = upper_units
    affordable_units = 0
    while low <= high:
        middle = (low + high) // 2
        quantity = Q_AMOUNT * middle
        requirement = (
            ZERO
            if middle == 0
            else _entry_cash_requirement(
                order,
                fill_price,
                quantity,
                cost_model,
                leverage,
                expected_cost_rate,
            )
        )
        if requirement <= available_margin:
            affordable_units = middle
            low = middle + 1
        else:
            high = middle - 1
    return Q_AMOUNT * affordable_units


def recompute_qty_and_stop(
    order: Order,
    fill_price: Decimal,
    *,
    risk_budget: Decimal | None = None,
    available_margin: Decimal | None = None,
    leverage: int = 1,
    cost_model: CostModel | None = None,
    expected_cost_rate: Decimal = ZERO,
) -> tuple[Decimal, Decimal | None]:
    """Re-anchor initial risk to the fill and truncate quantity to risk/margin."""
    if not isinstance(fill_price, Decimal) or fill_price <= ZERO:
        raise ValueError("fill_price must be a positive Decimal")
    if isinstance(leverage, bool) or not isinstance(leverage, int) or leverage <= 0:
        raise ValueError("leverage must be a positive int")
    if not isinstance(expected_cost_rate, Decimal) or expected_cost_rate < ZERO:
        raise ValueError("expected_cost_rate must be a non-negative Decimal")

    reference = order.price or fill_price
    new_stop: Decimal | None = None
    stop_distance: Decimal | None = None
    if order.stop_price is not None:
        stop_distance = abs(reference - order.stop_price)
        if stop_distance == ZERO:
            raise ValueError("initial stop distance must be positive")
        if order.position_side is PositionSide.LONG:
            new_stop = quantize_price(fill_price - stop_distance)
        elif order.position_side is PositionSide.SHORT:
            new_stop = quantize_price(fill_price + stop_distance)
        else:
            raise ValueError("entry direction is ambiguous for PositionSide.BOTH")

    quantity = order.remaining_quantity()
    if risk_budget is not None:
        if not isinstance(risk_budget, Decimal) or risk_budget <= ZERO:
            raise ValueError("risk_budget must be a positive Decimal")
        if stop_distance is None:
            raise ValueError("risk truncation requires an initial stop")
        quantity = min(quantity, quantize_amount(risk_budget / stop_distance))
    if available_margin is not None:
        if not isinstance(available_margin, Decimal) or available_margin < ZERO:
            raise ValueError("available_margin must be a non-negative Decimal")
        if cost_model is None:
            raise ValueError("margin truncation requires a CostModel")
        margin_quantity = _affordable_entry_quantity(
            order,
            fill_price,
            quantity,
            available_margin,
            cost_model,
            leverage,
            expected_cost_rate,
        )
        quantity = min(quantity, margin_quantity)
    return quantize_amount(quantity), new_stop


def match(
    order: Order,
    candle: Candle,
    history: list[Candle],
    cost_model: CostModel,
    fill_timing: str = "next_bar",
    *,
    risk_budget: Decimal | None = None,
    available_margin: Decimal | None = None,
    leverage: int = 1,
    expected_cost_rate: Decimal = ZERO,
) -> Fill:
    """Deterministically match one order at immediate close or next-bar open."""
    if order.status.is_terminal():
        raise ValueError("terminal orders cannot be matched")
    execution_candle, base_reference, timestamp = _execution_candle(
        candle,
        history,
        fill_timing,
    )
    triggered = _trigger_reference(order, execution_candle)
    if triggered is None:
        raise ValueError("order did not trigger in the execution candle")
    reference_price, gap_filled = triggered
    if order.order_type is OrderType.MARKET:
        reference_price = base_reference

    remaining = order.remaining_quantity()
    quantity = remaining
    new_stop: Decimal | None = None
    entry_margin = (
        None if order.reduce_only or order.close_position else available_margin
    )
    for _ in range(32):
        preview_price, _ = _execution_price(
            order,
            reference_price,
            quantity,
            cost_model,
            gap_filled=gap_filled,
        )
        recomputed, new_stop = recompute_qty_and_stop(
            order,
            preview_price,
            risk_budget=risk_budget,
            available_margin=entry_margin,
            leverage=leverage,
            cost_model=cost_model,
            expected_cost_rate=expected_cost_rate,
        )
        recomputed = min(quantity, recomputed)
        if recomputed == quantity:
            break
        quantity = recomputed
    else:
        raise RuntimeError("fee-aware quantity truncation did not converge")
    if quantity <= ZERO:
        raise ValueError("available risk or margin truncates the order to zero")
    qty_truncated = quantity < remaining
    if qty_truncated:
        order.quantity = quantize_amount(order.filled_quantity + quantity)
    if new_stop is not None:
        order.stop_price = new_stop
    if entry_margin is not None:
        final_price, _ = _execution_price(
            order,
            reference_price,
            quantity,
            cost_model,
            gap_filled=gap_filled,
        )
        if (
            _entry_cash_requirement(
                order,
                final_price,
                quantity,
                cost_model,
                leverage,
                expected_cost_rate,
            )
            > entry_margin
        ):
            raise RuntimeError("truncated entry still exceeds available cash")
    return _fill(
        order,
        reference_price,
        quantity,
        timestamp,
        cost_model,
        gap_filled=gap_filled,
        qty_truncated=qty_truncated,
        exit_reason=None,
    )


def _protection_reference(
    position: Position,
    candle: Candle,
    level: Decimal,
    reason: ExitReason,
) -> tuple[Decimal, bool]:
    open_price = _price(candle.open)
    if reason is ExitReason.LIQUIDATION:
        gap = (
            open_price < level
            if position.side is PositionSide.LONG
            else open_price > level
        )
        return level, gap
    if position.side is PositionSide.LONG:
        return min(level, open_price), open_price < level
    return max(level, open_price), open_price > level


def _synthetic_exit_order(
    position: Position,
    candle: Candle,
    reason: ExitReason,
) -> Order:
    side = OrderSide.SELL if position.side is PositionSide.LONG else OrderSide.BUY
    canonical = f"{position.symbol}|{candle.open_time.isoformat()}|{reason.value}"
    client_id = uuid5(NAMESPACE_URL, canonical)
    return Order(
        id=f"synthetic-{client_id}",
        wallet_id=position.wallet_id,
        signal_id=None,
        order_type=OrderType.MARKET,
        side=side,
        symbol=position.symbol,
        quantity=position.quantity,
        price=None,
        filled_quantity=quantize_amount(ZERO),
        average_filled_price=None,
        status=OrderStatus.NEW,
        fee=quantize_amount(ZERO),
        client_order_id=client_id,
        market_type=position.market_type,
        position_side=position.side,
        reduce_only=True,
        close_position=False,
        stop_price=None,
        time_in_force="GTC",
    )


def resolve_triggers(
    position: Position,
    candles: list[Candle],
    cost_model: CostModel,
    *,
    stop_price: Decimal | None = None,
    take_profit_price: Decimal | None = None,
    entry_time: datetime | None = None,
) -> Fill | None:
    """Resolve stop, take-profit, and liquidation with conservative precedence."""
    if position.side is PositionSide.BOTH:
        raise ValueError("trigger direction is ambiguous for PositionSide.BOTH")
    for candle in sorted(candles, key=lambda item: item.open_time):
        if (
            PositionBook.skip_first_sl_check
            and entry_time is not None
            and candle.open_time <= entry_time
        ):
            continue
        low = _price(candle.low)
        high = _price(candle.high)
        liquidation_level = position.liquidation_price
        if liquidation_level <= ZERO:
            liq_params = cost_model.liq_params()
            maintenance_margin_rate = liq_params.get("maintenance_margin_rate")
            if not isinstance(maintenance_margin_rate, Decimal):
                raise TypeError(
                    "liq_params.maintenance_margin_rate must be Decimal"
                )
            liquidation_level = liquidation.price(
                position.entry_price,
                position.leverage,
                maintenance_margin_rate,
                side=position.side,
            )
        liquidation_position = (
            position
            if position.liquidation_price > ZERO
            else replace(position, liquidation_price=liquidation_level)
        )
        adverse_extreme = low if position.side is PositionSide.LONG else high
        liquidation_hit = liquidation.is_triggered(
            liquidation_position,
            adverse_extreme,
        )
        stop_hit = (
            stop_price is not None
            and (
                low <= stop_price
                if position.side is PositionSide.LONG
                else high >= stop_price
            )
        )
        take_hit = (
            take_profit_price is not None
            and (
                high >= take_profit_price
                if position.side is PositionSide.LONG
                else low <= take_profit_price
            )
        )

        reason: ExitReason | None = None
        level: Decimal | None = None
        invalid_stop = (
            stop_price is not None
            and (
                stop_price < liquidation_level
                if position.side is PositionSide.LONG
                else stop_price > liquidation_level
            )
        )
        if stop_hit and liquidation_hit and invalid_stop:
            reason, level = ExitReason.LIQUIDATION, liquidation_level
        elif stop_hit:
            reason, level = ExitReason.STOP_LOSS, stop_price
        elif liquidation_hit:
            reason, level = ExitReason.LIQUIDATION, liquidation_level
        elif take_hit:
            reason, level = ExitReason.TAKE_PROFIT, take_profit_price
        if reason is None or level is None:
            continue

        reference, gap_filled = _protection_reference(
            position,
            candle,
            level,
            reason,
        )
        order = _synthetic_exit_order(position, candle, reason)
        return _fill(
            order,
            reference,
            position.quantity,
            candle.close_time,
            cost_model,
            gap_filled=gap_filled,
            qty_truncated=False,
            exit_reason=reason,
        )
    return None
