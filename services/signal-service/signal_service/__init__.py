"""Expose the signal-generation driver package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("signal-service")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
