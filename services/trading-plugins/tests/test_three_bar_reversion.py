"""Verify the three-bar mean-reversion strategy against its source document's one rule."""

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
from trading_plugins.strategies.three_bar_reversion import STRATEGY_ID, ThreeBarReversion

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_REGISTRATION_FILE = (
    _REPOSITORY_ROOT / "init-scripts/signal-service/20260923/06-register-three-bar-reversion.sql"
)
_START = datetime(2026, 1, 1, tzinfo=UTC)
_FORBIDDEN_PARAMETER_NAMES = {
    "leverage",
    "reward_risk",
    "atr_stop_multiple",
    "risk_per_trade",
    "position_size_pct",
    "margin",
    "quantity",
}


def _candle(index: int, *, open_price: float, close: float) -> Candle:
    opened = _START + timedelta(hours=index)
    return Candle(
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="1h",
        open_time=opened,
        close_time=opened + timedelta(hours=1),
        open=open_price,
        high=max(open_price, close) + 1.0,
        low=min(open_price, close) - 1.0,
        close=close,
        volume=100.0,
        quote_volume=10_000.0,
        trade_count=100,
    )


def _red(index: int) -> Candle:
    return _candle(index, open_price=101.0, close=100.0)


def _green(index: int) -> Candle:
    return _candle(index, open_price=100.0, close=101.0)


def _doji(index: int) -> Candle:
    return _candle(index, open_price=100.0, close=100.0)


def _market(candles: list[Candle], market_type: str = "futures") -> dict[str, object]:
    return {
        "candles": candles,
        "candle": candles[-1],
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "market_type": market_type,
        "indicators": {"atr:period=14@1h": 2.0},
    }


def _strategy() -> ThreeBarReversion:
    resolved = StrategyConfig.resolve(
        ThreeBarReversion.get_parameter_schema(),
        {"strategy_id": STRATEGY_ID, "params": {}},
    )
    return ThreeBarReversion(resolved)


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


def test_three_bar_declares_no_series_and_reads_three_bars_back() -> None:
    strategy = _strategy()
    assert isinstance(strategy, StrategyAdapter)
    metadata = strategy.get_metadata()
    assert metadata.required_indicators == []
    assert metadata.min_history == 3
    assert metadata.supported_timeframes == ["1h"]
    assert metadata.decision_contract is StrategyDecisionContract.DECISION_INTENT
    assert metadata.money_management.supported == ("manual",)
    assert metadata.money_management.default == "manual"
    assert metadata.money_management.supports_signal_exit is False
    assert metadata.money_management.supports_external_stop is True
    assert metadata.money_management.supports_external_take_profit is True
    assert metadata.money_management.supports_pyramiding is False
    assert strategy.get_parameter_schema().fields == {}
    assert _FORBIDDEN_PARAMETER_NAMES.isdisjoint(strategy.get_parameter_schema().fields)


