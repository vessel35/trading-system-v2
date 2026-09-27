"""The one place the plugin identifier rule is written.

A strategy id and a policy mode are kebab-case: groups of lowercase letters and digits
joined by single hyphens. The registration tables enforce the same rule as a check
constraint (``init-scripts/signal-service/20260724/01-redefine-strategy-registry.sql`` and
``init-scripts/signal-service/20260810/01-create-money-management-registry.sql``), and
``services/core-lib/tests/test_identifiers.py`` compares their expression with this one
character for character. Changing the rule therefore means changing three places together,
and changing one of them alone fails that test.

This module imports nothing from ``core_lib``, so ``core_lib.capabilities``, which otherwise
imports no sibling module, can carry the expression as a recorded value.
"""

from __future__ import annotations

import re
from typing import Final

__all__ = ["PLUGIN_IDENTIFIER_PATTERN", "is_plugin_identifier"]

PLUGIN_IDENTIFIER_PATTERN: Final = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
"""Written exactly as the DDL writes it, plain group and all, so the two can be compared."""


def is_plugin_identifier(text: object) -> bool:
    """Return whether ``text`` is a string the plugin identifier rule accepts."""
    return isinstance(text, str) and PLUGIN_IDENTIFIER_PATTERN.fullmatch(text) is not None
