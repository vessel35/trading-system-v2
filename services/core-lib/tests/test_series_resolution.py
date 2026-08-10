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
    ResolvedSeriesSpec,
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


class _PairedState:
    def __init__(self) -> None:
        self.samples = 0

    @property
    def warmed_up(self) -> bool:
        return self.samples >= 1

    def seed(
        self,
        candles: Sequence[Candle],
        reference_candles: Sequence[Candle],
    ) -> None:
        assert len(candles) == len(reference_candles)
        assert all(
            candle.close_time == reference.close_time
            for candle, reference in zip(candles, reference_candles, strict=True)
        )
        self.samples = len(candles)

    def update(self, candle: Candle, reference_candle: Candle) -> IndicatorValue:
        assert candle.close_time == reference_candle.close_time
        self.samples += 1
        return {"reference_close": reference_candle.close, "samples": float(self.samples)}


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
        explicit_min_history=1,
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


def test_series_key_requires_and_includes_the_resolved_timeframe() -> None:
    spec = _indicator("Bollinger Bands", {"period": 20, "multiplier": 2.0})

    assert series_key(spec, "4h") == "bollinger_bands:multiplier=2,period=20@4h"
    with pytest.raises(ValueError, match="positive minute, hour, or day interval"):
        series_key(spec, "strategy")
    with pytest.raises(TypeError):
        series_key(spec)  # type: ignore[call-arg]


def test_indicator_state_factory_must_match_its_reference_declaration() -> None:
    paired = IndicatorSpec(
        name="PAIRED_PROBE",
        params={},
        version="1.0.0",
        pinned_impl="test",
        min_history=1,
        category="statistics",
        required_inputs=(),
        _vectorized=lambda candles: [1.0 for _ in candles],
        _state_factory=_PairedState,
        needs_reference_series=True,
    )
    undeclared = IndicatorSpec(
        name="UNDECLARED_PAIRED_PROBE",
        params={},
        version="1.0.0",
        pinned_impl="test",
        min_history=1,
        category="statistics",
        required_inputs=(),
        _vectorized=lambda candles: [1.0 for _ in candles],
        _state_factory=_PairedState,
    )
    invalid_paired = IndicatorSpec(
        name="INVALID_PAIRED_PROBE",
        params={},
        version="1.0.0",
        pinned_impl="test",
        min_history=1,
        category="statistics",
        required_inputs=(),
        _vectorized=lambda candles: [1.0 for _ in candles],
        _state_factory=_IndicatorState,
        needs_reference_series=True,
    )

    assert paired.needs_reference_series is True
    assert undeclared.needs_reference_series is False
    assert paired.make_paired_state().__class__ is _PairedState
    with pytest.raises(TypeError, match="does not provide a single-series state"):
        paired.make_state()
    with pytest.raises(TypeError, match="does not provide a paired-series state"):
        undeclared.make_paired_state()
    with pytest.raises(TypeError, match="does not provide a single-series state"):
        undeclared.make_state()
    with pytest.raises(TypeError, match="state is not paired"):
        ResolvedSeriesSpec(invalid_paired, "1h").make_paired_state()


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

    assert (
        _ids(
            resolve_series_specs(
                mode,
                declared,
                explicit,
                indicators,
                patterns,
                execution_timeframe="1h",
            )
        )
        == expected
    )


def test_resolve_series_specs_allows_an_empty_side_and_an_empty_union() -> None:
    indicators, patterns = _registries()

    assert _ids(
        resolve_series_specs(
            "auto",
            [{"name": "pat_doji", "params": {}}],
            (),
            indicators,
            patterns,
            execution_timeframe="1h",
        )
    ) == ["pat_doji"]
    assert _ids(
        resolve_series_specs(
            "auto",
            [{"name": "EMA", "params": {"period": 9}}],
            (),
            indicators,
            patterns,
            execution_timeframe="1h",
        )
    ) == ["EMA(period=9)"]
    # A strategy that reads only candles declares nothing and still runs.
    assert (
        resolve_series_specs(
            "auto",
            (),
            (),
            indicators,
            patterns,
            execution_timeframe="1h",
        )
        == []
    )


def test_resolve_series_specs_reports_an_unknown_name_once() -> None:
    indicators, patterns = _registries()

    with pytest.raises(KeyError, match="series is not registered in either registry: UNKNOWN"):
        resolve_series_specs(
            "auto",
            [{"name": "UNKNOWN", "params": {}}],
            (),
            indicators,
            patterns,
            execution_timeframe="1h",
        )


def test_series_descriptor_timeframe_defaults_and_rejections_are_explicit() -> None:
    indicators, patterns = _registries()
    defaulted = [{"name": "EMA", "params": {"period": 9}}]
    explicit_strategy = [{"name": "EMA", "params": {"period": 9}, "timeframe": "strategy"}]

    assert _ids(
        resolve_series_specs(
            "auto",
            defaulted,
            (),
            indicators,
            patterns,
            execution_timeframe="1h",
        )
    ) == _ids(
        resolve_series_specs(
            "auto",
            explicit_strategy,
            (),
            indicators,
            patterns,
            execution_timeframe="1h",
        )
    )

    with pytest.raises(ValueError, match="execution timeframe must be declared as 'strategy'"):
        resolve_series_specs(
            "auto",
            [{"name": "EMA", "params": {"period": 9}, "timeframe": "1h"}],
            (),
            indicators,
            patterns,
            execution_timeframe="1h",
        )
    resolved = resolve_series_specs(
        "auto",
        [{"name": "EMA", "params": {"period": 9}, "timeframe": "4h"}],
        (),
        indicators,
        patterns,
        execution_timeframe="1h",
    )
    assert [(item.identifier, item.timeframe) for item in resolved] == [("EMA(period=9)", "4h")]
    with pytest.raises(ValueError, match="exactly name, params, and optional timeframe"):
        resolve_series_specs(
            "auto",
            [{"name": "EMA", "params": {"period": 9}, "unknown": True}],
            (),
            indicators,
            patterns,
            execution_timeframe="1h",
        )


def test_resolution_deduplicates_only_the_same_registry_identity_and_timeframe() -> None:
    indicators, patterns = _registries()
    resolved = resolve_series_specs(
        "auto",
        [
            {"name": "EMA", "params": {"period": 9}},
            {"name": "EMA", "params": {"period": 9}, "timeframe": "strategy"},
            {"name": "EMA", "params": {"period": 9}, "timeframe": "4h"},
        ],
        (),
        indicators,
        patterns,
        execution_timeframe="1h",
    )

    assert [(item.identifier, item.timeframe) for item in resolved] == [
        ("EMA(period=9)", "1h"),
        ("EMA(period=9)", "4h"),
    ]


def test_decision_g_is_enforced_after_execution_key_normalization() -> None:
    indicators = IndicatorRegistry()
    indicators.register(_indicator("Pat Hammer"))
    patterns = PatternRegistry()
    patterns.register(_pattern("pat_hammer"))

    with pytest.raises(ValueError, match="execution-key normalization: pat_hammer"):
        assert_disjoint_series_registry_names(indicators, patterns)
