"""Web API package for the read-only research catalog."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("web-api")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
