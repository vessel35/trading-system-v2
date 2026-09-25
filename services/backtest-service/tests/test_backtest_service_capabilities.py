"""Pin the platform capabilities that only the backtest runtime can show.

Every test here is named by an entry in ``core_lib.capabilities``. When one of
these fails, the platform gained or lost a capability and the recorded statement
has to be rewritten before the change lands.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, ClassVar, cast

import pytest
from backtest_service.config import RunConfig
from backtest_service.engine import Engine
from core_lib.capabilities import capability
from core_lib.money_management import (
    AccountRiskSnapshot,
    MarketSnapshot,
    MoneyManagementBase,
    MoneyManagementError,
    MoneyManagementPlan,
    PolicyIndicatorRequirement,
    RiskLimits,
)
from core_lib.types import Candle, DecisionIntent, MarketType, PositionSide
from pydantic import ValidationError


def _raw_config(**overrides: object) -> dict[str, object]:
    raw: dict[str, object] = {
        "run_name": "capability-fixture",
        "strategy_id": "fake-breakout",
        "params": {},
        "symbol": "BTCUSDT",
        "exchange": "binance",
        "timeframe": "1h",
        "market_type": "futures",
        "data_source": "crypto_data.ohlcv_futures",
        "start": datetime(2025, 1, 1, tzinfo=UTC),
        "end": datetime(2026, 1, 1, tzinfo=UTC),
        "initial_capital": Decimal("10000"),
        "profile_ref": "capability-profile",
    }
    raw.update(overrides)
    return raw


def test_run_config_names_one_traded_symbol() -> None:
    fields = {name for name in RunConfig.model_fields if "symbol" in name}

    assert fields == {"symbol", "reference_symbol"}
    config = RunConfig.model_validate(_raw_config())
    assert config.symbol == "BTCUSDT"
    # The second name feeds paired series such as BETA and CORREL. It is never traded,
    # so it does not make a run cover two instruments.
    assert config.reference_symbol is None
    assert capability("run.traded_symbols").value == 1


def test_run_config_names_one_decision_timeframe() -> None:
    fields = {name for name in RunConfig.model_fields if "timeframe" in name}

    assert fields == {"timeframe"}
    assert RunConfig.model_validate(_raw_config()).timeframe == "1h"
    assert capability("run.decision_timeframes").value == 1


def test_run_config_accepts_next_bar_fills_only() -> None:
    assert RunConfig.model_validate(_raw_config()).fill_timing == "next_bar"
    with pytest.raises(ValidationError, match="supports next_bar fill_timing only"):
        RunConfig.model_validate(_raw_config(fill_timing="immediate"))
    assert capability("run.fill_timing").value == ("next_bar",)


def test_run_config_accepts_the_timeframe_candle_trigger_only() -> None:
    assert RunConfig.model_validate(_raw_config()).trigger_feed == "tf_candle"
    with pytest.raises(NotImplementedError, match="m1_subcandle is reserved"):
        RunConfig.model_validate(_raw_config(trigger_feed="m1_subcandle"))
    assert capability("run.decision_trigger").value == ("tf_candle",)


def test_run_config_cannot_select_a_candle_kind() -> None:
    """Show there is no place to ask for Heikin-Ashi or any other derived candle."""
    assert [name for name in RunConfig.model_fields if "candle" in name] == []
    with pytest.raises(ValidationError):
        RunConfig.model_validate(_raw_config(candle_kind="heikin_ashi"))
    assert capability("candles.kinds").value == ("exchange_confirmed_ohlcv", "resampled")


class _Book:
    """Answer with a position on whichever side is asked for."""

    def get(self, symbol: str, side: PositionSide) -> object:
        del side
        return object() if symbol == "BTCUSDT" else None


class _Held:
    """The smallest thing ``Engine._current_position`` reads."""

    _book = _Book()

    def _config(self) -> Any:
        return cast("Any", RunConfig.model_validate(_raw_config()))


def test_engine_refuses_two_directional_positions() -> None:
    with pytest.raises(ValueError, match="one directional position at a time"):
        Engine._current_position(cast("Any", _Held()))
    assert capability("run.concurrent_directional_positions").value == 1


class _Position:
    """The two values ``Engine._exit_request`` reads off a position."""

    symbol = "BTCUSDT"
    quantity = Decimal("2.5")
    side = PositionSide.LONG
    market_type = MarketType.FUTURES


def test_an_exit_request_closes_the_whole_position() -> None:
    request = Engine._exit_request(cast("Any", None), cast("Any", _Position()))

    assert request.quantity == float(_Position.quantity)
    assert request.reduce_only is True
    assert capability("exit.partial").value is False


class _NoInputPolicy(MoneyManagementBase):
    """A policy whose protection needs no market input, such as a fixed percentage."""

    id: ClassVar[str] = "fixed-percent-fixture"
    version: ClassVar[str] = "1.0.0"

    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        return ()

    def resolved_config(self) -> dict[str, object]:
        return {"mode": self.id}

    def plan_entry(
        self,
        decision: DecisionIntent,
        market: MarketSnapshot,
        account: AccountRiskSnapshot,
        global_limits: RiskLimits,
    ) -> MoneyManagementPlan:
        raise AssertionError("the engine refuses this policy before it can plan")


class _TwoInputPolicy(_NoInputPolicy):
    id: ClassVar[str] = "two-input-fixture"

    def required_indicators(self) -> tuple[PolicyIndicatorRequirement, ...]:
        return (
            PolicyIndicatorRequirement(
                name="ATR", params={"period": 14}, timeframe="strategy", min_history=14
            ),
            PolicyIndicatorRequirement(
                name="ATR", params={"period": 20}, timeframe="strategy", min_history=20
            ),
        )


def _candle() -> Candle:
    open_time = datetime(2026, 1, 1, tzinfo=UTC)
    return Candle(
        symbol="BTCUSDT",
        exchange="binance",
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


@pytest.mark.parametrize("policy", [_NoInputPolicy(), _TwoInputPolicy()])
def test_a_policy_must_declare_exactly_one_volatility_input(policy: MoneyManagementBase) -> None:
    """Show why a protection rule needing no market input cannot ship as a policy alone."""
    with pytest.raises(MoneyManagementError, match="must declare exactly one volatility input"):
        Engine._money_management_volatility(cast("Any", None), _candle(), policy)
    assert capability("money_management.volatility_inputs_per_policy").value == 1
