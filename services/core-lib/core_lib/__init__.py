"""Expose the shared trading domain package."""

from importlib.metadata import version

__version__ = version("core-lib")

__all__ = ["__version__"]
