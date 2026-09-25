"""Verify the Bollinger band bounce strategy against its source document's one rule."""

from __future__ import annotations

import ast
import inspect
import json
import re
from collections.abc import Mapping
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
from trading_plugins.strategies import bollinger_band_bounce
from trading_plugins.strategies.bollinger_band_bounce import STRATEGY_ID, BollingerBandBounce

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_REGISTRATION_FILE = (
    _REPOSITORY_ROOT / "init-scripts/signal-service/20260923/07-register-bollinger-band-bounce.sql"
)
_START = datetime(2026, 1, 1, tzinfo=UTC)
_BANDS_KEY = "bollinger_bands:multiplier=2,period=20@1h"
_TIMEFRAME_HOURS = {"1h": 1, "4h": 4}
_FORBIDDEN_PARAMETER_NAMES = {
    "leverage",
    "reward_risk",
    "atr_stop_multiple",
    "risk_per_trade",
    "position_size_pct",
    "margin",
    "quantity",
}
# Packages a strategy may not import (authoring contract §4.1): services, storage, network,
# the clock, and randomness. The module may import only core_lib and the standard typing
# helpers it needs to stay pure.
_ALLOWED_IMPORT_ROOTS = {"__future__", "collections", "core_lib", "math"}


def _candle(
    *,
    close: float,
    low: float | None = None,
    high: float | None = None,
    timeframe: str = "1h",
) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        exchange="binance",
        timeframe=timeframe,
        open_time=_START,
        close_time=_START + timedelta(hours=_TIMEFRAME_HOURS[timeframe]),
        open=100.0,
        high=high if high is not None else max(100.0, close) + 0.5,
        low=low if low is not None else min(100.0, close) - 0.5,
        close=close,
        volume=100.0,
        quote_volume=10_000.0,
        trade_count=100,
    )


def _bands(
    *,
    upper: float = 104.0,
    middle: float = 100.0,
    lower: float = 96.0,
    percent_b: float = 0.5,
    bandwidth: float = 0.08,
) -> dict[str, float]:
    return {
        "middle": middle,
        "upper": upper,
        "lower": lower,
        "percent_b": percent_b,
        "bandwidth": bandwidth,
    }


def _market(
    candle: Candle,
    indicators: Mapping[str, object] | None = None,
    *,
    market_type: str = "futures",
    timeframe: str = "1h",
) -> dict[str, object]:
    return {
        "candles": [candle],
        "candle": candle,
        "symbol": "BTCUSDT",
        "timeframe": timeframe,
        "market_type": market_type,
        "indicators": {_BANDS_KEY: _bands()} if indicators is None else dict(indicators),
    }


def _strategy() -> BollingerBandBounce:
    resolved = StrategyConfig.resolve(
        BollingerBandBounce.get_parameter_schema(),
        {"strategy_id": STRATEGY_ID, "params": {}},
    )
    return BollingerBandBounce(resolved)


def _position(side: PositionSide, leverage: int = 1) -> Position:
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
        leverage=leverage,
        margin_type=MarginType.ISOLATED,
        margin=Decimal("100"),
        entry_price=Decimal("100"),
        mark_price=Decimal("100"),
        liquidation_price=Decimal("0"),
        funding_fee_total=Decimal("0"),
    )


def _decision(market: dict[str, object], position: Position | None = None) -> DecisionIntent:
    decision = _strategy().analyze(market, position)
    assert isinstance(decision, DecisionIntent)
    return decision


# --- declaration ----------------------------------------------------------------------


