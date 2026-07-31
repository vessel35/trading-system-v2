"""Make the shared test-data packages in this directory importable in both run modes.

`pytest services` from the repository root finds no configuration file, so it imports
test modules in prepend mode and this directory reaches `sys.path` on its own. Running
`pytest` inside `services/core-lib` picks up the `--import-mode=importlib` setting in
`pyproject.toml`, which deliberately leaves `sys.path` alone; without the line below a
test module could not import `indicator_reference` there. Adding the directory once,
here, is what lets the same import line work under either invocation.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS_ROOT = str(Path(__file__).parent)
if _TESTS_ROOT not in sys.path:
    sys.path.insert(0, _TESTS_ROOT)
