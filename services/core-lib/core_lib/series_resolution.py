"""Resolve shared indicator and candlestick-pattern series selections."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass

from core_lib.indicators.registry import IndicatorRegistry
from core_lib.patterns.registry import PatternRegistry
from core_lib.series import SeriesSpec, normalize_series_name
from core_lib.series import series_key as series_key


@dataclass(frozen=True, slots=True)
class SplitSeriesDescriptors:
    """Descriptors separated by the registry that owns their names."""

    indicators: tuple[Mapping[str, object], ...]
    patterns: tuple[Mapping[str, object], ...]


def assert_disjoint_series_registry_names(
    indicators: IndicatorRegistry,
    patterns: PatternRegistry,
) -> None:
    """Enforce Decision G at raw-name and execution-key levels."""
    indicator_names = {spec.name for spec in indicators.list()}
    pattern_names = patterns.names()
    raw_overlap = sorted(indicator_names & pattern_names)
    if raw_overlap:
        raise ValueError("indicator and pattern registry names overlap: " + ", ".join(raw_overlap))

    indicator_keys = _name_key_map(indicator_names)
    pattern_keys = _name_key_map(pattern_names)
    normalized_overlap = sorted(set(indicator_keys) & set(pattern_keys))
    if normalized_overlap:
        details = ", ".join(
            f"{key} (indicator={indicator_keys[key]}, pattern={pattern_keys[key]})"
            for key in normalized_overlap
        )
        raise ValueError(
            "indicator and pattern registry names overlap after execution-key "
            f"normalization: {details}"
        )


def split_series_descriptors(
    descriptors: Collection[Mapping[str, object]],
    indicators: IndicatorRegistry,
    patterns: PatternRegistry,
) -> SplitSeriesDescriptors:
    """Route descriptors by case-insensitive registry name ownership."""
    assert_disjoint_series_registry_names(indicators, patterns)
    indicator_names = {spec.name.casefold() for spec in indicators.list()}
    pattern_names = {name.casefold() for name in patterns.names()}
    indicator_descriptors: list[Mapping[str, object]] = []
    pattern_descriptors: list[Mapping[str, object]] = []

    for descriptor in descriptors:
        name, params = _descriptor_parts(descriptor)
        folded = name.casefold()
        in_indicators = folded in indicator_names
        in_patterns = folded in pattern_names
        if in_indicators and in_patterns:
            raise ValueError(f"series name is registered in both registries: {name}")
        if in_indicators:
            indicator_descriptors.append(descriptor)
        elif in_patterns:
            pattern_descriptors.append(descriptor)
        else:
            raise KeyError(f"series is not registered in either registry: {name} {dict(params)}")

    return SplitSeriesDescriptors(tuple(indicator_descriptors), tuple(pattern_descriptors))


def series_specs_from_descriptors(
    descriptors: Collection[Mapping[str, object]],
    indicators: IndicatorRegistry,
    patterns: PatternRegistry,
) -> list[SeriesSpec]:
    """Resolve descriptors from both registries without requiring a non-empty result."""
    split = split_series_descriptors(descriptors, indicators, patterns)
    return [
        *indicators.specs_from_descriptors(split.indicators),
        *patterns.specs_from_descriptors(split.patterns),
    ]


def resolve_series_specs(
    mode: str,
    declared: Collection[Mapping[str, object]],
    explicit: Collection[Mapping[str, object]],
    indicators: IndicatorRegistry,
    patterns: PatternRegistry,
) -> list[SeriesSpec]:
    """Resolve auto, explicit, or all selections across both registries.

    ``all`` keeps its historical indicator meaning: every registered indicator.
    Patterns are enabled only when the strategy declared them.
    """
    if mode not in {"auto", "explicit", "all"}:
        raise ValueError("indicator mode must be auto, explicit, or all")

    declared_split = split_series_descriptors(declared, indicators, patterns)
    explicit_split = split_series_descriptors(explicit, indicators, patterns)
    specs: list[SeriesSpec] = []
    if mode == "auto":
        specs.extend(indicators.specs_from_descriptors(declared_split.indicators))
        specs.extend(patterns.specs_from_descriptors(declared_split.patterns))
    elif mode == "explicit":
        specs.extend(indicators.specs_from_descriptors(explicit_split.indicators))
        specs.extend(patterns.specs_from_descriptors(explicit_split.patterns))
    else:
        specs.extend(indicators.list())
        specs.extend(patterns.specs_from_descriptors(declared_split.patterns))

    if not specs:
        raise ValueError("a series selection must resolve at least one spec")
    return specs


def _descriptor_parts(
    descriptor: Mapping[str, object],
) -> tuple[str, Mapping[str, object]]:
    if set(descriptor) != {"name", "params"}:
        raise ValueError("series descriptor must contain exactly name and params")
    name = descriptor["name"]
    params = descriptor["params"]
    if not isinstance(name, str) or not isinstance(params, Mapping):
        raise TypeError("series descriptor name/params have invalid types")
    return name, params


def _name_key_map(names: Collection[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in sorted(names):
        result.setdefault(normalize_series_name(name), name)
    return result
