"""The pre-deployment check for one strategy: stages 1 to 5, then 6 to 9.

Design: ``docs/fullspec/author_check_and_scaffold_design.md`` section 3.4. Stages 1 to 5 come
from ``trading_plugins.author_check`` (discovery, declaration, money-management composition,
parameters, registration precheck). This module adds:

- stage 6, the Engine on the fixed synthetic path for every declared mode, twice, through
  ``backtest_service.diagnostics.synthetic_dry_run``: no exception, Evidence integrity passed,
  the two hashes equal; zero trades in a mode is a warning;
- stage 7, ``ruff check``, ``ruff format --check`` and ``mypy`` in ``services/trading-plugins``;
- stage 8, the pytest modules there that import the strategy's class, at least one collected
  and all passing;
- stage 9, the integration tests marked ``integration``, selected by the strategy id, when the
  repository's ``.env`` reaches a PostgreSQL server; otherwise skipped with that reason. It is
  the only stage that may be skipped.

The command prints one JSON report and exits 1 when any stage failed. What it proves is that
the strategy is discovered, registered, composed, and runs; whether it trades as its document
says is the common-check suites' and ``verify-strategy``'s question.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import psycopg
from core_lib.money_management import MoneyManagementBase
from core_lib.strategy import AdapterClass
from trading_plugins import author_check as first_stages
from trading_plugins import discover_money_management, discover_strategies
from trading_plugins.author_check import (
    CheckReport,
    Finding,
    StageResult,
    load_mode_settings,
    not_run,
    parse_arguments,
    representative_settings,
)

from backtest_service.diagnostics.synthetic_dry_run import DryRunReport, dry_run

__all__ = [
    "INTEGRATION_TEST",
    "PLUGINS_DIRECTORY",
    "REPOSITORY_ROOT",
    "CommandOutcome",
    "check",
    "main",
    "probe_database",
    "run_command",
    "stage_dry_run",
    "stage_integration_tests",
    "stage_static_qa",
    "stage_unit_tests",
    "unit_test_modules_for",
]

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[3]
PLUGINS_DIRECTORY: Final = REPOSITORY_ROOT / "services" / "trading-plugins"
INTEGRATION_TEST: Final = "tests/test_facts_integration_postgres.py"
_PASSED: Final = re.compile(r"(\d+) passed")
_NO_TESTS_COLLECTED: Final = 5


@dataclass(frozen=True)
class CommandOutcome:
    """What one subprocess did: its arguments, exit code, and combined output."""

    argv: tuple[str, ...]
    returncode: int
    output: str

    def tail(self, lines: int = 20) -> str:
        return "\n".join(self.output.strip().splitlines()[-lines:])


Runner = Callable[[Sequence[str], Path], CommandOutcome]
DatabaseProbe = Callable[[], str | None]
DryRunFunction = Callable[[str, str, Mapping[str, object] | None], DryRunReport]


def run_command(argv: Sequence[str], cwd: Path) -> CommandOutcome:
    """Run one command to completion and return what it printed."""
    completed = subprocess.run(  # noqa: S603 - argv is built here, not from user text
        list(argv), cwd=cwd, capture_output=True, text=True, check=False
    )
    return CommandOutcome(tuple(argv), completed.returncode, completed.stdout + completed.stderr)


def _repository_env() -> dict[str, str]:
    values: dict[str, str] = {}
    path = REPOSITORY_ROOT / ".env"
    if not path.exists():
        return values
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def probe_database() -> str | None:
    """Return why the repository's PostgreSQL server is unreachable, or None when it answers."""
    values = _repository_env()
    required = ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD")
    missing = [name for name in required if name not in values]
    if missing:
        return f"repository .env lacks {', '.join(missing)}"
    try:
        connection = psycopg.connect(
            host=values["PGHOST"],
            port=int(values["PGPORT"]),
            user=values["PGUSER"],
            password=values["PGPASSWORD"],
            dbname="signal_db",
            connect_timeout=3,
        )
    except (Exception, SystemExit) as error:  # noqa: BLE001 - the reason is the answer
        return f"{type(error).__name__}: {error}"
    connection.close()
    return None


# --- stage 6: the Engine on the synthetic path ---------------------------------------------


