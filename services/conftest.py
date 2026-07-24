"""Keep local-PostgreSQL tests opt-in for repository-root pytest runs."""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register shared markers even without a root config file."""
    config.addinivalue_line(
        "markers",
        "integration: uses the local development PostgreSQL instance",
    )
    config.addinivalue_line(
        "markers",
        "real_data_long: runs the long-window real-data regression tier",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Skip integration tests unless the invocation explicitly selects them."""
    expression = config.option.markexpr
    explicitly_selected = (
        isinstance(expression, str)
        and "integration" in expression
        and "not integration" not in expression
    )
    if explicitly_selected:
        return
    skip = pytest.mark.skip(reason="integration tests require explicit -m integration")
    for item in items:
        if item.get_closest_marker("integration") is not None:
            item.add_marker(skip)
