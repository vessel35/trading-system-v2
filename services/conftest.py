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
        "acceptance: exercises the operator-assembled backtest against development data",
    )
    config.addinivalue_line(
        "markers",
        "real_data_long: runs the long-window real-data regression tier",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Skip database-backed tiers unless the invocation explicitly selects them."""
    expression = config.option.markexpr
    selected = expression if isinstance(expression, str) else ""
    integration_selected = (
        "integration" in selected and "not integration" not in selected
    )
    acceptance_selected = "acceptance" in selected and "not acceptance" not in selected
    skip_integration = pytest.mark.skip(
        reason="integration tests require explicit -m integration"
    )
    skip_acceptance = pytest.mark.skip(
        reason="acceptance tests require explicit -m acceptance"
    )
    for item in items:
        if (
            not integration_selected
            and item.get_closest_marker("integration") is not None
        ):
            item.add_marker(skip_integration)
        if (
            not acceptance_selected
            and item.get_closest_marker("acceptance") is not None
        ):
            item.add_marker(skip_acceptance)
