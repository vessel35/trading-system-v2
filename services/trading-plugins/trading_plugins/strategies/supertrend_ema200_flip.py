"""Deploy the SuperTrend(10, 3) + EMA 200 trend-permission strategy.

Source document: docs/samples_for_strategy_agent/01.SuperTrend_EMA200_Flip.md.

The document enters when the SuperTrend signal agrees with the side of the 200 EMA and exits
when the SuperTrend flips against the position. The platform hands a strategy only the
current bar's series values, so this class reads the SuperTrend *state* at the deciding bar
rather than detecting the flip bar itself: an entry happens on the first flat bar where the
state and the 200 EMA side agree, and an exit on the first held bar where the state opposes
the position. The exit is therefore the flip bar exactly; the entry differs from a flip-only
rule when the strategy is flat while the state already agrees (after a stop-out, or at the
start of a run).
"""

from __future__ import annotations

import math
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

STRATEGY_ID = "supertrend-ema200-flip"

_SUPERTREND_PARAMS = {"period": 10, "multiplier": 3.0}
_EMA_PARAMS = {"period": 200}
_UPTREND = 1.0
_DOWNTREND = -1.0


class SupertrendEma200Flip(StrategyBase):
    """Enter with the SuperTrend state on the 200 EMA's side; exit when it flips against."""

    STRATEGY_ID = STRATEGY_ID
    VERSION = "1.0.0"

    def __init__(self, config: ResolvedConfig) -> None:
        if config.strategy_id != STRATEGY_ID:
            raise ValueError(f"SupertrendEma200Flip requires strategy_id {STRATEGY_ID!r}")
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            required_indicators=[
                {"name": "SuperTrend", "params": {"period": 10, "multiplier": 3.0}},
                {"name": "EMA", "params": {"period": 200}},
            ],
            min_history=1,
            supported_timeframes=["1h", "4h"],
            profile=StrategyProfile(
                id="supertrend-ema200-flip-v1",
                family="trend",
                bar="1h",
                expected_win_rate=(0.30, 0.55),
                expected_payoff=(1.2, 3.0),
                tail_shape="right_fat",
                holding_horizon="multi_day",
                primary_metric="calmar",
                risk_adjusted_pref="sortino",
                profit_structure_to_preserve="trend-capture-with-state-exit",
                envelope_tolerance=0.20,
                envelope_status="provisional",
            ),
            money_management=MoneyManagementSupport(
                supported=("signal-exit-atr", "manual", "turtle"),
                default="signal-exit-atr",
                supports_external_stop=True,
                supports_external_take_profit=True,
                supports_signal_exit=True,
                supports_pyramiding=False,
            ),
            decision_contract=StrategyDecisionContract.DECISION_INTENT,
        )

    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        """Declare no strategy-owned parameters; the document fixes every value."""
        return ParameterSchema(fields={})

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> DecisionIntent | None:
        candle, indicators, timeframe, market_type = _inputs(market_data)
        supertrend = indicators.get(series_key_of("SuperTrend", _SUPERTREND_PARAMS, timeframe))
        if not isinstance(supertrend, Mapping):
            raise TypeError("SuperTrend series must be a mapping of named outputs")
        direction = _number(supertrend.get("direction"), "SuperTrend direction")
        ema200 = _number(indicators.get(series_key_of("EMA", _EMA_PARAMS, timeframe)), "EMA 200")
        if math.isnan(direction) or math.isnan(ema200):
            # The standard leaves the SuperTrend state undefined until its ATR exists.
            return None
        close = float(candle.close)

        if current_position is not None:
            against = (current_position.side is PositionSide.LONG and direction == _DOWNTREND) or (
                current_position.side is PositionSide.SHORT and direction == _UPTREND
            )
            if against:
                return _decision(candle, DecisionAction.EXIT, "supertrend-flipped-against-position")
            return _decision(candle, DecisionAction.HOLD, "supertrend-aligned-with-position")

        if close == ema200:
            return _decision(candle, DecisionAction.HOLD, "price-on-ema200")
        if close > ema200:
            if direction == _UPTREND:
                return _decision(candle, DecisionAction.ENTER_LONG, "supertrend-up-above-ema200")
            return _decision(candle, DecisionAction.HOLD, "supertrend-down-but-above-ema200")
        if direction == _DOWNTREND:
            if market_type is MarketType.SPOT:
                return _decision(candle, DecisionAction.HOLD, "spot-short-not-available")
            return _decision(candle, DecisionAction.ENTER_SHORT, "supertrend-down-below-ema200")
        return _decision(candle, DecisionAction.HOLD, "supertrend-up-but-below-ema200")


def _inputs(
    market_data: dict[str, object],
) -> tuple[Candle, Mapping[object, object], str, MarketType]:
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
    return candle, indicators, timeframe, MarketType(market_type_value)


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, float | int):
        raise TypeError(f"{name} must be numeric")
    return float(value)


def _decision(candle: Candle, action: DecisionAction, reason: str) -> DecisionIntent:
    return DecisionIntent(
        action=action,
        symbol=candle.symbol,
        timestamp=candle.close_time,
        reference_price=float(candle.close),
        confidence=1.0,
        reason=reason,
        metadata={"adaptee": STRATEGY_ID},
    )
