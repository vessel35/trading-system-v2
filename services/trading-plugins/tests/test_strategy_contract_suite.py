"""Common contract checks applied to every discovered strategy: the strategy-unit layer.

Design: ``docs/fullspec/strategy_contract_suite_design.md``, implemented by verification
layer as decided on 2026-09-25. This module is the first layer, the strategy unit. It
parametrizes every class ``trading_plugins.strategies`` discovers, on every timeframe it
declares, through a test-only scenario table (design section 3) and checks, on
production-shaped inputs:

- determinism on one instance and across fresh instances, with input immutability (4);
- money-management policy independence on the input shapes each policy produces (5);
- an order-independence check as the defensive part of time integrity, with its limit
  stated on the check (6);
- forbidden dependencies, statically over the module's imports and the strategy-package
  helpers it pulls in, and at run time through an audit hook and a frozen clock (7);
- declared-versus-actual access to series and parameters through a tracing mapping (8);
- entry and exit correspondence per direction (9);
- signatures and the additional common properties (10).

Fault-injection strategies at the end prove that each check catches the defect it exists
for (12). Two things this layer does not do, on purpose: the main time-integrity guarantee
(that no value used at a decision was finalized after it) belongs to the Engine composition
layer, and the refusal of policy combinations a strategy does not declare is checked here only
through ``AdapterManager.create_runtime``, not through a full engine run.
"""

from __future__ import annotations

import ast
import contextlib
import copy
import importlib
import inspect
import sys
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, ClassVar, cast
from unittest import mock

import pytest
from core_lib.indicators.registry import build_default_registry
from core_lib.money_management import MoneyManagementFactory
from core_lib.patterns import TALIB_PATTERN_REGISTRY
from core_lib.ports import StrategyRegistry
from core_lib.series import series_key_of
from core_lib.strategy import (
    AdapterClass,
    AdapterManager,
    FieldSpec,
    InProcessStrategyRegistry,
    MoneyManagementSupport,
    ParameterSchema,
    ResolvedConfig,
    StrategyBase,
    StrategyConfig,
    StrategyDecisionContract,
    StrategyMetadata,
    StrategyProfile,
    validate_strategy_result,
)
from core_lib.types import (
    Candle,
    DecisionAction,
    DecisionIntent,
    MarginType,
    MarketType,
    Position,
    PositionSide,
    TradingSignal,
)
from trading_plugins import discover_strategies, registered_money_management

