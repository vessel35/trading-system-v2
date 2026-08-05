"""Preserve the TA-Lib pattern cutover contract after legacy tests are retired."""

import math
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta

import pytest
from core_lib.indicators import DEFAULT_REGISTRY
from core_lib.patterns import (
    DEFAULT_PATTERN_REGISTRY,
    MATCHED,
    NOT_MATCHED,
    TALIB_CDL_PATTERN_COUNT,
    TALIB_PATTERN_REGISTRY_VERSION,
)
from core_lib.patterns.outputs import (
    BOUNDARY_STRENGTH,
    FULL_STRENGTH,
    assert_pattern_name,
    match_outputs,
    no_match_outputs,
    output_keys,
    undetermined_outputs,
)
from core_lib.patterns.registry import (
    PatternRegistry,
    PatternSeries,
    PatternSpec,
    PatternState,
    PatternValue,
)
from core_lib.patterns.specs import TALIB_GROUP_PORTS
from core_lib.patterns.talib_raw import (
    TALIB_PENETRATION_DEFAULTS,
    sparse_talib_integer_signals,
    talib_integer_from_outputs,
    validate_talib_version_pin,
)
from core_lib.series import SeriesSpec, SeriesState
from core_lib.types import Candle

import pattern_reference.series as reference_series
from pattern_reference import (
    CAPTURE_INSTRUCTIONS,
    CAPTURED,
    REGIME_NAMES,
    REGIMES,
    REGIMES_BY_NAME,
    SIGNALS,
    TOTAL_BAR_COUNT,
    candles_for,
    fingerprints,
    talib_signals,
)

_NEEDS_CAPTURE = pytest.mark.skipif(not CAPTURED, reason=CAPTURE_INSTRUCTIONS)
_ALLOWED_HISTORICAL_SEED_KEYS = frozenset({"mixed_hourly"})


class _ExampleState:
    """Tiny state used to test the public PatternSpec/PatternRegistry contract."""

    min_history = 3

    def __init__(self) -> None:
        self._seen = 0
        self._current = undetermined_outputs("pat_example")

    @property
    def warmed_up(self) -> bool:
        return self._seen >= self.min_history

    def seed(self, candles: Sequence[Candle]) -> None:
        self._seen = 0
        self._current = undetermined_outputs("pat_example")
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> PatternValue:
        del candle
        self._seen += 1
        self._current = (
            no_match_outputs("pat_example")
            if self.warmed_up
            else undetermined_outputs("pat_example")
        )
        return self.current()

    def current(self) -> PatternValue:
        return self._current


def _make_candle(index: int, price: float = 100.0) -> Candle:
    open_time = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=index)
    return Candle(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe="1h",
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open=price,
        high=price + 1.0,
        low=price - 1.0,
        close=price + 0.25,
        volume=1000.0,
        quote_volume=None,
        trade_count=None,
    )


def _example_series(candles: Sequence[Candle]) -> PatternSeries:
    state = _ExampleState()
    return [state.update(candle) for candle in candles]


def _make_spec(name: str = "pat_example", **overrides: object) -> PatternSpec:
    fields: dict[str, object] = {
        "name": name,
        "params": {},
        "version": TALIB_PATTERN_REGISTRY_VERSION,
        "_vectorized": _example_series,
        "_state_factory": _ExampleState,
        "explicit_min_history": _ExampleState.min_history,
    }
    fields.update(overrides)
    return PatternSpec(**fields)  # type: ignore[arg-type]


def _assert_same_value(
    name: str, index: int, left: Mapping[str, float], right: Mapping[str, float]
) -> None:
    assert left.keys() == right.keys(), f"{name} index {index}"
    for key, left_number in left.items():
        right_number = right[key]
        if math.isnan(left_number):
            assert math.isnan(right_number), f"{name} index {index} key {key}"
        else:
            assert left_number == right_number, f"{name} index {index} key {key}"


def _assert_same_series(
    name: str,
    left: Sequence[PatternValue],
    right: Sequence[PatternValue],
) -> None:
    assert len(left) == len(right)
    for index, (left_value, right_value) in enumerate(zip(left, right, strict=True)):
        _assert_same_value(name, index, left_value, right_value)


