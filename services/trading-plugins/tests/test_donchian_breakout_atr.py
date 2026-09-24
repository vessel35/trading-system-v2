"""Verify the Donchian 20-bar breakout strategy against its source document's rules."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from core_lib.strategy import (
    StrategyAdapter,
    StrategyConfig,
    StrategyDecisionContract,
    catalog_declaration_mismatch,
)
from core_lib.types import (
    Candle,
    DecisionAction,
    DecisionIntent,
    MarginType,
    MarketType,
    Position,
    PositionSide,
)
from trading_plugins.strategies.donchian_breakout_atr import STRATEGY_ID, DonchianBreakoutAtr

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_REGISTRATION_FILE = (
    _REPOSITORY_ROOT / "init-scripts/signal-service/20260923/05-register-donchian-breakout-atr.sql"
)
_START = datetime(2026, 1, 1, tzinfo=UTC)


def _candle(index: int, *, high: float, low: float, close: float) -> Candle:
    opened = _START + timedelta(hours=index)
    return Candle(
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="1h",
        open_time=opened,
        close_time=opened + timedelta(hours=1),
        open=close,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        quote_volume=10_000.0,
        trade_count=100,
    )


def _channel(count: int = 22) -> list[Candle]:
    """Return ``count`` bars ranging 90..110 so the prior-20 channel is 90 to 110."""
    return [_candle(i, high=110.0, low=90.0, close=100.0) for i in range(count)]


def _market(candles: list[Candle], market_type: str = "futures") -> dict[str, object]:
    return {
        "candles": candles,
        "candle": candles[-1],
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "market_type": market_type,
        "indicators": {"atr:period=14@1h": 2.0},
    }


def _strategy() -> DonchianBreakoutAtr:
    resolved = StrategyConfig.resolve(
        DonchianBreakoutAtr.get_parameter_schema(),
        {"strategy_id": STRATEGY_ID, "params": {}},
    )
    return DonchianBreakoutAtr(resolved)


def _position(side: PositionSide) -> Position:
    return Position(
        wallet_id=None,
        symbol="BTCUSDT",
        quantity=Decimal("1"),
        average_price=Decimal("100"),
        total_cost=Decimal("100"),
        current_price=Decimal("100"),
        unrealized_pnl=Decimal("0"),
        side=side,
        market_type=MarketType.FUTURES,
        leverage=1,
        margin_type=MarginType.ISOLATED,
        margin=Decimal("100"),
        entry_price=Decimal("100"),
        mark_price=Decimal("100"),
        liquidation_price=Decimal("0"),
        funding_fee_total=Decimal("0"),
    )


def test_donchian_declares_no_series_and_reads_twenty_one_bars_back() -> None:
    strategy = _strategy()
    assert isinstance(strategy, StrategyAdapter)
    metadata = strategy.get_metadata()
    assert metadata.required_indicators == []
    assert metadata.min_history == 21
    assert metadata.decision_contract is StrategyDecisionContract.DECISION_INTENT
    assert metadata.money_management.supported == ("manual",)
    assert metadata.money_management.supports_signal_exit is False
    assert metadata.money_management.supports_external_take_profit is True
    assert strategy.get_parameter_schema().fields == {}


def test_a_fresh_close_above_the_prior_twenty_high_enters_long() -> None:
    candles = _channel()
    candles[-1] = _candle(21, high=112.0, low=100.0, close=111.0)
    decision = _strategy().analyze(_market(candles), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.ENTER_LONG
    assert decision.reason == "donchian-upper-breakout"
    assert decision.reference_price == 111.0
    assert decision.metadata == {"adaptee": STRATEGY_ID}
    assert not hasattr(decision, "stop_loss")


def test_a_fresh_close_below_the_prior_twenty_low_enters_short() -> None:
    candles = _channel()
    candles[-1] = _candle(21, high=100.0, low=88.0, close=89.0)
    decision = _strategy().analyze(_market(candles), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.ENTER_SHORT
    assert decision.reason == "donchian-lower-breakout"


def test_the_deciding_bar_is_not_part_of_its_own_channel() -> None:
    # A close of 111 is above the prior-20 high of 110 even though this bar's high is 115.
    candles = _channel()
    candles[-1] = _candle(21, high=115.0, low=100.0, close=111.0)
    decision = _strategy().analyze(_market(candles), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.ENTER_LONG


def test_a_breakout_fires_once_and_not_on_every_bar_that_stays_outside() -> None:
    # The previous bar already closed above its own prior-20 high, so this bar is not fresh.
    candles = _channel()
    candles[-2] = _candle(20, high=112.0, low=100.0, close=111.0)
    candles[-1] = _candle(21, high=114.0, low=110.0, close=113.0)
    decision = _strategy().analyze(_market(candles), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.HOLD
    assert decision.reason == "donchian-already-above-channel"


def test_the_previous_bars_channel_is_its_own_prior_window() -> None:
    # The previous bar closed at 111 but its own prior window reached 111, so it was not a
    # breakout; this bar's close of 113 above the prior-20 high of 111 is therefore fresh.
    candles = _channel()
    candles[0] = _candle(0, high=111.0, low=90.0, close=100.0)
    candles[-2] = _candle(20, high=111.0, low=100.0, close=111.0)
    candles[-1] = _candle(21, high=114.0, low=110.0, close=113.0)
    decision = _strategy().analyze(_market(candles), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.ENTER_LONG


@pytest.mark.parametrize(
    ("close", "reason"),
    [(110.0, "donchian-inside-channel"), (90.0, "donchian-inside-channel")],
)
def test_a_close_on_the_channel_edge_does_not_enter(close: float, reason: str) -> None:
    candles = _channel()
    candles[-1] = _candle(21, high=110.0, low=90.0, close=close)
    decision = _strategy().analyze(_market(candles), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.HOLD
    assert decision.reason == reason


def test_a_spot_short_breakout_is_held_with_a_reason() -> None:
    candles = _channel()
    candles[-1] = _candle(21, high=100.0, low=88.0, close=89.0)
    decision = _strategy().analyze(_market(candles, "spot"), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.HOLD
    assert decision.reason == "spot-short-not-available"


@pytest.mark.parametrize("side", [PositionSide.LONG, PositionSide.SHORT])
def test_an_open_position_is_left_to_the_policy(side: PositionSide) -> None:
    candles = _channel()
    candles[-1] = _candle(21, high=112.0, low=100.0, close=111.0)
    decision = _strategy().analyze(_market(candles), _position(side))
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.HOLD
    assert decision.reason == "donchian-protection-owns-exit"


def test_too_little_history_is_held_rather_than_misjudged() -> None:
    candles = _channel(count=21)
    candles[-1] = _candle(20, high=112.0, low=100.0, close=111.0)
    decision = _strategy().analyze(_market(candles), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.HOLD
    assert decision.reason == "donchian-history-short"


def test_the_strategy_is_deterministic_and_reads_no_series() -> None:
    candles = _channel()
    candles[-1] = _candle(21, high=112.0, low=100.0, close=111.0)
    market = _market(candles)
    assert _strategy().analyze(market, None) == _strategy().analyze(market, None)
    without_series = {**market, "indicators": {}}
    assert _strategy().analyze(without_series, None) == _strategy().analyze(market, None)


def test_registration_script_matches_the_code_declaration() -> None:
    sql = _REGISTRATION_FILE.read_text()
    values = re.search(
        r"'(?P<version>\d+\.\d+\.\d+)',\s*"
        r"ARRAY\[(?P<timeframes>[^\]]+)\]::text\[\],\s*"
        r"'(?P<indicators>\[.*?\])'::jsonb,\s*"
        r"(?P<min_history>\d+),\s*"
        r"'(?P<defaults>\{.*?\})'::jsonb,",
        sql,
        re.DOTALL,
    )
    assert values is not None
    row = {
        "min_history": int(values["min_history"]),
        "supported_timeframes": [
            item.strip().strip("'") for item in values["timeframes"].split(",")
        ],
        "required_indicators_json": json.loads(values["indicators"]),
    }
    metadata = DonchianBreakoutAtr.get_metadata()
    assert values["version"] == DonchianBreakoutAtr.VERSION
    assert json.loads(values["defaults"]) == {}
    assert catalog_declaration_mismatch(row, metadata) is None
    assert catalog_declaration_mismatch({**row, "min_history": 20}, metadata) is not None