_START = datetime(2026, 1, 1, tzinfo=UTC)
_SYMBOL = "BTCUSDT"
_TIMEFRAME_MINUTES = {"1h": 60, "4h": 240, "1d": 1440}
# Names the authoring contract (section 4.2) reserves for money management.
_MONEY_MANAGEMENT_OWNED_NAMES = frozenset(
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
# Import roots a strategy module (and any helper it pulls in) may use. Everything else -
# services, storage, network, the clock, randomness, subprocesses, files - is forbidden
# (design section 7). The list is an allow list so a new forbidden module cannot slip in.
_ALLOWED_IMPORT_ROOTS = frozenset(
    {
        "__future__",
        "abc",
        "collections",
        "core_lib",
        "dataclasses",
        "decimal",
        "enum",
        "functools",
        "itertools",
        "math",
        "operator",
        "statistics",
        "typing",
    }
)
_CLOCK_AND_RANDOM_CALLS = frozenset(
    {
        "now",
        "utcnow",
        "today",
        "time",
        "time_ns",
        "monotonic",
        "monotonic_ns",
        "perf_counter",
        "perf_counter_ns",
        "process_time",
        "process_time_ns",
        "clock_gettime",
        "clock_gettime_ns",
        "gmtime",
        "localtime",
        "random",
        "randint",
        "choice",
        "shuffle",
    }
)
_DYNAMIC_IMPORT_CALLS = frozenset({"__import__", "import_module"})
_FROZEN_TIME_FUNCTIONS = (
    "time",
    "time_ns",
    "monotonic",
    "monotonic_ns",
    "perf_counter",
    "perf_counter_ns",
    "process_time",
    "process_time_ns",
    "clock_gettime",
    "clock_gettime_ns",
    "gmtime",
    "localtime",
)
_FORBIDDEN_AUDIT_EVENTS = frozenset(
    {
        "open",
        "socket.connect",
        "socket.bind",
        "socket.sendto",
        "socket.sendmsg",
        "subprocess.Popen",
        "os.system",
        "os.exec",
        "os.fork",
        "os.posix_spawn",
        "sqlite3.connect",
        "import",
    }
)
# The value a policy-required series carries in a production-shaped input. Today the only
# such series is ATR on the strategy timeframe, a plain number.
_POLICY_SERIES_VALUE = 2.0


# --- scenario table ---------------------------------------------------------------------

Bar = tuple[float, float, float, float]
"""One candle as (open, high, low, close); the timeframe is applied when candles are built."""


@dataclass(frozen=True)
class Inputs:
    """One decision's bars and declared series values, written for the 1h keys.

    Series values are keyed without a timeframe suffix (``ema:period=9``). The production
    key is resolved per declaration when the input is built: a series declared on the
    strategy timeframe takes the run's timeframe, a series declared with its own
    ``timeframe`` keeps it (contract section 4.4). The same scenario is therefore replayed
    on every timeframe the strategy declares, and a strategy that hard-codes ``@1h`` in a
    key fails on the other timeframes it advertises.
    """

    bars: tuple[Bar, ...]
    series: Mapping[str, object] = field(default_factory=dict)

    def candles(self, timeframe: str) -> list[Candle]:
        return [_candle(index, bar, timeframe=timeframe) for index, bar in enumerate(self.bars)]

    def indicators(self, cls: AdapterClass, timeframe: str) -> dict[str, object]:
        declared = _declared_specs(cls, timeframe)
        return {
            declared.get(_bare(key), f"{_bare(key)}@{timeframe}"): value
            for key, value in self.series.items()
        }


def _bare(key: str) -> str:
    """The series key without its timeframe suffix."""
    name, separator, _ = key.rpartition("@")
    return name if separator else key


@dataclass(frozen=True)
class Direction:
    """The evidence one entry direction must produce: an entry, then an exit."""

    action: DecisionAction
    entry: Inputs
    exit: Inputs

    @property
    def side(self) -> PositionSide:
        return PositionSide.LONG if self.action is DecisionAction.ENTER_LONG else PositionSide.SHORT


@dataclass(frozen=True)
class Case:
    """The scenario table row for one discovered strategy (design section 3).

    The policy expectations are the strategy's intended contract, written here so that a
    widening of what the class declares is caught against this row and not only against
    what the runtime happens to accept.
    """

    strategy_id: str
    params: Mapping[str, object]
    timeframes: tuple[str, ...]
    market_type: str
    supported: tuple[str, ...]
    default: str | None
    signal_exit: bool
    default_settings: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    long: Direction | None = None
    short: Direction | None = None
    hold: Inputs | None = None
    """A representative bar the strategy must hold on; required when there is no direction."""
    contract: StrategyDecisionContract = StrategyDecisionContract.DECISION_INTENT

    @property
    def directions(self) -> tuple[Direction, ...]:
        return tuple(direction for direction in (self.long, self.short) if direction is not None)

    @property
    def steps(self) -> tuple[tuple[Inputs, PositionSide | None], ...]:
        """The scenario as one ordered sequence: enter and exit each direction."""
        steps: list[tuple[Inputs, PositionSide | None]] = []
        if self.hold is not None:
            steps.append((self.hold, None))
        for direction in self.directions:
            steps.append((direction.entry, None))
            steps.append((direction.exit, direction.side))
        return tuple(steps)


def _candle(index: int, bar: Bar, *, timeframe: str) -> Candle:
    open_price, high, low, close = bar
    span = timedelta(minutes=_TIMEFRAME_MINUTES[timeframe])
    opened = _START + index * span
    return Candle(
        symbol=_SYMBOL,
        exchange="binance",
        timeframe=timeframe,
        open_time=opened,
        close_time=opened + span,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        quote_volume=10_000.0,
        trade_count=100,
    )


def _bar(close: float, open_price: float = 100.0) -> Bar:
    return (open_price, max(open_price, close) + 1.0, min(open_price, close) - 1.0, close)


_LEAD_BAR = _bar(100.5)
"""A neutral warm-up bar: the engine hands ``min_history`` bars plus the deciding bar."""


def _one(close: float, series: Mapping[str, object]) -> Inputs:
    return Inputs(bars=(_LEAD_BAR, _bar(close)), series=series)


def _supertrend(direction: float, ema200: float) -> dict[str, object]:
    return {
        "supertrend:multiplier=3,period=10": {
            "supertrend": 100.0,
            "direction": direction,
            "upper": 105.0,
            "lower": 95.0,
        },
        "ema:period=200": ema200,
    }


def _macd(macd: float, signal: float, ema200: float) -> dict[str, object]:
    return {
        "macd:fast_period=12,signal_period=9,slow_period=26": {
            "macd": macd,
            "signal": signal,
            "histogram": macd - signal,
        },
        "ema:period=200": ema200,
    }


def _bands(rsi: float | None = None) -> dict[str, object]:
    series: dict[str, object] = {
        "bollinger_bands:multiplier=2,period=20": {
            "middle": 100.0,
            "upper": 104.0,
            "lower": 96.0,
            "percent_b": 0.5,
            "bandwidth": 0.08,
        }
    }
    if rsi is not None:
        series["rsi:period=14"] = rsi
    return series


def _emas(fast: float, slow: float) -> dict[str, object]:
    return {"ema:period=9": fast, "ema:period=21": slow}


def _channel_breakout(close: float) -> Inputs:
    """Twenty-one bars ranging 90..110, then a close beyond that channel."""
    channel: tuple[Bar, ...] = tuple((100.0, 110.0, 90.0, 100.0) for _ in range(21))
    last: Bar = (100.0, max(112.0, close), min(88.0, close), close)
    return Inputs(bars=(*channel, last))


def _streak(colour: str, count: int = 3) -> Inputs:
    """A neutral warm-up bar, then ``count`` bars of one colour ending at the deciding bar."""
    bar = _bar(100.0, open_price=101.0) if colour == "red" else _bar(101.0, open_price=100.0)
    return Inputs(bars=(_LEAD_BAR, *(bar for _ in range(count))))


_CASES: dict[str, Case] = {
    "vessel-reference": Case(
        strategy_id="vessel-reference",
        params={},
        timeframes=("1h",),
        market_type="futures",
        supported=("manual", "turtle"),
        default="manual",
        signal_exit=True,
        long=Direction(
            DecisionAction.ENTER_LONG,
            entry=_one(101.0, _emas(102.0, 100.0)),
            exit=_one(101.0, _emas(99.0, 100.0)),
        ),
        short=Direction(
            DecisionAction.ENTER_SHORT,
            entry=_one(101.0, _emas(99.0, 100.0)),
            exit=_one(101.0, _emas(102.0, 100.0)),
        ),
    ),
    "supertrend-ema200-flip": Case(
        strategy_id="supertrend-ema200-flip",
        params={},
        timeframes=("1h", "4h"),
        market_type="futures",
        supported=("signal-exit-atr", "manual", "turtle"),
        default="signal-exit-atr",
        signal_exit=True,
        long=Direction(
            DecisionAction.ENTER_LONG,
            entry=_one(101.0, _supertrend(1.0, 90.0)),
            exit=_one(101.0, _supertrend(-1.0, 90.0)),
        ),
        short=Direction(
            DecisionAction.ENTER_SHORT,
            entry=_one(101.0, _supertrend(-1.0, 110.0)),
            exit=_one(101.0, _supertrend(1.0, 110.0)),
        ),
    ),
    "macd-ema200-zero-line": Case(
        strategy_id="macd-ema200-zero-line",
        params={},
        timeframes=("1h", "4h"),
        market_type="futures",
        supported=("manual",),
        default="manual",
        signal_exit=False,
        default_settings={"manual": {"atr_stop_multiple": 2.5, "reward_risk": 1.5}},
        long=Direction(
            DecisionAction.ENTER_LONG,
            entry=_one(101.0, _macd(-1.0, -1.5, 90.0)),
            exit=_one(101.0, _macd(1.0, 1.5, 90.0)),
        ),
        short=Direction(
            DecisionAction.ENTER_SHORT,
            entry=_one(101.0, _macd(1.0, 1.5, 110.0)),
            exit=_one(101.0, _macd(-1.0, -1.5, 110.0)),
        ),
    ),
    "bollinger-rsi-reversion": Case(
        strategy_id="bollinger-rsi-reversion",
        params={},
        timeframes=("1h", "4h"),
        market_type="futures",
        supported=("signal-exit-atr", "manual", "turtle"),
        default="signal-exit-atr",
        signal_exit=True,
        long=Direction(
            DecisionAction.ENTER_LONG,
            entry=_one(95.0, _bands(25.0)),
            exit=_one(100.0, _bands(50.0)),
        ),
        short=Direction(
            DecisionAction.ENTER_SHORT,
            entry=_one(105.0, _bands(75.0)),
            exit=_one(100.0, _bands(50.0)),
        ),
    ),
    "donchian-breakout-atr": Case(
        strategy_id="donchian-breakout-atr",
        params={},
        timeframes=("1h",),
        market_type="futures",
        supported=("manual",),
        default="manual",
        signal_exit=False,
        default_settings={"manual": {"atr_stop_multiple": 1.5, "reward_risk": 2.0}},
        long=Direction(
            DecisionAction.ENTER_LONG,
            entry=_channel_breakout(111.0),
            exit=_channel_breakout(89.0),
        ),
        short=Direction(
            DecisionAction.ENTER_SHORT,
            entry=_channel_breakout(89.0),
            exit=_channel_breakout(111.0),
        ),
    ),
    "three-bar-reversion": Case(
        strategy_id="three-bar-reversion",
        params={},
        timeframes=("1h",),
        market_type="futures",
        supported=("manual",),
        default="manual",
        signal_exit=False,
        long=Direction(
            DecisionAction.ENTER_LONG,
            entry=_streak("red"),
            exit=_streak("green"),
        ),
        short=Direction(
            DecisionAction.ENTER_SHORT,
            entry=_streak("green"),
            exit=_streak("red"),
        ),
    ),
    "bollinger-band-bounce": Case(
        strategy_id="bollinger-band-bounce",
        params={},
        timeframes=("1h",),
        market_type="futures",
        supported=("manual",),
        default="manual",
        signal_exit=False,
        default_settings={"manual": {"atr_stop_multiple": 1.5, "reward_risk": 1.5}},
        long=Direction(
            DecisionAction.ENTER_LONG,
            entry=_one(95.0, _bands()),
            exit=_one(105.0, _bands()),
        ),
        short=Direction(
            DecisionAction.ENTER_SHORT,
            entry=_one(105.0, _bands()),
            exit=_one(95.0, _bands()),
        ),
    ),
}

_DISCOVERED, _DISCOVERY_FAULTS = discover_strategies()
_POLICIES = registered_money_management()


# --- production-shaped inputs -----------------------------------------------------------


class AccessTracer(Mapping[str, object]):
    """Record every key a strategy reads, through any Mapping path (design section 8)."""

    def __init__(self, values: Mapping[str, object]) -> None:
        self._values = dict(values)
        self.read: set[str] = set()
        self.enumerated = False

    def __getitem__(self, key: str) -> object:
        self.read.add(key)
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        self.enumerated = True
        self.read.update(self._values)
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __contains__(self, key: object) -> bool:
        if isinstance(key, str):
            self.read.add(key)
        return key in self._values

    def get(self, key: str, default: object = None) -> object:
        self.read.add(key)
        return self._values.get(key, default)

    def keys(self):  # type: ignore[no-untyped-def]
        self.enumerated = True
        self.read.update(self._values)
        return self._values.keys()

    def values(self):  # type: ignore[no-untyped-def]
        self.enumerated = True
        self.read.update(self._values)
        return self._values.values()

    def items(self):  # type: ignore[no-untyped-def]
        self.enumerated = True
        self.read.update(self._values)
        return self._values.items()

    def __eq__(self, other: object) -> bool:
        return dict(self._values) == (dict(other) if isinstance(other, Mapping) else other)

    def __hash__(self) -> int:  # pragma: no cover - Mapping requires it be explicit
        raise TypeError("AccessTracer is not hashable")

    def __copy__(self) -> AccessTracer:
        self.enumerated = True
        self.read.update(self._values)
        return AccessTracer(self._values)

    def __deepcopy__(self, memo: dict[int, object]) -> AccessTracer:
        self.enumerated = True
        self.read.update(self._values)
        return AccessTracer(copy.deepcopy(self._values, memo))


def _declared_specs(cls: AdapterClass, timeframe: str) -> dict[str, str]:
    """Map each declared series' bare key to the production key on this run timeframe.

    A declaration may carry its own ``timeframe`` (a higher-timeframe series); the engine
    keys such a series on that timeframe, not on the run's, so the map does the same.
    """
    specs: dict[str, str] = {}
    for item in cls.get_metadata().required_indicators:
        name = str(item["name"])
        params = _params(item)
        declared_timeframe = item.get("timeframe")
        own = declared_timeframe if isinstance(declared_timeframe, str) else timeframe
        key = series_key_of(name, params, own)
        specs[_bare(key)] = key
    return specs


def _declared_keys(cls: AdapterClass, timeframe: str) -> set[str]:
    return set(_declared_specs(cls, timeframe).values())


def _params(item: Mapping[str, object]) -> Mapping[str, object]:
    params = item.get("params", {})
    if not isinstance(params, Mapping):
        raise TypeError("declared series params must be a mapping")
    return params


def _policy_keys(cls: AdapterClass, mode: str, timeframe: str) -> dict[str, object]:
    """The series a policy makes the engine add to the strategy's input, by mode.

    The policy is built the way a run builds it: from the strategy's declared
    ``default_settings`` for the mode, so a declared policy input (an ATR period, say)
    yields the key production would actually inject.
    """
    settings = cls.get_metadata().money_management.resolve_settings({"mode": mode})
    policy = MoneyManagementFactory.create(settings, _POLICIES)
    return {
        series_key_of(requirement.name, dict(requirement.params), timeframe): _POLICY_SERIES_VALUE
        for requirement in policy.required_indicators()
        if requirement.timeframe == "strategy"
    }


def _market(
    cls: AdapterClass,
    case: Case,
    inputs: Inputs,
    timeframe: str,
    *,
    extra_series: Mapping[str, object] | None = None,
    tracer: AccessTracer | None = None,
) -> dict[str, object]:
    """Build exactly the six keys the engine passes (capability ``run.strategy_inputs``)."""
    candles = inputs.candles(timeframe)
    series: dict[str, object] = {**inputs.indicators(cls, timeframe), **(extra_series or {})}
    return {
        "candles": candles,
        "candle": candles[-1],
        "symbol": _SYMBOL,
        "timeframe": timeframe,
        "market_type": case.market_type,
        "indicators": tracer if tracer is not None else series,
    }


def _position(side: PositionSide) -> Position:
    return Position(
        wallet_id=None,
        symbol=_SYMBOL,
        quantity=Decimal("1"),
        average_price=Decimal("100"),
        total_cost=Decimal("100"),
        current_price=Decimal("100"),
        unrealized_pnl=Decimal("0"),
        side=side,
        market_type=MarketType.FUTURES,
        leverage=1,
        margin_type=MarginType.ISOLATED,
        margin=Decimal("100"),
        entry_price=Decimal("100"),
        mark_price=Decimal("100"),
        liquidation_price=Decimal("0"),
        funding_fee_total=Decimal("0"),
    )


def _held(side: PositionSide | None) -> Position | None:
    return None if side is None else _position(side)


def _instance(cls: AdapterClass, case: Case) -> Any:
    resolved = StrategyConfig.resolve(
        cls.get_parameter_schema(),
        {"strategy_id": case.strategy_id, "params": dict(case.params)},
    )
    return cast("Callable[[ResolvedConfig], Any]", cls)(resolved)


def _snapshot(value: object) -> object:
    """A comparable copy of an input, taken before a call and compared after it."""
    if isinstance(value, AccessTracer):
        return copy.deepcopy(dict(value._values))
    if isinstance(value, Mapping):
        return {key: _snapshot(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_snapshot(item) for item in value]
    if isinstance(value, ResolvedConfig):
        return (value.strategy_id, _snapshot(value.params), value.schema_version)
    return copy.deepcopy(value)


def _instance_state(strategy: Any) -> dict[str, object]:
    """A comparable copy of everything the instance holds, slots and dict alike."""
    names: list[str] = []
    for klass in type(strategy).__mro__:
        names.extend(name for name in vars(klass).get("__slots__", ()) if name != "__dict__")
    names.extend(vars(strategy) if hasattr(strategy, "__dict__") else ())
    state: dict[str, object] = {}
    for name in names:
        if hasattr(strategy, name):
            state[name] = _snapshot(getattr(strategy, name))
    return state


def _decide(strategy: Any, market: dict[str, object], position: Position | None) -> Any:
    """Call the strategy the way the engine does and enforce its declared return contract.

    A ``DecisionIntent`` strategy must answer every bar with a ``DecisionIntent`` (a HOLD
    carries its reason instead of ``None``). A strategy that declares the legacy
    ``TradingSignal`` contract, which a scenario row must mark explicitly, may answer with
    a ``TradingSignal`` or ``None``; the legacy shape is never accepted from a target
    strategy. Neither the input mapping nor the position may change.
    """
    before = _snapshot(market)
    position_before = copy.deepcopy(position)
    state_before = _instance_state(strategy)
    result = strategy.analyze(market, position)
    assert _snapshot(market) == before, "analyze() changed its input"
    assert position == position_before, "analyze() changed its position"
    assert _instance_state(strategy) == state_before, (
        "analyze() changed the strategy's own state; a strategy is stateless (contract 4.1)"
    )
    metadata = strategy.get_metadata()
    if result is not None:
        try:
            validate_strategy_result(metadata, result)
        except TypeError as error:
            raise AssertionError(str(error)) from error
    if metadata.decision_contract is StrategyDecisionContract.DECISION_INTENT:
        assert isinstance(result, DecisionIntent), (
            "a DecisionIntent strategy must return a DecisionIntent for every bar; a HOLD "
            f"carries its reason instead of None (got {type(result).__name__})"
        )
        assert result.reason, "every decision must carry a reason"
    candle = market["candle"]
    assert isinstance(candle, Candle)
    if result is not None:
        assert result.timestamp <= candle.close_time, "a decision may not carry a future timestamp"
    return result


def _replay(cls: AdapterClass, case: Case, timeframe: str) -> list[DecisionIntent]:
    strategy = _instance(cls, case)
    return [
        _decide(strategy, _market(cls, case, inputs, timeframe), _held(side))
        for inputs, side in case.steps
    ]


# --- checks (each raises AssertionError with the defect named) --------------------------


def check_signatures(cls: AdapterClass, case: Case) -> None:
    """Design section 10: the Protocol check does not fix signatures, so compare them here.

    The row states which decision contract the strategy is held to. A legacy
    ``TradingSignal`` row is an explicit compatibility boundary (design section 2): it may
    stay, but it may not carry entry scenarios, so its behaviour is never taken as the
    normal shape of a new strategy.
    """
    analyze = inspect.signature(cls.analyze)
    assert list(analyze.parameters) == ["self", "market_data", "current_position"], (
        f"{cls.__name__}.analyze must take (self, market_data, current_position)"
    )
    for name in ("get_metadata", "get_parameter_schema"):
        attribute = inspect.getattr_static(cls, name)
        assert isinstance(attribute, classmethod), f"{cls.__name__}.{name} must be a classmethod"
        assert list(inspect.signature(getattr(cls, name)).parameters) == [], (
            f"{cls.__name__}.{name} takes no arguments"
        )
    metadata = cls.get_metadata()
    assert isinstance(metadata, StrategyMetadata)
    assert isinstance(cls.get_parameter_schema(), ParameterSchema)
    assert metadata.decision_contract is case.contract, (
        f"{cls.__name__} declares the {metadata.decision_contract.value} contract, the "
        f"scenario row holds it to {case.contract.value}"
    )
    if case.contract is StrategyDecisionContract.TRADING_SIGNAL:
        assert not case.directions, (
            f"{cls.__name__} is a legacy TradingSignal boundary and may not carry entry scenarios"
        )


def check_declared_series_are_registered(cls: AdapterClass, case: Case) -> None:
    indicators = build_default_registry()
    metadata = cls.get_metadata()
    assert metadata.min_history >= 1
    assert set(case.timeframes) == set(metadata.supported_timeframes), (
        f"the scenario row for {cls.__name__} must name exactly the declared timeframes "
        f"(row {sorted(case.timeframes)}, class {sorted(metadata.supported_timeframes)})"
    )
    for item in metadata.required_indicators:
        name = str(item["name"])
        params = cast("Mapping[str, bool | float | int | str]", _params(item))
        if name.startswith("pat_"):
            TALIB_PATTERN_REGISTRY.get(name, params)
        else:
            indicators.get(name, params)
    assert case.directions or case.hold is not None, (
        f"the scenario row for {cls.__name__} needs an entry direction or a HOLD input"
    )
    for inputs, _side in case.steps:
        for timeframe in case.timeframes:
            assert set(inputs.indicators(cls, timeframe)) == _declared_keys(cls, timeframe), (
                "the scenario must carry exactly the declared series"
            )
        assert len(inputs.bars) > metadata.min_history, (
            "the scenario must carry the warm-up the strategy declares plus the deciding bar"
        )


def check_policy_declaration(cls: AdapterClass, case: Case) -> None:
    """Section 10 items 5 and 6: the declaration equals the row and composes at run time."""
    metadata = cls.get_metadata()
    support = metadata.money_management
    assert support.supported == case.supported, (
        f"{cls.__name__} declares policies {support.supported}, the scenario row expects "
        f"{case.supported}"
    )
    assert support.default == case.default
    assert support.supports_signal_exit is case.signal_exit
    assert {mode: dict(values) for mode, values in support.default_settings.items()} == {
        mode: dict(values) for mode, values in case.default_settings.items()
    }, f"{cls.__name__} declares default settings the scenario row does not expect"
    assert _MONEY_MANAGEMENT_OWNED_NAMES.isdisjoint(cls.get_parameter_schema().fields), (
        "strategy parameters must not carry money-management-owned names (contract 4.2)"
    )
    if not support.supported:
        # The contract (5.5, "빈 정책 목록") allows a HOLD-only strategy to declare no policy;
        # it fails the moment it tries to enter, so it may not carry an entry scenario.
        assert not case.directions, (
            f"{cls.__name__} declares no policy, so its scenario may not expect an entry"
        )
        return
    assert set(support.supported) <= set(_POLICIES), (
        f"{cls.__name__} supports a policy that is not deployed: "
        f"{sorted(set(support.supported) - set(_POLICIES))}"
    )
    assert support.default in support.supported
    manager = _manager(cls, case.strategy_id)
    raw = {"strategy_id": case.strategy_id, "params": dict(case.params)}
    for mode in support.supported:
        try:
            runtime = manager.create_runtime(case.strategy_id, raw, {"mode": mode})
        except ValueError as error:
            raise AssertionError(
                f"{cls.__name__} declares the {mode} policy but the runtime refuses the "
                f"composition: {error}"
            ) from error
        policy = runtime.money_management
        assert policy is not None and policy.id == mode
    for mode in sorted(set(_POLICIES) - set(support.supported)):
        with pytest.raises(ValueError, match="does not support|requires strategy signal exits"):
            manager.create_runtime(case.strategy_id, raw, {"mode": mode})


def check_determinism(cls: AdapterClass, case: Case, timeframe: str) -> None:
    """Section 4: the same instance repeats itself, and fresh instances agree."""
    strategy = _instance(cls, case)
    for inputs, side in case.steps:
        market = _market(cls, case, inputs, timeframe)
        first = _decide(strategy, market, _held(side))
        for _ in range(3):
            assert _decide(strategy, market, _held(side)) == first, (
                f"{cls.__name__} answered differently on a repeated identical call"
            )
    assert _replay(cls, case, timeframe) == _replay(cls, case, timeframe), (
        f"{cls.__name__} depends on hidden shared state"
    )


def check_config_immutability(cls: AdapterClass, case: Case, timeframe: str) -> None:
    strategy = _instance(cls, case)
    before = dict(strategy.config.params)
    for inputs, side in case.steps:
        _decide(strategy, _market(cls, case, inputs, timeframe), _held(side))
    assert dict(strategy.config.params) == before, f"{cls.__name__} changed its resolved config"
    with pytest.raises(TypeError):
        strategy.config.params["injected"] = 1


def check_policy_independence(cls: AdapterClass, case: Case, timeframe: str) -> None:
    """Section 5: the policy-added series must not change a decision."""
    baseline = _replay(cls, case, timeframe)
    for mode in cls.get_metadata().money_management.supported:
        extra = _policy_keys(cls, mode, timeframe)
        strategy = _instance(cls, case)
        with_policy = [
            _decide(
                strategy, _market(cls, case, inputs, timeframe, extra_series=extra), _held(side)
            )
            for inputs, side in case.steps
        ]
        assert with_policy == baseline, (
            f"{cls.__name__} decides differently under the {mode} policy's input"
        )


def _shifted(inputs: Inputs) -> Inputs:
    """The same scenario step with every close moved, so the later input really differs."""
    bars = tuple((o, h + 0.7, lo - 0.7, c + 0.7) for o, h, lo, c in inputs.bars)
    return Inputs(bars=bars, series=inputs.series)


def check_time_integrity_defensive(cls: AdapterClass, case: Case, timeframe: str) -> None:
    """Section 6, unit layer only: order independence, and no decision dated in the future.

    The engine hands a strategy the confirmed prefix and the deciding bar's series values,
    so a production-shaped input holds no future value to read. What this layer can still
    catch is a strategy that lets an input it saw *later* change an answer it gives for an
    *earlier* bar: the reference replays the scenario in order, the probe first receives
    every later step with its closes moved and only then the earlier steps, and the two
    must agree on the earlier steps. The guarantee that no value used at a decision was
    finalized after it belongs to the Engine composition layer.
    """
    steps = case.steps
    for cut in range(1, len(steps)):
        reference = _instance(cls, case)
        expected = [
            _decide(reference, _market(cls, case, inputs, timeframe), _held(side))
            for inputs, side in steps[:cut]
        ]
        probe = _instance(cls, case)
        for inputs, side in steps[cut:]:
            _decide(probe, _market(cls, case, _shifted(inputs), timeframe), _held(side))
        observed = [
            _decide(probe, _market(cls, case, inputs, timeframe), _held(side))
            for inputs, side in steps[:cut]
        ]
        assert observed == expected, f"{cls.__name__} let later input change an earlier decision"


def check_declared_versus_accessed(cls: AdapterClass, case: Case, timeframe: str) -> None:
    """Section 8: read only what was declared; report what was declared but never read."""
    declared = _declared_keys(cls, timeframe)
    read_anywhere: set[str] = set()
    schema_names = set(cls.get_parameter_schema().fields)
    for inputs, side in case.steps:
        for mode in (None, *cls.get_metadata().money_management.supported):
            extra = {} if mode is None else _policy_keys(cls, mode, timeframe)
            tracer = AccessTracer({**inputs.indicators(cls, timeframe), **extra})
            strategy = _instance(cls, case)
            params_tracer = AccessTracer(dict(strategy.config.params))
            object.__setattr__(strategy.config, "params", params_tracer)
            _decide(strategy, _market(cls, case, inputs, timeframe, tracer=tracer), _held(side))
            assert not tracer.enumerated, (
                f"{cls.__name__} enumerated the series mapping instead of reading declared keys"
            )
            undeclared = tracer.read - declared
            assert not undeclared, f"{cls.__name__} read undeclared series {sorted(undeclared)}"
            read_anywhere |= tracer.read
            unknown_params = params_tracer.read - schema_names
            assert not unknown_params, (
                f"{cls.__name__} read parameters outside its schema {sorted(unknown_params)}"
            )
    never_read = declared - read_anywhere
    if never_read:
        # A diagnosis, not a verdict: the scenario may simply not reach the branch.
        sys.stderr.write(
            f"[contract-suite] {cls.__name__} declared but never read on {timeframe}: "
            f"{sorted(never_read)}\n"
        )


def check_entry_and_exit_correspondence(cls: AdapterClass, case: Case, timeframe: str) -> None:
    """Section 9: each direction enters on its own evidence and leaves on its own evidence."""
    support = cls.get_metadata().money_management
    for direction in case.directions:
        strategy = _instance(cls, case)
        entry = _decide(strategy, _market(cls, case, direction.entry, timeframe), None)
        assert entry.action is direction.action, (
            f"{cls.__name__} did not enter {direction.action.value} on the scenario "
            f"(got {entry.action.value}: {entry.reason})"
        )
        held = _decide(
            strategy, _market(cls, case, direction.exit, timeframe), _position(direction.side)
        )
        if support.supports_signal_exit:
            assert held.action is DecisionAction.EXIT, (
                f"{cls.__name__} declares signal exits but did not close its "
                f"{direction.side.value} position (got {held.action.value}: {held.reason})"
            )
        else:
            assert held.action is DecisionAction.HOLD, (
                f"{cls.__name__} declares no signal exit; holding must be a HOLD "
                f"(got {held.action.value})"
            )
        still_open = _decide(
            strategy, _market(cls, case, direction.entry, timeframe), _position(direction.side)
        )
        assert still_open.action is not direction.action, (
            f"{cls.__name__} re-entered while already holding a {direction.side.value} position"
        )


_TYPE_CHECKING_GUARD = "TYPE_CHECKING"


def _module_imports(tree: ast.AST) -> tuple[set[str], list[str], list[str]]:
    """Return import roots at module level, dynamic (nested) imports, and clock/random calls."""
    roots: set[str] = set()
    nested: list[str] = []
    clock_calls: list[str] = []

    def visit(node: ast.AST, top_level: bool, in_type_checking: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.If) and _is_type_checking_guard(child.test):
                visit(child, top_level, True)
                continue
            if isinstance(child, ast.Import | ast.ImportFrom):
                names = (
                    [alias.name for alias in child.names]
                    if isinstance(child, ast.Import)
                    else [child.module or ""]
                )
                if not top_level:
                    nested.extend(names)
                elif not in_type_checking:
                    if isinstance(child, ast.ImportFrom) and child.level > 0:
                        # A relative import stays inside the plugin package; the helper it
                        # names is followed and audited by ``_imported_plugin_modules``.
                        roots.add("trading_plugins")
                    else:
                        roots.update(name.split(".")[0] for name in names)
                continue
            if isinstance(child, ast.Call):
                callee = child.func
                if isinstance(callee, ast.Attribute) and callee.attr in _CLOCK_AND_RANDOM_CALLS:
                    clock_calls.append(ast.unparse(callee))
                if (isinstance(callee, ast.Name) and callee.id in _DYNAMIC_IMPORT_CALLS) or (
                    isinstance(callee, ast.Attribute) and callee.attr in _DYNAMIC_IMPORT_CALLS
                ):
                    nested.append(ast.unparse(child))
            nested_scope = isinstance(
                child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Lambda
            )
            visit(child, top_level and not nested_scope, in_type_checking)

    visit(tree, True, False)
    return roots, nested, clock_calls


def _is_type_checking_guard(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == _TYPE_CHECKING_GUARD) or (
        isinstance(test, ast.Attribute) and test.attr == _TYPE_CHECKING_GUARD
    )


def _imported_plugin_modules(tree: ast.AST, module_name: str) -> list[str]:
    """Every ``trading_plugins`` module the source imports, relative imports resolved."""
    package = module_name.rpartition(".")[0]
    targets: list[str] = []

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.If) and _is_type_checking_guard(child.test):
                # A type-only reference is not a runtime dependency (design section 7).
                for alternative in child.orelse:
                    visit(alternative)
                continue
            if isinstance(child, ast.Import):
                targets.extend(alias.name for alias in child.names)
            elif isinstance(child, ast.ImportFrom):
                if child.level == 0:
                    base = child.module or ""
                else:
                    parts = package.split(".")
                    base = ".".join(parts[: len(parts) - child.level + 1])
                    if child.module:
                        base = f"{base}.{child.module}"
                targets.append(base)
                # ``from package import helper`` names a module too when helper is one.
                targets.extend(f"{base}.{alias.name}" for alias in child.names)
            visit(child)

    visit(tree)
    return [target for target in targets if target.startswith("trading_plugins")]


def check_static_dependencies(
    source: str,
    module_name: str,
    *,
    source_of: Callable[[str], str | None] | None = None,
) -> None:
    """Section 7, static half: follow the strategy's imports up to the core_lib boundary.

    Helpers under ``trading_plugins`` (including ``trading_plugins.strategies``) are read
    and audited too; ``core_lib`` is the boundary and is not followed.
    """
    read_source = source_of or _source_of
    seen: set[str] = set()
    pending: list[tuple[str, str]] = [(source, module_name)]
    while pending:
        text, name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        tree = ast.parse(text)
        roots, nested, clock_calls = _module_imports(tree)
        assert not nested, f"{name} imports inside a function or class (dynamic import): {nested}"
        assert not clock_calls, f"{name} calls the clock or randomness: {clock_calls}"
        forbidden = roots - _ALLOWED_IMPORT_ROOTS - {"trading_plugins"}
        assert not forbidden, f"{name} imports forbidden modules: {sorted(forbidden)}"
        for target in _imported_plugin_modules(tree, name):
            if target in seen:
                continue
            helper_source = read_source(target)
            if helper_source is not None:
                pending.append((helper_source, target))


def _source_of(module_name: str) -> str | None:
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError:
        return None  # ``from package import name`` where name is an attribute, not a module
    return inspect.getsource(module)


class _RuntimeGuard:
    """Section 7, runtime half: fail file, network, database, subprocess, import, and clock."""

    armed: ClassVar[bool] = False
    installed: ClassVar[bool] = False

    @classmethod
    def install(cls) -> None:
        if cls.installed:
            return
        cls.installed = True

        def hook(event: str, _args: tuple[object, ...]) -> None:
            if cls.armed and event in _FORBIDDEN_AUDIT_EVENTS:
                raise RuntimeError(f"forbidden dependency at run time: {event}")

        sys.addaudithook(hook)

    @classmethod
    @contextlib.contextmanager
    def during(cls) -> Iterator[None]:
        cls.install()

        def frozen(*_args: object, **_kwargs: object) -> float:
            raise RuntimeError("forbidden dependency at run time: the clock")

        with contextlib.ExitStack() as stack:
            for name in _FROZEN_TIME_FUNCTIONS:
                if hasattr(time, name):
                    stack.enter_context(mock.patch.object(time, name, frozen))
            cls.armed = True
            try:
                yield
            finally:
                cls.armed = False


def check_runtime_dependencies(cls: AdapterClass, case: Case, timeframe: str) -> None:
    strategy = _instance(cls, case)
    # One unguarded warm-up call lets lazy imports inside core_lib happen once, so the guard
    # below observes the strategy's own behaviour and not the interpreter's first-use work.
    if case.steps:
        first_inputs, first_side = case.steps[0]
        _decide(strategy, _market(cls, case, first_inputs, timeframe), _held(first_side))
    for inputs, side in case.steps:
        try:
            with _RuntimeGuard.during():
                _decide(strategy, _market(cls, case, inputs, timeframe), _held(side))
        except RuntimeError as error:
            raise AssertionError(f"{cls.__name__}: {error}") from error


class _MemoryCatalog(StrategyRegistry):
    def __init__(self, strategy_id: str, cls: AdapterClass) -> None:
        self._row: dict[str, object] = {
            "strategy_id": strategy_id,
            "class_name": cls.__name__,
            "module_path": cls.__module__,
            "is_active": True,
            "is_deprecated": False,
        }

    def get(self, strategy_id: str) -> dict[str, object]:
        if strategy_id != self._row["strategy_id"]:
            raise KeyError(strategy_id)
        return dict(self._row)

    def list(self) -> list[dict[str, object]]:
        return [dict(self._row)]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError("read-only fixture")


def _manager(cls: AdapterClass, strategy_id: str) -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    plugins.register(strategy_id, cls)
    return AdapterManager(
        _MemoryCatalog(strategy_id, cls), plugins, money_management_policies=_POLICIES
    )


# --- the suite over every discovered strategy, on every declared timeframe --------------


def test_discovery_and_the_scenario_table_name_the_same_strategies() -> None:
    """Adding a strategy file without a scenario row is itself a failure (design section 3)."""
    assert _DISCOVERY_FAULTS == ()
    assert set(_DISCOVERED) == set(_CASES), (
        f"scenario rows missing: {sorted(set(_DISCOVERED) - set(_CASES))}; "
        f"rows without a strategy: {sorted(set(_CASES) - set(_DISCOVERED))}"
    )
    for strategy_id, case in _CASES.items():
        assert case.strategy_id == strategy_id


_CASE_IDS = sorted(_CASES)
_CASE_TIMEFRAMES = [
    (strategy_id, timeframe)
    for strategy_id in _CASE_IDS
    for timeframe in _CASES[strategy_id].timeframes
]
_TIMEFRAME_IDS = [f"{strategy_id}@{timeframe}" for strategy_id, timeframe in _CASE_TIMEFRAMES]


def _cls(strategy_id: str) -> AdapterClass:
    return _DISCOVERED[strategy_id]


@pytest.mark.parametrize("strategy_id", _CASE_IDS)
def test_signatures_and_target_contract(strategy_id: str) -> None:
    check_signatures(_cls(strategy_id), _CASES[strategy_id])


@pytest.mark.parametrize("strategy_id", _CASE_IDS)
def test_declared_series_are_registered_and_the_scenario_matches(strategy_id: str) -> None:
    check_declared_series_are_registered(_cls(strategy_id), _CASES[strategy_id])


@pytest.mark.parametrize("strategy_id", _CASE_IDS)
def test_policy_declaration_matches_the_row_and_the_runtime(strategy_id: str) -> None:
    check_policy_declaration(_cls(strategy_id), _CASES[strategy_id])


@pytest.mark.parametrize(("strategy_id", "timeframe"), _CASE_TIMEFRAMES, ids=_TIMEFRAME_IDS)
def test_decisions_are_deterministic(strategy_id: str, timeframe: str) -> None:
    check_determinism(_cls(strategy_id), _CASES[strategy_id], timeframe)


@pytest.mark.parametrize(("strategy_id", "timeframe"), _CASE_TIMEFRAMES, ids=_TIMEFRAME_IDS)
def test_resolved_config_is_immutable(strategy_id: str, timeframe: str) -> None:
    check_config_immutability(_cls(strategy_id), _CASES[strategy_id], timeframe)


@pytest.mark.parametrize(("strategy_id", "timeframe"), _CASE_TIMEFRAMES, ids=_TIMEFRAME_IDS)
def test_decisions_do_not_depend_on_the_policy(strategy_id: str, timeframe: str) -> None:
    check_policy_independence(_cls(strategy_id), _CASES[strategy_id], timeframe)


@pytest.mark.parametrize(("strategy_id", "timeframe"), _CASE_TIMEFRAMES, ids=_TIMEFRAME_IDS)
def test_later_input_cannot_change_an_earlier_decision(strategy_id: str, timeframe: str) -> None:
    check_time_integrity_defensive(_cls(strategy_id), _CASES[strategy_id], timeframe)


@pytest.mark.parametrize(("strategy_id", "timeframe"), _CASE_TIMEFRAMES, ids=_TIMEFRAME_IDS)
def test_the_strategy_reads_only_what_it_declared(strategy_id: str, timeframe: str) -> None:
    check_declared_versus_accessed(_cls(strategy_id), _CASES[strategy_id], timeframe)


@pytest.mark.parametrize(("strategy_id", "timeframe"), _CASE_TIMEFRAMES, ids=_TIMEFRAME_IDS)
def test_each_direction_enters_and_leaves_on_its_own_evidence(
    strategy_id: str, timeframe: str
) -> None:
    check_entry_and_exit_correspondence(_cls(strategy_id), _CASES[strategy_id], timeframe)


@pytest.mark.parametrize("strategy_id", _CASE_IDS)
def test_the_module_has_no_forbidden_dependency(strategy_id: str) -> None:
    cls = _cls(strategy_id)
    module = sys.modules[cls.__module__]
    check_static_dependencies(inspect.getsource(module), module.__name__)


@pytest.mark.parametrize(("strategy_id", "timeframe"), _CASE_TIMEFRAMES, ids=_TIMEFRAME_IDS)
def test_no_forbidden_dependency_is_used_at_run_time(strategy_id: str, timeframe: str) -> None:
    check_runtime_dependencies(_cls(strategy_id), _CASES[strategy_id], timeframe)


def test_a_strategy_base_subclass_missing_a_method_cannot_be_instantiated() -> None:
    class Incomplete(StrategyBase):
        @classmethod
        def get_metadata(cls) -> StrategyMetadata:  # pragma: no cover - never called
            raise NotImplementedError

        @classmethod
        def get_parameter_schema(cls) -> ParameterSchema:  # pragma: no cover
            raise NotImplementedError

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]


