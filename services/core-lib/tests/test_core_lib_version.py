"""Verify source-checkout package version fallback behavior."""

from __future__ import annotations

import runpy
from importlib import metadata
from pathlib import Path

import pytest


def test_core_lib_version_falls_back_when_distribution_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(distribution_name: str) -> str:
        raise metadata.PackageNotFoundError(distribution_name)

    monkeypatch.setattr(metadata, "version", missing)
    package_init = Path(__file__).parents[1] / "core_lib" / "__init__.py"

    namespace = runpy.run_path(str(package_init))

    assert namespace["__version__"] == "0.0.0+unknown"
