"""Find deployed strategies and policies by walking two known packages.

The two package paths are written here, in code. A registration row decides
whether a discovered strategy may run, and its ``class_name`` and ``module_path``
are compared against what was found, but no path from the database is ever
imported: a row that could name any module would let whoever writes that table
execute arbitrary code inside the process.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from collections.abc import Iterator, Mapping
from types import ModuleType
from typing import Final

from core_lib.money_management import MoneyManagementBase
from core_lib.strategy import AdapterClass, InProcessStrategyRegistry, StrategyBase

from . import money_management as money_management_package
from . import strategies as strategies_package

STRATEGY_PACKAGE: Final = strategies_package
MONEY_MANAGEMENT_PACKAGE: Final = money_management_package
"""The only two places a deployed file is looked for. Both are fixed in code."""


def _modules_in(package: ModuleType) -> Iterator[ModuleType]:
    for info in pkgutil.iter_modules(package.__path__):
        if info.name.startswith("_"):
            continue
        yield importlib.import_module(f"{package.__name__}.{info.name}")


def _concrete_subclasses(module: ModuleType, base: type) -> Iterator[type]:
    for _, member in inspect.getmembers(module, inspect.isclass):
        if member is base or not issubclass(member, base):
            continue
        # A module that imports another plugin's class would otherwise register it
        # twice under two module paths.
        if member.__module__ != module.__name__:
            continue
        if inspect.isabstract(member):
            continue
        yield member


def discover_strategies() -> Mapping[str, AdapterClass]:
    """Return every deployed strategy keyed by the id its class declares.

    The id lives on the class rather than in a separate table so a file cannot be
    deployed under a name it does not itself claim.
    """
    found: dict[str, AdapterClass] = {}
    for module in _modules_in(strategies_package):
        for candidate in _concrete_subclasses(module, StrategyBase):
            strategy_id = getattr(candidate, "STRATEGY_ID", None)
            if not isinstance(strategy_id, str) or not strategy_id:
                raise ValueError(
                    f"{module.__name__}.{candidate.__name__} must declare a non-empty "
                    "STRATEGY_ID to be deployed"
                )
            previous = found.get(strategy_id)
            if previous is not None:
                raise ValueError(
                    f"strategy id {strategy_id!r} is claimed by both "
                    f"{previous.__module__}.{previous.__name__} and "
                    f"{candidate.__module__}.{candidate.__name__}"
                )
            found[strategy_id] = candidate
    return found


def discover_money_management() -> Mapping[str, type[MoneyManagementBase]]:
    """Return every deployed policy keyed by the mode its class declares."""
    found: dict[str, type[MoneyManagementBase]] = {}
    for module in _modules_in(money_management_package):
        for candidate in _concrete_subclasses(module, MoneyManagementBase):
            mode = getattr(candidate, "id", None)
            if not isinstance(mode, str) or not mode:
                raise ValueError(
                    f"{module.__name__}.{candidate.__name__} must declare a non-empty "
                    "id to be deployed"
                )
            previous = found.get(mode)
            if previous is not None:
                raise ValueError(
                    f"money-management mode {mode!r} is claimed by both "
                    f"{previous.__module__}.{previous.__name__} and "
                    f"{candidate.__module__}.{candidate.__name__}"
                )
            found[mode] = candidate
    return found


def build_strategy_registry() -> InProcessStrategyRegistry:
    """Compose the platform's built-in strategies with everything deployed here.

    The built-ins stay registered in ``core_lib`` because moving them would shift
    the shared library's release for a reason unrelated to it. A deployed file that
    claims a built-in id is a conflict rather than an override, because silently
    replacing a shipped strategy would change results with no trace.
    """
    from core_lib.strategy import build_strategy_registry as build_builtin_registry

    registry = build_builtin_registry()
    for strategy_id, adaptee_class in discover_strategies().items():
        registry.register(strategy_id, adaptee_class)
    return registry


__all__ = [
    "MONEY_MANAGEMENT_PACKAGE",
    "STRATEGY_PACKAGE",
    "build_strategy_registry",
    "discover_money_management",
    "discover_strategies",
]
