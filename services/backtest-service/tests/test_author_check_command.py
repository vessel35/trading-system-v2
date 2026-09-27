"""Stages 6 to 9 of the pre-deployment check, with the subprocess stages driven by a fake runner.

Design: ``docs/fullspec/author_check_and_scaffold_design.md`` section 3.4. Stage 6 runs the real
Engine once here, on ``vessel-reference``; the subprocess stages are checked through the
arguments they build and the outcomes they map, so the suite does not spawn ruff, mypy, or a
nested pytest.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from backtest_service import author_check
from backtest_service.author_check import (
    INTEGRATION_TEST,
    PLUGINS_DIRECTORY,
    CommandOutcome,
    check,
    main,
    stage_dry_run,
    stage_integration_tests,
    stage_static_qa,
    stage_unit_tests,
    unit_test_modules_for,
)
from backtest_service.diagnostics.synthetic_dry_run import DryRunReport
from core_lib.strategy import AdapterClass
from trading_plugins import discover_strategies

_VESSEL = "vessel-reference"


class _Runner:
    """Answer each command with a scripted outcome and remember what was asked."""

    def __init__(self, outcomes: Mapping[str, tuple[int, str]] | None = None) -> None:
        self.calls: list[tuple[tuple[str, ...], Path]] = []
        self._outcomes = dict(outcomes or {})

    def __call__(self, argv: Sequence[str], cwd: Path) -> CommandOutcome:
        self.calls.append((tuple(argv), cwd))
        key = " ".join(argv[1:4]) if argv and argv[0] == sys.executable else " ".join(argv[:3])
        returncode, output = self._outcomes.get(key, (0, "1 passed in 0.01s"))
        return CommandOutcome(tuple(argv), returncode, output)


def _report(
    mode: str, *, trades: int = 3, integrity: str = "passed", match: bool = True
) -> DryRunReport:
    return DryRunReport(
        strategy_id=_VESSEL,
        mode=mode,
        integrity_status=integrity,
        trade_count=trades,
        exit_reasons={"SIGNAL_EXIT": trades} if trades else {},
        warmup_candles=21,
        evidence_hash="a" * 64,
        hashes_match=match,
        warning=None if trades else "no trade on the synthetic path",
    )


def _vessel_class() -> AdapterClass:
    return discover_strategies()[0][_VESSEL]


# --- stage 6 ------------------------------------------------------------------------------


def test_stage_6_runs_the_engine_for_every_declared_mode_of_vessel_reference() -> None:
    """The one real Engine run in this module: both declared modes, twice each, same hash."""
    cls = _vessel_class()
    stage = stage_dry_run(_VESSEL, cls)
    assert stage.status == "passed", stage.as_json()
    declared = cls.get_metadata().money_management.supported
    assert set(stage.data["modes"]) == set(declared)
    for entry in stage.data["modes"].values():
        assert entry["integrity_status"] == "passed" and entry["hashes_match"] is True
        assert entry["warmup_candles"] >= 1


def test_stage_6_maps_each_dry_run_outcome_to_its_rule() -> None:
    cls = _vessel_class()
    calls: list[tuple[str, str, Mapping[str, object] | None]] = []

    def scripted(
        strategy_id: str, mode: str, settings: Mapping[str, object] | None
    ) -> DryRunReport:
        calls.append((strategy_id, mode, settings))
        if mode == "manual":
            return _report(mode, integrity="diagnostic_only")
        return _report(mode, match=False)

    stage = stage_dry_run(_VESSEL, cls, dry_run_function=scripted)
    assert stage.status == "failed"
    assert sorted(finding.rule for finding in stage.findings) == [
        "dry-run-integrity",
        "dry-run-nondeterministic",
    ]
    assert {mode for _, mode, _ in calls} == set(cls.get_metadata().money_management.supported)

    def failing(strategy_id: str, mode: str, settings: Mapping[str, object] | None) -> DryRunReport:
        raise RuntimeError("boom")

    stage = stage_dry_run(_VESSEL, cls, dry_run_function=failing)
    assert [finding.rule for finding in stage.findings] == ["dry-run-error"] * len(
        cls.get_metadata().money_management.supported
    )

    def quiet(strategy_id: str, mode: str, settings: Mapping[str, object] | None) -> DryRunReport:
        return _report(mode, trades=0)

    stage = stage_dry_run(_VESSEL, cls, dry_run_function=quiet)
    assert stage.status == "passed"
    assert all("no trade" in warning for warning in stage.data["warnings"])
    assert len(stage.data["warnings"]) == len(cls.get_metadata().money_management.supported)


def test_stage_6_passes_mode_settings_through_to_the_dry_run() -> None:
    cls = _vessel_class()
    seen: dict[str, Mapping[str, object] | None] = {}

    def scripted(
        strategy_id: str, mode: str, settings: Mapping[str, object] | None
    ) -> DryRunReport:
        seen[mode] = settings
        return _report(mode)

    stage_dry_run(
        _VESSEL, cls, mode_settings={"manual": {"reward_risk": 1.5}}, dry_run_function=scripted
    )
    assert seen["manual"] is not None and seen["manual"]["reward_risk"] == 1.5


# --- stage 7 ------------------------------------------------------------------------------


def test_stage_7_runs_the_three_qa_commands_in_the_plugins_service() -> None:
    runner = _Runner()
    stage = stage_static_qa(runner)
    assert stage.status == "passed"
    assert [cwd for _, cwd in runner.calls] == [PLUGINS_DIRECTORY] * 3
    assert [argv[1:4] for argv, _ in runner.calls] == [
        ("-m", "ruff", "check"),
        ("-m", "ruff", "format"),
        ("-m", "mypy"),
    ]
    assert all(argv[0] == sys.executable for argv, _ in runner.calls)

    failing = _Runner({"-m mypy": (1, "error: bad type\nFound 1 error")})
    stage = stage_static_qa(failing)
    assert stage.status == "failed"
    assert [finding.rule for finding in stage.findings] == ["qa-failed"]
    assert "Found 1 error" in stage.findings[0].detail


# --- stage 8 ------------------------------------------------------------------------------


def test_stage_8_selects_the_modules_that_import_the_class_and_needs_one_pass() -> None:
    cls = _vessel_class()
    modules = unit_test_modules_for(cls)
    assert any(path.name == "test_vessel_reference.py" for path in modules)

    runner = _Runner()
    stage = stage_unit_tests(cls, runner)
    assert stage.status == "passed"
    argv, cwd = runner.calls[0]
    assert cwd == PLUGINS_DIRECTORY and argv[1:4] == ("-m", "pytest", "-q")
    assert "tests/test_vessel_reference.py" in argv

    stage = stage_unit_tests(cls, _Runner({"-m pytest -q": (1, "1 failed, 2 passed")}))
    assert stage.status == "failed"
    assert [finding.rule for finding in stage.findings] == ["unit-tests-failed"]

    stage = stage_unit_tests(cls, _Runner({"-m pytest -q": (0, "no tests ran")}))
    assert stage.status == "failed"


def test_stage_8_fails_when_no_module_imports_the_class(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(author_check, "unit_test_modules_for", lambda cls: [])
    stage = stage_unit_tests(_vessel_class(), _Runner())
    assert stage.status == "failed"
    assert "no test module" in stage.findings[0].detail


# --- stage 9 ------------------------------------------------------------------------------


def test_stage_9_skips_without_a_database_and_otherwise_selects_by_id() -> None:
    runner = _Runner()
    stage = stage_integration_tests(_VESSEL, runner, lambda: "OperationalError: refused")
    assert stage.status == "skipped" and runner.calls == []
    assert stage.detail is not None and "database unavailable" in stage.detail

    stage = stage_integration_tests(_VESSEL, runner, lambda: None)
    assert stage.status == "passed"
    argv, cwd = runner.calls[0]
    assert cwd == PLUGINS_DIRECTORY
    assert INTEGRATION_TEST in argv and argv[argv.index("-k") + 1] == _VESSEL
    assert argv[argv.index("-m", 2) + 1] == "integration"

    stage = stage_integration_tests(
        _VESSEL,
        _Runner({"-m pytest tests/test_facts_integration_postgres.py": (5, "no tests ran")}),
        lambda: None,
    )
    assert stage.status == "failed"
    assert "no integration test was collected" in stage.findings[0].detail

    stage = stage_integration_tests(
        _VESSEL,
        _Runner({"-m pytest tests/test_facts_integration_postgres.py": (1, "1 failed")}),
        lambda: None,
    )
    assert [finding.rule for finding in stage.findings] == ["integration-tests-failed"]


# --- all nine -----------------------------------------------------------------------------


def test_the_nine_stages_run_in_order_and_an_unknown_id_stops_after_discovery() -> None:
    def scripted(
        strategy_id: str, mode: str, settings: Mapping[str, object] | None
    ) -> DryRunReport:
        return _report(mode)

    report = check(
        _VESSEL, runner=_Runner(), probe=lambda: "no database", dry_run_function=scripted
    )
    assert [stage.stage for stage in report.stages] == list(range(1, 10))
    assert [stage.status for stage in report.stages] == ["passed"] * 8 + ["skipped"]
    assert report.verdict == "incomplete" and report.passed is False and report.failed is False
    assert report.as_json()["skipped_stages"] == [9]

    complete = check(_VESSEL, runner=_Runner(), probe=lambda: None, dry_run_function=scripted)
    assert complete.verdict == "passed" and complete.passed is True

    report = check("not-deployed", runner=_Runner(), probe=lambda: None, dry_run_function=scripted)
    assert report.verdict == "failed" and report.failed is True
    assert [stage.status for stage in report.stages] == ["failed"] * 9
    assert all(
        [finding.rule for finding in stage.findings] == ["stage-not-run"]
        for stage in report.stages[5:]
    )


def test_the_command_reports_argument_errors_as_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 1
    assert "usage" in json.loads(capsys.readouterr().out)["error"]
    assert main(["vessel-reference", "--mode-settings", "/nonexistent/settings.json"]) == 1
    assert "FileNotFoundError" in json.loads(capsys.readouterr().out)["error"]
