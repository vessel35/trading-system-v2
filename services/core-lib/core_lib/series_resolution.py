"""Resolve shared indicator and candlestick-pattern series selections."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import cast

from core_lib.indicators.registry import IndicatorRegistry
from core_lib.patterns.registry import PatternRegistry
from core_lib.series import (
    SeriesParam,
    SeriesSpec,
    SeriesState,
    normalize_series_name,
    resolve_series_timeframe,
    series_descriptor_parts,
)
from core_lib.series import series_key as series_key


@dataclass(frozen=True, slots=True)
class SplitSeriesDescriptors:
    """Descriptors separated by the registry that owns their names."""

    indicators: tuple[Mapping[str, object], ...]
    patterns: tuple[Mapping[str, object], ...]


@dataclass(frozen=True, slots=True)
class ResolvedSeriesSpec:
    """Bind one registry calculation to the concrete timeframe it runs on."""

    spec: SeriesSpec
    timeframe: str

    @property
    def identifier(self) -> str:
        return self.spec.identifier

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def params(self) -> Mapping[str, SeriesParam]:
        return self.spec.params

    @property
    def version(self) -> str:
        return self.spec.version

    @property
    def min_history(self) -> int:
        return self.spec.min_history

    @property
    def undefined_outputs(self) -> tuple[str, ...]:
        return self.spec.undefined_outputs

    def make_state(self) -> SeriesState:
        return self.spec.make_state()


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
    *,
    execution_timeframe: str,
) -> SplitSeriesDescriptors:
    """Route descriptors by case-insensitive registry name ownership."""
    assert_disjoint_series_registry_names(indicators, patterns)
    indicator_names = {spec.name.casefold() for spec in indicators.list()}
    pattern_names = {name.casefold() for name in patterns.names()}
    indicator_descriptors: list[Mapping[str, object]] = []
    pattern_descriptors: list[Mapping[str, object]] = []

    for descriptor in descriptors:
        name, params, declared_timeframe = series_descriptor_parts(descriptor)
        resolve_series_timeframe(declared_timeframe, execution_timeframe)
        normalized = {"name": name, "params": dict(params)}
        folded = name.casefold()
        in_indicators = folded in indicator_names
        in_patterns = folded in pattern_names
        if in_indicators and in_patterns:
            raise ValueError(f"series name is registered in both registries: {name}")
        if in_indicators:
            indicator_descriptors.append(normalized)
        elif in_patterns:
            pattern_descriptors.append(normalized)
        else:
            raise KeyError(f"series is not registered in either registry: {name} {dict(params)}")

    return SplitSeriesDescriptors(tuple(indicator_descriptors), tuple(pattern_descriptors))


def series_specs_from_descriptors(
    descriptors: Collection[Mapping[str, object]],
    indicators: IndicatorRegistry,
    patterns: PatternRegistry,
    *,
    execution_timeframe: str,
) -> list[ResolvedSeriesSpec]:
    """Resolve descriptors from both registries without requiring a non-empty result."""
    resolved: list[ResolvedSeriesSpec] = []
    for descriptor in descriptors:
        name, params, declared_timeframe = series_descriptor_parts(descriptor)
        timeframe = resolve_series_timeframe(declared_timeframe, execution_timeframe)
        split = split_series_descriptors(
            ({"name": name, "params": dict(params), "timeframe": declared_timeframe},),
            indicators,
            patterns,
            execution_timeframe=execution_timeframe,
        )
        specs = [
            *indicators.specs_from_descriptors(split.indicators),
            *patterns.specs_from_descriptors(split.patterns),
        ]
        if len(specs) != 1:
            raise RuntimeError("one series descriptor must resolve to exactly one registry spec")
        resolved.append(ResolvedSeriesSpec(cast(SeriesSpec, specs[0]), timeframe))
    indicator_order = {spec.identifier: index for index, spec in enumerate(indicators.list())}
    resolved.sort(
        key=lambda item: (
            (
                0,
                indicator_order[item.identifier],
                item.timeframe,
            )
            if item.identifier in indicator_order
            else (1, item.name.casefold(), item.timeframe)
        )
    )
    unique: list[ResolvedSeriesSpec] = []
    seen: set[tuple[str, str]] = set()
    for item in resolved:
        identity = (item.identifier, item.timeframe)
        if identity not in seen:
            seen.add(identity)
            unique.append(item)
    return unique


def resolve_series_specs(
    mode: str,
    declared: Collection[Mapping[str, object]],
    explicit: Collection[Mapping[str, object]],
    indicators: IndicatorRegistry,
    patterns: PatternRegistry,
    *,
    execution_timeframe: str,
) -> list[ResolvedSeriesSpec]:
    """Resolve auto, explicit, or all selections across both registries.

    ``all`` keeps its historical indicator meaning: every registered indicator.
    Patterns are enabled only when the strategy declared them.

    An empty selection resolves to no specs rather than an error. A strategy that
    reads only candles has nothing to declare, and demanding one series it never
    reads would make the declaration disagree with the code on purpose.
    """
    if mode not in {"auto", "explicit", "all"}:
        raise ValueError("indicator mode must be auto, explicit, or all")
    split_series_descriptors(
        declared,
        indicators,
        patterns,
        execution_timeframe=execution_timeframe,
    )
    split_series_descriptors(
        explicit,
        indicators,
        patterns,
        execution_timeframe=execution_timeframe,
    )

    if mode == "auto":
        return series_specs_from_descriptors(
            declared,
            indicators,
            patterns,
            execution_timeframe=execution_timeframe,
        )
    if mode == "explicit":
        return series_specs_from_descriptors(
            explicit,
            indicators,
            patterns,
            execution_timeframe=execution_timeframe,
        )
    pattern_names = {name.casefold() for name in patterns.names()}
    declared_patterns = [
        descriptor
        for descriptor in declared
        if str(descriptor.get("name", "")).casefold() in pattern_names
    ]
    return [
        *(ResolvedSeriesSpec(spec, execution_timeframe) for spec in indicators.list()),
        *series_specs_from_descriptors(
            declared_patterns,
            indicators,
            patterns,
            execution_timeframe=execution_timeframe,
        ),
    ]


def _name_key_map(names: Collection[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in sorted(names):
        result.setdefault(normalize_series_name(name), name)
    return result
