"""The synthetic dry run reaches every discovered strategy and stays out of operational code.

Design: ``docs/fullspec/author_check_and_scaffold_design.md`` section 3.4.1.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path

import pytest
from backtest_service.diagnostics import synthetic_dry_run
from backtest_service.diagnostics.synthetic_dry_run import (
    DiscoveredRows,
    DryRunReport,
    dry_run,
    main,
)
from trading_plugins import discover_strategies

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_BACKTEST_PACKAGE = REPOSITORY_ROOT / "services" / "backtest-service" / "backtest_service"
_WEB_API_PACKAGE = REPOSITORY_ROOT / "services" / "web-api" / "web_api"
_DIAGNOSTICS_IMPORT = re.compile(r"^\s*(from|import)\s+backtest_service\.diagnostics\b", re.M)


def test_the_rows_come_from_discovery_and_cover_every_deployed_strategy() -> None:
    found, faults = discover_strategies()
    assert faults == ()
    rows = DiscoveredRows(found)

    listed = {str(row["strategy_id"]) for row in rows.list()}
    assert listed == set(found)
    for strategy_id, adaptee in found.items():
        row = rows.get(strategy_id)
        assert row["class_name"] == adaptee.__name__
        assert row["module_path"] == adaptee.__module__
        assert row["is_active"] is True and row["is_deprecated"] is False
    with pytest.raises(KeyError):
        rows.get("not-deployed")


def test_two_runs_of_vessel_reference_hash_the_same_and_the_evidence_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The closing criterion names ``vessel-reference``, which the old fixture left out."""
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    report = dry_run("vessel-reference", "manual")

    assert isinstance(report, DryRunReport)
    assert report.strategy_id == "vessel-reference" and report.mode == "manual"
    assert report.integrity_status == "passed"
    assert report.hashes_match is True
    assert len(report.evidence_hash) == 64
    assert report.warmup_candles >= 1
    assert sum(report.exit_reasons.values()) == report.trade_count
    assert (report.warning is None) == (report.trade_count > 0)
    assert list(tmp_path.glob("synthetic-dry-run-*")) == []


def test_an_unknown_strategy_or_mode_is_a_reported_error_not_a_crash(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["not-deployed", "manual"]) == 1
    error = json.loads(capsys.readouterr().out)
    assert "unknown strategy" in error["error"]

    assert main(["vessel-reference", "not-a-mode"]) == 1
    error = json.loads(capsys.readouterr().out)
    assert error["error"]

    assert main(["only-one-argument"]) == 1
    assert "usage" in json.loads(capsys.readouterr().out)["error"]


def test_settings_cannot_select_another_mode_than_the_one_reported(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A ``mode`` inside the settings would run one policy under another's label."""
    with pytest.raises(ValueError, match="must not carry 'mode'"):
        dry_run("vessel-reference", "manual", {"mode": "turtle"})
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"mode": "turtle"}))
    assert main(["vessel-reference", "manual", str(settings)]) == 1
    assert "must not carry 'mode'" in json.loads(capsys.readouterr().out)["error"]


def test_the_command_line_prints_the_report_as_json(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"reward_risk": 1.5}))

    assert main(["vessel-reference", "manual", str(settings)]) == 0

    report = json.loads(capsys.readouterr().out)
    assert set(report) == {
        "strategy_id",
        "mode",
        "integrity_status",
        "trade_count",
        "exit_reasons",
        "warmup_candles",
        "evidence_hash",
        "hashes_match",
        "warning",
    }
    assert report["hashes_match"] is True


def test_the_synthetic_path_is_the_one_the_acceptance_tests_were_written_on() -> None:
    """The length and seed are fixed; changing them changes every judgment made on the path."""
    assert (synthetic_dry_run.WARMUP_HOURS, synthetic_dry_run.EVALUATION_HOURS) == (320, 240)
    assert synthetic_dry_run.SEED == 20260923
    candles = synthetic_dry_run.synthetic_hourly_candles()
    assert len(candles) == 560
    assert candles[-1].close_time == synthetic_dry_run.BASE + timedelta(
        hours=synthetic_dry_run.EVALUATION_HOURS
    )


def test_no_operational_module_imports_the_diagnostics_package() -> None:
    """The stand-ins stay in ``diagnostics``; the service and web-api never import them."""
    # The pre-deployment command is the one module allowed to import the diagnostics: it is
    # a command, and the web-api must not import it either (checked below).
    allowed = {_BACKTEST_PACKAGE / "author_check.py"}
    offenders: list[str] = []
    for package in (_BACKTEST_PACKAGE, _WEB_API_PACKAGE):
        for path in sorted(package.rglob("*.py")):
            if "diagnostics" in path.parts or path in allowed:
                continue
            if _DIAGNOSTICS_IMPORT.search(path.read_text()):
                offenders.append(str(path.relative_to(REPOSITORY_ROOT)))
    assert offenders == []
    command_import = re.compile(r"^\s*(from|import)\s+backtest_service\.author_check\b", re.M)
    assert not any(
        command_import.search(path.read_text()) for path in _WEB_API_PACKAGE.rglob("*.py")
    )