# --- fault injection (design section 12) ------------------------------------------------


def _fault_metadata(
    *,
    supported: tuple[str, ...] = ("manual",),
    supports_signal_exit: bool = True,
    timeframes: tuple[str, ...] = ("1h",),
) -> StrategyMetadata:
    return StrategyMetadata(
        required_indicators=[{"name": "EMA", "params": {"period": 9}}],
        min_history=1,
        supported_timeframes=list(timeframes),
        profile=StrategyProfile(
            id="fault-v1",
            family="test",
            bar="1h",
            expected_win_rate=(0.0, 1.0),
            expected_payoff=(0.0, 10.0),
            tail_shape="symmetric",
            holding_horizon="intraday",
            primary_metric="pf",
            risk_adjusted_pref="sortino",
            profit_structure_to_preserve="fault",
            envelope_tolerance=1.0,
            envelope_status="provisional",
        ),
        money_management=MoneyManagementSupport(
            supported=supported,
            default=supported[0] if supported else None,
            supports_external_stop=True,
            supports_external_take_profit=True,
            supports_signal_exit=supports_signal_exit,
        ),
        decision_contract=StrategyDecisionContract.DECISION_INTENT,
    )


def _fault_decision(candle: Candle, action: DecisionAction, reason: str) -> DecisionIntent:
    return DecisionIntent(
        action=action,
        symbol=candle.symbol,
        timestamp=candle.close_time,
        reference_price=float(candle.close),
        confidence=1.0,
        reason=reason,
        metadata={},
    )