def test_bounce_declares_the_bands_series_and_the_document_protection() -> None:
    strategy = _strategy()
    assert isinstance(strategy, StrategyAdapter)
    metadata = strategy.get_metadata()
    assert metadata.required_indicators == [
        {"name": "Bollinger Bands", "params": {"period": 20, "multiplier": 2.0}},
    ]
    assert metadata.min_history == 1
    assert metadata.supported_timeframes == ["1h"]
    assert metadata.decision_contract is StrategyDecisionContract.DECISION_INTENT
    assert metadata.money_management.supported == ("manual",)
    assert metadata.money_management.default == "manual"
    assert dict(metadata.money_management.default_settings["manual"]) == {
        "atr_stop_multiple": 1.5,
        "reward_risk": 1.5,
    }
    assert metadata.money_management.supports_signal_exit is False
    assert metadata.money_management.supports_external_stop is True
    assert metadata.money_management.supports_external_take_profit is True
    assert metadata.money_management.supports_pyramiding is False
    assert metadata.profile.id == "bollinger-band-bounce-v1"
    assert metadata.profile.bar == "1h"
    assert metadata.profile.envelope_status == "provisional"
    assert strategy.get_parameter_schema().fields == {}
    assert _FORBIDDEN_PARAMETER_NAMES.isdisjoint(strategy.get_parameter_schema().fields)


def test_the_module_imports_only_core_lib_and_pure_helpers() -> None:
    tree = ast.parse(inspect.getsource(bollinger_band_bounce))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module is not None
            roots.add(node.module.split(".")[0])
    assert roots <= _ALLOWED_IMPORT_ROOTS, roots


# --- entries --------------------------------------------------------------------------


@pytest.mark.parametrize("close", [95.0, 96.0], ids=["below-lower", "on-lower"])
def test_a_close_at_or_below_the_lower_band_enters_long(close: float) -> None:
    decision = _decision(_market(_candle(close=close)))
    assert decision.action is DecisionAction.ENTER_LONG
    assert decision.reason == "bounce-lower-band-touch-long"
    assert decision.reference_price == close
    assert decision.timestamp == _START + timedelta(hours=1)
    assert decision.confidence == 1.0
    assert decision.metadata == {"adaptee": STRATEGY_ID}
    assert not hasattr(decision, "stop_loss")


@pytest.mark.parametrize("close", [105.0, 104.0], ids=["above-upper", "on-upper"])
def test_a_close_at_or_above_the_upper_band_enters_short(close: float) -> None:
    decision = _decision(_market(_candle(close=close)))
    assert decision.action is DecisionAction.ENTER_SHORT
    assert decision.reason == "bounce-upper-band-touch-short"
    assert decision.reference_price == close


@pytest.mark.parametrize(
    "close", [96.01, 100.0, 103.99], ids=["just-above-lower", "middle", "just-below-upper"]
)
def test_a_close_inside_the_bands_is_held(close: float) -> None:
    decision = _decision(_market(_candle(close=close)))
    assert decision.action is DecisionAction.HOLD
    assert decision.reason == "bounce-inside-bands"


def test_a_wick_beyond_a_band_with_a_close_inside_is_not_a_touch() -> None:
    # The source does not say which price touches; the close is the reading taken. A bar
    # whose low pierced the lower band but closed back inside does not enter.
    pierced_lower = _decision(_market(_candle(close=100.0, low=90.0)))
    assert pierced_lower.action is DecisionAction.HOLD
    assert pierced_lower.reason == "bounce-inside-bands"
    pierced_upper = _decision(_market(_candle(close=100.0, high=110.0)))
    assert pierced_upper.action is DecisionAction.HOLD
    assert pierced_upper.reason == "bounce-inside-bands"


def test_collapsed_bands_satisfy_both_sides_and_are_held_with_their_own_reason() -> None:
    flat = {_BANDS_KEY: _bands(upper=100.0, middle=100.0, lower=100.0, bandwidth=0.0)}
    decision = _decision(_market(_candle(close=100.0), flat))
    assert decision.action is DecisionAction.HOLD
    assert decision.reason == "bounce-band-width-zero"


def test_a_spot_short_is_held_with_a_reason_and_a_spot_long_is_taken() -> None:
    short = _decision(_market(_candle(close=105.0), market_type="spot"))
    assert short.action is DecisionAction.HOLD
    assert short.reason == "spot-short-not-available"
    long = _decision(_market(_candle(close=95.0), market_type="spot"))
    assert long.action is DecisionAction.ENTER_LONG


# --- while a position is open -----------------------------------------------------------


