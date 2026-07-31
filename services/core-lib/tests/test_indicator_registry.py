"""Verify spec identity, selection, validation, and implementation pinning."""

from datetime import UTC, datetime, timedelta
from math import isnan, sin
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


# The registry is pinned by the exact set of registered identities rather than by
# a count. A count says only that the number moved; this says which combination
# appeared or disappeared, and it still refuses a silent addition or removal.
REGISTERED_IDENTIFIERS = frozenset(
    {
        "ATR(period=14)",
        "Bollinger Bands(multiplier=2.0,period=20)",
        "EMA(period=9)",
        "EMA(period=21)",
        "EMA(period=55)",
        "EMA(period=200)",
        "RSI(period=14)",
        "Stochastic(period=14,smooth_period=3)",
        "Volume SMA(period=20)",
    }
)


def test_registry_contains_required_coverage_and_pinned_authority() -> None:
    specs = DEFAULT_REGISTRY.list()
    assert {spec.identifier for spec in specs} == REGISTERED_IDENTIFIERS
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
    # The standard carries 82 systems; the registered ones and this catalog must
    # account for all of them, so the catalog length follows from the registry
    # instead of being written down twice.
    registered_systems = 6
    assert len(follow_up) == 82 - registered_systems
    assert len(set(follow_up)) == len(follow_up)


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
    assert DEFAULT_REGISTRY.resolve_enabled("explicit", {"RSI"}, {"ATR"}) == {"ATR"}
    assert DEFAULT_REGISTRY.resolve_enabled("all", set(), set()) == set(REGISTERED_IDENTIFIERS)
    with pytest.raises(ValueError, match="auto, explicit, or all"):
        DEFAULT_REGISTRY.resolve_enabled("unknown", set(), set())


def test_resolve_specs_is_the_single_descriptor_and_mode_interpreter() -> None:
    declared = [{"name": "ema", "params": {"period": 9}}]
    explicit = [{"name": "ATR", "params": {"period": 14}}]

    auto = DEFAULT_REGISTRY.resolve_specs("auto", declared, explicit)
    selected = DEFAULT_REGISTRY.resolve_specs("explicit", declared, explicit)
    all_specs = DEFAULT_REGISTRY.resolve_specs("all", declared, ())

    assert [spec.identifier for spec in auto] == ["EMA(period=9)"]
    assert [spec.identifier for spec in selected] == ["ATR(period=14)"]
    assert {spec.identifier for spec in all_specs} == REGISTERED_IDENTIFIERS


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


def test_every_spec_min_history_matches_its_state_min_history() -> None:
    """The two declarations of minimum history must agree for every spec.

    `IndicatorSpec.min_history` decides how much history a run fetches, while the
    incremental state's own `min_history` decides when that state calls itself
    warmed up. They are written in different files, so nothing but this check
    stops them from drifting apart; a drift shows up much later as a warm-up that
    is one candle short.
    """

    mismatched = [
        (spec.identifier, spec.min_history, spec.make_state().min_history)
        for spec in DEFAULT_REGISTRY.list()
        if spec.make_state().min_history != spec.min_history
    ]
    assert mismatched == []


def test_warmed_up_state_agrees_with_declared_min_history() -> None:
    """A state must be warm exactly once it has seen its declared minimum."""

    candles = make_candles(260)
    for spec in DEFAULT_REGISTRY.list():
        state = spec.make_state()
        state.seed(candles[: spec.min_history - 1])
        assert not state.warmed_up, f"{spec.identifier} warmed up early"
        state.update(candles[spec.min_history - 1])
        assert state.warmed_up, f"{spec.identifier} not warm at its declared minimum"


def test_only_the_standard_undefined_outputs_are_declared() -> None:
    """A spec may excuse a NaN only where the standard leaves the value undefined.

    §3.10 writes "분모 0 → 미정의" for Bollinger %B, so a collapsed band has no
    relative position to report. Nothing else in the registered set has such a
    clause, and this test is what keeps the excuse from spreading to indicators
    whose sections do define a substitute.
    """

    declared = {
        spec.identifier: spec.undefined_outputs
        for spec in DEFAULT_REGISTRY.list()
        if spec.undefined_outputs
    }
    assert declared == {"Bollinger Bands(multiplier=2.0,period=20)": ("percent_b",)}


def test_bollinger_leaves_percent_b_undefined_on_a_flat_window() -> None:
    """A perfectly flat window collapses the band, and %B stays NaN there."""

    spec = DEFAULT_REGISTRY.get("Bollinger Bands", {"period": 20, "multiplier": 2.0})
    base = make_candles(20)
    flat = [
        Candle(
            symbol=candle.symbol,
            exchange=candle.exchange,
            timeframe=candle.timeframe,
            open_time=candle.open_time,
            close_time=candle.close_time,
            open=100.0,
            high=100.0,
            low=100.0,
            close=100.0,
            volume=candle.volume,
            quote_volume=None,
            trade_count=None,
        )
        for candle in base
    ]
    state = spec.make_state()
    value = state.update(flat[0])
    for candle in flat[1:]:
        value = state.update(candle)

    assert isinstance(value, dict)
    assert value["middle"] == pytest.approx(100.0)
    assert isnan(value["percent_b"])
    assert "percent_b" in spec.undefined_outputs