def _talib_ports_by_name() -> dict[str, object]:
    return {port.name: port for ports in TALIB_GROUP_PORTS.values() for port in ports}


def _talib_functions() -> dict[str, str]:
    return {
        port.name: port.talib_function for ports in TALIB_GROUP_PORTS.values() for port in ports
    }


def _all_values_nan(value: Mapping[str, float]) -> bool:
    return all(math.isnan(number) for number in value.values())


def _all_values_finite(value: Mapping[str, float]) -> bool:
    return all(math.isfinite(number) for number in value.values())


def _assert_not_warmed_up(state: PatternState, message: str) -> None:
    assert not state.warmed_up, message


def _pattern_targeting_terms() -> frozenset[str]:
    terms: set[str] = set()
    for pattern, talib_function in _talib_functions().items():
        for term in (pattern.removeprefix("pat_"), talib_function.removeprefix("CDL")):
            normalized = term.casefold()
            terms.add(normalized)
            terms.add(re.sub(r"[^a-z0-9]+", "", normalized))
    return frozenset(term for term in terms if term)


def _regime_targeting_matches(text: str) -> tuple[str, ...]:
    matches = set(
        re.findall(
            r"\bCDL[A-Z0-9]*\b|§|\bpat_[a-z0-9_]+\b|\bTA[- ]?Lib\b",
            text,
            flags=re.IGNORECASE,
        )
    )
    folded = text.casefold()
    compact = re.sub(r"[^a-z0-9]+", "", folded)
    for term in _pattern_targeting_terms():
        if term in folded or re.sub(r"[^a-z0-9]+", "", term) in compact:
            matches.add(term)
    return tuple(sorted(matches))


@_NEEDS_CAPTURE
def test_capture_still_describes_the_current_regime_bundle() -> None:
    assert set(talib_signals.SERIES_FINGERPRINTS) == set(REGIME_NAMES)
    assert set(talib_signals.BAR_COUNTS) == set(REGIME_NAMES)
    assert set(SIGNALS) == set(REGIME_NAMES)
    assert dict(talib_signals.SERIES_FINGERPRINTS) == fingerprints()

    for regime in REGIMES:
        assert talib_signals.BAR_COUNTS[regime.name] == regime.bar_count
    assert sum(talib_signals.BAR_COUNTS.values()) == TOTAL_BAR_COUNT == 22_000
    validate_talib_version_pin(
        talib_signals.TALIB_VERSION,
        talib_signals.TALIB_UNDERLYING_VERSION,
    )


def test_regime_names_descriptions_and_seed_bypasses_cannot_target_patterns() -> None:
    for regime in REGIMES:
        for field_name, text in (("name", regime.name), ("character", regime.character)):
            found = _regime_targeting_matches(text)
            assert not found, f"{regime.name} {field_name} targets the capture with {found}"

    assert set(reference_series._HISTORICAL_SEEDS) <= _ALLOWED_HISTORICAL_SEED_KEYS


@pytest.mark.parametrize("targeted_name", ["tri_star", "tristar"])
def test_regime_targeting_guard_catches_separated_and_compact_pattern_names(
    targeted_name: str,
) -> None:
    assert _regime_targeting_matches(targeted_name)


def test_vectorized_prefixes_are_invariant_when_the_series_tail_is_removed() -> None:
    checked = 0
    for spec in DEFAULT_PATTERN_REGISTRY.list():
        for regime in REGIME_NAMES:
            candles = candles_for(regime)
            prefix_length = spec.min_history + 40
            whole = spec.compute_vectorized(candles)
            prefix = spec.compute_vectorized(candles[:prefix_length])

            _assert_same_series(spec.name, whole[:prefix_length], prefix)
            checked += 1

    assert checked == TALIB_CDL_PATTERN_COUNT * len(REGIME_NAMES) == 427