class _FaultBase:
    """A well-behaved EMA-9 regime strategy; each fault below breaks exactly one property."""

    STRATEGY_ID = "fault-fixture"
    VERSION = "1.0.0"

    def __init__(self, config: ResolvedConfig) -> None:
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return _fault_metadata()

    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        return ParameterSchema(fields={})

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> DecisionIntent | TradingSignal | None:
        candle, ema = self._read(market_data)
        return self._judge(candle, ema, current_position)

    @staticmethod
    def _read(market_data: dict[str, object]) -> tuple[Candle, float]:
        candle = market_data["candle"]
        indicators = market_data["indicators"]
        timeframe = market_data["timeframe"]
        assert isinstance(candle, Candle)
        assert isinstance(indicators, Mapping)
        assert isinstance(timeframe, str)
        ema = indicators.get(series_key_of("EMA", {"period": 9}, timeframe))
        assert isinstance(ema, float)
        return candle, ema

    @staticmethod
    def _judge(candle: Candle, ema: float, position: Position | None) -> DecisionIntent:
        above = float(candle.close) > ema
        if position is not None:
            opposed = (position.side is PositionSide.LONG) != above
            return _fault_decision(
                candle, DecisionAction.EXIT if opposed else DecisionAction.HOLD, "fault-held"
            )
        action = DecisionAction.ENTER_LONG if above else DecisionAction.ENTER_SHORT
        return _fault_decision(candle, action, "fault-enter")


