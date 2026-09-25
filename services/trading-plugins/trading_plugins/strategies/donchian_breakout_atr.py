"""Deploy the Donchian 20-bar breakout strategy with policy-owned ATR protection.

Source document: docs/samples_for_strategy_agent/04.Donchian_Breakout_ATR.md.

The document enters long on the bar whose close exceeds the highest high of the prior
twenty bars and short on the bar whose close falls below their lowest low, counts a breakout
once (on the bar that leaves the channel, not on every bar that stays outside), and exits
only through the policy's stop and target. The channel is read from ``candles`` rather than
from the registered Donchian series, because that series includes the deciding bar in its
own window while the document's channel is the *prior* twenty bars. Reading candles also
makes the once-only rule exact: the previous bar's close is compared with its own prior
window, which a registered series could not provide (its earlier value never arrives).
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

STRATEGY_ID = "donchian-breakout-atr"

_CHANNEL_BARS = 20
# The deciding bar, the twenty bars before it, and one more bar so the previous bar's own
# prior window is complete: that is what the once-only rule reads.
_BARS_READ = _CHANNEL_BARS + 2


class DonchianBreakoutAtr(StrategyBase):
    """Enter on a fresh close beyond the prior 20-bar channel; the policy owns every exit."""

    STRATEGY_ID = STRATEGY_ID
    VERSION = "1.0.0"

    def __init__(self, config: ResolvedConfig) -> None:
        if config.strategy_id != STRATEGY_ID:
            raise ValueError(f"DonchianBreakoutAtr requires strategy_id {STRATEGY_ID!r}")
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            required_indicators=[],
            min_history=_BARS_READ - 1,
            # The source tested hourly candles only; a 20-bar channel on another timeframe
            # would be a different strategy and is not advertised.
            supported_timeframes=["1h"],
            profile=StrategyProfile(
                id="donchian-breakout-atr-v1",
                family="breakout",
                bar="1h",
                expected_win_rate=(0.25, 0.45),
                expected_payoff=(1.5, 2.5),
                tail_shape="right_fat",
                holding_horizon="multi_day",
                primary_metric="pf",
                risk_adjusted_pref="calmar",
                profit_structure_to_preserve="channel-breakout-with-fixed-target",
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
        """Declare no strategy-owned parameters; the document fixes the channel at 20 bars."""
        return ParameterSchema(fields={})

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> DecisionIntent | None:
        candle, candles, market_type = _inputs(market_data)

        if current_position is not None:
            return _decision(candle, DecisionAction.HOLD, "donchian-protection-owns-exit")
        if len(candles) < _BARS_READ:
            return _decision(candle, DecisionAction.HOLD, "donchian-history-short")

        window = candles[-_CHANNEL_BARS - 1 : -1]
        previous_window = candles[-_CHANNEL_BARS - 2 : -2]
        previous = candles[-2]
        upper = max(bar.high for bar in window)
        lower = min(bar.low for bar in window)
        previous_upper = max(bar.high for bar in previous_window)
        previous_lower = min(bar.low for bar in previous_window)
        close = float(candle.close)

        if close > upper:
            if float(previous.close) > previous_upper:
                return _decision(candle, DecisionAction.HOLD, "donchian-already-above-channel")
            return _decision(candle, DecisionAction.ENTER_LONG, "donchian-upper-breakout")
        if close < lower:
            if float(previous.close) < previous_lower:
                return _decision(candle, DecisionAction.HOLD, "donchian-already-below-channel")
            if market_type is MarketType.SPOT:
                return _decision(candle, DecisionAction.HOLD, "spot-short-not-available")
            return _decision(candle, DecisionAction.ENTER_SHORT, "donchian-lower-breakout")
        return _decision(candle, DecisionAction.HOLD, "donchian-inside-channel")


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
