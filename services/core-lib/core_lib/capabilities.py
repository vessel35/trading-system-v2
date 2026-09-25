"""Record what this platform can express, so a strategy author never has to guess.

A strategy document is judged against two different kinds of fact, and confusing
them is what this module exists to prevent.

**Inventory** is what happens to be deployed right now: which indicator/parameter
combinations and candlestick patterns are registered, and which money-management
modes are deployed. Inventory is queried, from ``core_lib.indicators.registry``,
``core_lib.patterns``, and ``trading_plugins.discovery``.

**No ``value`` here may be inventory**, and a test enforces it. Values are what
the drift tests assert equality on, so a value listing today's policy modes would
have to be edited, inside ``core_lib``, before a third policy could ship - which
is exactly the rule that adding a strategy or a policy is a file plus a
registration row (contract section 6.1). A ``statement`` may name a deployed
thing as an example, because prose is read rather than asserted on; naming an
example goes stale visibly, while a pinned value goes stale by blocking someone.

**Capability** is what the platform can express at all: how many symbols one run
trades, when a fill happens, whether a position can be exited in part, whether a
protection price can move after entry. These change only when platform code
changes, so they are recorded here and pinned by tests.

Nothing imports this module at runtime. It is read by the strategy-authoring
procedure and by the tests that keep it honest. Because ``core_lib`` cannot see
``backtest_service`` or ``trading_plugins``, each entry names the test that
checks it, and those tests live in the service where the truth is visible.

What the tests prove, and what they do not: a ``STRUCTURE`` check reads a type,
its fields, or its annotations; a ``BEHAVIOR`` check calls the real code and
observes the value or the refusal. Neither proves that a *second* path will not
appear later. A partial-exit path added beside the one this module describes
would leave every test passing. Catching that is a review responsibility, not a
test's.

Read the path each statement is about. Several capabilities differ between a
backtest and paper execution - risk limits especially - and a statement that did
not say which one it meant would be false half the time.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

__all__ = [
    "PLATFORM_CAPABILITIES",
    "Capability",
    "CapabilityProof",
    "capability",
]


class CapabilityProof(StrEnum):
    """How the named test establishes one capability."""

    STRUCTURE = "structure"
    """It reads a type, its fields, or its annotations."""

    BEHAVIOR = "behavior"
    """It calls the real code and observes the value or the refusal."""


@dataclass(frozen=True, slots=True)
class Capability:
    """One thing the platform can or cannot express."""

    id: str
    statement: str
    value: object
    proof: CapabilityProof
    """The strongest kind of check among ``verified_by``."""

    verified_by: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("capability id must not be empty")
        if not self.statement.strip():
            raise ValueError(f"capability {self.id!r} must carry a statement")
        if not self.verified_by:
            raise ValueError(f"capability {self.id!r} must name at least one test")
        for reference in self.verified_by:
            path, separator, function = reference.partition("::")
            if not path.endswith(".py") or not separator or not function:
                raise ValueError(
                    f"capability {self.id!r} names {reference!r}, "
                    "which is not a 'path/to/test.py::function' reference"
                )


def _entries(*items: Capability) -> Mapping[str, Capability]:
    listed: dict[str, Capability] = {}
    for item in items:
        if item.id in listed:
            raise ValueError(f"duplicate capability id: {item.id}")
        listed[item.id] = item
    return MappingProxyType(listed)


_CORE_TESTS: Final = "services/core-lib/tests/test_core_lib_capabilities.py"
_BACKTEST_TESTS: Final = "services/backtest-service/tests/test_backtest_service_capabilities.py"
_PLUGIN_TESTS: Final = "services/trading-plugins/tests/test_trading_plugins_capabilities.py"
_SIGNAL_TESTS: Final = "services/signal-service/tests/test_signal_generation.py"
_ENGINE_TESTS: Final = "services/backtest-service/tests/test_engine_and_harness.py"
_MANAGER_TESTS: Final = "services/core-lib/tests/test_strategy_manager.py"
_EXECUTION_TESTS: Final = "services/core-lib/tests/test_execution.py"
_WALLET_TESTS: Final = "services/wallet-service/tests/test_wallet_service.py"


PLATFORM_CAPABILITIES: Final[Mapping[str, Capability]] = _entries(
    # ----- what one run covers -------------------------------------------------
    Capability(
        id="run.traded_symbols",
        statement=(
            "One run trades exactly one symbol. A second instrument reaches the strategy "
            "only through a registered paired series, which is named by reference_symbol "
            "and computed from both instruments; its raw candles never arrive and it is "
            "never traded. So a rule may compare two instruments if a registered series "
            "does the comparing, but a rule that positions in both cannot be expressed."
        ),
        value=1,
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(
            f"{_BACKTEST_TESTS}::test_run_config_names_one_traded_symbol",
            f"{_ENGINE_TESTS}"
            "::test_paired_series_waits_for_a_close_without_future_reference_values_and_records_source",
        ),
    ),
    Capability(
        id="run.decision_timeframes",
        statement=(
            "One run makes decisions on exactly one timeframe. Series may name other "
            "timeframes (see series.multi_timeframe), but the bar that calls the strategy "
            "is always the run's own timeframe."
        ),
        value=1,
        proof=CapabilityProof.STRUCTURE,
        verified_by=(f"{_BACKTEST_TESTS}::test_run_config_names_one_decision_timeframe",),
    ),
    Capability(
        id="run.fill_timing",
        statement=(
            "A decision made on a closed bar fills on the next bar. The run configuration "
            "refuses any other timing, because filling at the deciding bar's own close is "
            "the same-bar execution the authoring contract forbids."
        ),
        value=("next_bar",),
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(f"{_BACKTEST_TESTS}::test_run_config_accepts_next_bar_fills_only",),
    ),
    Capability(
        id="run.decision_trigger",
        statement=(
            "The strategy is called once per confirmed bar of the run's timeframe. The "
            "one-minute sub-candle trigger feed is a reserved name and is refused."
        ),
        value=("tf_candle",),
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(
            f"{_BACKTEST_TESTS}::test_run_config_accepts_the_timeframe_candle_trigger_only",
        ),
    ),
    Capability(
        id="run.concurrent_directional_positions",
        statement=(
            "A run holds at most one directional position. A long and a short at once is "
            "a runtime error, and a second entry on the side already held is skipped and "
            "recorded as pyramiding_disabled."
        ),
        value=1,
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(f"{_BACKTEST_TESTS}::test_engine_refuses_two_directional_positions",),
    ),
    Capability(
        id="run.strategy_inputs",
        statement=(
            "A strategy is called with two things: a mapping holding exactly these six "
            "keys, and the position it currently holds, which is None when flat. The "
            "position describes the open trade - its quantity, entry price, leverage, and "
            "liquidation price - and nothing else arrives. There is no equity, no cash, and "
            "no record of any closed trade, so a strategy cannot count its own wins, "
            "losses, or trades per day."
        ),
        value=("candles", "candle", "symbol", "timeframe", "market_type", "indicators"),
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(
            f"{_ENGINE_TESTS}::test_engine_passes_exactly_the_six_declared_inputs",
            f"{_CORE_TESTS}::test_a_strategy_is_called_with_market_data_and_its_open_position",
        ),
    ),
    # ----- series and candles --------------------------------------------------
    Capability(
        id="series.sources",
        statement=(
            "A series is a registered indicator or a registered candlestick pattern, and "
            "nothing else. The two name spaces are disjoint, so a declaration is routed to "
            "one registry or the other by name alone."
        ),
        value=("indicator registry", "pattern registry"),
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(f"{_CORE_TESTS}::test_series_come_from_two_disjoint_registries",),
    ),
    Capability(
        id="series.multi_timeframe",
        statement=(
            "A strategy may declare a series on a timeframe other than the one it runs on, "
            "and the value it reads is taken from the last higher bar that had closed at "
            "decision time. The run's own timeframe is named 'strategy'; naming it "
            "concretely is refused so two declarations cannot collide on one execution key."
        ),
        value=True,
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(
            f"{_CORE_TESTS}::test_a_series_may_name_another_timeframe_but_not_the_running_one",
            f"{_ENGINE_TESTS}"
            "::test_multi_timeframe_series_aligns_without_future_values_and_records_its_source",
        ),
    ),
    Capability(
        id="series.raw_candle_streams",
        statement=(
            "Only one raw candle stream reaches the strategy: the run's own timeframe. A "
            "rule that must walk the highs and lows of a higher timeframe bar by bar cannot "
            "be expressed unless that reading is itself a registered series."
        ),
        value=1,
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(
            f"{_ENGINE_TESTS}"
            "::test_multi_timeframe_series_aligns_without_future_values_and_records_its_source",
        ),
    ),
    Capability(
        id="series.registration_unit",
        statement=(
            "An indicator is registered as a name together with one parameter combination, "
            "so a combination that is not registered cannot be declared. Patterns are "
            "registered by name and take no parameters."
        ),
        value="name and parameter combination",
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(f"{_CORE_TESTS}::test_an_unregistered_parameter_combination_is_refused",),
    ),
    Capability(
        id="series.value_shapes",
        statement=(
            "One bar of a series is either a single number or a mapping of named outputs. "
            "Candlestick patterns are always the second shape."
        ),
        value=("float", "dict[str, float]"),
        proof=CapabilityProof.STRUCTURE,
        verified_by=(f"{_CORE_TESTS}::test_a_series_value_is_a_number_or_named_numbers",),
    ),
    Capability(
        id="candles.kinds",
        statement=(
            "Candles are exchange-confirmed OHLCV, optionally regrouped into a longer "
            "timeframe. There is no derived candle type such as Heikin-Ashi or Renko, and "
            "no place in the run configuration to select one."
        ),
        value=("exchange_confirmed_ohlcv", "resampled"),
        proof=CapabilityProof.STRUCTURE,
        verified_by=(
            f"{_CORE_TESTS}::test_a_candle_does_not_carry_a_kind",
            f"{_BACKTEST_TESTS}::test_run_config_cannot_select_a_candle_kind",
        ),
    ),
    # ----- what a decision is --------------------------------------------------
    Capability(
        id="decision.intent_fields",
        statement=(
            "A decision carries exactly these seven fields. Stop price, target price, "
            "quantity, and leverage are not among them: they belong to money management."
        ),
        value=(
            "action",
            "symbol",
            "timestamp",
            "reference_price",
            "confidence",
            "reason",
            "metadata",
        ),
        proof=CapabilityProof.STRUCTURE,
        verified_by=(f"{_CORE_TESTS}::test_a_decision_carries_no_sizing_or_protection",),
    ),
    Capability(
        id="decision.money_management_needs_decision_intent",
        statement=(
            "A policy attaches only to a strategy that declares the DecisionIntent "
            "contract. A strategy still declaring the legacy TradingSignal contract is "
            "refused a policy outright."
        ),
        value=True,
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(f"{_MANAGER_TESTS}::test_policy_attachment_rejects_mutated_legacy_metadata",),
    ),
    # ----- money management ----------------------------------------------------
    Capability(
        id="money_management.volatility_inputs_per_policy",
        statement=(
            "A policy must declare exactly one volatility input. Declaring none or two is "
            "refused at entry, so a policy whose protection needs no market input - a fixed "
            "percentage stop, for instance - cannot run without changing the runtime."
        ),
        value=1,
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(
            f"{_BACKTEST_TESTS}::test_a_policy_must_declare_exactly_one_volatility_input",
        ),
    ),
    Capability(
        id="money_management.prepared_requirement_timeframes",
        statement=(
            "Values are prepared for a policy requirement on the run's own timeframe and, "
            "through the Turtle daily-N path, on 1d. The annotation names those two, but "
            "the constructor does not enforce them, so a requirement naming any other "
            "timeframe is built happily and then finds no value at run time."
        ),
        value=("strategy", "1d"),
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(f"{_CORE_TESTS}::test_a_policy_requirement_timeframe_is_not_validated",),
    ),
    Capability(
        id="money_management.protection_fixed_at_entry",
        statement=(
            "A policy plans once, at entry. Its protection prices are fixed from that "
            "moment: there is no method by which a policy revises a stop, moves it to break "
            "even, or trails it."
        ),
        value=True,
        proof=CapabilityProof.STRUCTURE,
        verified_by=(f"{_CORE_TESTS}::test_a_policy_plans_once_and_cannot_revise_protection",),
    ),
    Capability(
        id="money_management.live_signal_requirements",
        statement=(
            "Running under signal generation asks more of a policy than backtesting does: "
            "it must declare that protection prices and leverage ignore account state, and "
            "its single input must be on the strategy timeframe. A policy that backtests "
            "may still be refused there."
        ),
        value=("protection_and_leverage_ignore_account_state", "one strategy-timeframe input"),
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(
            f"{_SIGNAL_TESTS}::test_signal_service_rejects_policy_without_signal_account_state_capability",
            f"{_SIGNAL_TESTS}::test_signal_generation_refuses_an_account_dependent_policy",
        ),
    ),
    # ----- execution -----------------------------------------------------------
    Capability(
        id="execution.protection_checked_from_bar_after_fill",
        statement=(
            "A stop, a target, and a forced liquidation are not checked on the bar that "
            "filled the entry; the trigger walk starts at the next bar. A level touched "
            "inside the fill bar does not close the position on that bar, and no run "
            "configuration or API turns this off."
        ),
        value=True,
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(
            f"{_EXECUTION_TESTS}::test_trigger_gap_uses_unfavorable_open_and_skips_the_fill_candle",
            f"{_EXECUTION_TESTS}::test_take_profit_and_liquidation_are_not_checked_on_the_fill_candle",
        ),
    ),
    Capability(
        id="execution.simultaneous_stop_and_target",
        statement=(
            "When one bar touches both the stop and the target, the position closes at the "
            "stop. The conservative reading is fixed; a bar cannot be read as reaching the "
            "target first."
        ),
        value="stop_loss",
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(
            f"{_EXECUTION_TESTS}::test_simultaneous_stop_and_take_profit_resolves_to_stop_loss",
        ),
    ),
    # ----- exits ---------------------------------------------------------------
    Capability(
        id="exit.partial",
        statement=(
            "An exit closes the whole position. Taking half off at a target and letting the "
            "rest run cannot be expressed."
        ),
        value=False,
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(f"{_BACKTEST_TESTS}::test_an_exit_request_closes_the_whole_position",),
    ),
    Capability(
        id="exit.trailing_stop",
        statement=(
            "There is no trailing stop. The order type exists in the enumeration, but "
            "matching one is refused as reserved."
        ),
        value=False,
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(f"{_CORE_TESTS}::test_matching_a_trailing_stop_is_refused",),
    ),
    # ----- risk ----------------------------------------------------------------
    Capability(
        id="risk.account_limits",
        statement=(
            "In a backtest these three are the whole of what a policy is told about the "
            "account's limits, and it receives them as an argument rather than being "
            "checked against them afterwards. Paper execution adds its own limits on top "
            "(see risk.paper_execution_guard); a backtest does not apply those."
        ),
        value=("risk_per_trade", "maintenance_margin_rate", "max_leverage"),
        proof=CapabilityProof.STRUCTURE,
        verified_by=(f"{_CORE_TESTS}::test_the_account_wide_limits_are_exactly_three",),
    ),
    Capability(
        id="risk.max_risk_per_trade",
        statement=(
            "Risk per trade is capped at one percent of equity and a larger value is "
            "refused, so a document asking for two percent cannot be honoured."
        ),
        value=0.01,
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(f"{_CORE_TESTS}::test_risk_per_trade_above_one_percent_is_refused",),
    ),
    Capability(
        id="risk.between_trade_rules",
        statement=(
            "A backtest applies no rule that reads earlier trades: no daily or weekly loss "
            "limit, no consecutive-loss halt, no cap on trades per day. The three functions "
            "in core_lib.sizing.exposure_limit read like such rules, and paper execution "
            "does aggregate through them, but the backtest engine calls each with one "
            "element under a fixed one-percent limit, so in a backtest nothing is summed. "
            "A document asking for any of these is asking for something a backtest result "
            "will not contain."
        ),
        value=(),
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(
            f"{_CORE_TESTS}::test_the_account_wide_limits_are_exactly_three",
            f"{_CORE_TESTS}::test_the_three_exposure_limits_share_one_body",
            f"{_ENGINE_TESTS}::test_engine_passes_exactly_the_six_declared_inputs",
        ),
    ),
    Capability(
        id="risk.independent_governor",
        statement=(
            "A backtest has no layer between the policy and execution that could refuse a "
            "trade on account-wide grounds: the policy keeps the limits itself and nothing "
            "rechecks it. This is the layer the authoring contract calls a target state, "
            "and it does not exist on the backtest path."
        ),
        value=False,
        proof=CapabilityProof.STRUCTURE,
        verified_by=(f"{_CORE_TESTS}::test_no_independent_risk_governor_stands_between_layers",),
    ),
    Capability(
        id="risk.paper_execution_guard",
        statement=(
            "Paper execution does have such a layer, and it is not the backtest's. Before "
            "any fill the wallet service refuses a signal on a kill switch, an allowed "
            "symbol list, order quantity and notional caps, a one-R limit, and per-market, "
            "per-correlation-group, and per-direction limits. Those last three see the "
            "candidate trade only: the wallet holds one position at a time and refuses a "
            "second entry, so it never has an earlier trade to add. A strategy whose "
            "backtest passes can still be refused here, and a backtest result never "
            "reflects these refusals."
        ),
        value=True,
        proof=CapabilityProof.BEHAVIOR,
        verified_by=(
            f"{_WALLET_TESTS}::test_risk_guards_reject_before_fill_or_write",
            f"{_WALLET_TESTS}::test_kill_switch_is_one_way_and_blocks_before_sizing",
            f"{_WALLET_TESTS}::test_one_r_tolerance_remains_fail_closed_for_material_overshoot",
            f"{_WALLET_TESTS}::test_a_second_entry_is_refused_while_a_paper_position_is_open",
        ),
    ),
    # ----- deployment ----------------------------------------------------------
    Capability(
        id="deployment.packages",
        statement=(
            "A strategy is found in trading_plugins.strategies and a policy in "
            "trading_plugins.money_management. Those two paths are fixed in code; a "
            "registration row is compared against what was found and is never imported."
        ),
        value=("trading_plugins.strategies", "trading_plugins.money_management"),
        proof=CapabilityProof.STRUCTURE,
        verified_by=(f"{_PLUGIN_TESTS}::test_deployment_scans_exactly_two_packages",),
    ),
    Capability(
        id="registry.name_does_not_fix_definition",
        statement=(
            "A registered name says which implementation was adopted, not that it computes "
            "what a strategy document means by that word. An indicator pins the standard "
            "section it was ported from, and every pattern is a port of TA-Lib 0.7.1, whose "
            "definitions differ from the informal ones documents usually give."
        ),
        value=True,
        proof=CapabilityProof.STRUCTURE,
        verified_by=(
            f"{_CORE_TESTS}::test_every_registered_series_names_the_source_of_its_definition",
        ),
    ),
)
"""Every capability, keyed by id."""


def capability(identifier: str) -> Capability:
    """Return one capability, refusing an unknown id by name."""
    try:
        return PLATFORM_CAPABILITIES[identifier]
    except KeyError as error:
        raise KeyError(f"unknown capability: {identifier}") from error