_FAULT_CASE = Case(
    strategy_id="fault-fixture",
    params={},
    timeframes=("1h",),
    market_type="futures",
    supported=("manual",),
    default="manual",
    signal_exit=True,
    long=Direction(
        DecisionAction.ENTER_LONG,
        entry=_one(101.0, {"ema:period=9": 100.0}),
        exit=_one(99.0, {"ema:period=9": 100.0}),
    ),
    short=Direction(
        DecisionAction.ENTER_SHORT,
        entry=_one(99.0, {"ema:period=9": 100.0}),
        exit=_one(101.0, {"ema:period=9": 100.0}),
    ),
)
_HOLD_ONLY_CASE = Case(
    strategy_id="fault-fixture",
    params={},
    timeframes=("1h",),
    market_type="futures",
    supported=(),
    default=None,
    signal_exit=False,
    hold=_one(101.0, {"ema:period=9": 100.0}),
)


class _GlobalStateFault(_FaultBase):
    calls: ClassVar[int] = 0

    def analyze(
        self, market_data: dict[str, object], current_position: Position | None
    ) -> DecisionIntent | None:
        type(self).calls += 1
        candle, ema = self._read(market_data)
        if type(self).calls % 2 == 0:
            return _fault_decision(candle, DecisionAction.HOLD, "fault-global-flip")
        return self._judge(candle, ema, current_position)


