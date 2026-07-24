"""Verify spec identity, selection, validation, and implementation pinning."""

from datetime import UTC, datetime, timedelta
from math import sin
from typing import cast

import pytest
from core_lib.indicators import (
    bill_williams,
    breadth,
    cycle,
    donchian,
    momentum,
    strength,
    systems,
    trend,
    volatility,
    volume,
)
from core_lib.indicators.contracts import UnfinalizedCandleError
from core_lib.indicators.registry import (
    DEFAULT_REGISTRY,
    IndicatorParam,
    IndicatorRegistry,
    IndicatorSpec,
    build_default_registry,
)
from core_lib.types import Candle


def make_candles(count: int) -> list[Candle]:
    candles: list[Candle] = []
    start = datetime(2025, 1, 1, tzinfo=UTC)
    previous_close = 100.0
    for index in range(count):
        close = 100.0 + 0.15 * index + sin(index / 5.0)
        open_time = start + timedelta(hours=index)
        candles.append(
            Candle(
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe="1h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open=previous_close,
                high=max(previous_close, close) + 1.0,
                low=min(previous_close, close) - 1.0,
                close=close,
                volume=1000.0 + index,
                quote_volume=None,
                trade_count=None,
            )
        )
        previous_close = close
    return candles


def test_registry_contains_required_coverage_and_pinned_authority() -> None:
    specs = DEFAULT_REGISTRY.list()
    assert len(specs) == 9
    assert {spec.name for spec in specs} == {
        "EMA",
        "RSI",
        "Stochastic",
        "ATR",
        "Bollinger Bands",
        "Volume SMA",
    }
    for spec in specs:
        expected_version = "1.0.1" if spec.name == "Bollinger Bands" else "1.0.0"
        assert spec.version == expected_version
        assert "technical_indicators_calc_spec.md §" in spec.pinned_impl
        assert spec.min_history > 0


def test_follow_up_catalog_preserves_all_76_not_yet_registered_items() -> None:
    follow_up = (
        trend.FOLLOW_UP_INDICATORS
        + momentum.FOLLOW_UP_INDICATORS
        + volatility.FOLLOW_UP_INDICATORS
        + volume.FOLLOW_UP_INDICATORS
        + strength.FOLLOW_UP_INDICATORS
        + bill_williams.FOLLOW_UP_INDICATORS
        + breadth.FOLLOW_UP_INDICATORS
        + cycle.FOLLOW_UP_INDICATORS
        + systems.FOLLOW_UP_INDICATORS
        + donchian.FOLLOW_UP_INDICATORS
    )
    assert len(follow_up) == 76
    assert len(set(follow_up)) == 76


def test_specs_are_immutable_and_parameterized_identity_is_exact() -> None:
    spec = DEFAULT_REGISTRY.get("EMA", {"period": 9})
    mutable_view = cast(dict[str, IndicatorParam], spec.params)
    with pytest.raises(TypeError):
        mutable_view["period"] = 21
    with pytest.raises(KeyError, match="not registered"):
        DEFAULT_REGISTRY.get("EMA", {"period": 10})


def test_register_rejects_duplicate_identity() -> None:
    registry = build_default_registry()
    with pytest.raises(ValueError, match="already registered"):
        registry.register(registry.get("RSI", {"period": 14}))


def test_resolve_enabled_supports_auto_explicit_and_all() -> None:
    assert DEFAULT_REGISTRY.resolve_enabled("auto", {"RSI"}, {"ATR"}) == {"RSI"}
    assert DEFAULT_REGISTRY.resolve_enabled("explicit", {"RSI"}, {"ATR"}) == {
        "RSI",
        "ATR",
    }
    assert len(DEFAULT_REGISTRY.resolve_enabled("all", set(), set())) == 9
    with pytest.raises(ValueError, match="auto, explicit, or all"):
        DEFAULT_REGISTRY.resolve_enabled("unknown", set(), set())


def test_resolve_specs_is_the_single_descriptor_and_mode_interpreter() -> None:
    declared = [{"name": "ema", "params": {"period": 9}}]
    explicit = [{"name": "ATR", "params": {"period": 14}}]

    auto = DEFAULT_REGISTRY.resolve_specs("auto", declared, explicit)
    selected = DEFAULT_REGISTRY.resolve_specs("explicit", declared, explicit)
    all_specs = DEFAULT_REGISTRY.resolve_specs("all", declared, ())

    assert [spec.identifier for spec in auto] == ["EMA(period=9)"]
    assert [spec.identifier for spec in selected] == [
        "ATR(period=14)",
        "EMA(period=9)",
    ]
    assert len(all_specs) == 9


def test_resolve_specs_rejects_invalid_or_empty_descriptor_selection() -> None:
    with pytest.raises(ValueError, match="exactly name and params"):
        DEFAULT_REGISTRY.resolve_specs(
            "auto",
            [{"name": "RSI", "params": {"period": 14}, "extra": True}],
            (),
        )
    with pytest.raises(KeyError, match="not registered"):
        DEFAULT_REGISTRY.resolve_specs(
            "auto",
            [{"name": "RSI", "params": {"period": 10}}],
            (),
        )
    with pytest.raises(ValueError, match="at least one spec"):
        DEFAULT_REGISTRY.resolve_specs("auto", (), ())


def test_batch_computes_only_selected_registered_specs() -> None:
    candles = make_candles(30)
    result = DEFAULT_REGISTRY.compute_batch(
        candles,
        {"EMA(period=9)", "RSI"},
        decision_time=candles[-1].close_time,
    )
    assert set(result) == {"EMA(period=9)", "RSI(period=14)"}
    assert all(len(series) == len(candles) for series in result.values())


def test_batch_rejects_insufficient_history_and_unfinalized_tail() -> None:
    candles = make_candles(10)
    with pytest.raises(ValueError, match="requires 14 candles"):
        DEFAULT_REGISTRY.compute_batch(candles, {"ATR"})
    with pytest.raises(UnfinalizedCandleError):
        DEFAULT_REGISTRY.compute_batch(
            candles,
            {"EMA(period=9)"},
            decision_time=candles[-1].close_time - timedelta(microseconds=1),
        )


def test_batch_skips_specs_without_their_declared_input_channels() -> None:
    source = DEFAULT_REGISTRY.get("RSI", {"period": 14})
    conditional = IndicatorSpec(
        name="Conditional RSI",
        params={"period": 14},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §2.1",
        min_history=15,
        category="breadth",
        required_inputs=("advances",),
        _vectorized=source._vectorized,
        _state_factory=source._state_factory,
    )
    registry = IndicatorRegistry()
    registry.register(conditional)
    candles = make_candles(20)
    assert registry.compute_batch(candles, {"Conditional RSI"}) == {}
    assert set(
        registry.compute_batch(
            candles,
            {"Conditional RSI"},
            available_inputs={"advances"},
        )
    ) == {"Conditional RSI(period=14)"}
