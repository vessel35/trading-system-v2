"""Define the single shared float-to-Decimal quantization gateway."""

from collections.abc import Callable
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from core_lib.types import Order, OrderRequest, OrderStatus
from core_lib.types.money import ZERO, quantize_amount, quantize_price

Quantizer = Callable[[Decimal], Decimal]


def to_decimal(
    value: float,
    *,
    quantizer: Quantizer = quantize_amount,
) -> Decimal:
    """Convert through ``str`` exactly once, then apply the shared quantizer."""
    if not isinstance(value, float):
        raise TypeError("normalizer accepts float values only")
    return quantizer(Decimal(str(value)))


def normalize_order(
    request: OrderRequest,
    *,
    order_id: str | None = None,
    client_order_id: UUID | None = None,
    wallet_id: str | None = None,
    signal_id: str | None = None,
) -> Order:
    """Normalize a float OrderRequest into a deterministic NEW Decimal Order."""
    canonical = "|".join(
        (
            request.symbol,
            request.side.value,
            request.order_type.value,
            str(request.quantity),
            str(request.price),
            str(request.stop_price),
            request.market_type.value,
            request.position_side.value,
            str(request.reduce_only),
            str(request.close_position),
            request.time_in_force,
        )
    )
    normalized_client_id = client_order_id or uuid5(NAMESPACE_URL, canonical)
    normalized_order_id = order_id or str(normalized_client_id)
    return Order(
        id=normalized_order_id,
        wallet_id=wallet_id,
        signal_id=signal_id,
        order_type=request.order_type,
        side=request.side,
        symbol=request.symbol,
        quantity=to_decimal(request.quantity),
        price=(
            None if request.price is None else to_decimal(request.price, quantizer=quantize_price)
        ),
        filled_quantity=quantize_amount(ZERO),
        average_filled_price=None,
        status=OrderStatus.NEW,
        fee=quantize_amount(ZERO),
        client_order_id=normalized_client_id,
        market_type=request.market_type,
        position_side=request.position_side,
        reduce_only=request.reduce_only,
        close_position=request.close_position,
        stop_price=(
            None
            if request.stop_price is None
            else to_decimal(request.stop_price, quantizer=quantize_price)
        ),
        time_in_force=request.time_in_force,
    )
