"""Provide the execution contract shared by indicators and candlestick patterns."""

import re

from .contracts import SeriesParam, SeriesSpec, SeriesState, SeriesValue

_SERIES_NAME_KEY = re.compile(r"[^a-z0-9]+")


def normalize_series_name(name: str) -> str:
    """Return the execution-key name prefix shared by both services."""
    return _SERIES_NAME_KEY.sub("_", name.casefold()).strip("_")


def series_key(spec: SeriesSpec) -> str:
    """Return the stable key used in indicator snapshots and strategy inputs."""
    params = ",".join(f"{key}={_series_param(value)}" for key, value in sorted(spec.params.items()))
    name = normalize_series_name(spec.name)
    return name if not params else f"{name}:{params}"


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
]