def test_all_talib_pattern_states_honor_seed_warmup_and_current_contract() -> None:
    checked = 0
    for spec in DEFAULT_PATTERN_REGISTRY.list():
        for regime in REGIME_NAMES:
            candles = candles_for(regime)
            vector = spec.compute_vectorized(candles)
            state = spec.make_state()

            assert state.min_history == spec.min_history
            _assert_not_warmed_up(state, f"{spec.name}/{regime} started warm")
            assert _all_values_nan(state.current())

            for index, candle in enumerate(candles[: spec.min_history - 1]):
                value = state.update(candle)
                _assert_not_warmed_up(
                    state,
                    f"{spec.name}/{regime} warmed early at {index}",
                )
                assert _all_values_nan(value)
                _assert_same_value(spec.name, index, value, state.current())

            boundary_index = spec.min_history - 1
            boundary_value = state.update(candles[boundary_index])
            assert state.warmed_up, f"{spec.name}/{regime} did not warm at {boundary_index}"
            assert _all_values_finite(boundary_value)
            _assert_same_value(spec.name, boundary_index, vector[boundary_index], boundary_value)
            _assert_same_value(spec.name, boundary_index, boundary_value, state.current())

            replayed = spec.make_state()
            for candle in candles[: spec.min_history + 17]:
                replayed.update(candle)
            seeded = spec.make_state()
            seeded.seed(candles[: spec.min_history + 17])
            seeded.seed(candles[: spec.min_history + 17])

            assert seeded.warmed_up == replayed.warmed_up
            _assert_same_value(
                spec.name, spec.min_history + 16, replayed.current(), seeded.current()
            )
            checked += 1

    assert checked == TALIB_CDL_PATTERN_COUNT * len(REGIME_NAMES) == 427


@_NEEDS_CAPTURE
def test_degenerate_captured_bar_stays_nan_only_during_warmup_then_finite_and_captured() -> None:
    regime = "quiet_small_bodies"
    candles = candles_for(regime)
    degenerate_indexes = [
        index
        for index, candle in enumerate(candles)
        if candle.open == candle.high == candle.low == candle.close
    ]
    assert degenerate_indexes == [835]
    degenerate_index = degenerate_indexes[0]

    function_by_pattern = _talib_functions()
    checked = 0
    for spec in DEFAULT_PATTERN_REGISTRY.list():
        values = spec.compute_vectorized(candles)
        assert _all_values_nan(values[0])
        assert degenerate_index >= spec.min_history - 1
        assert _all_values_finite(values[degenerate_index])

        talib_function = function_by_pattern[spec.name]
        actual = talib_integer_from_outputs(spec.name, values[degenerate_index])
        expected = SIGNALS[regime][talib_function].get(degenerate_index, 0)
        assert actual == expected, f"{spec.name}/{talib_function} at {degenerate_index}"
        checked += 1

    assert checked == TALIB_CDL_PATTERN_COUNT


def test_output_builders_keep_the_four_key_contract() -> None:
    assert output_keys("pat_hammer") == (
        "pat_hammer",
        "pat_hammer_dir",
        "pat_hammer_strength",
        "pat_hammer_confirm",
    )
    assert set(undetermined_outputs("pat_hammer")) == set(output_keys("pat_hammer"))
    assert _all_values_nan(undetermined_outputs("pat_hammer"))
    assert no_match_outputs("pat_hammer") == {
        "pat_hammer": NOT_MATCHED,
        "pat_hammer_dir": NOT_MATCHED,
        "pat_hammer_strength": NOT_MATCHED,
        "pat_hammer_confirm": NOT_MATCHED,
    }
    assert match_outputs("pat_hammer", direction=1.0) == {
        "pat_hammer": MATCHED,
        "pat_hammer_dir": 1.0,
        "pat_hammer_strength": FULL_STRENGTH,
        "pat_hammer_confirm": NOT_MATCHED,
    }
    assert match_outputs("pat_hammer", direction=-1.0, strength=BOUNDARY_STRENGTH) == {
        "pat_hammer": MATCHED,
        "pat_hammer_dir": -1.0,
        "pat_hammer_strength": BOUNDARY_STRENGTH,
        "pat_hammer_confirm": NOT_MATCHED,
    }
    with pytest.raises(ValueError):
        assert_pattern_name("hammer")
    with pytest.raises(ValueError):
        assert_pattern_name("pat_hammer_dir")
    with pytest.raises(ValueError, match="direction"):
        match_outputs("pat_hammer", direction=2.0)


