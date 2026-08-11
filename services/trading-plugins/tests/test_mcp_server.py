"""Prove that the MCP handlers are only a boundary over the fact module."""

from __future__ import annotations

from typing import cast

import pytest
from mcp.types import CallToolResult, TextContent
from trading_plugins import facts, mcp_server


def test_each_handler_returns_the_underlying_fact_value() -> None:
    assert mcp_server.capabilities() == facts.capabilities()
    assert mcp_server.series() == facts.series()
    assert mcp_server.deployed("strategy") == facts.deployed("strategy")
    assert mcp_server.declaration("strategy", "vessel-reference") == facts.declaration(
        "strategy", "vessel-reference"
    )
    assert mcp_server.registration_sql(
        "strategy",
        "vessel-reference",
        "Vessel Reference",
        "Reference strategy",
        True,
        {"operator": "value"},
    ) == facts.registration_sql(
        "strategy",
        "vessel-reference",
        "Vessel Reference",
        "Reference strategy",
        True,
        {"operator": "value"},
    )
    assert mcp_server.catalog_precheck("strategy", "vessel-reference") == facts.catalog_precheck(
        "strategy", "vessel-reference"
    )


def test_lookup_failure_is_a_structured_tool_error_with_the_cli_message() -> None:
    result = cast(CallToolResult, mcp_server.capabilities("unknown"))

    assert result.isError is True
    assert result.content == [TextContent(type="text", text="unknown capability: unknown")]


def test_unexpected_lookup_failure_does_not_expose_the_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_: str | None = None) -> object:
        raise RuntimeError("raw exception detail")

    monkeypatch.setattr(facts, "capabilities", fail)

    result = cast(CallToolResult, mcp_server.capabilities())

    assert result.isError is True
    assert result.content == [TextContent(type="text", text="fact lookup failed")]
