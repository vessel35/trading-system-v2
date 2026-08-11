"""Pin the strategy fact surface to its repository-owned sources."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import cast

import pytest
from core_lib.capabilities import PLATFORM_CAPABILITIES
from core_lib.indicators.registry import build_default_registry
from core_lib.patterns import TALIB_PATTERN_REGISTRY
from trading_plugins import facts
from trading_plugins.discovery import PluginFault, discover_money_management, discover_strategies

_PATTERN_DEFINITION_CHECK = (
    "Check this pattern definition against docs/references/candlestick_pattern_calc_spec.md."
)


def _strict_json(value: object) -> object:
    return json.loads(json.dumps(value, allow_nan=False))


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
        requirement = cast("dict[str, facts.JSONValue]", declared["indicator_requirement"])
        assert requirement["name"]


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
