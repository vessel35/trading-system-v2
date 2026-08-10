"""Provide the first stateless Vessel reference Adaptee for pipeline validation."""

from __future__ import annotations

from collections.abc import Mapping

from core_lib.series import series_key_of
from core_lib.strategy import (
    MoneyManagementSupport,
    ParameterSchema,
    ResolvedConfig,
    StrategyBase,
    StrategyDecisionContract,
    StrategyMetadata,
    StrategyProfile,
)
from core_lib.types import (
    Candle,
    DecisionAction,
    DecisionIntent,
    MarketType,
    Position,
    PositionSide,
)

STRATEGY_ID = "vessel-reference"

_FAST_EMA_PARAMS = {"period": 9}
_SLOW_EMA_PARAMS = {"period": 21}


class VesselReference(StrategyBase):
    """Own only the EMA entry/exit edge; runtime policies own money management."""

    STRATEGY_ID = STRATEGY_ID
    VERSION = "3.1.0"

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
            ],
            min_history=1,
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
            money_management=MoneyManagementSupport(
                supported=("manual", "turtle"),
                default="manual",
                supports_external_stop=True,
                supports_external_take_profit=True,
                supports_signal_exit=True,
                supports_pyramiding=False,
            ),
            decision_contract=StrategyDecisionContract.DECISION_INTENT,
        )

    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        """Declare that this strategy has no strategy-owned parameters."""
        return ParameterSchema(fields={})

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> DecisionIntent:
        """Emit explicit EMA-regime entry and exit decisions without sizing fields."""
        candle = market_data.get("candle")
        indicators = market_data.get("indicators")
        timeframe = market_data.get("timeframe")
        market_type_value = market_data.get("market_type")
        if not isinstance(candle, Candle):
            raise TypeError("market_data.candle must be Candle")
        if not isinstance(indicators, Mapping):
            raise TypeError("market_data.indicators must be a mapping")
        if not isinstance(timeframe, str):
            raise TypeError("market_data.timeframe must be a string")
        if not isinstance(market_type_value, str):
            raise TypeError("market_data.market_type must be a string")

        fast = self._indicator(
            indicators,
            series_key_of("EMA", _FAST_EMA_PARAMS, timeframe),
        )
        slow = self._indicator(
            indicators,
            series_key_of("EMA", _SLOW_EMA_PARAMS, timeframe),
        )
        market_type = MarketType(market_type_value)

        if current_position is not None:
            should_exit = (current_position.side is PositionSide.LONG and fast <= slow) or (
                current_position.side is PositionSide.SHORT and fast >= slow
            )
            if not should_exit:
                return self._decision(
                    candle,
                    DecisionAction.HOLD,
                    reason="vessel-ema-regime-intact",
                )
            return self._decision(
                candle,
                DecisionAction.EXIT,
                reason="vessel-ema-regime-exit",
            )

        if fast == slow:
            return self._decision(
                candle,
                DecisionAction.HOLD,
                reason="vessel-ema-regime-flat",
            )
        is_long = fast > slow
        if market_type is MarketType.SPOT and not is_long:
            return self._decision(
                candle,
                DecisionAction.HOLD,
                reason="vessel-spot-short-not-available",
            )
        return self._decision(
            candle,
            DecisionAction.ENTER_LONG if is_long else DecisionAction.ENTER_SHORT,
            reason="vessel-ema-regime-entry",
        )

    @staticmethod
    def _indicator(indicators: Mapping[object, object], key: str) -> float:
        value = indicators.get(key)
        if isinstance(value, bool) or not isinstance(value, float | int):
            raise TypeError(f"indicator {key!r} must be numeric")
        return float(value)

    @staticmethod
    def _decision(
        candle: Candle,
        action: DecisionAction,
        *,
        reason: str,
    ) -> DecisionIntent:
        return DecisionIntent(
            action=action,
            symbol=candle.symbol,
            timestamp=candle.close_time,
            reference_price=float(candle.close),
            confidence=1.0,
            reason=reason,
            metadata={"adaptee": STRATEGY_ID},
        )
