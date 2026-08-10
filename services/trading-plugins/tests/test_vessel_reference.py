"""Verify the first Vessel reference Adaptee's fixed-protection contract."""

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
from trading_plugins.strategies.vessel_reference import STRATEGY_ID, VesselReference


def _candle() -> Candle:
    opened = datetime(2026, 1, 1, tzinfo=UTC)
    return Candle(
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="1h",
        open_time=opened,
        close_time=opened + timedelta(hours=1),
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=100.0,
        quote_volume=10_000.0,
        trade_count=100,
    )


def _strategy() -> VesselReference:
    resolved = StrategyConfig.resolve(
        VesselReference.get_parameter_schema(),
        {"strategy_id": STRATEGY_ID, "params": {}},
    )
    return VesselReference(resolved)


def _position() -> Position:
    return Position(
        wallet_id=None,
        symbol="BTCUSDT",
        quantity=Decimal("1"),
        average_price=Decimal("101"),
        total_cost=Decimal("101"),
        current_price=Decimal("101"),
        unrealized_pnl=Decimal("0"),
        side=PositionSide.LONG,
        market_type=MarketType.FUTURES,
        leverage=1,
        margin_type=MarginType.ISOLATED,
        margin=Decimal("101"),
        entry_price=Decimal("101"),
        mark_price=Decimal("101"),
        liquidation_price=Decimal("0"),
        funding_fee_total=Decimal("0"),
    )


def test_vessel_declares_exact_pipeline_inputs_and_no_trailing() -> None:
    strategy = _strategy()
    assert isinstance(strategy, StrategyAdapter)
    metadata = strategy.get_metadata()
    assert metadata.min_history == 1
    assert metadata.required_indicators == [
        {"name": "EMA", "params": {"period": 9}},
        {"name": "EMA", "params": {"period": 21}},
    ]
    assert metadata.money_management.supported == ("manual", "turtle")
    assert metadata.decision_contract is StrategyDecisionContract.DECISION_INTENT
    assert metadata.money_management.default == "manual"

    signal = strategy.analyze(
        {
            "candle": _candle(),
            "timeframe": "1h",
            "market_type": "futures",
            "indicators": {
                "ema:period=9@1h": 102.0,
                "ema:period=21@1h": 100.0,
                "atr:period=14@1h": 2.0,
            },
        },
        None,
    )
    assert signal is not None
    assert isinstance(signal, DecisionIntent)
    assert signal.action is DecisionAction.ENTER_LONG
    assert not hasattr(signal, "stop_loss")
    assert not hasattr(signal, "leverage")
    assert signal.metadata == {"adaptee": STRATEGY_ID}
    assert "trailing" not in signal.metadata


def test_vessel_exits_only_when_ema_regime_reverses() -> None:
    strategy = _strategy()
    signal = strategy.analyze(
        {
            "candle": _candle(),
            "timeframe": "1h",
            "market_type": "futures",
            "indicators": {
                "ema:period=9@1h": 99.0,
                "ema:period=21@1h": 100.0,
                "atr:period=14@1h": 2.0,
            },
        },
        _position(),
    )
    assert signal is not None
    assert isinstance(signal, DecisionIntent)
    assert signal.action is DecisionAction.EXIT
    assert signal.reason == "vessel-ema-regime-exit"


@pytest.mark.parametrize(
    ("fast", "slow", "market_type", "current_position", "reason"),
    [
        (102.0, 100.0, "futures", _position(), "vessel-ema-regime-intact"),
        (100.0, 100.0, "futures", None, "vessel-ema-regime-flat"),
        (99.0, 100.0, "spot", None, "vessel-spot-short-not-available"),
    ],
)
def test_vessel_hold_reasons_distinguish_each_non_execution_case(
    fast: float,
    slow: float,
    market_type: str,
    current_position: Position | None,
    reason: str,
) -> None:
    decision = _strategy().analyze(
        {
            "candle": _candle(),
            "timeframe": "1h",
            "market_type": market_type,
            "indicators": {
                "ema:period=9@1h": fast,
                "ema:period=21@1h": slow,
            },
        },
        current_position,
    )

    assert decision.action is DecisionAction.HOLD
    assert decision.reason == reason
    assert decision.metadata == {"adaptee": STRATEGY_ID}


def test_vessel_parameter_schema_has_no_money_management_names() -> None:
    forbidden = {
        "leverage",
        "reward_risk",
        "atr_stop_multiple",
        "risk_per_trade",
        "position_size_pct",
        "margin",
        "quantity",
    }

    assert forbidden.isdisjoint(VesselReference.get_parameter_schema().fields)
    assert VesselReference.VERSION == "3.1.0"


def test_vessel_registration_script_matches_the_code_declaration() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    sql = (
        repository_root / "init-scripts/signal-service/20260724/02-register-vessel-reference.sql"
    ).read_text()
    values = re.search(
        r"'(?P<version>\d+\.\d+\.\d+)',\s*"
        r"ARRAY\['(?P<timeframe>[^']+)'\]::text\[\],\s*"
        r"'(?P<indicators>\[.*?\])'::jsonb,\s*"
        r"(?P<min_history>\d+),\s*"
        r"'(?P<defaults>\{.*?\})'::jsonb,",
        sql,
        re.DOTALL,
    )
    assert values is not None
    row = {
        "min_history": int(values["min_history"]),
        "supported_timeframes": [values["timeframe"]],
        "required_indicators_json": json.loads(values["indicators"]),
    }
    metadata = VesselReference.get_metadata()

    assert values["version"] == VesselReference.VERSION
    assert json.loads(values["defaults"]) == {}
    assert catalog_declaration_mismatch(row, metadata) is None
    assert (
        catalog_declaration_mismatch({**row, "min_history": 21}, metadata)
        == "catalog min_history does not match the Adaptee: 21 != 1"
    )