class _CallCountFault(_FaultBase):
    def __init__(self, config: ResolvedConfig) -> None:
        super().__init__(config)
        self._calls = 0

    def analyze(
        self, market_data: dict[str, object], current_position: Position | None
    ) -> DecisionIntent | None:
        self._calls += 1
        candle, ema = self._read(market_data)
        if self._calls > 1:
            return _fault_decision(candle, DecisionAction.HOLD, "fault-second-call")
        return self._judge(candle, ema, current_position)


class _LaterInputFault(_FaultBase):
    """Remembers the highest close it has seen and lets it override an earlier answer."""

    def __init__(self, config: ResolvedConfig) -> None:
        super().__init__(config)
        self._highest = 0.0

    def analyze(
        self, market_data: dict[str, object], current_position: Position | None
    ) -> DecisionIntent | None:
        candle, ema = self._read(market_data)
        self._highest = max(self._highest, float(candle.high))
        # The scenario's highs stop at 102.0; only a later, shifted step reaches beyond.
        if self._highest > 102.5:
            return _fault_decision(candle, DecisionAction.HOLD, "fault-saw-a-later-high")
        return self._judge(candle, ema, current_position)


class _RetainedStateFault(_FaultBase):
    """Keeps every bar it has seen on the instance while answering exactly as before."""

    def __init__(self, config: ResolvedConfig) -> None:
        super().__init__(config)
        self._seen: list[Candle] = []

    def analyze(
        self, market_data: dict[str, object], current_position: Position | None
    ) -> DecisionIntent | None:
        candle, ema = self._read(market_data)
        self._seen.append(candle)
        return self._judge(candle, ema, current_position)


class _MutatingInputFault(_FaultBase):
    def analyze(
        self, market_data: dict[str, object], current_position: Position | None
    ) -> DecisionIntent | None:
        candles = market_data["candles"]
        assert isinstance(candles, list)
        candles.clear()
        candle, ema = self._read(market_data)
        return self._judge(candle, ema, current_position)


class _HiddenReadFault(_FaultBase):
    def analyze(
        self, market_data: dict[str, object], current_position: Position | None
    ) -> DecisionIntent | None:
        candle, ema = self._read(market_data)
        indicators = market_data["indicators"]
        assert isinstance(indicators, Mapping)
        atr = indicators.get("atr:period=14@1h")
        if isinstance(atr, float) and atr > 1.0:
            return _fault_decision(candle, DecisionAction.HOLD, "fault-read-policy-series")
        return self._judge(candle, ema, current_position)


