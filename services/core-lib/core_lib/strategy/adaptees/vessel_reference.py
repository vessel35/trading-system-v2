"""Provide the first stateless Vessel reference Adaptee for pipeline validation."""

from __future__ import annotations

from collections.abc import Mapping

from core_lib.types import Candle, MarketType, Position, PositionSide, TradingSignal

from ..base import StrategyMetadata
from ..config import FieldSpec, ParameterSchema, ResolvedConfig
from ..profile import StrategyProfile

STRATEGY_ID = "vessel-reference"

_FAST_EMA = "ema:period=9"
_SLOW_EMA = "ema:period=21"
_ATR = "atr:period=14"


class VesselReference:
    """Use an EMA regime with fixed ATR protection and no trailing state."""

    VERSION = "1.0.0"

    def __init__(self, config: ResolvedConfig) -> None:
        if config.strategy_id != STRATEGY_ID:
            raise ValueError(f"VesselReference requires strategy_id {STRATEGY_ID!r}")
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        """Declare the exact indicator and warm-up surface consumed by this Adaptee."""
        return StrategyMetadata(
            required_indicators=[
                {"name": "EMA", "params": {"period": 9}},
                {"name": "EMA", "params": {"period": 21}},
                {"name": "ATR", "params": {"period": 14}},
            ],
            min_history=21,
            supported_timeframes=["1h"],
            profile=StrategyProfile(
                id="vessel-reference-v1",
                family="trend",
                bar="1h",
                expected_win_rate=(0.25, 0.65),
                expected_payoff=(1.0, 4.0),
                tail_shape="right_fat",
                holding_horizon="multi_day",
                primary_metric="calmar",
                risk_adjusted_pref="sortino",
                profit_structure_to_preserve="fixed-risk-trend-capture",
                envelope_tolerance=0.20,
                envelope_status="provisional",
            ),
        )

    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        """Declare fixed-protection and leverage parameters owned by the Adaptee."""
        return ParameterSchema(
            fields={
                "atr_stop_multiple": FieldSpec(
                    type="number",
                    default=2.0,
                    range=(0.1, 10.0),
                ),
                "reward_risk": FieldSpec(
                    type="number",
                    default=2.0,
                    range=(0.1, 10.0),
                ),
                "leverage": FieldSpec(
                    type="integer",
                    default=1,
                    range=(1, 100),
                ),
            }
        )

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> TradingSignal | None:
        """Emit EMA-regime entries/exits using fixed ATR stop and target levels."""
        candle = market_data.get("candle")
        indicators = market_data.get("indicators")
        market_type_value = market_data.get("market_type")
        if not isinstance(candle, Candle):
            raise TypeError("market_data.candle must be Candle")
        if not isinstance(indicators, Mapping):
            raise TypeError("market_data.indicators must be a mapping")
        if not isinstance(market_type_value, str):
            raise TypeError("market_data.market_type must be a string")

        fast = self._indicator(indicators, _FAST_EMA)
        slow = self._indicator(indicators, _SLOW_EMA)
        atr = self._indicator(indicators, _ATR)
        market_type = MarketType(market_type_value)
        leverage = self._integer_param("leverage")

        if current_position is not None:
            should_exit = (current_position.side is PositionSide.LONG and fast <= slow) or (
                current_position.side is PositionSide.SHORT and fast >= slow
            )
            if not should_exit:
                return None
            return self._signal(
                candle,
                market_type,
                leverage,
                stop_loss=None,
                take_profit=None,
                reason="vessel-ema-regime-exit",
            )

        if fast == slow:
            return None
        is_long = fast > slow
        if market_type is MarketType.SPOT and not is_long:
            return None
        stop_distance = atr * self._number_param("atr_stop_multiple")
        reward_distance = stop_distance * self._number_param("reward_risk")
        if is_long:
            stop_loss = candle.close - stop_distance
            take_profit = candle.close + reward_distance
        else:
            stop_loss = candle.close + stop_distance
            take_profit = candle.close - reward_distance
        if stop_loss <= 0.0 or take_profit <= 0.0:
            return None
        return self._signal(
            candle,
            market_type,
            leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason="vessel-ema-regime-entry",
        )

    @staticmethod
    def _indicator(indicators: Mapping[object, object], key: str) -> float:
        value = indicators.get(key)
        if isinstance(value, bool) or not isinstance(value, float | int):
            raise TypeError(f"indicator {key!r} must be numeric")
        return float(value)

    def _number_param(self, name: str) -> float:
        value = self.config.params[name]
        if isinstance(value, bool) or not isinstance(value, float | int):
            raise TypeError(f"resolved parameter {name!r} must be numeric")
        return float(value)

    def _integer_param(self, name: str) -> int:
        value = self.config.params[name]
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"resolved parameter {name!r} must be integer")
        return value

    @staticmethod
    def _signal(
        candle: Candle,
        market_type: MarketType,
        leverage: int,
        *,
        stop_loss: float | None,
        take_profit: float | None,
        reason: str,
    ) -> TradingSignal:
        return TradingSignal(
            symbol=candle.symbol,
            timestamp=candle.close_time,
            confidence=1.0,
            price=float(candle.close),
            stop_loss=stop_loss,
            take_profit=take_profit,
            market_type=market_type,
            leverage=leverage,
            reason=reason,
            metadata={"adaptee": STRATEGY_ID, "trailing": False},
        )
