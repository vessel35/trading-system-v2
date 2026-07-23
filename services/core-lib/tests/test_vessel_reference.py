"""Verify the first Vessel reference Adaptee's fixed-protection contract."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from core_lib.strategy import StrategyAdapter, StrategyConfig
from core_lib.strategy.adaptees import STRATEGY_ID, VesselReference
from core_lib.types import (
    Candle,
    MarginType,
    MarketType,
    Position,
    PositionSide,
)


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
    assert metadata.min_history == 21
    assert metadata.required_indicators == [
        {"name": "EMA", "params": {"period": 9}},
        {"name": "EMA", "params": {"period": 21}},
        {"name": "ATR", "params": {"period": 14}},
    ]

    signal = strategy.analyze(
        {
            "candle": _candle(),
            "market_type": "futures",
            "indicators": {
                "ema:period=9": 102.0,
                "ema:period=21": 100.0,
                "atr:period=14": 2.0,
            },
        },
        None,
    )
    assert signal is not None
    assert signal.stop_loss == 97.0
    assert signal.take_profit == 109.0
    assert signal.metadata == {"adaptee": STRATEGY_ID, "trailing": False}


def test_vessel_exits_only_when_ema_regime_reverses() -> None:
    strategy = _strategy()
    signal = strategy.analyze(
        {
            "candle": _candle(),
            "market_type": "futures",
            "indicators": {
                "ema:period=9": 99.0,
                "ema:period=21": 100.0,
                "atr:period=14": 2.0,
            },
        },
        _position(),
    )
    assert signal is not None
    assert signal.stop_loss is None
    assert signal.take_profit is None
    assert signal.reason == "vessel-ema-regime-exit"