def stage_dry_run(
    strategy_id: str,
    cls: AdapterClass,
    *,
    mode_settings: Mapping[str, Mapping[str, object]] | None = None,
    policies: Mapping[str, type[MoneyManagementBase]] | None = None,
    dry_run_function: DryRunFunction = dry_run,
) -> StageResult:
    """Every declared mode runs the Engine twice on the synthetic path with the same hash."""
    name = "synthetic-dry-run"
    deployed = discover_money_management()[0] if policies is None else policies
    try:
        support = cls.get_metadata().money_management
    except (Exception, SystemExit) as error:  # noqa: BLE001
        return StageResult(
            6,
            name,
            "failed",
            (Finding("declaration-unreadable", f"{type(error).__name__}: {error}"),),
        )
    findings: list[Finding] = []
    modes: dict[str, Any] = {}
    warnings: list[str] = []
    for mode in support.supported:
        policy_class = deployed.get(mode)
        if policy_class is None:
            findings.append(
                Finding("policy-mode-not-deployed", "declared mode is not deployed", {"mode": mode})
            )
            continue
        overrides = None if mode_settings is None else mode_settings.get(mode)
        try:
            settings, missing = representative_settings(cls, mode, policy_class, overrides)
        except ValueError as error:
            findings.append(Finding("mode-settings-invalid", str(error), {"mode": mode}))
            continue
        if missing:
            findings.append(
                Finding(
                    "policy-settings-required",
                    "the policy has settings without defaults; give them with --mode-settings",
                    {"mode": mode, "missing": sorted(missing)},
                )
            )
            continue
        try:
            report = dry_run_function(strategy_id, mode, settings)
        except (Exception, SystemExit) as error:  # noqa: BLE001
            findings.append(
                Finding("dry-run-error", f"{type(error).__name__}: {error}", {"mode": mode})
            )
            continue
        modes[mode] = {
            "trade_count": report.trade_count,
            "exit_reasons": dict(report.exit_reasons),
            "warmup_candles": report.warmup_candles,
            "integrity_status": report.integrity_status,
            "hashes_match": report.hashes_match,
        }
        if report.integrity_status != "passed":
            findings.append(
                Finding(
                    "dry-run-integrity",
                    f"Evidence integrity was {report.integrity_status!r}",
                    {"mode": mode},
                )
            )
        if not report.hashes_match:
            findings.append(
                Finding("dry-run-nondeterministic", "two runs hashed differently", {"mode": mode})
            )
        if report.warning is not None:
            warnings.append(f"{mode}: {report.warning}")
    if findings:
        return StageResult(6, name, "failed", tuple(findings), data={"modes": modes})
    return StageResult(6, name, "passed", (), None, {"modes": modes, "warnings": warnings})


# --- stage 7: static QA -------------------------------------------------------------------


def stage_static_qa(runner: Runner = run_command) -> StageResult:
    """ruff, ruff format, and mypy pass in the plugins service."""
    name = "static-qa"
    commands = (
        (sys.executable, "-m", "ruff", "check", "."),
        (sys.executable, "-m", "ruff", "format", "--check", "."),
        (sys.executable, "-m", "mypy"),
    )
    findings: list[Finding] = []
    for argv in commands:
        outcome = runner(argv, PLUGINS_DIRECTORY)
        if outcome.returncode != 0:
            findings.append(
                Finding(
                    "qa-failed",
                    outcome.tail(),
                    {"command": list(outcome.argv), "returncode": outcome.returncode},
                )
            )
    if findings:
        return StageResult(7, name, "failed", tuple(findings))
    return StageResult(7, name, "passed", (), None, {"commands": [list(argv) for argv in commands]})


# --- stage 8: unit tests that import the class ---------------------------------------------


def unit_test_modules_for(cls: AdapterClass) -> list[Path]:
    """The plugin test modules whose source names the class's module or the class itself."""
    tests = PLUGINS_DIRECTORY / "tests"
    needles = (cls.__module__, cls.__name__)
    return sorted(
        path
        for path in tests.glob("test_*.py")
        if any(needle in path.read_text() for needle in needles)
    )


