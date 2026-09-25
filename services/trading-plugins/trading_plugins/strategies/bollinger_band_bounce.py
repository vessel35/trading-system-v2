"""Deploy the Bollinger band bounce strategy with policy-owned ATR protection.

Source document: docs/samples_for_strategy_agent/06.Bollinger_Band_Bounce.md.

The source states one rule: "Fade a touch of the lower band (long) or upper band (short),
20-period / 2 SD; 1.5x ATR stop; 1.5R target". This class owns only the entry judgement: it
enters long on the bar whose close is at or below the lower band and short on the bar whose
close is at or above the upper band, and it holds while a position is open because the source
names no exit other than the stop and the target, which the manual policy owns.

The source does not say which price "touches" the band. The close is used, which is the
stricter of the two readings (a close beyond the band implies a wick beyond it, not the
reverse) and compares like with like, because the registered bands are computed from closes.
A bar whose bands have collapsed to one price satisfies both sides of the rule at once and is
held with its own reason rather than read as either direction.

The bands are the registered ``Bollinger Bands`` series at period 20 and multiplier 2.0, the
only registered combination, pinned to technical_indicators_calc_spec.md §3.10 (SMA of closes,
population standard deviation). The ATR the stop needs belongs to the manual policy, which
requires ATR(14), the only registered ATR combination.
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

STRATEGY_ID = "bollinger-band-bounce"

# The one series the source names: "20-period / 2 SD" Bollinger Bands. The execution key is
# built from this at decision time because it carries the run's timeframe.
_BOLLINGER_NAME = "Bollinger Bands"
_BOLLINGER_PARAMS = {"period": 20, "multiplier": 2.0}


class BollingerBandBounce(StrategyBase):
    """Fade a close at or beyond a Bollinger band; the policy owns every exit."""

    STRATEGY_ID = STRATEGY_ID
    VERSION = "1.0.0"

    def __init__(self, config: ResolvedConfig) -> None:
        if config.strategy_id != STRATEGY_ID:
            raise ValueError(f"BollingerBandBounce requires strategy_id {STRATEGY_ID!r}")
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            required_indicators=[
                {"name": _BOLLINGER_NAME, "params": dict(_BOLLINGER_PARAMS)},
            ],
            # Only the deciding bar's close and this bar's band values are read.
            min_history=1,
            # The source tested hourly candles only; a band touch on another timeframe
            # would be a different strategy and is not advertised.
            supported_timeframes=["1h"],
            profile=StrategyProfile(
                id="bollinger-band-bounce-v1",
                family="mean_reversion",
                bar="1h",
                # The source reports win rates of 36.1% to 39.7% across its four markets.
                expected_win_rate=(0.30, 0.45),
                # Implied by the reported profit factors and win rates (0.5 to 1.3); the
                # upper bound is the 1.5R target the rule fixes, the ceiling before costs.
                expected_payoff=(0.5, 1.5),
                tail_shape="symmetric",
                holding_horizon="intraday",
                primary_metric="pf",
                risk_adjusted_pref="sortino",
                profit_structure_to_preserve="band-touch-fade-with-fixed-target",
                envelope_tolerance=0.20,
                envelope_status="provisional",
            ),
            money_management=MoneyManagementSupport(
                supported=("manual",),
                default="manual",
                # The document fixes the protection: stop 1.5 x ATR, target 1.5R. A run
                # submitted without settings and the screen's first values use these.
                default_settings={"manual": {"atr_stop_multiple": 1.5, "reward_risk": 1.5}},
                supports_external_stop=True,
                supports_external_take_profit=True,
                supports_signal_exit=False,
                supports_pyramiding=False,
            ),
            decision_contract=StrategyDecisionContract.DECISION_INTENT,
        )

    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        """Declare no strategy-owned parameters; the source fixes the bands at 20 and 2 SD."""
        return ParameterSchema(fields={})

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> DecisionIntent | None:
        candle, indicators, timeframe, market_type = _inputs(market_data)

        if current_position is not None:
            return _decision(candle, DecisionAction.HOLD, "bounce-protection-owns-exit")

        bands = indicators.get(series_key_of(_BOLLINGER_NAME, _BOLLINGER_PARAMS, timeframe))
        if not isinstance(bands, Mapping):
            raise TypeError("Bollinger Bands series must be a mapping of named outputs")
        upper = _band(bands.get("upper"), "upper")
        lower = _band(bands.get("lower"), "lower")
        close = float(candle.close)

        touched_lower = close <= lower
        touched_upper = close >= upper
        if touched_lower and touched_upper:
            # Both sides of the rule hold only when the bands have collapsed to one price;
            # the source gives no way to read that bar as either direction.
            return _decision(candle, DecisionAction.HOLD, "bounce-band-width-zero")
        if touched_lower:
            return _decision(candle, DecisionAction.ENTER_LONG, "bounce-lower-band-touch-long")
        if touched_upper:
            if market_type is MarketType.SPOT:
                return _decision(candle, DecisionAction.HOLD, "spot-short-not-available")
            return _decision(candle, DecisionAction.ENTER_SHORT, "bounce-upper-band-touch-short")
        return _decision(candle, DecisionAction.HOLD, "bounce-inside-bands")


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


def _band(value: object, name: str) -> float:
    # The upper and lower bands are defined on every bar after warm-up (§3.10 names no
    # undefined case for them), so a missing or non-finite value is an invariant failure,
    # not a bar the strategy may skip.
    if isinstance(value, bool) or not isinstance(value, float | int):
        raise TypeError(f"Bollinger {name} band must be numeric")
    band = float(value)
    if not math.isfinite(band):
        raise ValueError(f"Bollinger {name} band must be finite after warm-up")
    return band


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
