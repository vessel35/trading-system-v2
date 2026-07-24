"""Expose the shared trading domain package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("core-lib")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
