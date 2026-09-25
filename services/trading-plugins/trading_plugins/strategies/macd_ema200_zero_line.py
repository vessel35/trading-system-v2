"""Deploy the MACD + EMA 200 zero-line strategy with protection-only exits.

Source document: docs/samples_for_strategy_agent/02.MACD_EMA200_ZeroLine.md.

The document enters long when the MACD line crosses above its signal line while below zero
and price is above the 200 EMA, and short on the mirror image; exits are the policy's stop
and target only. The platform hands a strategy only the current bar's series values, so this
class reads the MACD *state* at the deciding bar: long when the MACD line is above the signal
line and still below zero on the 200 EMA's upper side. On a bar where the strategy is flat
that state first holds on the cross bar itself; the reading differs from a cross-only rule
when the strategy returns to flat while the state persists (after a stop or target fill).
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
)

STRATEGY_ID = "macd-ema200-zero-line"

_MACD_PARAMS = {"fast_period": 12, "slow_period": 26, "signal_period": 9}
_EMA_PARAMS = {"period": 200}


class MacdEma200ZeroLine(StrategyBase):
    """Enter on a MACD/signal state on the correct side of zero; the policy owns every exit."""

    STRATEGY_ID = STRATEGY_ID
    VERSION = "1.0.0"

    def __init__(self, config: ResolvedConfig) -> None:
        if config.strategy_id != STRATEGY_ID:
            raise ValueError(f"MacdEma200ZeroLine requires strategy_id {STRATEGY_ID!r}")
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            required_indicators=[
                {
                    "name": "MACD",
                    "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
                },
                {"name": "EMA", "params": {"period": 200}},
            ],
            min_history=1,
            supported_timeframes=["1h", "4h"],
            profile=StrategyProfile(
                id="macd-ema200-zero-line-v1",
                family="trend",
                bar="1h",
                expected_win_rate=(0.35, 0.60),
                expected_payoff=(1.0, 2.0),
                tail_shape="symmetric",
                holding_horizon="multi_day",
                primary_metric="pf",
                risk_adjusted_pref="sharpe",
                profit_structure_to_preserve="pullback-entry-with-fixed-target",
                envelope_tolerance=0.20,
                envelope_status="provisional",
            ),
            money_management=MoneyManagementSupport(
                supported=("manual",),
                default="manual",
                # The document fixes the protection: stop 2.5 x ATR, target 3.75 ATR, which
                # is 1.5 times the stop distance. A run submitted without settings and the
                # screen's first values use these.
                default_settings={"manual": {"atr_stop_multiple": 2.5, "reward_risk": 1.5}},
                supports_external_stop=True,
                supports_external_take_profit=True,
                supports_signal_exit=False,
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
        macd_value = indicators.get(series_key_of("MACD", _MACD_PARAMS, timeframe))
        if not isinstance(macd_value, Mapping):
            raise TypeError("MACD series must be a mapping of named outputs")
        macd_line = _number(macd_value.get("macd"), "MACD line")
        signal_line = _number(macd_value.get("signal"), "MACD signal")
        ema200 = _number(indicators.get(series_key_of("EMA", _EMA_PARAMS, timeframe)), "EMA 200")
        if math.isnan(macd_line) or math.isnan(signal_line) or math.isnan(ema200):
            # The standard defines the signal line only once enough MACD values exist.
            return None
        close = float(candle.close)

        if current_position is not None:
            return _decision(candle, DecisionAction.HOLD, "macd-protection-owns-exit")

        if close == ema200:
            return _decision(candle, DecisionAction.HOLD, "price-on-ema200")
        if close > ema200:
            if macd_line <= signal_line:
                return _decision(candle, DecisionAction.HOLD, "macd-below-signal-in-uptrend")
            if macd_line >= 0.0:
                return _decision(candle, DecisionAction.HOLD, "macd-cross-not-below-zero")
            return _decision(
                candle, DecisionAction.ENTER_LONG, "macd-bullish-below-zero-above-ema200"
            )
        if macd_line >= signal_line:
            return _decision(candle, DecisionAction.HOLD, "macd-above-signal-in-downtrend")
        if macd_line <= 0.0:
            return _decision(candle, DecisionAction.HOLD, "macd-cross-not-above-zero")
        if market_type is MarketType.SPOT:
            return _decision(candle, DecisionAction.HOLD, "spot-short-not-available")
        return _decision(candle, DecisionAction.ENTER_SHORT, "macd-bearish-above-zero-below-ema200")


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
