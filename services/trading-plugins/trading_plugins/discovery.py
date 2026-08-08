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
import logging
import pkgutil
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from types import ModuleType
from typing import Final

from core_lib.money_management import MoneyManagementBase
from core_lib.strategy import AdapterClass, InProcessStrategyRegistry, StrategyBase

from . import money_management as money_management_package
from . import strategies as strategies_package

STRATEGY_PACKAGE: Final = strategies_package
MONEY_MANAGEMENT_PACKAGE: Final = money_management_package
_LOGGER = logging.getLogger(__name__)
"""The only two places a deployed file is looked for. Both are fixed in code."""


def _modules_in(package: ModuleType) -> Iterator[tuple[str, ModuleType | Exception]]:
    """Import each module, handing back the failure instead of raising it.

    One unloadable file must not take the others down with it. A strategy the
    database still points at simply will not be found, and the manager refuses it
    by name at creation, which says far more than a failed process start.
    """
    for info in pkgutil.iter_modules(package.__path__):
        if info.name.startswith("_"):
            continue
        name = f"{package.__name__}.{info.name}"
        try:
            yield name, importlib.import_module(name)
        except Exception as error:  # noqa: BLE001 - the fault is the return value
            yield name, error


@dataclass(frozen=True, slots=True)
class PluginFault:
    """One deployed file that could not be loaded, and why."""

    module: str
    reason: str


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


def discover_strategies(
    package: ModuleType = strategies_package,
) -> tuple[Mapping[str, AdapterClass], tuple[PluginFault, ...]]:
    """Return every deployed strategy keyed by the id its class declares.

    The id must be written on the class itself, not inherited, so a file cannot be
    deployed under a name it never claimed.
    """
    found: dict[str, AdapterClass] = {}
    faults: list[PluginFault] = []
    for name, module in _modules_in(package):
        if isinstance(module, Exception):
            faults.append(PluginFault(name, f"{type(module).__name__}: {module}"))
            continue
        for candidate in _concrete_subclasses(module, StrategyBase):
            strategy_id = vars(candidate).get("STRATEGY_ID")
            if not isinstance(strategy_id, str) or not strategy_id:
                faults.append(
                    PluginFault(
                        name,
                        f"{candidate.__name__} must declare its own non-empty STRATEGY_ID",
                    )
                )
                continue
            previous = found.get(strategy_id)
            if previous is not None:
                faults.append(
                    PluginFault(
                        name,
                        f"strategy id {strategy_id!r} is already claimed by "
                        f"{previous.__module__}.{previous.__name__}",
                    )
                )
                continue
            found[strategy_id] = candidate
    return found, tuple(faults)


def discover_money_management(
    package: ModuleType = money_management_package,
) -> tuple[Mapping[str, type[MoneyManagementBase]], tuple[PluginFault, ...]]:
    """Return every deployed policy keyed by the mode its class declares."""
    found: dict[str, type[MoneyManagementBase]] = {}
    faults: list[PluginFault] = []
    for name, module in _modules_in(package):
        if isinstance(module, Exception):
            faults.append(PluginFault(name, f"{type(module).__name__}: {module}"))
            continue
        for candidate in _concrete_subclasses(module, MoneyManagementBase):
            mode = vars(candidate).get("id")
            if not isinstance(mode, str) or not mode:
                faults.append(
                    PluginFault(name, f"{candidate.__name__} must declare its own non-empty id")
                )
                continue
            previous = found.get(mode)
            if previous is not None:
                faults.append(
                    PluginFault(
                        name,
                        f"money-management mode {mode!r} is already claimed by "
                        f"{previous.__module__}.{previous.__name__}",
                    )
                )
                continue
            found[mode] = candidate
    return found, tuple(faults)


def build_strategy_registry() -> InProcessStrategyRegistry:
    """Compose the platform's built-in strategies with everything deployed here.

    The built-ins stay registered in ``core_lib`` because moving them would shift
    the shared library's release for a reason unrelated to it. A deployed file that
    claims a built-in id is a conflict rather than an override, because silently
    replacing a shipped strategy would change results with no trace.
    """
    from core_lib.strategy import build_strategy_registry as build_builtin_registry

    registry = build_builtin_registry()
    found, faults = discover_strategies()
    for fault in faults:
        _LOGGER.error("deployed strategy was not loaded: %s (%s)", fault.module, fault.reason)
    for strategy_id, adaptee_class in found.items():
        try:
            registry.register(strategy_id, adaptee_class)
        except ValueError as error:
            # A built-in already holds this id. Refusing keeps a shipped strategy
            # from being replaced without a trace.
            _LOGGER.error("deployed strategy %s was not registered: %s", strategy_id, error)
    return registry


def registered_money_management() -> Mapping[str, type[MoneyManagementBase]]:
    """Compose the platform's built-in policies with everything deployed here.

    A deployed policy that claims a built-in mode is refused rather than allowed to
    replace it, for the same reason a strategy cannot take a built-in id: replacing
    a shipped policy changes every run that names that mode, with no trace.
    """
    from core_lib.money_management import BUILTIN_POLICIES

    registered = dict(BUILTIN_POLICIES)
    found, faults = discover_money_management()
    for fault in faults:
        _LOGGER.error("deployed policy was not loaded: %s (%s)", fault.module, fault.reason)
    for mode, policy_class in found.items():
        if mode in registered:
            _LOGGER.error("deployed policy %s was not registered: mode is already built in", mode)
            continue
        registered[mode] = policy_class
    return registered


__all__ = [
    "MONEY_MANAGEMENT_PACKAGE",
    "PluginFault",
    "STRATEGY_PACKAGE",
    "build_strategy_registry",
    "discover_money_management",
    "discover_strategies",
    "registered_money_management",
]
