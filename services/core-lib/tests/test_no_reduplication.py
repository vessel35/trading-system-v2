"""Guard shared standards against service-local reimplementation."""

import ast
import tomllib
from pathlib import Path


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

    service_directories = {
        path.name for path in service_package.iterdir() if path.is_dir()
    }

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


def test_core_lib_dependencies_follow_the_one_way_component_graph() -> None:
    """Keep ports/eval as leaves and reject reverse component dependencies."""
    core_package = Path(__file__).resolve().parents[1] / "core_lib"
    allowed_dependencies = {
        "types": set(),
        "indicators": {"types"},
        "sizing": {"types"},
        "costs": {"ports", "types"},
        "eval": {"types"},
        "ports": {"types"},
        "strategy": {"indicators", "ports", "types"},
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
                violations.append(
                    f"{path.relative_to(core_package)} -> {target_component}"
                )
    assert violations == []


def test_pip_bootstrap_resolves_both_workspace_projects_together() -> None:
    """Keep pip from resolving the sibling core-lib name through an index."""
    repository_root = Path(__file__).resolve().parents[3]
    requirements = (
        repository_root / "services" / "requirements-dev.txt"
    ).read_text().splitlines()
    editable = {
        line
        for raw_line in requirements
        if (line := raw_line.strip()) and not line.startswith("#")
    }
    assert editable == {
        "-e ./services/core-lib[dev]",
        "-e ./services/backtest-service[dev]",
    }
    backtest_project = tomllib.loads(
        (
            repository_root / "services" / "backtest-service" / "pyproject.toml"
        ).read_text()
    )["project"]
    assert "core-lib==0.2.0" in backtest_project["dependencies"]