class _EnumeratingReadFault(_FaultBase):
    def analyze(
        self, market_data: dict[str, object], current_position: Position | None
    ) -> DecisionIntent | None:
        candle, ema = self._read(market_data)
        indicators = market_data["indicators"]
        assert isinstance(indicators, Mapping)
        if any(key.startswith("atr") for key in indicators):
            return _fault_decision(candle, DecisionAction.HOLD, "fault-enumerated")
        return self._judge(candle, ema, current_position)


class _FileReadingFault(_FaultBase):
    def analyze(
        self, market_data: dict[str, object], current_position: Position | None
    ) -> DecisionIntent | None:
        with open(__file__, encoding="utf-8") as handle:  # noqa: PTH123 - the fault
            handle.readline()
        candle, ema = self._read(market_data)
        return self._judge(candle, ema, current_position)


class _ClockFault(_FaultBase):
    def analyze(
        self, market_data: dict[str, object], current_position: Position | None
    ) -> DecisionIntent | None:
        time.time()
        candle, ema = self._read(market_data)
        return self._judge(candle, ema, current_position)


class _CachedImportClockFault(_FaultBase):
    """Reaches the clock through an already-imported module, so no import event fires."""

    def analyze(
        self, market_data: dict[str, object], current_position: Position | None
    ) -> DecisionIntent | None:
        __import__("time").clock_gettime(time.CLOCK_REALTIME)
        candle, ema = self._read(market_data)
        return self._judge(candle, ema, current_position)


class _MutatingPositionFault(_FaultBase):
    def analyze(
        self, market_data: dict[str, object], current_position: Position | None
    ) -> DecisionIntent | None:
        if current_position is not None:
            current_position.quantity = Decimal("2")
        candle, ema = self._read(market_data)
        return self._judge(candle, ema, current_position)


class _LegacySignalStrategy(_FaultBase):
    """A retained legacy strategy: declares TradingSignal and answers with one or None."""

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        metadata = _fault_metadata(supported=(), supports_signal_exit=False)
        metadata.decision_contract = StrategyDecisionContract.TRADING_SIGNAL
        return metadata

    def analyze(
        self, market_data: dict[str, object], current_position: Position | None
    ) -> TradingSignal | None:
        candle, ema = self._read(market_data)
        if current_position is not None or float(candle.close) <= ema:
            return None
        return TradingSignal(
            symbol=candle.symbol,
            timestamp=candle.close_time,
            confidence=0.5,
            price=candle.close,
            stop_loss=candle.close - 1.0,
            take_profit=candle.close + 2.0,
            market_type=MarketType.FUTURES,
            leverage=1,
            reason="legacy-entry",
            metadata={},
        )


class _LegacyShapeFromTargetFault(_LegacySignalStrategy):
    """Declares the target contract but answers with the legacy shape."""

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return _fault_metadata(supported=(), supports_signal_exit=False)


class _WrongDirectionExitFault(_FaultBase):
    """Exits a short on the long scenario's evidence and never closes a long."""

    @staticmethod
    def _judge(candle: Candle, ema: float, position: Position | None) -> DecisionIntent:
        above = float(candle.close) > ema
        if position is not None:
            if position.side is PositionSide.SHORT and above:
                return _fault_decision(candle, DecisionAction.EXIT, "fault-short-exit")
            return _fault_decision(candle, DecisionAction.HOLD, "fault-hold-forever")
        action = DecisionAction.ENTER_LONG if above else DecisionAction.ENTER_SHORT
        return _fault_decision(candle, action, "fault-enter")


class _UnsupportedPolicyFault(_FaultBase):
    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return _fault_metadata(supported=("turtle",), supports_signal_exit=False)


class _WidenedPolicyFault(_FaultBase):
    """Declares more policies than the scenario row says it should."""

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return _fault_metadata(supported=("manual", "turtle"))


class _OwnedNameFault(_FaultBase):
    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        return ParameterSchema(fields={"leverage": FieldSpec(type="integer", default=1)})


class _HardCodedTimeframeFault(_FaultBase):
    """Reads the 1h key whatever timeframe the run is on."""

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return _fault_metadata(timeframes=("1h", "4h"))

    @staticmethod
    def _read(market_data: dict[str, object]) -> tuple[Candle, float]:
        candle = market_data["candle"]
        indicators = market_data["indicators"]
        assert isinstance(candle, Candle)
        assert isinstance(indicators, Mapping)
        ema = indicators.get("ema:period=9@1h")
        assert isinstance(ema, float), "fault: the 1h key is not there on this timeframe"
        return candle, ema


class _HoldOnlyStrategy(_FaultBase):
    """A compliant strategy that never enters and declares no policy (contract 5.5)."""

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return _fault_metadata(supported=(), supports_signal_exit=False)

    def analyze(
        self, market_data: dict[str, object], current_position: Position | None
    ) -> DecisionIntent | None:
        candle, _ema = self._read(market_data)
        return _fault_decision(candle, DecisionAction.HOLD, "hold-only")


class _HoldOnlyFileFault(_HoldOnlyStrategy):
    """A HOLD-only strategy that still reads a file on every bar."""

    def analyze(
        self, market_data: dict[str, object], current_position: Position | None
    ) -> DecisionIntent | None:
        with open(__file__, encoding="utf-8") as handle:  # noqa: PTH123 - the fault
            handle.readline()
        return super().analyze(market_data, current_position)


class _HigherTimeframeStrategy(_FaultBase):
    """A compliant strategy whose one series is declared on 4h while it runs on 1h."""

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        metadata = _fault_metadata()
        metadata.required_indicators = [{"name": "EMA", "params": {"period": 9}, "timeframe": "4h"}]
        return metadata

    @staticmethod
    def _read(market_data: dict[str, object]) -> tuple[Candle, float]:
        candle = market_data["candle"]
        indicators = market_data["indicators"]
        assert isinstance(candle, Candle)
        assert isinstance(indicators, Mapping)
        ema = indicators.get(series_key_of("EMA", {"period": 9}, "4h"))
        assert isinstance(ema, float), "the 4h key must arrive whatever the run timeframe"
        return candle, ema


_STATIC_FAULT_SOURCE = '''
"""A strategy module that imports a service package and reads the clock."""

import subprocess
from datetime import datetime

from core_lib.strategy import StrategyBase


def _now():
    return datetime.now()


def _shell():
    import os

    return os.getcwd()
'''

_STATIC_HELPER_SOURCES = {
    "trading_plugins.strategies.clean": (
        "from core_lib.strategy import StrategyBase\n"
        "from trading_plugins.strategies._tainted_helper import decide\n"
    ),
    "trading_plugins.strategies._tainted_helper": "import socket\n\ndef decide():\n    return 1\n",
    "trading_plugins.strategies.relative": "from ._tainted_helper import decide\n",
}


@pytest.mark.parametrize(
    ("fault", "check", "message"),
    [
        (_GlobalStateFault, check_determinism, "answered differently|hidden shared state"),
        (_CallCountFault, check_determinism, "answered differently|changed the strategy's own"),
        (
            _LaterInputFault,
            check_time_integrity_defensive,
            "later input|changed the strategy's own",
        ),
        (_RetainedStateFault, check_determinism, "changed the strategy's own state"),
        (_MutatingInputFault, check_determinism, "changed its input"),
        (_HiddenReadFault, check_declared_versus_accessed, "read undeclared series"),
        (_EnumeratingReadFault, check_declared_versus_accessed, "enumerated the series mapping"),
        (_HiddenReadFault, check_policy_independence, "decides differently under the manual"),
        (_FileReadingFault, check_runtime_dependencies, "forbidden dependency at run time: open"),
        (_ClockFault, check_runtime_dependencies, "the clock"),
        (_CachedImportClockFault, check_runtime_dependencies, "the clock"),
        (_MutatingPositionFault, check_determinism, "changed its position"),
        (_WrongDirectionExitFault, check_entry_and_exit_correspondence, "did not close its long"),
    ],
    ids=[
        "global-state",
        "call-count",
        "later-input",
        "retained-state",
        "mutates-input",
        "hidden-read",
        "enumerating-read",
        "hidden-read-changes-decision",
        "file-read",
        "clock",
        "cached-import-clock",
        "mutates-position",
        "wrong-direction-exit",
    ],
)
def test_each_check_catches_the_fault_it_exists_for(
    fault: AdapterClass, check: Callable[[AdapterClass, Case, str], None], message: str
) -> None:
    _GlobalStateFault.calls = 0
    with pytest.raises(AssertionError, match=message):
        check(fault, _FAULT_CASE, "1h")