@pytest.mark.parametrize("side", [PositionSide.LONG, PositionSide.SHORT])
@pytest.mark.parametrize(
    "close", [95.0, 100.0, 105.0], ids=["lower-touch", "inside", "upper-touch"]
)
def test_an_open_position_is_left_to_the_policy(side: PositionSide, close: float) -> None:
    # Neither a fresh touch on the other side nor a return inside produces an exit or a
    # reversal: the source names only the stop and the target, and the policy owns both.
    decision = _decision(_market(_candle(close=close)), _position(side))
    assert decision.action is DecisionAction.HOLD
    assert decision.reason == "bounce-protection-owns-exit"


def test_the_policy_owned_fields_of_a_position_do_not_change_the_judgement() -> None:
    market = _market(_candle(close=95.0))
    assert _decision(market, _position(PositionSide.LONG, leverage=1)) == _decision(
        market, _position(PositionSide.LONG, leverage=7)
    )


# --- series access -----------------------------------------------------------------------


def test_the_execution_key_carries_the_run_timeframe() -> None:
    # The key is built from the run's timeframe rather than written as text, so the same
    # class reads "@4h" when a run on four-hour candles calls it.
    candle = _candle(close=95.0, timeframe="4h")
    four_hour = _market(
        candle, {"bollinger_bands:multiplier=2,period=20@4h": _bands()}, timeframe="4h"
    )
    assert _decision(four_hour).action is DecisionAction.ENTER_LONG
    one_hour_key_only = _market(candle, {_BANDS_KEY: _bands()}, timeframe="4h")
    with pytest.raises(TypeError, match="Bollinger Bands"):
        _strategy().analyze(one_hour_key_only, None)


def test_only_the_upper_and_lower_bands_decide() -> None:
    baseline = _decision(_market(_candle(close=95.0)))
    other_outputs = {_BANDS_KEY: _bands(middle=50.0, percent_b=-3.0, bandwidth=9.0)}
    assert _decision(_market(_candle(close=95.0), other_outputs)) == baseline
    with_undeclared_series = {
        _BANDS_KEY: _bands(),
        "atr:period=14@1h": 2.0,
        "rsi:period=14@1h": 10.0,
    }
    assert _decision(_market(_candle(close=95.0), with_undeclared_series)) == baseline


def test_the_declared_series_is_the_one_read_and_must_be_well_formed() -> None:
    with pytest.raises(TypeError, match="Bollinger Bands"):
        _strategy().analyze(_market(_candle(close=95.0), {}), None)
    with pytest.raises(TypeError, match="Bollinger upper band"):
        _strategy().analyze(
            _market(_candle(close=95.0), {_BANDS_KEY: {"upper": "104", "lower": 96.0}}), None
        )
    with pytest.raises(ValueError, match="finite"):
        _strategy().analyze(
            _market(_candle(close=95.0), {_BANDS_KEY: _bands(lower=float("nan"))}), None
        )


def test_the_strategy_is_deterministic() -> None:
    market = _market(_candle(close=95.0))
    assert _strategy().analyze(market, None) == _strategy().analyze(market, None)
    held = _market(_candle(close=105.0))
    assert _strategy().analyze(held, _position(PositionSide.LONG)) == _strategy().analyze(
        held, _position(PositionSide.LONG)
    )


def test_a_wrong_strategy_id_is_refused() -> None:
    resolved = StrategyConfig.resolve(
        BollingerBandBounce.get_parameter_schema(),
        {"strategy_id": "something-else", "params": {}},
    )
    with pytest.raises(ValueError, match=STRATEGY_ID):
        BollingerBandBounce(resolved)


# --- registration --------------------------------------------------------------------


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
    metadata = BollingerBandBounce.get_metadata()
    assert values["version"] == BollingerBandBounce.VERSION
    assert json.loads(values["defaults"]) == {}
    assert "'BollingerBandBounce'" in sql
    assert "'trading_plugins.strategies.bollinger_band_bounce'" in sql
    assert sql.startswith("\\set ON_ERROR_STOP on")
    assert "BEGIN;" in sql and sql.rstrip().endswith("COMMIT;")
    assert catalog_declaration_mismatch(row, metadata) is None
    assert catalog_declaration_mismatch({**row, "min_history": 2}, metadata) is not None
    assert (
        catalog_declaration_mismatch({**row, "required_indicators_json": []}, metadata) is not None
    )
