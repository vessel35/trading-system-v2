"""Expose the deterministic backtest orchestration service."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("backtest-service")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