@pytest.mark.parametrize(
    ("fault", "case", "message"),
    [
        (_UnsupportedPolicyFault, _FAULT_CASE, "declares policies"),
        (_WidenedPolicyFault, _FAULT_CASE, "declares policies"),
        (_OwnedNameFault, _FAULT_CASE, "money-management-owned names"),
        (_FaultBase, _HOLD_ONLY_CASE, "declares policies"),
        (_HoldOnlyStrategy, _FAULT_CASE, "declares policies"),
    ],
    ids=[
        "unsupported-policy",
        "widened-policy",
        "owned-parameter-name",
        "row-expects-no-policy-but-class-declares-one",
        "class-declares-no-policy-but-row-expects-one",
    ],
)
def test_the_policy_declaration_check_catches_a_row_mismatch(
    fault: AdapterClass, case: Case, message: str
) -> None:
    with pytest.raises(AssertionError, match=message):
        check_policy_declaration(fault, case)


def test_a_turtle_declaration_without_signal_exits_is_refused_by_the_runtime() -> None:
    case = Case(
        strategy_id="fault-fixture",
        params={},
        timeframes=("1h",),
        market_type="futures",
        supported=("turtle",),
        default="turtle",
        signal_exit=False,
        long=_FAULT_CASE.long,
        short=_FAULT_CASE.short,
    )
    with pytest.raises(AssertionError, match="requires strategy signal exits"):
        check_policy_declaration(_UnsupportedPolicyFault, case)


def test_a_hold_only_strategy_without_policies_is_accepted_and_still_checked() -> None:
    check_signatures(_HoldOnlyStrategy, _HOLD_ONLY_CASE)
    check_policy_declaration(_HoldOnlyStrategy, _HOLD_ONLY_CASE)
    check_declared_series_are_registered(_HoldOnlyStrategy, _HOLD_ONLY_CASE)
    check_determinism(_HoldOnlyStrategy, _HOLD_ONLY_CASE, "1h")
    check_declared_versus_accessed(_HoldOnlyStrategy, _HOLD_ONLY_CASE, "1h")
    check_entry_and_exit_correspondence(_HoldOnlyStrategy, _HOLD_ONLY_CASE, "1h")
    check_runtime_dependencies(_HoldOnlyStrategy, _HOLD_ONLY_CASE, "1h")
    with pytest.raises(AssertionError, match="forbidden dependency at run time: open"):
        check_runtime_dependencies(_HoldOnlyFileFault, _HOLD_ONLY_CASE, "1h")
    with pytest.raises(AssertionError, match="needs an entry direction or a HOLD input"):
        check_declared_series_are_registered(
            _HoldOnlyStrategy,
            Case(
                strategy_id="fault-fixture",
                params={},
                timeframes=("1h",),
                market_type="futures",
                supported=(),
                default=None,
                signal_exit=False,
            ),
        )


def test_a_series_declared_on_its_own_timeframe_keeps_that_key() -> None:
    assert _declared_keys(_HigherTimeframeStrategy, "1h") == {"ema:period=9@4h"}
    check_declared_series_are_registered(_HigherTimeframeStrategy, _FAULT_CASE)
    check_determinism(_HigherTimeframeStrategy, _FAULT_CASE, "1h")
    check_declared_versus_accessed(_HigherTimeframeStrategy, _FAULT_CASE, "1h")
    check_entry_and_exit_correspondence(_HigherTimeframeStrategy, _FAULT_CASE, "1h")


def test_a_type_checking_only_helper_import_is_not_a_runtime_dependency() -> None:
    check_static_dependencies(
        "from __future__ import annotations\n\n"
        "from typing import TYPE_CHECKING\n\n"
        "if TYPE_CHECKING:\n"
        "    from trading_plugins.strategies._tainted_helper import decide\n",
        "trading_plugins.strategies.typed",
        source_of=_STATIC_HELPER_SOURCES.get,
    )


_LEGACY_CASE = Case(
    strategy_id="fault-fixture",
    params={},
    timeframes=("1h",),
    market_type="futures",
    supported=(),
    default=None,
    signal_exit=False,
    contract=StrategyDecisionContract.TRADING_SIGNAL,
    hold=_one(99.0, {"ema:period=9": 100.0}),
)


def test_a_legacy_row_is_an_explicit_boundary_and_never_widens_the_target_contract() -> None:
    check_signatures(_LegacySignalStrategy, _LEGACY_CASE)
    check_policy_declaration(_LegacySignalStrategy, _LEGACY_CASE)
    check_determinism(_LegacySignalStrategy, _LEGACY_CASE, "1h")
    check_runtime_dependencies(_LegacySignalStrategy, _LEGACY_CASE, "1h")
    with pytest.raises(AssertionError, match="holds it to DecisionIntent"):
        check_signatures(_LegacySignalStrategy, _HOLD_ONLY_CASE)
    with pytest.raises(AssertionError, match="may not carry entry scenarios"):
        check_signatures(
            _LegacySignalStrategy,
            Case(
                strategy_id="fault-fixture",
                params={},
                timeframes=("1h",),
                market_type="futures",
                supported=(),
                default=None,
                signal_exit=False,
                contract=StrategyDecisionContract.TRADING_SIGNAL,
                long=_FAULT_CASE.long,
            ),
        )
    with pytest.raises(AssertionError, match="declared DecisionIntent but returned TradingSignal"):
        check_determinism(_LegacyShapeFromTargetFault, _FAULT_CASE, "1h")


def test_the_static_check_catches_import_calls_that_bypass_the_import_statement() -> None:
    with pytest.raises(AssertionError, match="dynamic import"):
        check_static_dependencies(
            "from core_lib.strategy import StrategyBase\n\n\n"
            "def _clock():\n    return __import__('time').clock_gettime(0)\n",
            "fault_module",
        )
    with pytest.raises(AssertionError, match="dynamic import"):
        check_static_dependencies(
            "import importlib\n\n\ndef _load():\n    return importlib.import_module('os')\n",
            "fault_module",
        )


def test_a_hard_coded_timeframe_key_fails_on_the_other_declared_timeframe() -> None:
    case = Case(
        strategy_id="fault-fixture",
        params={},
        timeframes=("1h", "4h"),
        market_type="futures",
        supported=("manual",),
        default="manual",
        signal_exit=True,
        long=_FAULT_CASE.long,
        short=_FAULT_CASE.short,
    )
    check_determinism(_HardCodedTimeframeFault, case, "1h")
    with pytest.raises(AssertionError, match="the 1h key is not there"):
        check_determinism(_HardCodedTimeframeFault, case, "4h")


def test_the_faults_pass_the_checks_they_do_not_break() -> None:
    """The fault base itself is a well-behaved strategy, so failures above are the faults'."""
    check_signatures(_FaultBase, _FAULT_CASE)
    check_declared_series_are_registered(_FaultBase, _FAULT_CASE)
    check_policy_declaration(_FaultBase, _FAULT_CASE)
    check_determinism(_FaultBase, _FAULT_CASE, "1h")
    check_policy_independence(_FaultBase, _FAULT_CASE, "1h")
    check_time_integrity_defensive(_FaultBase, _FAULT_CASE, "1h")
    check_declared_versus_accessed(_FaultBase, _FAULT_CASE, "1h")
    check_entry_and_exit_correspondence(_FaultBase, _FAULT_CASE, "1h")
    check_runtime_dependencies(_FaultBase, _FAULT_CASE, "1h")


def test_the_static_check_catches_service_imports_dynamic_imports_and_the_clock() -> None:
    with pytest.raises(AssertionError, match="dynamic import"):
        check_static_dependencies(_STATIC_FAULT_SOURCE, "fault_module")
    without_dynamic = _STATIC_FAULT_SOURCE.replace(
        "    import os\n\n    return os.getcwd()", "    return 1"
    )
    with pytest.raises(AssertionError, match="calls the clock"):
        check_static_dependencies(without_dynamic, "fault_module")
    without_clock = without_dynamic.replace("    return datetime.now()", "    return 1")
    with pytest.raises(AssertionError, match="forbidden modules: \\['datetime', 'subprocess'\\]"):
        check_static_dependencies(without_clock, "fault_module")


def test_the_static_check_follows_helpers_inside_the_strategies_package() -> None:
    for module_name in ("trading_plugins.strategies.clean", "trading_plugins.strategies.relative"):
        with pytest.raises(AssertionError, match="_tainted_helper imports forbidden modules"):
            check_static_dependencies(
                _STATIC_HELPER_SOURCES[module_name],
                module_name,
                source_of=_STATIC_HELPER_SOURCES.get,
            )


def test_a_module_the_static_check_accepts() -> None:
    check_static_dependencies(
        "from __future__ import annotations\nfrom core_lib.strategy import StrategyBase\n",
        "clean_module",
    )
