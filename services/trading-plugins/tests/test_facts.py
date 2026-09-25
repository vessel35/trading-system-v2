"""Pin the strategy fact surface to its repository-owned sources."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import ClassVar, cast

import pytest
from core_lib.capabilities import PLATFORM_CAPABILITIES
from core_lib.indicators.registry import build_default_registry
from core_lib.money_management import (
    AccountRiskSnapshot,
    MarketSnapshot,
    MoneyManagementBase,
    MoneyManagementPlan,
    PolicyIndicatorRequirement,
    RiskLimits,
)
from core_lib.patterns import TALIB_PATTERN_REGISTRY
from core_lib.strategy import (
    FieldSpec,
    MoneyManagementSupport,
    ParameterSchema,
    ResolvedConfig,
    StrategyMetadata,
)
from core_lib.types import DecisionIntent
from trading_plugins import facts
from trading_plugins.discovery import (
    PluginFault,
    discover_money_management,
    discover_strategies,
    registered_money_management,
)
from trading_plugins.strategies.vessel_reference import VesselReference

_PATTERN_DEFINITION_CHECK = (
    "Check this pattern definition against docs/references/candlestick_pattern_calc_spec.md."
)


def _strict_json(value: object) -> object:
    return json.loads(json.dumps(value, allow_nan=False))


@dataclass(frozen=True, slots=True)
class _FixedPercentagePolicy(MoneyManagementBase):
    stop_pct: float = 1.5

    id: ClassVar[str] = "fixed-percentage-test-policy"
    version: ClassVar[str] = "1.0.0"

    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        return ()

    def resolved_config(self) -> Mapping[str, object]:
        return {"mode": self.id, "stop_pct": self.stop_pct}

    def plan_entry(
        self,
        decision: DecisionIntent,
        market: MarketSnapshot,
        account: AccountRiskSnapshot,
        global_limits: RiskLimits,
    ) -> MoneyManagementPlan:
        raise AssertionError("fact lookup must not plan an entry")


@dataclass(frozen=True, slots=True)
class _MultipleInputPolicy(_FixedPercentagePolicy):
    id: ClassVar[str] = "multiple-input-test-policy"

    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        return (
            PolicyIndicatorRequirement(
                name="ATR",
                params={"period": 14},
                timeframe="strategy",
                min_history=14,
            ),
            PolicyIndicatorRequirement(
                name="TURTLE_N",
                params={"period": 20},
                timeframe="1d",
                min_history=20,
            ),
        )


@dataclass(frozen=True, slots=True)
class _RequiredSettingPolicy(MoneyManagementBase):
    atr_period: int

    id: ClassVar[str] = "required-setting-test-policy"
    version: ClassVar[str] = "1.0.0"

    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        return (
            PolicyIndicatorRequirement(
                name="ATR",
                params={"period": self.atr_period},
                timeframe="strategy",
                min_history=self.atr_period,
            ),
        )

    def resolved_config(self) -> Mapping[str, object]:
        return {"mode": self.id, "atr_period": self.atr_period}

    def plan_entry(
        self,
        decision: DecisionIntent,
        market: MarketSnapshot,
        account: AccountRiskSnapshot,
        global_limits: RiskLimits,
    ) -> MoneyManagementPlan:
        raise AssertionError("fact lookup must not plan an entry")


class _GeneratedStrategy(VesselReference):
    __module__ = "trading_plugins.strategies.generated_test"

    STRATEGY_ID = "generated-test"
    VERSION = "7.8.9"
    history: ClassVar[int] = 3
    reverse_series: ClassVar[bool] = False
    timeframes: ClassVar[tuple[str, ...]] = ("5m", "1h", "4h")

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        metadata = VesselReference.get_metadata()
        metadata.min_history = cls.history
        metadata.supported_timeframes = list(cls.timeframes)
        if cls.reverse_series:
            metadata.required_indicators.reverse()
        return metadata


class _DefaultedStrategy(_GeneratedStrategy):
    __module__ = "trading_plugins.strategies.defaulted_test"

    STRATEGY_ID = "defaulted-test"
    VERSION = "7.8.9"

    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        return ParameterSchema(fields={"threshold": FieldSpec(type="number", default=0.75)})


@dataclass(frozen=True, slots=True)
class _NoSettingsPolicy(MoneyManagementBase):
    id: ClassVar[str] = "no-settings-test"
    version: ClassVar[str] = "1.0.0"

    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        return ()

    def resolved_config(self) -> Mapping[str, object]:
        return {"mode": self.id}

    def plan_entry(
        self,
        decision: DecisionIntent,
        market: MarketSnapshot,
        account: AccountRiskSnapshot,
        global_limits: RiskLimits,
    ) -> MoneyManagementPlan:
        raise AssertionError("registration generation must not plan an entry")


_NoSettingsPolicy.__module__ = "trading_plugins.money_management.no_settings_test"


@dataclass(frozen=True, slots=True)
class _ParsedRegistration:
    table: str
    row: dict[str, object]
    update_columns: tuple[str, ...]
    guard_current: tuple[str, ...]
    guard_excluded: tuple[str, ...]


def _split_sql_items(value: str) -> list[str]:
    items: list[str] = []
    start = 0
    depth = 0
    quoted = False
    index = 0
    while index < len(value):
        character = value[index]
        if quoted:
            if character == "'":
                if index + 1 < len(value) and value[index + 1] == "'":
                    index += 1
                else:
                    quoted = False
        elif character == "'":
            quoted = True
        elif character in "([":
            depth += 1
        elif character in ")]":
            depth -= 1
        elif character == "," and depth == 0:
            items.append(value[start:index].strip())
            start = index + 1
        index += 1
    items.append(value[start:].strip())
    return items


def _parse_sql_string(value: str) -> str:
    assert value.startswith("'") and value.endswith("'")
    return value[1:-1].replace("''", "'")


def _parse_sql_value(value: str) -> object:
    if value.endswith("::jsonb"):
        return json.loads(_parse_sql_string(value[: -len("::jsonb")]))
    if value.startswith("ARRAY[") and value.endswith("]::text[]"):
        inner = value[len("ARRAY[") : -len("]::text[]")]
        return [] if not inner else [_parse_sql_string(item) for item in _split_sql_items(inner)]
    if value.startswith("'"):
        return _parse_sql_string(value)
    if value in {"true", "false"}:
        return value == "true"
    return int(value)


def _parse_registration(statement: str) -> _ParsedRegistration:
    insert = re.search(
        r"INSERT INTO (?P<table>\S+) \((?P<columns>.*?)\)\s*"
        r"VALUES \((?P<values>.*?)\)\s*ON CONFLICT",
        statement,
        flags=re.DOTALL,
    )
    updates = re.search(r"DO UPDATE\s+SET\s+(?P<set>.*?)\s+WHERE \(", statement, re.DOTALL)
    guard = re.search(
        r"WHERE \((?P<current>.*?)\) IS DISTINCT FROM \((?P<excluded>.*?)\);",
        statement,
        flags=re.DOTALL,
    )
    assert insert is not None and updates is not None and guard is not None
    columns = [item.strip() for item in _split_sql_items(insert.group("columns"))]
    values = [_parse_sql_value(item) for item in _split_sql_items(insert.group("values"))]
    update_columns = tuple(
        assignment.split("=", 1)[0].strip() for assignment in _split_sql_items(updates.group("set"))
    )
    current = tuple(
        item.strip().rsplit(".", 1)[-1] for item in _split_sql_items(guard.group("current"))
    )
    excluded = tuple(
        item.strip().removeprefix("excluded.") for item in _split_sql_items(guard.group("excluded"))
    )
    return _ParsedRegistration(
        table=insert.group("table"),
        row=dict(zip(columns, values, strict=True)),
        update_columns=update_columns,
        guard_current=current,
        guard_excluded=excluded,
    )


def test_capabilities_match_the_source_entry_for_entry() -> None:
    expected = [_strict_json(asdict(entry)) for entry in PLATFORM_CAPABILITIES.values()]

    assert facts.capabilities() == expected
    for entry in expected:
        assert isinstance(entry, dict)
        assert facts.capabilities(str(entry["id"])) == entry


def test_series_match_both_registries_entry_for_entry() -> None:
    indicators = [
        {
            "name": spec.name,
            "params": dict(spec.params),
            "min_history": spec.min_history,
            "kind": "indicator",
            "pinned_impl": spec.pinned_impl,
        }
        for spec in build_default_registry().list()
    ]
    patterns = [
        {
            "name": spec.name,
            "params": dict(spec.params),
            "min_history": spec.min_history,
            "kind": "pattern",
            "version": spec.version,
            "definition_check": _PATTERN_DEFINITION_CHECK,
        }
        for spec in TALIB_PATTERN_REGISTRY.list()
    ]

    assert facts.series() == [*indicators, *patterns]
    for name in {str(item["name"]) for item in (*indicators, *patterns)}:
        assert facts.series(name) == [
            item for item in (*indicators, *patterns) if item["name"] == name
        ]


def test_deployed_includes_discovery_faults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    found, _ = discover_strategies()
    fault = PluginFault("broken.module", "broken for testing")
    monkeypatch.setattr("trading_plugins.facts.discover_strategies", lambda: (found, (fault,)))

    result = facts.deployed("strategy")

    assert result["items"] == [
        {
            "identifier": identifier,
            "class_name": strategy_class.__name__,
            "module_path": strategy_class.__module__,
        }
        for identifier, strategy_class in sorted(found.items())
    ]
    assert result["faults"] == [{"module": "broken.module", "reason": "broken for testing"}]


def test_declarations_are_strict_json_data() -> None:
    strategies, _ = discover_strategies()
    policies, _ = discover_money_management()

    for identifier in strategies:
        declared = facts.declaration("strategy", identifier)
        assert _strict_json(declared) == declared
        metadata = cast("dict[str, facts.JSONValue]", declared["metadata"])
        decision_contract = metadata["decision_contract"]
        assert isinstance(decision_contract, str)
        assert decision_contract in {
            "TradingSignal",
            "DecisionIntent",
        }
    for identifier in policies:
        declared = facts.declaration("money_management", identifier)
        assert _strict_json(declared) == declared
        requirements = cast("list[dict[str, facts.JSONValue]]", declared["indicator_requirements"])
        assert requirements
        assert all(requirement["name"] for requirement in requirements)
        assert declared["indicator_requirements_unavailable_reason"] is None


def test_policy_declaration_reports_zero_indicator_requirements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        facts,
        "discover_money_management",
        lambda: ({_FixedPercentagePolicy.id: _FixedPercentagePolicy}, ()),
    )

    declared = facts.declaration("money_management", _FixedPercentagePolicy.id)

    assert declared["indicator_requirements"] == []
    assert declared["indicator_requirements_unavailable_reason"] is None
    assert declared["settings"] == {
        "stop_pct": {"has_default": True, "default": 1.5},
    }


def test_policy_declaration_reports_multiple_indicator_requirements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        facts,
        "discover_money_management",
        lambda: ({_MultipleInputPolicy.id: _MultipleInputPolicy}, ()),
    )

    declared = facts.declaration("money_management", _MultipleInputPolicy.id)

    requirements = cast("list[dict[str, facts.JSONValue]]", declared["indicator_requirements"])
    assert [requirement["name"] for requirement in requirements] == ["ATR", "TURTLE_N"]
    assert declared["indicator_requirements_unavailable_reason"] is None


def test_policy_declaration_reports_a_setting_without_a_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        facts,
        "discover_money_management",
        lambda: ({_RequiredSettingPolicy.id: _RequiredSettingPolicy}, ()),
    )

    declared = facts.declaration("money_management", _RequiredSettingPolicy.id)

    assert declared["settings"] == {"atr_period": {"has_default": False}}
    assert declared["indicator_requirements"] == []
    assert declared["indicator_requirements_unavailable_reason"] == (
        "policy has settings without defaults"
    )


def test_strategy_declaration_reports_discovery_faults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fault = PluginFault("broken.strategy.module", "broken for testing")
    monkeypatch.setattr(facts, "discover_strategies", lambda: ({}, (fault,)))

    declared = facts.declaration("strategy", "broken-strategy")

    assert declared == {
        "kind": "strategy",
        "identifier": "broken-strategy",
        "discovery_faults": [
            {"module": "broken.strategy.module", "reason": "broken for testing"},
        ],
    }


def test_facts_source_contains_no_deployment_inventory_literals() -> None:
    source_path = Path(facts.__file__)
    source = source_path.read_text()
    inventory = {
        *registered_money_management(),
        *(spec.name for spec in build_default_registry().list()),
        *(spec.name for spec in TALIB_PATTERN_REGISTRY.list()),
    }
    recorded = {
        name
        for name in inventory
        if re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])",
            source,
            flags=re.IGNORECASE,
        )
    }

    assert recorded == set()


def test_unknown_capability_is_rejected() -> None:
    with pytest.raises(facts.FactsError, match="unknown capability"):
        facts.capabilities("not-a-platform-capability")


def test_unknown_strategy_is_rejected() -> None:
    with pytest.raises(facts.FactsError, match="unknown strategy"):
        facts.declaration("strategy", "not-a-deployed-strategy")


def test_unknown_kind_is_rejected() -> None:
    with pytest.raises(facts.FactsError, match="unknown plugin kind"):
        facts.deployed("not-a-kind")


def test_vessel_registration_matches_the_committed_declaration_and_display_columns() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    committed = _parse_registration(
        (
            repository_root
            / "init-scripts/signal-service/20260724/02-register-vessel-reference.sql"
        ).read_text()
    )
    generated = _parse_registration(
        facts.registration_sql(
            "strategy",
            "vessel-reference",
            "Vessel Reference",
            "EMA decision-only Vessel Adaptee with injected money-management policies.",
            True,
            {},
        )
    )
    compared_columns = {
        "strategy_id",
        "class_name",
        "module_path",
        "display_name",
        "description",
        "strategy_version",
        "supported_timeframes",
        "required_indicators_json",
        "min_history",
        "default_params_json",
    }

    assert {name: generated.row[name] for name in compared_columns} == {
        name: committed.row[name] for name in compared_columns
    }


def test_registration_update_and_guard_exclude_lifecycle_and_match_exactly() -> None:
    generated = _parse_registration(
        facts.registration_sql(
            "strategy",
            "vessel-reference",
            "Vessel Reference",
            "description",
            True,
        )
    )

    assert generated.update_columns == generated.guard_current
    assert generated.update_columns == generated.guard_excluded
    assert "is_active" not in generated.update_columns
    assert "is_deprecated" not in generated.update_columns

    existing = dict(generated.row)
    existing["is_active"] = False
    existing["is_deprecated"] = True
    for column in generated.update_columns:
        existing[column] = generated.row[column]

    assert existing["is_active"] is False
    assert existing["is_deprecated"] is True


def test_registration_quotes_non_ascii_module_paths_and_json_survive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        facts,
        "discover_strategies",
        lambda: ({_GeneratedStrategy.STRATEGY_ID: _GeneratedStrategy}, ()),
    )
    monkeypatch.setattr(
        _GeneratedStrategy,
        "__module__",
        "trading_plugins.strategies.o'brien",
    )
    generated = _parse_registration(
        facts.registration_sql(
            "strategy",
            _GeneratedStrategy.STRATEGY_ID,
            "O'Brien 전략",
            "인용 '문장'도 보존한다.",
            True,
            {"operator_note": "d'Artagnan"},
        )
    )

    assert generated.row["module_path"] == "trading_plugins.strategies.o'brien"
    assert generated.row["display_name"] == "O'Brien 전략"
    assert generated.row["description"] == "인용 '문장'도 보존한다."
    assert generated.row["default_params_json"] == {"operator_note": "d'Artagnan"}


def test_strategy_and_policy_declaration_shapes_generate_canonical_statements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        facts,
        "discover_strategies",
        lambda: ({_GeneratedStrategy.STRATEGY_ID: _GeneratedStrategy}, ()),
    )
    strategy = _parse_registration(
        facts.registration_sql(
            "strategy",
            _GeneratedStrategy.STRATEGY_ID,
            "Generated",
            "Several timeframes and an empty strategy parameter schema.",
            False,
        )
    )
    policy = _parse_registration(
        facts.registration_sql(
            "money_management",
            "manual",
            "Manual",
            "Several policy settings.",
            True,
        )
    )
    monkeypatch.setattr(
        facts,
        "discover_money_management",
        lambda: ({_NoSettingsPolicy.id: _NoSettingsPolicy}, ()),
    )
    empty_policy_sql = facts.registration_sql(
        "money_management",
        _NoSettingsPolicy.id,
        "No settings",
        "No setting names.",
        True,
    )

    assert strategy.row["supported_timeframes"] == ["5m", "1h", "4h"]
    assert strategy.row["default_params_json"] == {}
    assert policy.row["settings_names"] == [
        "atr_stop_multiple",
        "leverage",
        "reward_risk",
    ]
    assert "ARRAY[]::text[]" in empty_policy_sql


def test_strategy_schema_defaults_never_become_operator_default_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        facts,
        "discover_strategies",
        lambda: ({_DefaultedStrategy.STRATEGY_ID: _DefaultedStrategy}, ()),
    )
    absent = _parse_registration(
        facts.registration_sql(
            "strategy",
            _DefaultedStrategy.STRATEGY_ID,
            "Defaulted",
            "The operator column is independent.",
            True,
        )
    )
    supplied = _parse_registration(
        facts.registration_sql(
            "strategy",
            _DefaultedStrategy.STRATEGY_ID,
            "Defaulted",
            "The operator column is independent.",
            True,
            {"threshold": 0.5},
        )
    )

    assert absent.row["default_params_json"] == {}
    assert supplied.row["default_params_json"] == {"threshold": 0.5}


def test_registration_guard_is_stable_and_changes_for_a_declared_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        facts,
        "discover_strategies",
        lambda: ({_GeneratedStrategy.STRATEGY_ID: _GeneratedStrategy}, ()),
    )
    first_sql = facts.registration_sql(
        "strategy",
        _GeneratedStrategy.STRATEGY_ID,
        "Generated",
        "Stable declaration.",
        True,
    )
    first = _parse_registration(first_sql)
    unchanged_row = dict(first.row)
    assert not any(unchanged_row[column] != first.row[column] for column in first.update_columns)

    monkeypatch.setattr(_GeneratedStrategy, "reverse_series", True)
    reordered_sql = facts.registration_sql(
        "strategy",
        _GeneratedStrategy.STRATEGY_ID,
        "Generated",
        "Stable declaration.",
        True,
    )
    assert reordered_sql == first_sql

    first_history = first.row["min_history"]
    assert isinstance(first_history, int)
    monkeypatch.setattr(_GeneratedStrategy, "history", first_history + 1)
    changed = _parse_registration(
        facts.registration_sql(
            "strategy",
            _GeneratedStrategy.STRATEGY_ID,
            "Generated",
            "Stable declaration.",
            True,
        )
    )
    assert any(first.row[column] != changed.row[column] for column in first.update_columns)


def test_registration_rejects_non_finite_json_and_an_outside_module_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(facts.FactsError, match="non-finite"):
        facts.registration_sql(
            "strategy",
            "vessel-reference",
            "Vessel",
            "description",
            True,
            {"not_finite": float("nan")},
        )

    monkeypatch.setattr(
        facts,
        "discover_strategies",
        lambda: ({_GeneratedStrategy.STRATEGY_ID: _GeneratedStrategy}, ()),
    )
    monkeypatch.setattr(_GeneratedStrategy, "__module__", "outside_plugins.generated")
    with pytest.raises(facts.FactsError, match="module_path must be inside"):
        facts.registration_sql(
            "strategy",
            _GeneratedStrategy.STRATEGY_ID,
            "Generated",
            "description",
            True,
        )


def test_catalog_precheck_passes_matching_rows_and_names_runtime_mismatches() -> None:
    strategy_row = _parse_registration(
        facts.registration_sql(
            "strategy",
            "vessel-reference",
            "Vessel",
            "description",
            True,
        )
    ).row
    strategy_pass = facts.catalog_precheck("strategy", "vessel-reference", strategy_row)
    mismatched_strategy_row = dict(strategy_row)
    mismatched_strategy_row["min_history"] = cast(int, strategy_row["min_history"]) + 1
    strategy_failure = facts.catalog_precheck(
        "strategy", "vessel-reference", mismatched_strategy_row
    )

    policy_row = _parse_registration(
        facts.registration_sql(
            "money_management",
            "manual",
            "Manual",
            "description",
            True,
        )
    ).row
    policy_pass = facts.catalog_precheck("money_management", "manual", policy_row)
    mismatched_policy_row = dict(policy_row)
    mismatched_policy_row["settings_names"] = []
    policy_failure = facts.catalog_precheck("money_management", "manual", mismatched_policy_row)

    assert strategy_pass["passed"] is True
    assert policy_pass["passed"] is True
    assert strategy_failure["passed"] is False
    assert policy_failure["passed"] is False
    strategy_findings = cast("list[dict[str, facts.JSONValue]]", strategy_failure["findings"])
    policy_findings = cast("list[dict[str, facts.JSONValue]]", policy_failure["findings"])
    assert [finding["state"] for finding in strategy_findings] == ["declaration_mismatch"]
    assert [finding["reason"] for finding in policy_findings] == ["declaration_mismatch"]
    expected_not_checked = [
        "execution timeframe support",
        "series resolution",
        "policy input arity",
        "live-signal capability",
        "return-type violation on the first decision",
    ]
    for result in (strategy_pass, strategy_failure, policy_pass, policy_failure):
        assert result["not_checked"] == expected_not_checked


def test_registration_tools_are_reachable_from_the_facts_command_line() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    commands = (
        (
            "registration_sql",
            "strategy",
            "vessel-reference",
            "Vessel",
            "설명",
            "true",
            '{"operator": "value"}',
        ),
        ("catalog_precheck", "strategy", "vessel-reference"),
    )

    for command in commands:
        completed = subprocess.run(
            [sys.executable, "-m", "trading_plugins.facts", *command],
            cwd=repository_root,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stdout
        assert json.loads(completed.stdout)


def test_command_line_failure_is_one_json_error_on_stdout() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "trading_plugins.facts", "capabilities", "unknown"],
        cwd=Path(__file__).parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == {"error": "unknown capability: unknown"}


def test_author_strategy_fact_commands_are_accepted() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    skill = repository_root / ".claude/skills/author-strategy/SKILL.md"
    strategies = cast(
        "list[dict[str, facts.JSONValue]]",
        facts.deployed("strategy")["items"],
    )
    policies = cast(
        "list[dict[str, facts.JSONValue]]",
        facts.deployed("money_management")["items"],
    )
    assert strategies and policies
    placeholders = {
        "<deployed-strategy-identifier>": cast(str, strategies[0]["identifier"]),
        "<deployed-money-management-identifier>": cast(str, policies[0]["identifier"]),
    }
    commands = re.findall(
        r"^\.venv/bin/python -m trading_plugins\.facts .+$",
        skill.read_text(),
        flags=re.MULTILINE,
    )

    assert commands
    for command in commands:
        for placeholder, identifier in placeholders.items():
            command = command.replace(placeholder, identifier)
        arguments = shlex.split(command)
        completed = subprocess.run(
            [sys.executable, *arguments[1:]],
            cwd=repository_root,
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0, (command, completed.stdout, completed.stderr)


class _MisdeclaringVessel(VesselReference):
    """Declare a manual setting the manual policy has no name for."""

    STRATEGY_ID = "misdeclaring-vessel"
    VERSION = "1.0.0"

    def __init__(self, config: ResolvedConfig) -> None:
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        metadata = super().get_metadata()
        metadata.money_management = MoneyManagementSupport(
            supported=("manual",),
            default="manual",
            default_settings={"manual": {"not_a_setting": 1.0}},
            supports_external_stop=True,
            supports_external_take_profit=True,
            supports_signal_exit=True,
        )
        return metadata


def test_declaration_reports_the_default_settings_a_strategy_declares(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Declaring(VesselReference):
        STRATEGY_ID = "declaring-vessel"
        VERSION = "1.0.0"

        @classmethod
        def get_metadata(cls) -> StrategyMetadata:
            metadata = super().get_metadata()
            metadata.money_management = MoneyManagementSupport(
                supported=("manual",),
                default="manual",
                default_settings={"manual": {"atr_stop_multiple": 1.5}},
                supports_external_stop=True,
                supports_external_take_profit=True,
                supports_signal_exit=True,
            )
            return metadata

    monkeypatch.setattr(
        facts, "discover_strategies", lambda: ({"declaring-vessel": _Declaring}, ())
    )

    declared = facts.declaration("strategy", "declaring-vessel")

    metadata = cast("dict[str, facts.JSONValue]", declared["metadata"])
    support = cast("dict[str, facts.JSONValue]", metadata["money_management"])
    assert support["default_settings"] == {"manual": {"atr_stop_multiple": 1.5}}


def test_catalog_precheck_refuses_default_settings_the_policy_does_not_accept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        facts,
        "discover_strategies",
        lambda: ({"misdeclaring-vessel": _MisdeclaringVessel}, ()),
    )
    monkeypatch.setattr(
        _MisdeclaringVessel, "__module__", "trading_plugins.strategies.vessel_reference"
    )

    result = facts.catalog_precheck("strategy", "misdeclaring-vessel")

    assert result["passed"] is False
    assert result["adapter_construction_error"] is None
    findings = cast("list[dict[str, facts.JSONValue]]", result["findings"])
    assert [finding["rule"] for finding in findings] == ["policy-default-settings-refused"]
    assert findings[0]["mode"] == "manual"
    assert "not_a_setting" in str(findings[0]["detail"])
    assert "policy default settings" in cast("list[str]", result["checks_performed"])
