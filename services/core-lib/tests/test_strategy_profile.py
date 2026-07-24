"""Verify strategy metadata and profile schema constraints."""

import pytest
from core_lib.strategy import StrategyMetadata, StrategyProfile


def make_profile(**overrides: object) -> StrategyProfile:
    values: dict[str, object] = {
        "id": "fake-breakout-profile",
        "family": "breakout",
        "bar": "1h",
        "expected_win_rate": (0.35, 0.55),
        "expected_payoff": (1.5, 3.0),
        "tail_shape": "right_fat",
        "holding_horizon": "multi_day",
        "primary_metric": "calmar",
        "risk_adjusted_pref": "sortino",
        "profit_structure_to_preserve": "few_large_winners",
        "envelope_tolerance": 0.1,
        "envelope_status": "provisional",
    }
    values.update(overrides)
    return StrategyProfile(**values)  # type: ignore[arg-type]


def test_profile_and_metadata_carry_strategy_owned_shape() -> None:
    profile = make_profile()
    metadata = StrategyMetadata(
        required_indicators=[{"name": "EMA", "params": {"period": 21}}],
        min_history=55,
        supported_timeframes=["1h", "4h"],
        profile=profile,
    )
    assert metadata.profile.envelope_status == "provisional"
    assert metadata.required_indicators[0]["name"] == "EMA"


def test_established_is_a_valid_maturity_without_imposing_a_universal_gate() -> None:
    assert make_profile(envelope_status="established").envelope_status == "established"


def test_profile_rejects_invalid_envelopes_and_vocabularies() -> None:
    with pytest.raises(ValueError, match="expected_win_rate"):
        make_profile(expected_win_rate=(0.8, 0.2))
    with pytest.raises(ValueError, match="tail_shape"):
        make_profile(tail_shape="unknown")
    with pytest.raises(ValueError, match="envelope_status"):
        make_profile(envelope_status="final")
    with pytest.raises(ValueError, match="tolerance"):
        make_profile(envelope_tolerance=-0.1)
