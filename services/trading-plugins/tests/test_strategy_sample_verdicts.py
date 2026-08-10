"""Hold the two sample verdicts to the facts they were decided on.

``docs/fullspec/strategy_sample_verdicts.md`` says why neither document in
``docs/samples_for_strategy_agent/`` can be built as written. Each reason rests on
something absent from this platform, and absence is exactly what goes stale
quietly. When one of these fails, the platform gained a capability or a
calculation and the verdict has to be decided again.
"""

from __future__ import annotations

import dataclasses

from core_lib.capabilities import capability
from core_lib.indicators.registry import build_default_registry
from core_lib.patterns import TALIB_PATTERN_REGISTRY
from trading_plugins.money_management.manual import ManualMoneyManagement


def _registered_series_names() -> set[str]:
    return {
        *(spec.name.casefold() for spec in build_default_registry().list()),
        *(spec.name.casefold() for spec in TALIB_PATTERN_REGISTRY.list()),
    }


def test_heikin_ashi_is_not_a_registered_series() -> None:
    """The first sample's trigger is a Heikin-Ashi body, and there is no such candle."""
    names = _registered_series_names()

    assert not [name for name in names if "heikin" in name or "ashi" in name]
    assert capability("candles.kinds").value == ("exchange_confirmed_ohlcv", "resampled")


def test_the_first_sample_needs_three_things_this_platform_lacks() -> None:
    # A cap of five trades a day needs the outcome of earlier trades, which never
    # reaches a strategy.
    assert capability("risk.between_trade_rules").value == ()
    assert capability("run.strategy_inputs").value == (
        "candles",
        "candle",
        "symbol",
        "timeframe",
        "market_type",
        "indicators",
    )
    # A fixed-percentage stop needs no market input, and a policy must declare one.
    assert capability("money_management.volatility_inputs_per_policy").value == 1
    # The document suggests one to two percent per trade; only the first is allowed.
    assert capability("risk.max_risk_per_trade").value == 0.01


def test_the_second_sample_is_not_blocked_by_multiple_timeframes() -> None:
    """Guard the correction that a design review had to make.

    Declaring a 4h series inside a 15m run works. What does not work is walking
    the raw 4h candles, which is what the sample's zone construction needs.
    """
    assert capability("series.multi_timeframe").value is True
    assert capability("series.raw_candle_streams").value == 1


def test_the_second_sample_needs_four_things_this_platform_lacks() -> None:
    assert capability("exit.partial").value is False
    assert capability("exit.trailing_stop").value is False
    assert capability("money_management.protection_fixed_at_entry").value is True
    assert capability("run.traded_symbols").value == 1


def test_the_second_samples_first_experiment_still_has_its_materials() -> None:
    """H1 stays feasible: engulfing, ATR(14), and a fixed reward-to-risk exit."""
    registered = {
        (spec.name, tuple(sorted(spec.params.items()))) for spec in build_default_registry().list()
    }
    settings = {field.name for field in dataclasses.fields(ManualMoneyManagement)}

    assert "pat_engulfing" in _registered_series_names()
    assert ("ATR", (("period", 14),)) in registered
    assert {"atr_stop_multiple", "reward_risk"} <= settings


def test_the_first_experiment_carries_two_approved_deviations() -> None:
    """Both differences the verdict says a user must approve are still real."""
    # The document enters at the trigger bar's close; this platform fills next bar.
    assert capability("run.fill_timing").value == ("next_bar",)
    # The document's hammer is a wick ratio; the registered one is TA-Lib's.
    assert capability("registry.name_does_not_fix_definition").value is True
    patterns = {spec.name: spec for spec in TALIB_PATTERN_REGISTRY.list()}
    assert "talib" in patterns["pat_hammer"].version
    assert "talib" in patterns["pat_shooting_star"].version