def test_three_consecutive_red_candles_enter_long() -> None:
    candles = [_green(0), _red(1), _red(2), _red(3)]
    decision = _strategy().analyze(_market(candles), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.ENTER_LONG
    assert decision.reason == "three-red-bars-buy"
    assert decision.reference_price == 100.0
    assert decision.timestamp == candles[-1].close_time
    assert decision.metadata == {"adaptee": STRATEGY_ID}
    assert not hasattr(decision, "stop_loss")


def test_three_consecutive_green_candles_enter_short() -> None:
    candles = [_red(0), _green(1), _green(2), _green(3)]
    decision = _strategy().analyze(_market(candles), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.ENTER_SHORT
    assert decision.reason == "three-green-bars-sell-short"


@pytest.mark.parametrize(
    "candles",
    [
        [_red(0), _red(1), _green(2), _red(3)],
        [_red(0), _red(1), _red(2), _green(3)],
        [_green(0), _green(1), _red(2), _green(3)],
        [_red(0), _green(1), _red(2), _green(3)],
    ],
    ids=["red-broken-in-middle", "red-broken-on-deciding-bar", "green-broken", "alternating"],
)
def test_a_streak_shorter_than_three_is_held(candles: list[Candle]) -> None:
    decision = _strategy().analyze(_market(candles), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.HOLD
    assert decision.reason == "three-bar-no-streak"


def test_only_the_last_three_candles_count() -> None:
    # Three reds followed by a green: the deciding bar breaks the streak. Two reds after a
    # long red run do not count either; the rule reads the deciding bar and the two before it.
    broken = [_red(0), _red(1), _red(2), _green(3)]
    decision = _strategy().analyze(_market(broken), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.HOLD
    # Any earlier colour is irrelevant once the last three agree.
    fresh = [_green(0), _green(1), _red(2), _red(3), _red(4)]
    decision = _strategy().analyze(_market(fresh), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.ENTER_LONG


def test_a_fourth_consecutive_red_bar_still_satisfies_the_rule_when_flat() -> None:
    # The source states no once-only rule, so the literal condition (the last three bars are
    # red) is what fires; whether a position is already held is the engine's concern.
    candles = [_red(0), _red(1), _red(2), _red(3)]
    decision = _strategy().analyze(_market(candles), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.ENTER_LONG


@pytest.mark.parametrize(
    "candles",
    [
        [_red(0), _doji(1), _red(2), _red(3)],
        [_red(0), _red(1), _red(2), _doji(3)],
        [_green(0), _green(1), _doji(2), _green(3)],
    ],
    ids=["doji-first", "doji-deciding", "doji-middle-green"],
)
def test_a_bar_that_closes_at_its_open_breaks_the_streak(candles: list[Candle]) -> None:
    decision = _strategy().analyze(_market(candles), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.HOLD
    assert decision.reason == "three-bar-doji-breaks-streak"


def test_colour_is_close_against_open_not_against_the_previous_close() -> None:
    # Each bar gaps up from the previous close yet closes below its own open: red.
    candles = [
        _candle(0, open_price=100.0, close=99.0),
        _candle(1, open_price=103.0, close=102.0),
        _candle(2, open_price=106.0, close=105.0),
        _candle(3, open_price=109.0, close=108.0),
    ]
    decision = _strategy().analyze(_market(candles), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.ENTER_LONG
    assert decision.reason == "three-red-bars-buy"


def test_a_spot_short_is_held_with_a_reason() -> None:
    candles = [_red(0), _green(1), _green(2), _green(3)]
    decision = _strategy().analyze(_market(candles, "spot"), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.HOLD
    assert decision.reason == "spot-short-not-available"


def test_a_spot_long_is_still_taken() -> None:
    candles = [_green(0), _red(1), _red(2), _red(3)]
    decision = _strategy().analyze(_market(candles, "spot"), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.ENTER_LONG


@pytest.mark.parametrize("side", [PositionSide.LONG, PositionSide.SHORT])
@pytest.mark.parametrize(
    "candles",
    [
        [_green(0), _red(1), _red(2), _red(3)],
        [_red(0), _green(1), _green(2), _green(3)],
    ],
    ids=["three-red", "three-green"],
)
def test_an_open_position_is_left_to_the_policy(side: PositionSide, candles: list[Candle]) -> None:
    # Even a fresh streak in either direction produces neither an exit nor a reversal.
    decision = _strategy().analyze(_market(candles), _position(side))
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.HOLD
    assert decision.reason == "three-bar-protection-owns-exit"


def test_too_little_history_is_held_rather_than_misjudged() -> None:
    candles = [_red(0), _red(1)]
    decision = _strategy().analyze(_market(candles), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.HOLD
    assert decision.reason == "three-bar-history-short"


def test_exactly_three_candles_are_enough() -> None:
    candles = [_red(0), _red(1), _red(2)]
    decision = _strategy().analyze(_market(candles), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.ENTER_LONG


def test_the_strategy_is_deterministic_and_reads_no_series() -> None:
    candles = [_green(0), _red(1), _red(2), _red(3)]
    market = _market(candles)
    assert _strategy().analyze(market, None) == _strategy().analyze(market, None)
    without_series = {**market, "indicators": {}}
    assert _strategy().analyze(without_series, None) == _strategy().analyze(market, None)


def test_a_wrong_strategy_id_is_refused() -> None:
    resolved = StrategyConfig.resolve(
        ThreeBarReversion.get_parameter_schema(),
        {"strategy_id": "something-else", "params": {}},
    )
    with pytest.raises(ValueError, match=STRATEGY_ID):
        ThreeBarReversion(resolved)


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
    metadata = ThreeBarReversion.get_metadata()
    assert values["version"] == ThreeBarReversion.VERSION
    assert json.loads(values["defaults"]) == {}
    assert "'ThreeBarReversion'" in sql
    assert "'trading_plugins.strategies.three_bar_reversion'" in sql
    assert catalog_declaration_mismatch(row, metadata) is None
    assert catalog_declaration_mismatch({**row, "min_history": 2}, metadata) is not None