def stage_unit_tests(cls: AdapterClass, runner: Runner = run_command) -> StageResult:
    """At least one plugin test module imports the class, and every one of them passes."""
    name = "unit-tests"
    modules = unit_test_modules_for(cls)
    if not modules:
        return StageResult(
            8,
            name,
            "failed",
            (
                Finding(
                    "unit-tests-failed",
                    "no test module in services/trading-plugins/tests imports the class",
                    {"class_name": cls.__name__, "module_path": cls.__module__},
                ),
            ),
        )
    argv = (
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        *(str(path.relative_to(PLUGINS_DIRECTORY)) for path in modules),
    )
    outcome = runner(argv, PLUGINS_DIRECTORY)
    passed = _passed_count(outcome.output)
    data = {
        "modules": [str(path.relative_to(PLUGINS_DIRECTORY)) for path in modules],
        "passed": passed,
    }
    if outcome.returncode != 0 or passed < 1:
        return StageResult(
            8,
            name,
            "failed",
            (Finding("unit-tests-failed", outcome.tail(), {"returncode": outcome.returncode}),),
            data=data,
        )
    return StageResult(8, name, "passed", (), None, data)


def _passed_count(output: str) -> int:
    match = _PASSED.search(output)
    return int(match.group(1)) if match else 0


# --- stage 9: the disposable-database integration tests -----------------------------------


def stage_integration_tests(
    strategy_id: str,
    runner: Runner = run_command,
    probe: DatabaseProbe = probe_database,
) -> StageResult:
    """The integration tests selected by the id run against a disposable schema, or skip."""
    name = "integration-tests"
    reason = probe()
    if reason is not None:
        return StageResult(9, name, "skipped", (), f"database unavailable: {reason}")
    argv = (
        sys.executable,
        "-m",
        "pytest",
        INTEGRATION_TEST,
        "-m",
        "integration",
        "-k",
        strategy_id,
        "-q",
        "-p",
        "no:cacheprovider",
    )
    outcome = runner(argv, PLUGINS_DIRECTORY)
    passed = _passed_count(outcome.output)
    data = {"selection": strategy_id, "passed": passed}
    if outcome.returncode == _NO_TESTS_COLLECTED:
        return StageResult(
            9,
            name,
            "failed",
            (Finding("integration-tests-failed", "no integration test was collected for the id"),),
            data=data,
        )
    if outcome.returncode != 0 or passed < 1:
        return StageResult(
            9,
            name,
            "failed",
            (
                Finding(
                    "integration-tests-failed", outcome.tail(), {"returncode": outcome.returncode}
                ),
            ),
            data=data,
        )
    return StageResult(9, name, "passed", (), None, data)


# --- all nine ---------------------------------------------------------------------------


def check(
    strategy_id: str,
    *,
    mode_settings: Mapping[str, Mapping[str, object]] | None = None,
    runner: Runner = run_command,
    probe: DatabaseProbe = probe_database,
    dry_run_function: DryRunFunction = dry_run,
) -> CheckReport:
    """Run stages 1 to 9 in order; ``runner``, ``probe`` and ``dry_run_function`` are for tests."""
    base = first_stages.check(strategy_id, mode_settings=mode_settings)
    stages = list(base.stages)
    cls = discover_strategies()[0].get(strategy_id)
    if stages[0].status != "passed" or cls is None:
        because = "stage 1 (discovery) failed"
        stages.extend(
            not_run(number, name, because)
            for number, name in (
                (6, "synthetic-dry-run"),
                (7, "static-qa"),
                (8, "unit-tests"),
                (9, "integration-tests"),
            )
        )
        return CheckReport(strategy_id, tuple(stages))
    stages.append(
        stage_dry_run(
            strategy_id, cls, mode_settings=mode_settings, dry_run_function=dry_run_function
        )
    )
    stages.append(stage_static_qa(runner))
    stages.append(stage_unit_tests(cls, runner))
    stages.append(stage_integration_tests(strategy_id, runner, probe))
    return CheckReport(strategy_id, tuple(stages))


_USAGE: Final = (
    "usage: python -m backtest_service.author_check <strategy-id> [--mode-settings <file>]"
)


def main(argv: Sequence[str] | None = None) -> int:
    """Print the JSON report of all nine stages; exit 1 when any failed."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        strategy_id, settings_path = parse_arguments(arguments)
        mode_settings = None if settings_path is None else load_mode_settings(settings_path)
    except (Exception, SystemExit) as error:  # noqa: BLE001 - the boundary reports, never raises
        message = _USAGE if "usage:" in str(error) else f"{type(error).__name__}: {error}"
        print(json.dumps({"error": message}))
        return 1
    report = check(strategy_id, mode_settings=mode_settings)
    print(json.dumps(report.as_json(), sort_keys=True))
    return 1 if report.failed else 0


if __name__ == "__main__":  # pragma: no cover - exercised through main() in tests
    sys.exit(main())
