"""Guard shared standards against service-local reimplementation."""

import ast
import importlib
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, cast

import pytest
from core_lib.ports import StrategyRegistry
from core_lib.strategy import CATALOG_COLUMNS


class _CatalogResult:
    def __init__(self, row: Sequence[object]) -> None:
        self._row = row

    def fetchall(self) -> list[Sequence[object]]:
        return [self._row]

    def fetchone(self) -> Sequence[object]:
        return self._row


class _CatalogConnection:
    def __init__(self, row: Sequence[object]) -> None:
        self._row = row

    def execute(self, query: str, params: tuple[object, ...]) -> _CatalogResult:
        del params
        assert "sentinel" in query
        return _CatalogResult(self._row)


class _RegistryFactory(Protocol):
    def __call__(self, connection: _CatalogConnection) -> StrategyRegistry: ...


def test_backtest_service_has_no_core_component_directories() -> None:
    """Keep domain-standard component directories exclusive to core_lib."""
    repository_root = Path(__file__).resolve().parents[3]
    service_package = repository_root / "services" / "backtest-service" / "backtest_service"
    forbidden_components = {
        "costs",
        "eval",
        "execution",
        "indicators",
        "ports",
        "sizing",
        "strategy",
        "types",
    }

    service_directories = {path.name for path in service_package.iterdir() if path.is_dir()}

    assert forbidden_components.isdisjoint(service_directories)


def test_services_do_not_copy_canonical_calculation_modules() -> None:
    """Reject renamed component directories and copied standard module files."""
    repository_root = Path(__file__).resolve().parents[3]
    core_package = repository_root / "services" / "core-lib" / "core_lib"
    canonical_components = {
        "costs",
        "eval",
        "execution",
        "indicators",
        "sizing",
    }
    canonical_names = {
        path.name
        for component in canonical_components
        for path in (core_package / component).glob("*.py")
        if path.name != "__init__.py"
    }
    copied: list[str] = []
    for service in (repository_root / "services").iterdir():
        if service.name == "core-lib" or not service.is_dir():
            continue
        for path in service.rglob("*.py"):
            if path.name in canonical_names:
                copied.append(path.relative_to(repository_root).as_posix())
    assert copied == []


def test_services_do_not_redeclare_the_strategy_catalog_row_contract() -> None:
    """Keep the shared column list and row parser out of both service adapters."""
    repository_root = Path(__file__).resolve().parents[3]
    paths = (
        repository_root
        / "services"
        / "backtest-service"
        / "backtest_service"
        / "adapters"
        / "strategy_registry.py",
        repository_root
        / "services"
        / "signal-service"
        / "signal_service"
        / "infrastructure"
        / "strategy_registry.py",
    )

    for path in paths:
        tree = ast.parse(path.read_text())
        assigned_names = {
            target.id
            for node in ast.walk(tree)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
            if isinstance(target, ast.Name)
        }
        function_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        shared_imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "core_lib.strategy"
            for alias in node.names
        }

        assert "_COLUMNS" not in assigned_names
        assert "CATALOG_COLUMNS" not in assigned_names
        assert "_entry" not in function_names
        assert "catalog_row_entry" not in function_names
        assert {"CATALOG_COLUMNS", "catalog_row_entry"} <= shared_imports


@pytest.mark.parametrize(
    ("module_name", "class_name"),
    [
        (
            "backtest_service.adapters.strategy_registry",
            "BacktestStrategyRegistry",
        ),
        (
            "signal_service.infrastructure.strategy_registry",
            "SignalStrategyRegistry",
        ),
    ],
)
def test_shared_catalog_column_extension_reaches_both_service_adapters(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    class_name: str,
) -> None:
    """Prove one shared column addition reaches each service query and row parser."""
    strategy_module = importlib.import_module("core_lib.strategy")
    catalog_row_module = importlib.import_module("core_lib.strategy.catalog_row")
    registry_module = importlib.import_module(module_name)
    extended_columns = (*CATALOG_COLUMNS, "sentinel")
    values: dict[str, object] = {column: f"value:{column}" for column in extended_columns}
    values["strategy_id"] = "probe"
    values["required_indicators_json"] = []
    values["default_params_json"] = {}
    row = tuple(values[column] for column in extended_columns)

    with monkeypatch.context() as patch:
        patch.setattr(catalog_row_module, "CATALOG_COLUMNS", extended_columns)
        patch.setattr(strategy_module, "CATALOG_COLUMNS", extended_columns)
        registry_module = importlib.reload(registry_module)
        factory = cast(_RegistryFactory, getattr(registry_module, class_name))

        entry = factory(_CatalogConnection(row)).get("probe")

        assert entry["sentinel"] == "value:sentinel"

    importlib.reload(registry_module)


