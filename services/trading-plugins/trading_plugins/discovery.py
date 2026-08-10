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

from core_lib.money_management import MoneyManagementBase, policy_settings
from core_lib.strategy import AdapterClass, InProcessStrategyRegistry, StrategyBase

from . import money_management as money_management_package
from . import strategies as strategies_package

STRATEGY_PACKAGE: Final = strategies_package
MONEY_MANAGEMENT_PACKAGE: Final = money_management_package
_LOGGER = logging.getLogger(__name__)
"""The only two places a deployed file is looked for. Both are fixed in code."""


def _modules_in(package: ModuleType) -> Iterator[tuple[str, ModuleType | BaseException]]:
    """Import each module, handing back the failure instead of raising it.

    One unloadable file must not take the others down with it. A strategy the
    database still points at simply will not be found, and the manager refuses it
    by name at creation, which says far more than a failed process start.

    ``SystemExit`` is caught alongside ordinary errors because a deployed file
    that calls ``sys.exit`` at import time would otherwise end the process that
    imported it, which is exactly the blast radius this isolation exists to stop.
    ``KeyboardInterrupt`` is left to propagate so the operator keeps control.

    A file that hangs at import time is not covered. Import runs on this thread
    and cannot be interrupted from outside it, so a deployment that blocks at the
    top level blocks the service that loads it.
    """
    for info in pkgutil.iter_modules(package.__path__):
        if info.name.startswith("_"):
            continue
        name = f"{package.__name__}.{info.name}"
        try:
            yield name, importlib.import_module(name)
        except (Exception, SystemExit) as error:  # noqa: BLE001 - the fault is the return value
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
        if isinstance(module, BaseException):
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
        if isinstance(module, BaseException):
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
            # Read the configuration surface now. Waiting until a run names this
            # mode would hide a broken deployment until the first request.
            try:
                policy_settings(candidate)
            except TypeError as error:
                faults.append(PluginFault(name, str(error)))
                continue
            if not isinstance(getattr(candidate, "requires_signal_exit", None), bool):
                faults.append(
                    PluginFault(
                        name,
                        f"{candidate.__name__} must declare requires_signal_exit",
                    )
                )
                continue
            found[mode] = candidate
    return found, tuple(faults)


def build_strategy_registry() -> InProcessStrategyRegistry:
    """Build a fresh registry from every strategy discovered in the fixed package."""
    registry = InProcessStrategyRegistry()
    found, faults = discover_strategies()
    for fault in faults:
        _LOGGER.error("deployed strategy was not loaded: %s (%s)", fault.module, fault.reason)
    for strategy_id, adaptee_class in found.items():
        registry.register(strategy_id, adaptee_class)
    return registry


def registered_money_management() -> Mapping[str, type[MoneyManagementBase]]:
    """Return every valid policy discovered in the fixed deployment package."""
    registered: dict[str, type[MoneyManagementBase]] = {}
    found, faults = discover_money_management()
    for fault in faults:
        _LOGGER.error("deployed policy was not loaded: %s (%s)", fault.module, fault.reason)
    registered.update(found)
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
