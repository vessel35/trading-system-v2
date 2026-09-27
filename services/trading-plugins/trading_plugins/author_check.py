"""Stages 1 to 5 of the pre-deployment check: what needs neither the Engine nor a database.

Design: ``docs/fullspec/author_check_and_scaffold_design.md`` sections 3.4 and 3.4.2. One
strategy id goes through discovery (with the identifier rule), declaration (series registered,
timeframes well formed), money-management composition (the runtime called for every declared
mode with a representative setting), parameter ownership (no policy-owned name in the schema),
and the catalog precheck. Each stage catches its own failure and reports it under a rule name
from ``RULES``; the command exits 1 if any stage failed.

``backtest_service.author_check`` imports this module for its first five stages and adds the
Engine run and the subprocess stages. The MCP server carries these five stages as one tool.

This module reads ``facts`` and never edits it: the fact module's closed command set and its
pinned tests stay as they are. Like ``facts``, it never touches a database, prints JSON only,
and names no deployed inventory (mode, indicator, or pattern names) in its source.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import MISSING, dataclass, field, fields
from pathlib import Path
from typing import Any, Final, Literal, cast

from core_lib.identifiers import PLUGIN_IDENTIFIER_PATTERN, is_plugin_identifier
from core_lib.indicators import DEFAULT_REGISTRY
from core_lib.money_management import MoneyManagementBase, policy_settings
from core_lib.patterns import DEFAULT_PATTERN_REGISTRY
from core_lib.ports import StrategyRegistry
from core_lib.series import series_key_of
from core_lib.series_resolution import series_specs_from_descriptors
from core_lib.strategy import AdapterClass, AdapterManager, InProcessStrategyRegistry

from . import facts
from .discovery import PluginFault, discover_money_management, discover_strategies

__all__ = [
    "MONEY_MANAGEMENT_OWNED_PARAMETERS",
    "RULES",
    "CheckReport",
    "Finding",
    "StageResult",
    "check",
    "main",
    "representative_settings",
    "stage_declaration",
    "stage_discovery",
    "stage_money_management",
    "stage_parameters",
    "stage_registration",
]

# The authoring contract (section 4.2) reserves these names for money management. The
# strategy-unit layer of the common checks keeps its own copy inside its test module, which
# cannot be imported from here; when the contract changes, both change.
MONEY_MANAGEMENT_OWNED_PARAMETERS: Final = frozenset(
    {
        "leverage",
        "reward_risk",
        "atr_stop_multiple",
        "risk_per_trade",
        "position_size_pct",
        "margin",
        "quantity",
    }
)

RULES: Final = frozenset(
    {
        "discovery-fault",
        "identifier-format",
        "timeframe-format",
        "series-unregistered",
        "policy-mode-not-deployed",
        "policy-settings-required",
        "runtime-refused",
        "parameter-policy-owned",
        "precheck-failed",
        "declaration-unreadable",
        "dry-run-error",
        "dry-run-integrity",
        "dry-run-nondeterministic",
        "qa-failed",
        "unit-tests-failed",
        "integration-tests-failed",
        "mode-settings-invalid",
        "stage-not-run",
    }
)
"""Every rule name a finding may carry, in this module and in the backtest-service stages."""

Status = Literal["passed", "failed", "skipped"]
JSONObject = dict[str, Any]


@dataclass(frozen=True)
class Finding:
    """One reason a stage failed, under a rule name from ``RULES``."""

    rule: str
    detail: str
    data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.rule not in RULES:
            raise ValueError(f"unknown rule name: {self.rule}")

    def as_json(self) -> JSONObject:
        return {"rule": self.rule, "detail": self.detail, **dict(self.data)}


@dataclass(frozen=True)
class StageResult:
    """The outcome of one numbered stage."""

    stage: int
    name: str
    status: Status
    findings: tuple[Finding, ...] = ()
    detail: str | None = None
    data: Mapping[str, Any] = field(default_factory=dict)

    def as_json(self) -> JSONObject:
        return {
            "stage": self.stage,
            "name": self.name,
            "status": self.status,
            "findings": [finding.as_json() for finding in self.findings],
            "detail": self.detail,
            "data": dict(self.data),
        }


@dataclass(frozen=True)
class CheckReport:
    """Every stage that ran, and one verdict over them.

    ``passed`` is true only when every stage passed. A skipped stage is not a pass, so a
    report with a skipped stage is ``incomplete``; it is still not ``failed``, and the command
    exits 0 on it, because the only skippable stage is the database one and its absence is an
    environment fact rather than a defect in the strategy.
    """

    strategy_id: str
    stages: tuple[StageResult, ...]

    @property
    def failed(self) -> bool:
        return any(stage.status == "failed" for stage in self.stages)

    @property
    def passed(self) -> bool:
        return all(stage.status == "passed" for stage in self.stages)

    @property
    def verdict(self) -> Literal["passed", "incomplete", "failed"]:
        if self.failed:
            return "failed"
        return "passed" if self.passed else "incomplete"

    def as_json(self) -> JSONObject:
        return {
            "strategy_id": self.strategy_id,
            "verdict": self.verdict,
            "passed": self.passed,
            "failed": self.failed,
            "skipped_stages": [stage.stage for stage in self.stages if stage.status == "skipped"],
            "stages": [stage.as_json() for stage in self.stages],
        }


def _failed(stage: int, name: str, *findings: Finding, detail: str | None = None) -> StageResult:
    return StageResult(stage, name, "failed", tuple(findings), detail)


def _passed(stage: int, name: str, **data: Any) -> StageResult:
    return StageResult(stage, name, "passed", (), None, data)


def not_run(stage: int, name: str, because: str) -> StageResult:
    """A stage that could not run because an earlier one failed: a failure, not a skip."""
    return _failed(stage, name, Finding("stage-not-run", because))


# --- stage 1: discovery -------------------------------------------------------------------


def stage_discovery(
    strategy_id: str,
    *,
    discovered: tuple[Mapping[str, AdapterClass], tuple[PluginFault, ...]] | None = None,
) -> tuple[StageResult, AdapterClass | None]:
    """The id is discovered in the fixed package without a fault, including the id rule."""
    name = "discovery"
    found, faults = discover_strategies() if discovered is None else discovered
    if not is_plugin_identifier(strategy_id):
        finding = Finding(
            "identifier-format",
            f"strategy id must be kebab-case: {PLUGIN_IDENTIFIER_PATTERN.pattern}",
            {"strategy_id": strategy_id},
        )
        return _failed(1, name, finding), None
    cls = found.get(strategy_id)
    if cls is not None:
        return _passed(1, name, class_name=cls.__name__, module_path=cls.__module__), cls
    findings = [
        Finding("discovery-fault", fault.reason, {"module": fault.module}) for fault in faults
    ]
    if not findings:
        findings.append(
            Finding(
                "discovery-fault",
                "no deployed file declares this strategy id",
                {"strategy_id": strategy_id},
            )
        )
    return _failed(1, name, *findings), None


# --- stage 2: declaration -----------------------------------------------------------------


def stage_declaration(strategy_id: str, cls: AdapterClass) -> StageResult:
    """Every declared series is registered and every supported timeframe is well formed."""
    name = "declaration"
    try:
        metadata = cls.get_metadata()
    except (Exception, SystemExit) as error:  # noqa: BLE001 - the failure is the finding
        return _failed(
            2, name, Finding("declaration-unreadable", f"{type(error).__name__}: {error}")
        )
    findings: list[Finding] = []
    timeframes = list(metadata.supported_timeframes)
    if not timeframes:
        findings.append(Finding("timeframe-format", "supported_timeframes is empty"))
    for timeframe in timeframes:
        try:
            series_key_of("probe", {}, str(timeframe))
        except (Exception, SystemExit) as error:  # noqa: BLE001
            findings.append(
                Finding("timeframe-format", str(error), {"timeframe": _plain(timeframe)})
            )
    well_formed = [
        timeframe
        for timeframe in timeframes
        if not any(item.data.get("timeframe") == timeframe for item in findings)
    ]
    for descriptor in metadata.required_indicators:
        for timeframe in well_formed:
            try:
                series_specs_from_descriptors(
                    [descriptor],
                    DEFAULT_REGISTRY,
                    DEFAULT_PATTERN_REGISTRY,
                    execution_timeframe=str(timeframe),
                )
            except (Exception, SystemExit) as error:  # noqa: BLE001
                findings.append(
                    Finding(
                        "series-unregistered",
                        f"{type(error).__name__}: {error}",
                        {"declared": _plain(descriptor), "timeframe": str(timeframe)},
                    )
                )
                break
    if findings:
        return _failed(2, name, *findings)
    return _passed(
        2,
        name,
        series=[_plain(item) for item in metadata.required_indicators],
        supported_timeframes=[str(item) for item in timeframes],
        strategy_id=strategy_id,
    )


# --- stage 3: money-management composition ------------------------------------------------


def _settings_without_defaults(policy_class: type[MoneyManagementBase]) -> frozenset[str]:
    names = policy_settings(policy_class)
    return frozenset(
        declared.name
        for declared in fields(cast(Any, policy_class))
        if declared.name in names
        and declared.default is MISSING
        and declared.default_factory is MISSING
    )


def representative_settings(
    cls: AdapterClass,
    mode: str,
    policy_class: type[MoneyManagementBase],
    overrides: Mapping[str, object] | None,
) -> tuple[dict[str, object], frozenset[str]]:
    """The strategy's declared settings for ``mode`` under the caller's overrides.

    Returns the merged settings and the names the policy requires that are still missing.
    """
    support = cls.get_metadata().money_management
    merged: dict[str, object] = dict(support.default_settings.get(mode, {}))
    extra = dict(overrides or {})
    if "mode" in extra:
        raise ValueError("settings for a mode must not carry 'mode'; the mode is the key")
    merged.update(extra)
    missing = _settings_without_defaults(policy_class) - set(merged)
    return merged, missing


class _Rows(StrategyRegistry):
    """The registration row each class would carry, for composing outside the database."""

    def __init__(self, strategies: Mapping[str, AdapterClass]) -> None:
        self._strategies = dict(strategies)

    def get(self, strategy_id: str) -> dict[str, object]:
        cls = self._strategies[strategy_id]
        return {
            "strategy_id": strategy_id,
            "class_name": cls.__name__,
            "module_path": cls.__module__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get(strategy_id) for strategy_id in self._strategies]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError("the check composes on read-only rows")


def _manager(
    strategies: Mapping[str, AdapterClass],
    policies: Mapping[str, type[MoneyManagementBase]],
) -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    for strategy_id, cls in strategies.items():
        plugins.register(strategy_id, cls)
    return AdapterManager(_Rows(strategies), plugins, money_management_policies=policies)


def stage_money_management(
    strategy_id: str,
    cls: AdapterClass,
    *,
    policies: Mapping[str, type[MoneyManagementBase]] | None = None,
    mode_settings: Mapping[str, Mapping[str, object]] | None = None,
) -> StageResult:
    """The runtime accepts every declared mode with its representative settings."""
    name = "money-management"
    deployed, policy_faults = _deployed_policies() if policies is None else (policies, ())
    try:
        support = cls.get_metadata().money_management
    except (Exception, SystemExit) as error:  # noqa: BLE001
        return _failed(
            3, name, Finding("declaration-unreadable", f"{type(error).__name__}: {error}")
        )
    findings: list[Finding] = []
    composed: list[str] = []
    manager = _manager({strategy_id: cls}, deployed)
    raw = {"strategy_id": strategy_id, "params": {}}
    for mode in support.supported:
        policy_class = deployed.get(mode)
        if policy_class is None:
            findings.append(
                Finding(
                    "policy-mode-not-deployed",
                    "declared mode is not deployed",
                    {
                        "mode": mode,
                        "policy_discovery_faults": [
                            {"module": fault.module, "reason": fault.reason}
                            for fault in policy_faults
                        ],
                    },
                )
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
            manager.create_runtime(strategy_id, raw, {**settings, "mode": mode})
        except (Exception, SystemExit) as error:  # noqa: BLE001
            findings.append(
                Finding("runtime-refused", f"{type(error).__name__}: {error}", {"mode": mode})
            )
            continue
        composed.append(mode)
    if findings:
        return _failed(3, name, *findings)
    return _passed(3, name, composed_modes=composed, default_mode=support.default)


def _deployed_policies() -> tuple[Mapping[str, type[MoneyManagementBase]], tuple[PluginFault, ...]]:
    return discover_money_management()


# --- stage 4: parameters ------------------------------------------------------------------


def stage_parameters(strategy_id: str, cls: AdapterClass) -> StageResult:
    """The parameter schema holds no name the money-management policy owns."""
    name = "parameters"
    del strategy_id
    try:
        schema = cls.get_parameter_schema()
    except (Exception, SystemExit) as error:  # noqa: BLE001
        return _failed(
            4, name, Finding("declaration-unreadable", f"{type(error).__name__}: {error}")
        )
    owned = sorted(set(schema.fields) & MONEY_MANAGEMENT_OWNED_PARAMETERS)
    if owned:
        return _failed(
            4,
            name,
            *(
                Finding(
                    "parameter-policy-owned",
                    "this name belongs to the money-management policy (contract section 4.2)",
                    {"parameter": item},
                )
                for item in owned
            ),
        )
    return _passed(4, name, parameters=sorted(schema.fields))


# --- stage 5: registration precheck -------------------------------------------------------


def stage_registration(strategy_id: str) -> StageResult:
    """The row the registration statement would insert passes the catalog precheck."""
    name = "registration"
    try:
        result = facts.catalog_precheck("strategy", strategy_id)
    except (Exception, SystemExit) as error:  # noqa: BLE001
        return _failed(5, name, Finding("precheck-failed", f"{type(error).__name__}: {error}"))
    if result.get("passed") is True:
        return _passed(5, name, checks_performed=list(cast(list[str], result["checks_performed"])))
    findings = [
        Finding("precheck-failed", "the catalog precheck reported a finding", {"finding": item})
        for item in cast(list[Any], result.get("findings", []))
    ]
    construction_error = result.get("adapter_construction_error")
    if construction_error is not None:
        findings.append(Finding("precheck-failed", str(construction_error)))
    if not findings:
        findings.append(Finding("precheck-failed", "the catalog precheck did not pass"))
    return _failed(5, name, *findings)


# --- the five together ------------------------------------------------------------------


def check(
    strategy_id: str,
    *,
    mode_settings: Mapping[str, Mapping[str, object]] | None = None,
    discovered: tuple[Mapping[str, AdapterClass], tuple[PluginFault, ...]] | None = None,
    policies: Mapping[str, type[MoneyManagementBase]] | None = None,
    with_registration: bool = True,
) -> CheckReport:
    """Run stages 1 to 5 in order.

    ``discovered`` and ``policies`` let a test inject a throwaway package; they are Python
    arguments only and are not on the command line or the MCP surface. The registration stage
    only makes sense for a class in the deployed package, so a test that injects one turns it
    off with ``with_registration``.
    """
    first, cls = stage_discovery(strategy_id, discovered=discovered)
    stages: list[StageResult] = [first]
    if cls is None:
        because = "stage 1 (discovery) failed"
        stages.extend(
            not_run(number, name, because)
            for number, name in (
                (2, "declaration"),
                (3, "money-management"),
                (4, "parameters"),
                (5, "registration"),
            )
        )
        return CheckReport(strategy_id, tuple(stages))
    stages.append(stage_declaration(strategy_id, cls))
    stages.append(
        stage_money_management(strategy_id, cls, policies=policies, mode_settings=mode_settings)
    )
    stages.append(stage_parameters(strategy_id, cls))
    if with_registration:
        stages.append(stage_registration(strategy_id))
    return CheckReport(strategy_id, tuple(stages))


def _plain(value: object) -> Any:
    """Make a declaration value JSON-safe without stringifying what already is."""
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [_plain(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


# --- command line -------------------------------------------------------------------------

_USAGE: Final = (
    "usage: python -m trading_plugins.author_check <strategy-id> [--mode-settings <file>]"
)


def load_mode_settings(path: str) -> dict[str, Mapping[str, object]]:
    """Read ``{mode: {setting: value}}`` from a JSON file."""
    loaded = json.loads(Path(path).read_text())
    if not isinstance(loaded, dict) or not all(
        isinstance(value, dict) for value in loaded.values()
    ):
        raise ValueError("--mode-settings must hold a JSON object of mode to settings object")
    if any("mode" in settings for settings in loaded.values()):
        raise ValueError(
            "--mode-settings: a settings object must not carry 'mode'; the mode is the key"
        )
    return {str(mode): dict(settings) for mode, settings in loaded.items()}


def parse_arguments(argv: Sequence[str]) -> tuple[str, str | None]:
    """Return the strategy id and the optional settings path, or raise with the usage."""
    arguments = list(argv)
    settings_path: str | None = None
    if "--mode-settings" in arguments:
        index = arguments.index("--mode-settings")
        if index + 1 >= len(arguments):
            raise ValueError(_USAGE)
        settings_path = arguments[index + 1]
        del arguments[index : index + 2]
    if len(arguments) != 1:
        raise ValueError(_USAGE)
    return arguments[0], settings_path


def main(argv: Sequence[str] | None = None) -> int:
    """Print the JSON report; exit 1 when a stage failed or the arguments were wrong."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        strategy_id, settings_path = parse_arguments(arguments)
        mode_settings = None if settings_path is None else load_mode_settings(settings_path)
    except (Exception, SystemExit) as error:  # noqa: BLE001 - the boundary reports, never raises
        print(json.dumps({"error": f"{type(error).__name__}: {error}"}))
        return 1
    report = check(strategy_id, mode_settings=mode_settings)
    print(json.dumps(report.as_json(), sort_keys=True))
    return 1 if report.failed else 0


if __name__ == "__main__":  # pragma: no cover - exercised through main() in tests
    sys.exit(main())
