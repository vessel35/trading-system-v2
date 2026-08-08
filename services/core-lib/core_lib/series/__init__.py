"""Provide the execution contract shared by indicators and candlestick patterns."""

import re
from collections.abc import Mapping

from .contracts import SeriesParam, SeriesSpec, SeriesState, SeriesValue

_SERIES_NAME_KEY = re.compile(r"[^a-z0-9]+")


def normalize_series_name(name: str) -> str:
    """Return the execution-key name prefix shared by both services."""
    return _SERIES_NAME_KEY.sub("_", name.casefold()).strip("_")


def series_key(spec: SeriesSpec) -> str:
    """Return the stable key used in indicator snapshots and strategy inputs."""
    return series_key_of(spec.name, spec.params)


def series_key_of(name: str, params: Mapping[str, object]) -> str:
    """Build the same key from a name and parameters alone.

    Evidence stores the declaration, not the spec, so a reader that reconstructs
    a key has no spec to pass. Both callers go through this one function so the
    rule cannot drift between writing a key and reading it back.
    """
    rendered = ",".join(f"{key}={_series_param(value)}" for key, value in sorted(params.items()))
    normalized = normalize_series_name(name)
    return normalized if not rendered else f"{normalized}:{rendered}"


def _series_param(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


__all__ = [
    "SeriesParam",
    "SeriesSpec",
    "SeriesState",
    "SeriesValue",
    "normalize_series_name",
    "series_key",
    "series_key_of",
]
