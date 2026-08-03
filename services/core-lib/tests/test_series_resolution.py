"""Verify shared indicator/pattern descriptor resolution."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from core_lib.indicators.registry import (
    IndicatorParam,
    IndicatorRegistry,
    IndicatorSpec,
    IndicatorValue,
)
from core_lib.patterns.registry import PatternRegistry, PatternSpec, PatternValue
from core_lib.series import SeriesSpec
from core_lib.series_resolution import (
    assert_disjoint_series_registry_names,
    resolve_series_specs,
    series_key,
)
from core_lib.types import Candle


class _IndicatorState:
    min_history = 1

    @property
    def warmed_up(self) -> bool:
        return True

    def seed(self, candles: Sequence[Candle]) -> None:
        del candles

    def update(self, candle: Candle) -> IndicatorValue:
        del candle
        return 1.0

    def current(self) -> IndicatorValue:
        return 1.0


class _PatternState:
    min_history = 1

    @property
    def warmed_up(self) -> bool:
        return True

    def seed(self, candles: Sequence[Candle]) -> None:
        del candles

    def update(self, candle: Candle) -> PatternValue:
        del candle
        return {"pat_doji": 0.0}

    def current(self) -> PatternValue:
        return {"pat_doji": 0.0}


def _indicator(name: str, params: dict[str, IndicatorParam] | None = None) -> IndicatorSpec:
    return IndicatorSpec(
        name=name,
        params={} if params is None else params,
        version="1.0.0",
        pinned_impl="test",
        min_history=1,
        category="test",
        required_inputs=(),
        _vectorized=lambda candles: [1.0 for _ in candles],
        _state_factory=_IndicatorState,
    )


def _pattern(name: str) -> PatternSpec:
    return PatternSpec(
        name=name,
        params={},
        version="1.0.0",
        bar_count=1,
        requires_trend=False,
        _vectorized=lambda candles: [{"pat_doji": 0.0} for _ in candles],
        _state_factory=_PatternState,
    )


def _registries() -> tuple[IndicatorRegistry, PatternRegistry]:
    indicators = IndicatorRegistry()
    indicators.register(_indicator("EMA", {"period": 9}))
    indicators.register(_indicator("ATR", {"period": 14}))
    patterns = PatternRegistry()
    patterns.register(_pattern("pat_doji"))
    patterns.register(_pattern("pat_hammer"))
    return indicators, patterns


def _ids(specs: Sequence[SeriesSpec]) -> list[str]:
    return [spec.identifier for spec in specs]


def test_series_key_matches_the_existing_execution_key_contract() -> None:
    spec = _indicator("Bollinger Bands", {"period": 20, "multiplier": 2.0})

    assert series_key(spec) == "bollinger_bands:multiplier=2,period=20"


@pytest.mark.parametrize(
    ("mode", "expected"),
    (
        ("auto", ["EMA(period=9)", "pat_doji"]),
        ("explicit", ["ATR(period=14)", "pat_hammer"]),
        ("all", ["ATR(period=14)", "EMA(period=9)", "pat_doji"]),
    ),
)
def test_resolve_series_specs_applies_the_mode_table(
    mode: str,
    expected: list[str],
) -> None:
    indicators, patterns = _registries()
    declared = [
        {"name": "EMA", "params": {"period": 9}},
        {"name": "pat_doji", "params": {}},
    ]
    explicit = [
        {"name": "ATR", "params": {"period": 14}},
        {"name": "PAT_HAMMER", "params": {}},
    ]

    assert _ids(resolve_series_specs(mode, declared, explicit, indicators, patterns)) == expected


def test_resolve_series_specs_allows_one_empty_side_but_not_empty_union() -> None:
    indicators, patterns = _registries()

    assert _ids(
        resolve_series_specs(
            "auto",
            [{"name": "pat_doji", "params": {}}],
            (),
            indicators,
            patterns,
        )
    ) == ["pat_doji"]
    assert _ids(
        resolve_series_specs(
            "auto",
            [{"name": "EMA", "params": {"period": 9}}],
            (),
            indicators,
            patterns,
        )
    ) == ["EMA(period=9)"]
    with pytest.raises(ValueError, match="series selection must resolve at least one spec"):
        resolve_series_specs("auto", (), (), indicators, patterns)


def test_resolve_series_specs_reports_an_unknown_name_once() -> None:
    indicators, patterns = _registries()

    with pytest.raises(KeyError, match="series is not registered in either registry: UNKNOWN"):
        resolve_series_specs(
            "auto",
            [{"name": "UNKNOWN", "params": {}}],
            (),
            indicators,
            patterns,
        )


def test_decision_g_is_enforced_after_execution_key_normalization() -> None:
    indicators = IndicatorRegistry()
    indicators.register(_indicator("Pat Hammer"))
    patterns = PatternRegistry()
    patterns.register(_pattern("pat_hammer"))

    with pytest.raises(ValueError, match="execution-key normalization: pat_hammer"):
        assert_disjoint_series_registry_names(indicators, patterns)
