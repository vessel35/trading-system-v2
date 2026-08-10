"""Pin the platform capabilities that core_lib can see for itself.

Every test here is named by an entry in ``core_lib.capabilities``. When one of
these fails, the platform gained or lost a capability and the recorded statement
has to be rewritten before the change lands.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import inspect
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast, get_args

import pytest
from core_lib.candles import resample_confirmed_ohlcv
from core_lib.capabilities import PLATFORM_CAPABILITIES, CapabilityProof, capability
from core_lib.execution import match, normalize_order
from core_lib.indicators.registry import IndicatorSpec, build_default_registry
from core_lib.money_management import (
    MoneyManagementBase,
    MoneyManagementPlan,
    PolicyIndicatorRequirement,
    RiskLimits,
)
from core_lib.patterns import TALIB_PATTERN_REGISTRY
from core_lib.ports import CostModel
from core_lib.series import SeriesValue, resolve_series_timeframe
from core_lib.sizing import exposure_limit
from core_lib.types import (
    Candle,
    DecisionIntent,
    MarketType,
    Order,
    OrderRequest,
    OrderSide,
    OrderType,
    PositionSide,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_every_capability_names_a_test_that_exists() -> None:
    """Keep a capability from outliving the check it points at.

    This proves the reference resolves and nothing more. Whether the named test
    is collected, is not skipped, and asserts the right thing is a review
    question; an empty function of the same name would satisfy this.
    """
    missing: list[str] = []
    for entry in PLATFORM_CAPABILITIES.values():
        for reference in entry.verified_by:
            path, _, function = reference.partition("::")
            source = REPOSITORY_ROOT / path
            if not source.is_file() or f"def {function}(" not in source.read_text():
                missing.append(f"{entry.id} -> {reference}")
    assert missing == []


def test_every_capability_is_stated_and_proved_one_of_two_ways() -> None:
    for entry in PLATFORM_CAPABILITIES.values():
        assert entry.statement.strip()
        assert entry.proof in {CapabilityProof.STRUCTURE, CapabilityProof.BEHAVIOR}
    assert capability("exit.partial").value is False
    with pytest.raises(KeyError, match="unknown capability"):
        capability("exit.partial.please")


def test_series_come_from_two_disjoint_registries() -> None:
    indicators = {spec.name for spec in build_default_registry().list()}
    patterns = {spec.name for spec in TALIB_PATTERN_REGISTRY.list()}

    assert indicators and patterns
    assert indicators.isdisjoint(patterns)
    assert capability("series.sources").value == ("indicator registry", "pattern registry")


def test_a_series_may_name_another_timeframe_but_not_the_running_one() -> None:
    assert resolve_series_timeframe("strategy", "1h") == "1h"
    assert resolve_series_timeframe("4h", "1h") == "4h"
    with pytest.raises(ValueError, match="must be declared as 'strategy'"):
        resolve_series_timeframe("1h", "1h")
    assert capability("series.multi_timeframe").value is True


def test_an_unregistered_parameter_combination_is_refused() -> None:
    """Build the missing combination out of a registered one.

    Naming a concrete absent combination would make this fail the day someone
    registers it, which is a normal thing to do and must never break the
    capability list.
    """
    registry = build_default_registry()
    sample, name, value = next(
        (spec, key, item)
        for spec in registry.list()
        for key, item in spec.params.items()
        if isinstance(item, int) and not isinstance(item, bool)
    )
    absent = {**dict(sample.params), name: value + 10_000}

    assert registry.get(sample.name, sample.params) is sample
    with pytest.raises(KeyError, match="indicator is not registered"):
        registry.get(sample.name, absent)
    assert capability("series.registration_unit").value == "name and parameter combination"


def test_a_series_value_is_a_number_or_named_numbers() -> None:
    assert get_args(SeriesValue) == (float, dict[str, float])
    assert capability("series.value_shapes").value == ("float", "dict[str, float]")


def test_a_candle_does_not_carry_a_kind() -> None:
    fields = {field.name for field in dataclasses.fields(Candle)}

    assert fields == {
        "symbol",
        "exchange",
        "timeframe",
        "open_time",
        "close_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
    }
    # Regrouping into a longer timeframe is the only transformation core_lib does.
    assert callable(resample_confirmed_ohlcv)
    assert capability("candles.kinds").value == ("exchange_confirmed_ohlcv", "resampled")


def test_a_decision_carries_no_sizing_or_protection() -> None:
    fields = tuple(field.name for field in dataclasses.fields(DecisionIntent))

    assert fields == capability("decision.intent_fields").value
    assert not {"stop_loss", "take_profit", "quantity", "leverage"} & set(fields)


def test_a_policy_requirement_timeframe_is_not_validated() -> None:
    """Show the gap the capability statement describes.

    The annotation names two timeframes, but nothing rejects a third at
    construction time, so a policy can be built that no runtime will feed.
    """
    requirement = PolicyIndicatorRequirement(
        name="ATR",
        params={"period": 14},
        timeframe=cast("Any", "4h"),
        min_history=14,
    )

    # The annotation is what mypy sees, so the built value is read back untyped.
    assert cast("str", requirement.timeframe) == "4h"
    assert capability("money_management.prepared_requirement_timeframes").value == (
        "strategy",
        "1d",
    )


def test_a_policy_plans_once_and_cannot_revise_protection() -> None:
    declared = {
        name
        for name, member in inspect.getmembers(MoneyManagementBase)
        if getattr(member, "__isabstractmethod__", False)
    }

    assert declared == {"required_indicators", "resolved_config", "plan_entry"}
    assert {field.name for field in dataclasses.fields(MoneyManagementPlan)} == {
        "stop_loss",
        "take_profit",
        "requested_quantity",
        "requested_leverage",
        "initial_risk_amount",
        "diagnostics",
    }
    assert capability("money_management.protection_fixed_at_entry").value is True


class _ZeroCostModel(CostModel):
    """Charge nothing, so matching is the only thing under test."""

    def fee(self, symbol: str, notional: Decimal) -> Decimal:
        del symbol, notional
        return Decimal("0")

    def slippage(self, order: Order, context: dict[str, object]) -> Decimal:
        del order, context
        return Decimal("0")

    def funding_rate(self, at: datetime) -> Decimal:
        del at
        return Decimal("0")

    def liq_params(self) -> dict[str, object]:
        return {"maintenance_margin_rate": Decimal("0.004")}


def _candle(open_time: datetime) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe="1h",
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open=100.0,
        high=110.0,
        low=90.0,
        close=105.0,
        volume=10.0,
        quote_volume=None,
        trade_count=None,
    )


def test_matching_a_trailing_stop_is_refused() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    order = normalize_order(
        OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.TRAILING_STOP_MARKET,
            quantity=1.0,
            price=None,
            stop_price=95.0,
            market_type=MarketType.FUTURES,
            position_side=PositionSide.LONG,
            reduce_only=True,
            close_position=False,
            time_in_force="GTC",
        )
    )
    candles = [_candle(start), _candle(start + timedelta(hours=1))]

    with pytest.raises(NotImplementedError, match="trailing-stop matching is reserved"):
        match(order, candles[0], candles, _ZeroCostModel())
    assert capability("exit.trailing_stop").value is False


def test_the_account_wide_limits_are_exactly_three() -> None:
    fields = tuple(field.name for field in dataclasses.fields(RiskLimits))

    assert fields == capability("risk.account_limits").value
    assert capability("risk.between_trade_rules").value == ()


def test_risk_per_trade_above_one_percent_is_refused() -> None:
    assert RiskLimits(risk_per_trade=0.01, maintenance_margin_rate=0.004).risk_per_trade == 0.01
    with pytest.raises(ValueError, match=r"risk_per_trade must be a finite float in \(0, 0.01\]"):
        RiskLimits(risk_per_trade=0.02, maintenance_margin_rate=0.004)
    assert capability("risk.max_risk_per_trade").value == 0.01


def test_the_three_exposure_limits_share_one_body() -> None:
    """Show that three inviting names are one rule that never aggregates."""
    limits = (
        exposure_limit.single_market,
        exposure_limit.correlation_group,
        exposure_limit.single_direction,
    )
    cases: tuple[list[float], ...] = ([0.01], [0.011], [0.005, 0.005], [0.006, 0.006], [])

    for risks in cases:
        answers = {limit(list(risks), 0.01) for limit in limits}
        assert len(answers) == 1

    bodies = {inspect.getsource(limit).strip().splitlines()[-1].strip() for limit in limits}
    assert bodies == {"return _within_limit(risks, limit)"}


def test_no_independent_risk_governor_stands_between_layers() -> None:
    """Pin the absence the authoring contract calls a target state.

    The contract describes a common risk governor that approves a trade on
    account-wide grounds. Nothing implements it, and this fails the day one
    arrives, which is when the capability statement has to change.
    """
    assert importlib.util.find_spec("core_lib.risk_governor") is None
    assert capability("risk.independent_governor").value is False


def test_every_registered_series_names_the_source_of_its_definition() -> None:
    indicators: list[IndicatorSpec] = build_default_registry().list()

    assert indicators
    assert all(spec.pinned_impl.strip() for spec in indicators)
    patterns = TALIB_PATTERN_REGISTRY.list()
    assert patterns
    assert all("talib" in spec.version for spec in patterns)
    assert capability("registry.name_does_not_fix_definition").value is True
