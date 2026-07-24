"""Define valid order lifecycle transitions."""

from core_lib.types import Order, OrderStatus


def can_transition(current: OrderStatus, target: OrderStatus) -> bool:
    """Consume, without copying, the transition table owned by ``types.Order``."""
    normalized_current = OrderStatus(current)
    normalized_target = OrderStatus(target)
    return normalized_target in Order.VALID_TRANSITIONS[normalized_current]
