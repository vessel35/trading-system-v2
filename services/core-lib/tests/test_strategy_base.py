"""Verify the optional strategy authoring base without making inheritance mandatory."""

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from core_lib.indicators import DEFAULT_REGISTRY
from core_lib.patterns import DEFAULT_PATTERN_REGISTRY
from core_lib.series import normalize_series_name, series_key
from core_lib.strategy import (
    DecisionInputs,
    ParameterSchema,
    StrategyAdapter,
    StrategyBase,
    StrategyMetadata,
)
from core_lib.types import Candle, DecisionAction, DecisionIntent, MarketType, Position


class _ConvenienceStrategy(StrategyBase):
    """Concrete only so the base helper can be exercised in isolation."""

    __slots__ = ()

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        raise NotImplementedError

    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        raise NotImplementedError

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> DecisionIntent | None:
        del market_data, current_position
        return None


def test_strategy_base_is_an_optional_stateless_strategy_adapter() -> None:
    strategy = _ConvenienceStrategy()

    assert isinstance(strategy, StrategyAdapter)
    assert StrategyBase.__slots__ == ()


def test_strategy_base_reads_indicator_and_pattern_values_by_series_key() -> None:
    strategy = _ConvenienceStrategy()
    indicator = DEFAULT_REGISTRY.get("EMA", {"period": 9})
    pattern = DEFAULT_PATTERN_REGISTRY.list()[0]
    indicator_key = series_key(indicator, "1h")
    pattern_key = series_key(pattern, "1h")
    pattern_value = {
        "pattern_detected": 1.0,
        "pattern_strength": 100.0,
        "pattern_direction": 1.0,
        "pattern_reliability": 1.0,
    }
    values: dict[str, object] = {
        indicator_key: 101.25,
        pattern_key: pattern_value,
    }
    market_data: dict[str, object] = {"indicators": values, "timeframe": "1h"}
    original = dict(values)

    assert indicator_key == "ema:period=9@1h"
    assert pattern_key == f"{normalize_series_name(pattern.name)}@1h"
    assert strategy.series_value(market_data, indicator) == 101.25
    assert strategy.series_value(market_data, pattern) is pattern_value
    assert values == original


# --- the five helpers (author_check design section 3.5) ------------------------------------


def _helper_candle() -> Candle:
    opened = datetime(2026, 1, 1, tzinfo=UTC)
    return Candle(
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="1h",
        open_time=opened,
        close_time=opened + timedelta(hours=1),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1.0,
        quote_volume=None,
        trade_count=None,
    )


def _helper_market_data(**overrides: object) -> dict[str, object]:
    candle = _helper_candle()
    data: dict[str, object] = {
        "candles": [candle],
        "candle": candle,
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "market_type": "futures",
        "indicators": {"ema:period=9@1h": 100.25, "pat_engulfing@1h": {"occurred": 1.0}},
    }
    data.update(overrides)
    return data


def test_read_inputs_returns_the_six_inputs_typed_and_frozen() -> None:
    inputs = StrategyBase.read_inputs(_helper_market_data())
    assert isinstance(inputs, DecisionInputs)
    assert inputs.candles == (_helper_candle(),) and inputs.candle == _helper_candle()
    assert inputs.symbol == "BTCUSDT" and inputs.timeframe == "1h"
    assert inputs.market_type is MarketType.FUTURES
    assert inputs.indicators["ema:period=9@1h"] == 100.25
    with pytest.raises(TypeError):
        cast(dict[str, object], inputs.indicators)["x"] = 1.0
    assert StrategyBase.read_inputs(
        _helper_market_data(market_type=MarketType.SPOT)
    ).market_type is (MarketType.SPOT)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"candles": []}, "candles must be a non-empty"),
        ({"candles": ["not a candle"]}, "Candle values only"),
        ({"candle": "no"}, "candle must be Candle"),
        ({"symbol": ""}, "symbol must be a non-empty"),
        ({"timeframe": 1}, "timeframe must be a non-empty"),
        ({"market_type": "margin"}, "not a market type"),
        ({"market_type": 3}, "market type or its name"),
        ({"indicators": [1.0]}, "indicators must be a mapping"),
    ],
)
def test_read_inputs_refuses_a_missing_or_mistyped_input(
    override: dict[str, object], message: str
) -> None:
    with pytest.raises(TypeError, match=message):
        StrategyBase.read_inputs(_helper_market_data(**override))


def test_series_reads_by_the_execution_key_and_names_a_missing_declaration() -> None:
    inputs = StrategyBase.read_inputs(_helper_market_data())
    assert StrategyBase.series(inputs, "EMA", {"period": 9}) == 100.25
    assert StrategyBase.series(inputs, "pat_engulfing", {}) == {"occurred": 1.0}
    with pytest.raises(KeyError, match="ema:period=21@1h.*declare it"):
        StrategyBase.series(inputs, "EMA", {"period": 21})
    higher = StrategyBase.read_inputs(_helper_market_data(indicators={"ema:period=9@4h": 7.0}))
    assert StrategyBase.series(higher, "EMA", {"period": 9}, "4h") == 7.0
    assert StrategyBase.series(inputs, "EMA", {"period": 9}, "strategy") == 100.25
    with pytest.raises(KeyError, match="ema:period=9@1h"):
        StrategyBase.series(higher, "EMA", {"period": 9})


def test_number_and_outputs_narrow_values_and_refuse_the_wrong_shape() -> None:
    assert StrategyBase.number(3, "EMA") == 3.0 and isinstance(StrategyBase.number(3, "EMA"), float)
    for wrong in (True, "3", None, {"a": 1.0}):
        with pytest.raises(TypeError, match="must be a number"):
            StrategyBase.number(wrong, "EMA")
    outputs = StrategyBase.outputs({"occurred": 1, "strength": 0.5}, "pat_engulfing")
    assert dict(outputs) == {"occurred": 1.0, "strength": 0.5}
    with pytest.raises(TypeError):
        cast(dict[str, float], outputs)["x"] = 1.0
    with pytest.raises(TypeError, match="mapping of named outputs"):
        StrategyBase.outputs(1.0, "pat_engulfing")
    with pytest.raises(TypeError, match=r"pat_engulfing\['occurred'\] must be a number"):
        StrategyBase.outputs({"occurred": True}, "pat_engulfing")


def test_decide_builds_the_intent_from_the_deciding_candle() -> None:
    candle = _helper_candle()
    decision = StrategyBase.decide(candle, DecisionAction.ENTER_LONG, "rule-held", adaptee="x-y")
    assert decision.symbol == candle.symbol and decision.timestamp == candle.close_time
    assert decision.reference_price == 100.5 and decision.confidence == 1.0
    assert decision.reason == "rule-held" and dict(decision.metadata) == {"adaptee": "x-y"}
    tagged = StrategyBase.decide(
        candle, "HOLD", "no-signal", adaptee="x-y", confidence=0.25, metadata={"bar": 3}
    )
    assert tagged.action is DecisionAction.HOLD and tagged.confidence == 0.25
    assert dict(tagged.metadata) == {"adaptee": "x-y", "bar": 3}
    with pytest.raises(ValueError):
        StrategyBase.decide(candle, DecisionAction.EXIT, "", adaptee="x-y")
