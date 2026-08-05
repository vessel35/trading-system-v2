"""Build the TA-Lib-backed candlestick pattern registry."""

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Final, Protocol, cast

from core_lib.patterns.registry import PatternRegistry, PatternSeries, PatternSpec, PatternState
from core_lib.patterns.talib_hikkake import TALIB_HIKKAKE_PATTERNS
from core_lib.patterns.talib_multi_candle import TALIB_MULTI_CANDLE_PATTERNS
from core_lib.patterns.talib_raw import TALIB_CDL_PATTERN_COUNT, TALIB_SOURCE_VERSION
from core_lib.patterns.talib_single_candle import TALIB_SINGLE_CANDLE_PATTERNS
from core_lib.patterns.talib_three_candle import TALIB_THREE_CANDLE_PATTERNS
from core_lib.patterns.talib_two_candle import TALIB_TWO_CANDLE_PATTERNS
from core_lib.types import Candle

TALIB_PATTERN_REGISTRY_VERSION: Final = f"2.0.0+talib.{TALIB_SOURCE_VERSION}"
"""Pattern calculation version for the TA-Lib v0.7.1 registry cutover."""


class _TalibRegistryPort(Protocol):
    name: str
    talib_function: str
    min_history: int

    def compute_vectorized(self, candles: Sequence[Candle]) -> PatternSeries: ...

    def make_state(self) -> PatternState: ...


TALIB_GROUP_PORTS: Mapping[str, tuple[_TalibRegistryPort, ...]] = MappingProxyType(
    {
        "single_candle": cast(tuple[_TalibRegistryPort, ...], TALIB_SINGLE_CANDLE_PATTERNS),
        "two_candle": cast(tuple[_TalibRegistryPort, ...], TALIB_TWO_CANDLE_PATTERNS),
        "three_candle": cast(tuple[_TalibRegistryPort, ...], TALIB_THREE_CANDLE_PATTERNS),
        "multi_candle": cast(tuple[_TalibRegistryPort, ...], TALIB_MULTI_CANDLE_PATTERNS),
        "hikkake": cast(tuple[_TalibRegistryPort, ...], TALIB_HIKKAKE_PATTERNS),
    }
)
TALIB_GROUPS: tuple[str, ...] = tuple(TALIB_GROUP_PORTS)


def _talib_functions_by_pattern() -> Mapping[str, str]:
    """Return the TA-Lib CDL function name for every ported pattern name."""
    functions: dict[str, str] = {}
    for ports in TALIB_GROUP_PORTS.values():
        for port in ports:
            talib_function = port.talib_function
            if port.name in functions:
                raise ValueError(f"TA-Lib pattern is registered twice: {port.name}")
            if talib_function in functions.values():
                raise ValueError(f"TA-Lib function is registered twice: {talib_function}")
            functions[port.name] = talib_function
    return MappingProxyType(functions)


TALIB_FUNCTIONS: Mapping[str, str] = _talib_functions_by_pattern()
"""TA-Lib CDL function names keyed by the public pattern registry name."""


def _talib_spec_for(port: _TalibRegistryPort) -> PatternSpec:
    """Adapt one TA-Lib port to the shared seven-member consumption contract."""
    return PatternSpec(
        name=port.name,
        params={},
        version=TALIB_PATTERN_REGISTRY_VERSION,
        _vectorized=port.compute_vectorized,
        _state_factory=port.make_state,
        explicit_min_history=port.min_history,
    )


def talib_all_specs() -> tuple[PatternSpec, ...]:
    """Return every TA-Lib registered pattern spec in a fixed group order."""
    return tuple(_talib_spec_for(port) for ports in TALIB_GROUP_PORTS.values() for port in ports)


def build_talib_pattern_registry() -> PatternRegistry:
    """Build the TA-Lib-backed registry used by runtime consumers."""
    registry = PatternRegistry()
    for spec in talib_all_specs():
        registry.register(spec)
    return registry


TALIB_PATTERN_REGISTRY = build_talib_pattern_registry()
"""The TA-Lib v0.7.1 pattern registry used by the public package default."""


def _assert_talib_registry_complete() -> None:
    """Fail import when the function map and runtime registry stop matching."""
    registry_names = TALIB_PATTERN_REGISTRY.names()
    function_names = set(TALIB_FUNCTIONS)
    if (
        len(registry_names) != TALIB_CDL_PATTERN_COUNT
        or len(function_names) != TALIB_CDL_PATTERN_COUNT
        or registry_names != function_names
    ):
        missing_functions = sorted(registry_names - function_names)
        missing_specs = sorted(function_names - registry_names)
        raise RuntimeError(
            "TA-Lib pattern registry/function map is incomplete: "
            f"missing_functions={missing_functions}, missing_specs={missing_specs}, "
            f"registry_count={len(registry_names)}, function_count={len(function_names)}, "
            f"expected_count={TALIB_CDL_PATTERN_COUNT}"
        )


_assert_talib_registry_complete()
