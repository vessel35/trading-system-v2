"""The plugin identifier rule is one expression, shared by the code and the registration DDL.

``core_lib.capabilities`` records the rule as ``plugin.identifier_format`` and names this
module as its proof.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest
from core_lib import identifiers
from core_lib.identifiers import PLUGIN_IDENTIFIER_PATTERN, is_plugin_identifier

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

# Each file carries exactly one identifier check constraint, on the named column.
_DDL_CHECKS = (
    ("init-scripts/signal-service/20260724/01-redefine-strategy-registry.sql", "strategy_id"),
    ("init-scripts/signal-service/20260810/01-create-money-management-registry.sql", "mode"),
)


def _ddl_expression(relative_path: str, column: str) -> str:
    text = (REPOSITORY_ROOT / relative_path).read_text()
    found = re.findall(rf"\b{column} ~ '([^']*)'", text)
    assert len(found) == 1, f"{relative_path} must check {column} exactly once, found {found}"
    return str(found[0])


@pytest.mark.parametrize(("relative_path", "column"), _DDL_CHECKS)
def test_the_code_expression_matches_the_ddl_check_character_for_character(
    relative_path: str, column: str
) -> None:
    """Change the rule in one place only and this is the test that fails."""
    assert _ddl_expression(relative_path, column) == PLUGIN_IDENTIFIER_PATTERN.pattern


@pytest.mark.parametrize(
    "text",
    ["a", "7", "ab1", "vessel-reference", "signal-exit-atr", "ema-200-x9", "a-b-c-d"],
)
def test_kebab_case_identifiers_are_accepted(text: str) -> None:
    assert is_plugin_identifier(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Vessel",
        "vessel_reference",
        "-vessel",
        "vessel-",
        "vessel--reference",
        "vessel reference",
        "vessel.reference",
        "vessel-reference\n",
        "전략",
        None,
        3,
    ],
)
def test_anything_else_is_refused(text: object) -> None:
    assert not is_plugin_identifier(text)


def test_the_identifier_module_imports_nothing_from_core_lib() -> None:
    """``core_lib.capabilities`` imports this module; it must not pull the rest of core_lib in."""
    source = inspect.getsource(identifiers)
    assert "from core_lib" not in source
    assert "import core_lib" not in source
