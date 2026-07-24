"""Expose the deterministic backtest orchestration service."""

from importlib.metadata import version

__version__ = version("backtest-service")

__all__ = ["__version__"]
