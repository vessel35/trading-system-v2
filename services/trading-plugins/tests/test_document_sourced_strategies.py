"""Verify the three document-sourced strategies against their declared rules."""

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
from trading_plugins.strategies import (
    bollinger_rsi_reversion,
    macd_ema200_zero_line,
    supertrend_ema200_flip,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_REGISTRATION_DIR = _REPOSITORY_ROOT / "init-scripts/signal-service/20260923"
_FORBIDDEN_PARAMETER_NAMES = {
    "leverage",
    "reward_risk",
    "atr_stop_multiple",
    "risk_per_trade",
    "position_size_pct",
    "margin",
    "quantity",
}


def _candle(close: float = 101.0) -> Candle:
    opened = datetime(2026, 1, 1, tzinfo=UTC)
    return Candle(
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="1h",
        open_time=opened,
        close_time=opened + timedelta(hours=1),
        open=100.0,
        high=max(102.0, close),
        low=min(99.0, close),
        close=close,
        volume=100.0,
        quote_volume=10_000.0,
        trade_count=100,
    )


def _position(side: PositionSide) -> Position:
    return Position(
        wallet_id=None,
        symbol="BTCUSDT",
        quantity=Decimal("1"),
        average_price=Decimal("101"),
        total_cost=Decimal("101"),
        current_price=Decimal("101"),
        unrealized_pnl=Decimal("0"),
        side=side,
        market_type=MarketType.FUTURES,
        leverage=1,
        margin_type=MarginType.ISOLATED,
        margin=Decimal("101"),
        entry_price=Decimal("101"),
        mark_price=Decimal("101"),
        liquidation_price=Decimal("0"),
        funding_fee_total=Decimal("0"),
    )


def _market(
    close: float, indicators: dict[str, object], market_type: str = "futures"
) -> dict[str, object]:
    return {
        "candle": _candle(close),
        "timeframe": "1h",
        "market_type": market_type,
        "indicators": indicators,
    }


def _registration_row(strategy_id: str) -> tuple[dict[str, object], str, dict[str, object]]:
    matches = sorted(_REGISTRATION_DIR.glob(f"*-register-{strategy_id}.sql"))
    assert len(matches) == 1, f"one registration file expected for {strategy_id}"
    sql = matches[0].read_text()
    values = re.search(
        r"'(?P<version>\d+\.\d+\.\d+)',\s*"
        r"ARRAY\[(?P<timeframes>[^\]]+)\]::text\[\],\s*"
        r"'(?P<indicators>\[.*?\])'::jsonb,\s*"
        r"(?P<min_history>\d+),\s*"
        r"'(?P<defaults>\{.*?\})'::jsonb,",
        sql,
        re.DOTALL,
    )
    assert values is not None, f"registration values not found in {matches[0].name}"
    timeframes = [item.strip().strip("'") for item in values["timeframes"].split(",")]
    row = {
        "min_history": int(values["min_history"]),
        "supported_timeframes": timeframes,
        "required_indicators_json": json.loads(values["indicators"]),
    }
    return row, values["version"], json.loads(values["defaults"])


# --- SuperTrend + EMA 200 -------------------------------------------------------------


def _supertrend() -> supertrend_ema200_flip.SupertrendEma200Flip:
    resolved = StrategyConfig.resolve(
        supertrend_ema200_flip.SupertrendEma200Flip.get_parameter_schema(),
        {"strategy_id": supertrend_ema200_flip.STRATEGY_ID, "params": {}},
    )
    return supertrend_ema200_flip.SupertrendEma200Flip(resolved)


def _supertrend_series(direction: float, ema200: float) -> dict[str, object]:
    return {
        "supertrend:multiplier=3,period=10@1h": {
            "supertrend": 100.0,
            "direction": direction,
            "upper": 105.0,
            "lower": 95.0,
        },
        "ema:period=200@1h": ema200,
        "atr:period=14@1h": 2.0,
    }


def test_supertrend_declares_the_document_series_and_signal_exit() -> None:
    strategy = _supertrend()
    assert isinstance(strategy, StrategyAdapter)
    metadata = strategy.get_metadata()
    assert metadata.required_indicators == [
        {"name": "SuperTrend", "params": {"period": 10, "multiplier": 3.0}},
        {"name": "EMA", "params": {"period": 200}},
    ]
    assert metadata.min_history == 1
    assert metadata.decision_contract is StrategyDecisionContract.DECISION_INTENT
    assert metadata.money_management.default == "signal-exit-atr"
    assert metadata.money_management.supports_signal_exit is True
    assert _FORBIDDEN_PARAMETER_NAMES.isdisjoint(strategy.get_parameter_schema().fields)


@pytest.mark.parametrize(
    ("direction", "ema200", "close", "action", "reason"),
    [
        (1.0, 90.0, 101.0, DecisionAction.ENTER_LONG, "supertrend-up-above-ema200"),
        (-1.0, 110.0, 101.0, DecisionAction.ENTER_SHORT, "supertrend-down-below-ema200"),
        (-1.0, 90.0, 101.0, DecisionAction.HOLD, "supertrend-down-but-above-ema200"),
        (1.0, 110.0, 101.0, DecisionAction.HOLD, "supertrend-up-but-below-ema200"),
        (1.0, 101.0, 101.0, DecisionAction.HOLD, "price-on-ema200"),
    ],
)
def test_supertrend_entries_follow_the_ema200_permission(
    direction: float, ema200: float, close: float, action: DecisionAction, reason: str
) -> None:
    signal = _supertrend().analyze(_market(close, _supertrend_series(direction, ema200)), None)
    assert isinstance(signal, DecisionIntent)
    assert signal.action is action
    assert signal.reason == reason
    assert signal.metadata == {"adaptee": supertrend_ema200_flip.STRATEGY_ID}
    assert not hasattr(signal, "stop_loss")


def test_supertrend_refuses_a_spot_short() -> None:
    signal = _supertrend().analyze(
        _market(101.0, _supertrend_series(-1.0, 110.0), market_type="spot"), None
    )
    assert isinstance(signal, DecisionIntent)
    assert signal.action is DecisionAction.HOLD
    assert signal.reason == "spot-short-not-available"


@pytest.mark.parametrize(
    ("side", "direction", "action", "reason"),
    [
        (PositionSide.LONG, -1.0, DecisionAction.EXIT, "supertrend-flipped-against-position"),
        (PositionSide.SHORT, 1.0, DecisionAction.EXIT, "supertrend-flipped-against-position"),
        (PositionSide.LONG, 1.0, DecisionAction.HOLD, "supertrend-aligned-with-position"),
        (PositionSide.SHORT, -1.0, DecisionAction.HOLD, "supertrend-aligned-with-position"),
    ],
)
def test_supertrend_exits_only_when_the_state_opposes_the_position(
    side: PositionSide, direction: float, action: DecisionAction, reason: str
) -> None:
    # The EMA 200 side must not matter once a position is held.
    signal = _supertrend().analyze(
        _market(101.0, _supertrend_series(direction, 500.0)), _position(side)
    )
    assert isinstance(signal, DecisionIntent)
    assert signal.action is action
    assert signal.reason == reason


def test_supertrend_is_deterministic_and_ignores_the_policy() -> None:
    market = _market(101.0, _supertrend_series(1.0, 90.0))
    first = _supertrend().analyze(market, None)
    second = _supertrend().analyze(market, None)
    assert first == second


def test_supertrend_registration_script_matches_the_code_declaration() -> None:
    row, version, defaults = _registration_row(supertrend_ema200_flip.STRATEGY_ID)
    metadata = supertrend_ema200_flip.SupertrendEma200Flip.get_metadata()
    assert version == supertrend_ema200_flip.SupertrendEma200Flip.VERSION
    assert defaults == {}
    assert catalog_declaration_mismatch(row, metadata) is None
    assert catalog_declaration_mismatch({**row, "min_history": 10}, metadata) is not None


# --- MACD + EMA 200 -------------------------------------------------------------------


def _macd() -> macd_ema200_zero_line.MacdEma200ZeroLine:
    resolved = StrategyConfig.resolve(
        macd_ema200_zero_line.MacdEma200ZeroLine.get_parameter_schema(),
        {"strategy_id": macd_ema200_zero_line.STRATEGY_ID, "params": {}},
    )
    return macd_ema200_zero_line.MacdEma200ZeroLine(resolved)


def _macd_series(macd: float, signal: float, ema200: float) -> dict[str, object]:
    return {
        "macd:fast_period=12,signal_period=9,slow_period=26@1h": {
            "macd": macd,
            "signal": signal,
            "histogram": macd - signal,
        },
        "ema:period=200@1h": ema200,
        "atr:period=14@1h": 2.0,
    }


def test_macd_declares_the_document_series_and_no_signal_exit() -> None:
    strategy = _macd()
    metadata = strategy.get_metadata()
    assert metadata.required_indicators == [
        {"name": "MACD", "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9}},
        {"name": "EMA", "params": {"period": 200}},
    ]
    assert metadata.money_management.supported == ("manual",)
    assert metadata.money_management.supports_signal_exit is False
    assert metadata.money_management.supports_external_take_profit is True
    assert _FORBIDDEN_PARAMETER_NAMES.isdisjoint(strategy.get_parameter_schema().fields)


@pytest.mark.parametrize(
    ("macd", "signal", "ema200", "action", "reason"),
    [
        (-1.0, -1.5, 90.0, DecisionAction.ENTER_LONG, "macd-bullish-below-zero-above-ema200"),
        (1.0, 1.5, 110.0, DecisionAction.ENTER_SHORT, "macd-bearish-above-zero-below-ema200"),
        (1.0, 0.5, 90.0, DecisionAction.HOLD, "macd-cross-not-below-zero"),
        (-1.5, -1.0, 90.0, DecisionAction.HOLD, "macd-below-signal-in-uptrend"),
        (-1.0, -0.5, 110.0, DecisionAction.HOLD, "macd-cross-not-above-zero"),
        (1.5, 1.0, 110.0, DecisionAction.HOLD, "macd-above-signal-in-downtrend"),
        (-1.0, -1.5, 101.0, DecisionAction.HOLD, "price-on-ema200"),
    ],
)
def test_macd_entries_need_the_zero_line_side_and_the_ema200_side(
    macd: float, signal: float, ema200: float, action: DecisionAction, reason: str
) -> None:
    decision = _macd().analyze(_market(101.0, _macd_series(macd, signal, ema200)), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is action
    assert decision.reason == reason


def test_macd_never_exits_by_signal_and_refuses_a_spot_short() -> None:
    held = _macd().analyze(
        _market(101.0, _macd_series(1.0, 1.5, 110.0)), _position(PositionSide.LONG)
    )
    assert isinstance(held, DecisionIntent)
    assert held.action is DecisionAction.HOLD
    assert held.reason == "macd-protection-owns-exit"
    spot = _macd().analyze(_market(101.0, _macd_series(1.0, 1.5, 110.0), "spot"), None)
    assert isinstance(spot, DecisionIntent)
    assert spot.action is DecisionAction.HOLD
    assert spot.reason == "spot-short-not-available"


def test_macd_registration_script_matches_the_code_declaration() -> None:
    row, version, defaults = _registration_row(macd_ema200_zero_line.STRATEGY_ID)
    metadata = macd_ema200_zero_line.MacdEma200ZeroLine.get_metadata()
    assert version == macd_ema200_zero_line.MacdEma200ZeroLine.VERSION
    assert defaults == {}
    assert catalog_declaration_mismatch(row, metadata) is None


# --- Bollinger Bands + RSI ------------------------------------------------------------


def _bollinger(
    params: dict[str, object] | None = None,
) -> bollinger_rsi_reversion.BollingerRsiReversion:
    resolved = StrategyConfig.resolve(
        bollinger_rsi_reversion.BollingerRsiReversion.get_parameter_schema(),
        {"strategy_id": bollinger_rsi_reversion.STRATEGY_ID, "params": params or {}},
    )
    return bollinger_rsi_reversion.BollingerRsiReversion(resolved)


def _bollinger_series(rsi: float) -> dict[str, object]:
    return {
        "bollinger_bands:multiplier=2,period=20@1h": {
            "middle": 100.0,
            "upper": 104.0,
            "lower": 96.0,
            "percent_b": 0.5,
            "bandwidth": 0.08,
        },
        "rsi:period=14@1h": rsi,
        "atr:period=14@1h": 2.0,
    }


def test_bollinger_declares_the_document_series_and_threshold_parameters() -> None:
    strategy = _bollinger()
    metadata = strategy.get_metadata()
    assert metadata.required_indicators == [
        {"name": "Bollinger Bands", "params": {"period": 20, "multiplier": 2.0}},
        {"name": "RSI", "params": {"period": 14}},
    ]
    assert metadata.money_management.supports_signal_exit is True
    schema = strategy.get_parameter_schema()
    assert set(schema.fields) == {"rsi_oversold", "rsi_overbought"}
    assert _FORBIDDEN_PARAMETER_NAMES.isdisjoint(schema.fields)
    assert strategy.config.params["rsi_oversold"] == 30.0
    assert strategy.config.params["rsi_overbought"] == 70.0
    with pytest.raises(ValueError, match="rsi_oversold"):
        _bollinger({"rsi_oversold": 60.0, "rsi_overbought": 55.0})


@pytest.mark.parametrize(
    ("close", "rsi", "action", "reason"),
    [
        (95.0, 25.0, DecisionAction.ENTER_LONG, "bb-below-lower-rsi-oversold"),
        (95.0, 35.0, DecisionAction.HOLD, "bb-below-lower-rsi-not-oversold"),
        (105.0, 75.0, DecisionAction.ENTER_SHORT, "bb-above-upper-rsi-overbought"),
        (105.0, 65.0, DecisionAction.HOLD, "bb-above-upper-rsi-not-overbought"),
        (100.0, 25.0, DecisionAction.HOLD, "bb-inside-bands"),
        (96.0, 25.0, DecisionAction.HOLD, "bb-inside-bands"),
    ],
)
def test_bollinger_entries_need_the_band_breach_and_the_rsi_extreme(
    close: float, rsi: float, action: DecisionAction, reason: str
) -> None:
    decision = _bollinger().analyze(_market(close, _bollinger_series(rsi)), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is action
    assert decision.reason == reason


@pytest.mark.parametrize(
    ("side", "close", "action", "reason"),
    [
        (PositionSide.LONG, 100.0, DecisionAction.EXIT, "bb-long-reached-middle-band"),
        (PositionSide.LONG, 99.0, DecisionAction.HOLD, "bb-long-below-middle-band"),
        (PositionSide.SHORT, 100.0, DecisionAction.EXIT, "bb-short-reached-middle-band"),
        (PositionSide.SHORT, 101.0, DecisionAction.HOLD, "bb-short-above-middle-band"),
    ],
)
def test_bollinger_exits_at_the_middle_band(
    side: PositionSide, close: float, action: DecisionAction, reason: str
) -> None:
    decision = _bollinger().analyze(_market(close, _bollinger_series(50.0)), _position(side))
    assert isinstance(decision, DecisionIntent)
    assert decision.action is action
    assert decision.reason == reason


def test_bollinger_thresholds_come_from_the_resolved_parameters() -> None:
    strict = _bollinger({"rsi_oversold": 20.0, "rsi_overbought": 80.0})
    decision = strict.analyze(_market(95.0, _bollinger_series(25.0)), None)
    assert isinstance(decision, DecisionIntent)
    assert decision.action is DecisionAction.HOLD
    assert decision.reason == "bb-below-lower-rsi-not-oversold"


def test_bollinger_registration_script_matches_the_code_declaration() -> None:
    row, version, defaults = _registration_row(bollinger_rsi_reversion.STRATEGY_ID)
    metadata = bollinger_rsi_reversion.BollingerRsiReversion.get_metadata()
    assert version == bollinger_rsi_reversion.BollingerRsiReversion.VERSION
    assert defaults == {"rsi_oversold": 30.0, "rsi_overbought": 70.0}
    assert catalog_declaration_mismatch(row, metadata) is None
