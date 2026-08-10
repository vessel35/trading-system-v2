"""Provide the execution contract shared by indicators and candlestick patterns."""

import re
from collections.abc import Mapping

from core_lib.candles import _TIMEFRAME_PATTERN

from .contracts import PairedSeriesState, SeriesParam, SeriesSpec, SeriesState, SeriesValue

_SERIES_NAME_KEY = re.compile(r"[^a-z0-9]+")


def normalize_series_name(name: str) -> str:
    """Return the execution-key name prefix shared by both services."""
    return _SERIES_NAME_KEY.sub("_", name.casefold()).strip("_")


def series_descriptor_parts(
    descriptor: Mapping[str, object],
) -> tuple[str, Mapping[str, object], str]:
    """Validate and split a strategy or run-config series declaration."""
    if set(descriptor) not in ({"name", "params"}, {"name", "params", "timeframe"}):
        raise ValueError(
            "series descriptor must contain exactly name, params, and optional timeframe"
        )
    name = descriptor["name"]
    params = descriptor["params"]
    timeframe = descriptor.get("timeframe", "strategy")
    if not isinstance(name, str) or not name:
        raise TypeError("series descriptor name must be a non-empty string")
    if not isinstance(params, Mapping) or any(not isinstance(key, str) for key in params):
        raise TypeError("series descriptor params must be a string-keyed mapping")
    if not isinstance(timeframe, str) or (
        timeframe != "strategy" and _TIMEFRAME_PATTERN.fullmatch(timeframe) is None
    ):
        raise ValueError(
            "series descriptor timeframe must be strategy or a positive "
            "minute, hour, or day interval"
        )
    return name, params, timeframe


def resolve_series_timeframe(declared: str, execution: str) -> str:
    """Resolve a declaration to the concrete candle timeframe it names."""
    if _TIMEFRAME_PATTERN.fullmatch(execution) is None:
        raise ValueError("execution timeframe must be a positive minute, hour, or day interval")
    if declared == "strategy":
        return execution
    if declared == execution:
        raise ValueError("execution timeframe must be declared as 'strategy'")
    return declared


def series_key(spec: SeriesSpec, timeframe: str) -> str:
    """Return the stable key used in indicator snapshots and strategy inputs."""
    return series_key_of(spec.name, spec.params, timeframe)


def series_key_of(name: str, params: Mapping[str, object], timeframe: str) -> str:
    """Build the same key from a name and parameters alone.

    Evidence stores the declaration, not the spec, so a reader that reconstructs
    a key has no spec to pass. Both callers go through this one function so the
    rule cannot drift between writing a key and reading it back.
    """
    if _TIMEFRAME_PATTERN.fullmatch(timeframe) is None:
        raise ValueError("series key timeframe must be a positive minute, hour, or day interval")
    rendered = ",".join(f"{key}={_series_param(value)}" for key, value in sorted(params.items()))
    normalized = normalize_series_name(name)
    identity = normalized if not rendered else f"{normalized}:{rendered}"
    return f"{identity}@{timeframe}"


def _series_param(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


__all__ = [
    "SeriesParam",
    "PairedSeriesState",
    "SeriesSpec",
    "SeriesState",
    "SeriesValue",
    "normalize_series_name",
    "resolve_series_timeframe",
    "series_descriptor_parts",
    "series_key",
    "series_key_of",
]
