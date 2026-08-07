"""Verify the optional strategy authoring base without making inheritance mandatory."""

from core_lib.indicators import DEFAULT_REGISTRY
from core_lib.patterns import DEFAULT_PATTERN_REGISTRY
from core_lib.series import normalize_series_name, series_key
from core_lib.strategy import (
    ParameterSchema,
    StrategyAdapter,
    StrategyBase,
    StrategyMetadata,
)
from core_lib.types import DecisionIntent, Position


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
    indicator_key = series_key(indicator)
    pattern_key = series_key(pattern)
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
    market_data: dict[str, object] = {"indicators": values}
    original = dict(values)

    assert indicator_key == "ema:period=9"
    assert pattern_key == normalize_series_name(pattern.name)
    assert strategy.series_value(market_data, indicator) == 101.25
    assert strategy.series_value(market_data, pattern) is pattern_value
    assert values == original
