"""Deploy the Bollinger Bands + RSI mean-reversion strategy.

Source document: docs/samples_for_strategy_agent/03.BollingerRSI_MeanReversion.md.

The document enters long when price crosses below the lower band while the RSI crosses
below its oversold threshold, and exits when price crosses the middle band; shorts mirror it.
The platform hands a strategy only the current bar's series values, so this class reads the
*state* at the deciding bar: long when the close is below the lower band and the RSI is below
the threshold, exit when the close is at or beyond the middle band. While a position is open
the state reading and the cross reading coincide; they differ only when the strategy is flat
on consecutive qualifying bars, where the state reading enters on the first such bar.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from core_lib.series import series_key_of
from core_lib.strategy import (
    FieldSpec,
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

STRATEGY_ID = "bollinger-rsi-reversion"

_BOLLINGER_PARAMS = {"period": 20, "multiplier": 2.0}
_RSI_PARAMS = {"period": 14}


def _thresholds_are_ordered(params: Mapping[str, object]) -> None:
    oversold = _number(params["rsi_oversold"], "rsi_oversold")
    overbought = _number(params["rsi_overbought"], "rsi_overbought")
    if oversold >= overbought:
        raise ValueError("rsi_oversold must be below rsi_overbought")


class BollingerRsiReversion(StrategyBase):
    """Enter outside the bands with an RSI extreme; exit when price returns to the middle."""

    STRATEGY_ID = STRATEGY_ID
    VERSION = "1.0.0"

    def __init__(self, config: ResolvedConfig) -> None:
        if config.strategy_id != STRATEGY_ID:
            raise ValueError(f"BollingerRsiReversion requires strategy_id {STRATEGY_ID!r}")
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            required_indicators=[
                {"name": "Bollinger Bands", "params": {"period": 20, "multiplier": 2.0}},
                {"name": "RSI", "params": {"period": 14}},
            ],
            min_history=1,
            supported_timeframes=["1h", "4h"],
            profile=StrategyProfile(
                id="bollinger-rsi-reversion-v1",
                family="mean_reversion",
                bar="1h",
                expected_win_rate=(0.45, 0.70),
                expected_payoff=(0.6, 1.5),
                tail_shape="left_fat",
                holding_horizon="intraday",
                primary_metric="pf",
                risk_adjusted_pref="sortino",
                profit_structure_to_preserve="band-reversion-to-mean",
                envelope_tolerance=0.20,
                envelope_status="provisional",
            ),
            money_management=MoneyManagementSupport(
                supported=("signal_exit_atr", "manual", "turtle"),
                default="signal_exit_atr",
                supports_external_stop=True,
                supports_external_take_profit=True,
                supports_signal_exit=True,
                supports_pyramiding=False,
            ),
            decision_contract=StrategyDecisionContract.DECISION_INTENT,
        )

    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        """Expose the two RSI thresholds the source names but does not fix."""
        return ParameterSchema(
            fields={
                "rsi_oversold": FieldSpec(type="number", default=30.0, range=(1.0, 50.0)),
                "rsi_overbought": FieldSpec(type="number", default=70.0, range=(50.0, 99.0)),
            },
            cross_validators=(_thresholds_are_ordered,),
        )

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> DecisionIntent | None:
        candle, indicators, timeframe, market_type = _inputs(market_data)
        bands = indicators.get(series_key_of("Bollinger Bands", _BOLLINGER_PARAMS, timeframe))
        if not isinstance(bands, Mapping):
            raise TypeError("Bollinger Bands series must be a mapping of named outputs")
        upper = _number(bands.get("upper"), "Bollinger upper band")
        middle = _number(bands.get("middle"), "Bollinger middle band")
        lower = _number(bands.get("lower"), "Bollinger lower band")
        rsi = _number(indicators.get(series_key_of("RSI", _RSI_PARAMS, timeframe)), "RSI")
        if any(math.isnan(value) for value in (upper, middle, lower, rsi)):
            return None
        close = float(candle.close)
        oversold = _number(self.config.params["rsi_oversold"], "rsi_oversold")
        overbought = _number(self.config.params["rsi_overbought"], "rsi_overbought")

        if current_position is not None:
            if current_position.side is PositionSide.LONG:
                if close >= middle:
                    return _decision(candle, DecisionAction.EXIT, "bb-long-reached-middle-band")
                return _decision(candle, DecisionAction.HOLD, "bb-long-below-middle-band")
            if close <= middle:
                return _decision(candle, DecisionAction.EXIT, "bb-short-reached-middle-band")
            return _decision(candle, DecisionAction.HOLD, "bb-short-above-middle-band")

        if close < lower:
            if rsi < oversold:
                return _decision(candle, DecisionAction.ENTER_LONG, "bb-below-lower-rsi-oversold")
            return _decision(candle, DecisionAction.HOLD, "bb-below-lower-rsi-not-oversold")
        if close > upper:
            if rsi <= overbought:
                return _decision(candle, DecisionAction.HOLD, "bb-above-upper-rsi-not-overbought")
            if market_type is MarketType.SPOT:
                return _decision(candle, DecisionAction.HOLD, "spot-short-not-available")
            return _decision(candle, DecisionAction.ENTER_SHORT, "bb-above-upper-rsi-overbought")
        return _decision(candle, DecisionAction.HOLD, "bb-inside-bands")


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