def test_pattern_spec_and_registry_keep_the_shared_consumption_contract() -> None:
    spec = _make_spec(params={"n": 3})
    assert spec.identifier == "pat_example(n=3)"
    assert spec.min_history == _ExampleState.min_history
    assert spec.undefined_outputs == ()
    assert dict(spec.params) == {"n": 3}
    with pytest.raises(TypeError):
        spec.params["n"] = 4  # type: ignore[index]

    registry = PatternRegistry()
    registry.register(spec)
    assert registry.names() == {"pat_example"}
    assert registry.get("pat_example", {"n": 3}) == spec
    descriptors = [{"name": "pat_example", "params": {"n": 3}}]
    assert registry.specs_from_descriptors(descriptors) == [spec]
    assert registry.resolve_specs("auto", descriptors, []) == [spec]
    assert registry.resolve_specs("explicit", [], descriptors) == [spec]
    assert registry.resolve_specs("all", [], []) == [spec]

    with pytest.raises(ValueError, match="already registered"):
        registry.register(spec)
    with pytest.raises(KeyError):
        registry.specs_from_descriptors([{"name": "pat_missing", "params": {}}])
    with pytest.raises(ValueError, match="exactly name and params"):
        registry.specs_from_descriptors([{"name": "pat_example"}])
    with pytest.raises(ValueError, match="pattern mode"):
        registry.resolve_specs("everything", [], [])

    candles = [_make_candle(index) for index in range(2)]
    with pytest.raises(ValueError, match="requires 3 candles"):
        registry.compute_batch(candles, {"pat_example(n=3)"})


def test_pattern_specs_satisfy_the_shared_series_protocol_without_expanding_it() -> None:
    pattern: SeriesSpec = DEFAULT_PATTERN_REGISTRY.list()[0]
    state: SeriesState = pattern.make_state()

    assert isinstance(pattern, SeriesSpec)
    assert isinstance(state, SeriesState)
    assert set(vars(SeriesSpec)) - {name for name in vars(SeriesSpec) if name.startswith("_")} == {
        "identifier",
        "name",
        "params",
        "version",
        "min_history",
        "undefined_outputs",
        "make_state",
    }
    assert set(vars(SeriesState)) - {
        name for name in vars(SeriesState) if name.startswith("_")
    } == {"seed", "warmed_up", "update"}
    assert not hasattr(SeriesState, "current")
    assert all(not spec.name.startswith("pat_") for spec in DEFAULT_REGISTRY.list())


@_NEEDS_CAPTURE
def test_capture_records_every_talib_function_and_optional_argument_default() -> None:
    function_by_pattern = _talib_functions()
    function_names = set(function_by_pattern.values())
    assert len(function_by_pattern) == TALIB_CDL_PATTERN_COUNT
    assert len(function_names) == TALIB_CDL_PATTERN_COUNT

    for regime in REGIME_NAMES:
        assert set(SIGNALS[regime]) == function_names

    assert dict(talib_signals.FUNCTION_PARAMETERS) == {
        function: {"penetration": value} for function, value in TALIB_PENETRATION_DEFAULTS.items()
    }
    assert set(talib_signals.FUNCTION_PARAMETERS) <= function_names


@_NEEDS_CAPTURE
def test_registered_talib_specs_match_capture_on_all_regime_pattern_pairs() -> None:
    function_by_pattern = _talib_functions()
    checked = 0
    compared_bars = 0
    for spec in DEFAULT_PATTERN_REGISTRY.list():
        talib_function = function_by_pattern[spec.name]
        for regime in REGIME_NAMES:
            candles = candles_for(regime)
            actual = sparse_talib_integer_signals(spec.name, spec.compute_vectorized(candles))
            expected = dict(SIGNALS[regime][talib_function])

            assert actual == expected, f"{spec.name}/{talib_function} on {regime}"
            checked += 1
            compared_bars += REGIMES_BY_NAME[regime].bar_count

    assert checked == TALIB_CDL_PATTERN_COUNT * len(REGIME_NAMES) == 427
    assert compared_bars == TALIB_CDL_PATTERN_COUNT * TOTAL_BAR_COUNT == 1_342_000
