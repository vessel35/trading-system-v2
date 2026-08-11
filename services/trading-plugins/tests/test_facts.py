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
from core_lib.types import DecisionIntent
from trading_plugins import facts
from trading_plugins.discovery import (
    PluginFault,
    discover_money_management,
    discover_strategies,
    registered_money_management,
)

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
    commands = re.findall(
        r"^\.venv/bin/python -m trading_plugins\.facts .+$",
        skill.read_text(),
        flags=re.MULTILINE,
    )

    assert commands
    for command in commands:
        arguments = shlex.split(command)
        completed = subprocess.run(
            [sys.executable, *arguments[1:]],
            cwd=repository_root,
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0, (command, completed.stdout, completed.stderr)
