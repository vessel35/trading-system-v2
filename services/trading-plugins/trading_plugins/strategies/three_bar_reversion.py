"""Deploy the three-bar mean-reversion strategy with policy-owned ATR protection.

Source document: docs/samples_for_strategy_agent/05.Three_Bar_Reversion.md.

The source states one rule: "Buy after 3 consecutive red candles, sell short after 3 green;
1.5x ATR stop; 1.5R target". This class owns only the entry judgement: it enters long on the
bar that completes three consecutive red candles and short on the bar that completes three
consecutive green candles, and it holds while a position is open because the source names no
exit other than the stop and the target, which the manual policy owns.

A red candle is one whose close is below its open, a green one whose close is above its open;
a bar whose close equals its open is neither and breaks the streak. The three colours are read
from the raw candles, which the authoring contract allows without a series declaration. The
registered ``pat_three_black_crows`` and ``pat_three_white_soldiers`` are not used: they are
TA-Lib definitions with shadow, body and open-position conditions the source does not state.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

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

STRATEGY_ID = "three-bar-reversion"

# The deciding bar and the two bars before it: the three consecutive candles the rule counts.
_STREAK_BARS = 3


class ThreeBarReversion(StrategyBase):
    """Enter against a three-candle colour streak; the policy owns every exit."""

    STRATEGY_ID = STRATEGY_ID
    VERSION = "1.0.0"

    def __init__(self, config: ResolvedConfig) -> None:
        if config.strategy_id != STRATEGY_ID:
            raise ValueError(f"ThreeBarReversion requires strategy_id {STRATEGY_ID!r}")
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            required_indicators=[],
            min_history=_STREAK_BARS,
            # The source tested hourly candles only; three bars on another timeframe would
            # be a different strategy and is not advertised.
            supported_timeframes=["1h"],
            profile=StrategyProfile(
                id="three-bar-reversion-v1",
                family="mean_reversion",
                bar="1h",
                expected_win_rate=(0.30, 0.50),
                expected_payoff=(1.0, 1.5),
                tail_shape="symmetric",
                holding_horizon="intraday",
                primary_metric="pf",
                risk_adjusted_pref="sortino",
                profit_structure_to_preserve="three-bar-reversion-with-fixed-target",
                envelope_tolerance=0.20,
                envelope_status="provisional",
            ),
            money_management=MoneyManagementSupport(
                supported=("manual",),
                default="manual",
                supports_external_stop=True,
                supports_external_take_profit=True,
                supports_signal_exit=False,
                supports_pyramiding=False,
            ),
            decision_contract=StrategyDecisionContract.DECISION_INTENT,
        )

    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        """Declare no strategy-owned parameters; the source fixes the streak at three bars."""
        return ParameterSchema(fields={})

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> DecisionIntent | None:
        candle, candles, market_type = _inputs(market_data)

        if current_position is not None:
            return _decision(candle, DecisionAction.HOLD, "three-bar-protection-owns-exit")
        if len(candles) < _STREAK_BARS:
            return _decision(candle, DecisionAction.HOLD, "three-bar-history-short")

        streak = candles[-_STREAK_BARS:]
        if any(float(bar.close) == float(bar.open) for bar in streak):
            return _decision(candle, DecisionAction.HOLD, "three-bar-doji-breaks-streak")
        if all(float(bar.close) < float(bar.open) for bar in streak):
            return _decision(candle, DecisionAction.ENTER_LONG, "three-red-bars-buy")
        if all(float(bar.close) > float(bar.open) for bar in streak):
            if market_type is MarketType.SPOT:
                return _decision(candle, DecisionAction.HOLD, "spot-short-not-available")
            return _decision(candle, DecisionAction.ENTER_SHORT, "three-green-bars-sell-short")
        return _decision(candle, DecisionAction.HOLD, "three-bar-no-streak")


def _inputs(market_data: dict[str, object]) -> tuple[Candle, Sequence[Candle], MarketType]:
    candle = market_data.get("candle")
    candles = market_data.get("candles")
    market_type_value = market_data.get("market_type")
    if not isinstance(candle, Candle):
        raise TypeError("market_data.candle must be Candle")
    if not isinstance(candles, Sequence) or isinstance(candles, str | bytes):
        raise TypeError("market_data.candles must be a sequence of Candle")
    if not all(isinstance(item, Candle) for item in candles):
        raise TypeError("market_data.candles must hold only Candle values")
    if not isinstance(market_type_value, str):
        raise TypeError("market_data.market_type must be a string")
    indicators = market_data.get("indicators")
    if not isinstance(indicators, Mapping):
        raise TypeError("market_data.indicators must be a mapping")
    return candle, candles, MarketType(market_type_value)


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
