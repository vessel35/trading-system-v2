"""Guard shared standards against service-local reimplementation."""

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
