"""Enforce confirmed-candle indicator contracts."""

from collections.abc import Sequence
from datetime import datetime

from core_lib.types import Candle


class UnfinalizedCandleError(ValueError):
    """Raised when a future or still-open candle reaches an indicator."""


def assert_finalized(candle: Candle, decision_time: datetime) -> None:
    """Require the candle to have closed by the strategy decision time."""
    if candle.close_time > decision_time:
        raise UnfinalizedCandleError(
            f"candle closes at {candle.close_time.isoformat()}, "
            f"after decision time {decision_time.isoformat()}"
        )


def drop_unfinalized(candles: Sequence[Candle], decision_time: datetime) -> list[Candle]:
    """Return only candles closed no later than the decision time."""
    return [candle for candle in candles if candle.close_time <= decision_time]
