"""Expose :mod:`trading_plugins.facts` through MCP without changing its results.

The server answers from the modules imported when its process started. Restart the
server after changing a plugin or fact source file. The command-line interface,
``python -m trading_plugins.facts``, starts a fresh process for every lookup and has no
such restart caveat.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

from . import facts

mcp = FastMCP("trading-plugin-facts")


def _tool_error(message: str) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        isError=True,
    )


def _lookup(call: Callable[[], object]) -> object:
    try:
        return call()
    except facts.FactsError as error:
        return _tool_error(str(error.args[0]))
    except (Exception, SystemExit):
        return _tool_error("fact lookup failed")


@mcp.tool(structured_output=False)
def capabilities(id: str | None = None) -> object:
    """Return every platform capability, or the exact entry named by ``id``."""
    return _lookup(lambda: facts.capabilities(id))


@mcp.tool(structured_output=False)
def series(name: str | None = None) -> object:
    """Return registered indicator combinations and candlestick patterns."""
    return _lookup(lambda: facts.series(name))


@mcp.tool(structured_output=False)
def deployed(kind: str) -> object:
    """Return plugins found in the fixed package and isolated discovery faults."""
    return _lookup(lambda: facts.deployed(kind))


@mcp.tool(structured_output=False)
def declaration(kind: str, id: str) -> object:
    """Return the declaration owned by one discovered strategy or policy class."""
    return _lookup(lambda: facts.declaration(kind, id))


@mcp.tool(structured_output=False)
def registration_sql(
    kind: str,
    id: str,
    display_name: str,
    description: str,
    is_active: bool,
    default_params: Mapping[str, object] | None = None,
) -> object:
    """Generate one idempotent catalog statement without writing to a database."""
    return _lookup(
        lambda: facts.registration_sql(
            kind,
            id,
            display_name,
            description,
            is_active,
            default_params,
        )
    )


@mcp.tool(structured_output=False)
def catalog_precheck(
    kind: str,
    id: str,
    row: Mapping[str, object] | None = None,
) -> object:
    """Compare a candidate row with runtime catalog comparators, without simulation."""
    return _lookup(lambda: facts.catalog_precheck(kind, id, row))


def main() -> None:
    """Run the fact server over the MCP standard-input/output transport."""
    mcp.run()


if __name__ == "__main__":
    main()


__all__ = [
    "capabilities",
    "catalog_precheck",
    "declaration",
    "deployed",
    "main",
    "mcp",
    "registration_sql",
    "series",
]