def test_core_lib_dependencies_follow_the_one_way_component_graph() -> None:
    """Keep ports/eval as leaves and reject reverse component dependencies."""
    core_package = Path(__file__).resolve().parents[1] / "core_lib"
    allowed_dependencies = {
        "types": set(),
        "series": {"candles", "types"},
        "indicators": {"types"},
        "patterns": {"indicators", "series", "types"},
        "sizing": {"types"},
        "money_management": {"types"},
        "costs": {"ports", "types"},
        "eval": {"types"},
        "ports": {"types"},
        "strategy": {
            "indicators",
            "money_management",
            "ports",
            "series",
            "types",
        },
        "execution": {"costs", "ports", "types"},
    }
    violations: list[str] = []
    for path in core_package.rglob("*.py"):
        source_component = path.relative_to(core_package).parts[0]
        if source_component not in allowed_dependencies:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            parts = node.module.split(".")
            if len(parts) < 2 or parts[0] != "core_lib":
                continue
            target_component = parts[1]
            if (
                target_component != source_component
                and target_component not in allowed_dependencies[source_component]
            ):
                violations.append(f"{path.relative_to(core_package)} -> {target_component}")
    assert violations == []


def test_series_resolution_dependencies_are_explicitly_bounded() -> None:
    """Keep top-level series resolution from importing strategy/runtime layers."""
    core_package = Path(__file__).resolve().parents[1] / "core_lib"
    path = core_package / "series_resolution.py"
    allowed_dependencies = {"indicators", "patterns", "series"}

    violations = sorted(_core_lib_import_components(path) - allowed_dependencies)

    assert violations == []


def test_pip_bootstrap_resolves_workspace_projects_together() -> None:
    """Keep pip from resolving the sibling core-lib name through an index."""
    repository_root = Path(__file__).resolve().parents[3]
    requirements = (repository_root / "services" / "requirements-dev.txt").read_text().splitlines()
    editable = {
        line for raw_line in requirements if (line := raw_line.strip()) and not line.startswith("#")
    }
    assert editable == {
        "-e ./services/core-lib[dev]",
        "-e ./services/trading-plugins[dev]",
        "-e ./services/service-commons[dev]",
        "-e ./services/collector[dev]",
        "-e ./services/backtest-service[dev]",
        "-e ./services/signal-service[dev]",
        "-e ./services/wallet-service[dev]",
        "-e ./services/web-api[dev]",
    }
    backtest_project = tomllib.loads(
        (repository_root / "services" / "backtest-service" / "pyproject.toml").read_text()
    )["project"]
    assert "core-lib==0.2.0" in backtest_project["dependencies"]
    signal_project = tomllib.loads(
        (repository_root / "services" / "signal-service" / "pyproject.toml").read_text()
    )["project"]
    assert "core-lib==0.2.0" in signal_project["dependencies"]
    wallet_project = tomllib.loads(
        (repository_root / "services" / "wallet-service" / "pyproject.toml").read_text()
    )["project"]
    assert "core-lib==0.2.0" in wallet_project["dependencies"]


def _core_lib_import_components(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    components: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            parts = node.module.split(".")
            if parts[0] != "core_lib":
                continue
            if len(parts) == 1:
                components.update(
                    alias.name.split(".")[0] for alias in node.names if alias.name != "*"
                )
            else:
                components.add(parts[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "core_lib" and len(parts) > 1:
                    components.add(parts[1])
    return components
