"""Keep acceptance marker behavior stable under either service's pytest config."""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register acceptance when a multi-service run chooses core-lib as rootdir."""
    config.addinivalue_line(
        "markers",
        "acceptance: exercises the operator-assembled backtest against development data",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Deselect acceptance items unless the invocation explicitly requests them."""
    expression = config.option.markexpr
    selected = expression if isinstance(expression, str) else ""
    if "acceptance" in selected and "not acceptance" not in selected:
        return
    deselected = [item for item in items if item.get_closest_marker("acceptance") is not None]
    if not deselected:
        return
    items[:] = [item for item in items if item not in deselected]
    config.hook.pytest_deselected(items=deselected)
