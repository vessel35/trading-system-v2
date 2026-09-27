"""Common contract checks applied to every discovered strategy: the Engine composition layer.

Design: ``docs/fullspec/strategy_contract_suite_design.md``, section 16 (2026-09-26). This is the
second verification layer; the strategy-unit layer is
``services/trading-plugins/tests/test_strategy_contract_suite.py``. Here every strategy that
``trading_plugins.strategies`` discovers is run through the production ``Engine`` on one synthetic
feed, once per declared timeframe under its default policy and once more under Turtle when it
declares that policy, and each run is checked from two sides:

- what the strategy actually received at every decision, recorded by wrapping its ``analyze``
  (design 16.4, check 1), and the series timestamps the Engine recorded for the same bars (2);
- the Evidence the run left: every decision precedes its execution (3), Turtle sizing used the most
  recent daily bar closed at or before the decision, re-derived from the daily input alone (4), and
  the Engine's own audit passed (6).

A combination the strategy did not declare is refused by ``Engine.run`` before a run is registered
(5). The faults at the end are injected into the composition, never into a strategy, and prove that
each check catches the defect it exists for (design 16.5).

This layer does not recompute strategy decisions (that is ``verify-strategy``'s job) and does not
run the full policy-by-timeframe product: the only path on which a policy changes a time relation
is Turtle's daily N, and the independence of decisions from the policy is the strategy-unit layer's
check.
"""

from __future__ import annotations

import json
import math
import random
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any, cast

import pytest
from backtest_service.adapters.broker import BacktestBroker
from backtest_service.adapters.catalog_store import DeterminismReference
from backtest_service.adapters.clock import BacktestClock
from backtest_service.adapters.cost_model import BacktestCostModel
from backtest_service.adapters.evidence_sink import BacktestEvidenceSink, epoch_milliseconds
from backtest_service.adapters.ohlcv_gaps import timeframe_milliseconds
from backtest_service.config import RunConfig
from backtest_service.engine import Engine, RunResult
from core_lib.money_management import (
    MoneyManagementBase,
    MoneyManagementFactory,
    turtle_n_series,
)
from core_lib.ports import CatalogStore, DataFeed, StrategyRegistry
from core_lib.series import series_key_of
from core_lib.strategy import AdapterClass, AdapterManager, InProcessStrategyRegistry
from core_lib.types import Candle, Fill, OrderRequest, Position
from trading_plugins import discover_strategies, registered_money_management

_DISCOVERED, _DISCOVERY_FAULTS = discover_strategies()
_POLICIES = registered_money_management()


# --- the engine case table (design 16.2) --------------------------------------------------------


@dataclass(frozen=True)
class EngineCase:
    """One discovered strategy's representative run inputs.

    Timeframes and policies are not written here: they are read from the strategy's declaration,
    and the strategy-unit layer already checks that declaration against its scenario table.
    """

    strategy_id: str
    params: Mapping[str, object]
    market_type: str


_ENGINE_CASES: Mapping[str, EngineCase] = {
    "vessel-reference": EngineCase("vessel-reference", {}, "futures"),
    "supertrend-ema200-flip": EngineCase("supertrend-ema200-flip", {}, "futures"),
    "macd-ema200-zero-line": EngineCase("macd-ema200-zero-line", {}, "futures"),
    "bollinger-rsi-reversion": EngineCase("bollinger-rsi-reversion", {}, "futures"),
    "donchian-breakout-atr": EngineCase("donchian-breakout-atr", {}, "futures"),
    "three-bar-reversion": EngineCase("three-bar-reversion", {}, "futures"),
    "bollinger-band-bounce": EngineCase("bollinger-band-bounce", {}, "futures"),
}


@dataclass(frozen=True)
class Combination:
    """One Engine run: a strategy on one declared timeframe under one declared policy."""

    strategy_id: str
    timeframe: str
    mode: str

    @property
    def label(self) -> str:
        return f"{self.strategy_id}@{self.timeframe}+{self.mode}"


def _combinations() -> tuple[Combination, ...]:
    """Every declared timeframe under the default policy, plus Turtle once where declared."""
    found: list[Combination] = []
    for strategy_id in sorted(_ENGINE_CASES):
        cls = _DISCOVERED[strategy_id]
        metadata = cls.get_metadata()
        support = metadata.money_management
        default = support.default
        assert default is not None, f"{strategy_id} declares no default policy"
        for timeframe in metadata.supported_timeframes:
            found.append(Combination(strategy_id, timeframe, default))
        if "turtle" in support.supported and default != "turtle":
            found.append(Combination(strategy_id, metadata.supported_timeframes[0], "turtle"))
    return tuple(found)


_COMBINATIONS = _combinations()
_COMBINATION_IDS = [combination.label for combination in _COMBINATIONS]
_TURTLE_COMBINATIONS = [item for item in _COMBINATIONS if item.mode == "turtle"]


# --- materials (design 16.3) --------------------------------------------------------------------

_SYMBOL = "BTCUSDT"
_EXCHANGE = "binance"
_END = datetime(2026, 1, 11, tzinfo=UTC)
_MINUTE_MS = 60_000
_HOUR_MS = 60 * _MINUTE_MS
_DAY_MS = 24 * _HOUR_MS
# Warm-up budget in bars of the execution timeframe, above the longest declared history (EMA 200).
_WARMUP_BARS = 320
# Daily history the Turtle policy can ask for before the first evaluated bar, in days.
_DAILY_HISTORY_DAYS = 60
# Fixed when the material was made (2026-09-26): of four candidate seeds it is the one on which
# every combination enters at least three times and each Turtle combination enters on at least
# three different days. It is part of the material, not a knob to turn when a run stops entering.
_MATERIAL_SEED = 2


def _evaluation_bars(timeframe: str) -> int:
    """How many bars of ``timeframe`` are evaluated: 240 up to an hour, then 480 hours' worth."""
    duration = timeframe_milliseconds(timeframe)
    if duration <= _HOUR_MS:
        return 240
    return max(20, 480 * _HOUR_MS // duration)


def _declared_timeframes() -> frozenset[str]:
    return frozenset(
        timeframe
        for cls in _DISCOVERED.values()
        for timeframe in cls.get_metadata().supported_timeframes
    )


def _path_hours() -> int:
    """Hours of 1m material that cover every declared timeframe's warm-up and evaluation.

    The length follows the declarations, so a strategy that declares a timeframe no current
    strategy uses gets a path that fits it rather than a missing key. Rounded up to whole days so
    that daily bars aggregate on UTC day boundaries.
    """
    needed = [_DAILY_HISTORY_DAYS * 24 * _HOUR_MS]
    for timeframe in _declared_timeframes():
        duration = timeframe_milliseconds(timeframe)
        needed.append((_WARMUP_BARS + _evaluation_bars(timeframe)) * duration)
    days = -(-max(needed) // _DAY_MS)
    return days * 24


def _candle(
    timeframe: str,
    open_time: datetime,
    duration: timedelta,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float,
) -> Candle:
    return Candle(
        symbol=_SYMBOL,
        exchange=_EXCHANGE,
        timeframe=timeframe,
        open_time=open_time,
        close_time=open_time + duration,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        quote_volume=None,
        trade_count=None,
    )


@cache
def _minute_path() -> tuple[Candle, ...]:
    """The base material: a fixed-seed 1m path with alternating regimes ending at ``_END``.

    Every other timeframe is aggregated from it, so the execution path, the 1m origin the Engine
    validates, and the daily series Turtle reads are one price history. The seed is part of the
    material, not a knob (design 16.3).
    """
    rng = random.Random(_MATERIAL_SEED)
    minutes = _path_hours() * 60
    first_open = _END - timedelta(minutes=minutes)
    price = 100.0
    candles: list[Candle] = []
    for index in range(minutes):
        drift = (0.0012 / 60.0) * math.sin(2.0 * math.pi * index / (160.0 * 60.0))
        shock = rng.gauss(0.0, 0.008 / math.sqrt(60.0))
        open_price = price
        price = price * math.exp(drift + shock)
        candles.append(
            _candle(
                "1m",
                first_open + timedelta(minutes=index),
                timedelta(minutes=1),
                open_price=open_price,
                high=max(open_price, price) * (1.0 + abs(rng.gauss(0.0, 0.0003))),
                low=min(open_price, price) * (1.0 - abs(rng.gauss(0.0, 0.0003))),
                close=price,
                volume=100.0 / 60.0,
            )
        )
    return tuple(candles)


@cache
def _path(timeframe: str) -> tuple[Candle, ...]:
    """The finalized bars of one timeframe, aggregated from the 1m material."""
    if timeframe == "1m":
        return _minute_path()
    duration = timeframe_milliseconds(timeframe)
    width = duration // _MINUTE_MS
    minutes = _minute_path()
    assert len(minutes) % width == 0, f"the material does not divide into {timeframe} bars"
    bars: list[Candle] = []
    for index in range(0, len(minutes), width):
        group = minutes[index : index + width]
        bars.append(
            _candle(
                timeframe,
                group[0].open_time,
                timedelta(milliseconds=duration),
                open_price=group[0].open,
                high=max(candle.high for candle in group),
                low=min(candle.low for candle in group),
                close=group[-1].close,
                volume=sum(candle.volume for candle in group),
            )
        )
    return tuple(bars)


def _daily_path() -> tuple[Candle, ...]:
    """The finalized daily series Turtle reads: the same material on UTC day boundaries.

    The Engine reads it up to the run's end, so the bars that close inside an evaluation window
    are served from the start and must be used only once they have closed.
    """
    return _path("1d")


class _Feed(DataFeed):
    """Serve every timeframe the combinations need from the cached materials."""

    def candles(self, symbol: str, tf: str, up_to: datetime) -> list[Candle]:
        assert symbol == _SYMBOL
        return [candle for candle in _path(tf) if candle.close_time <= up_to]

    def source_candles(
        self, symbol: str, range_start: datetime, range_end: datetime
    ) -> tuple[Candle, ...]:
        assert symbol == _SYMBOL
        return tuple(
            candle
            for candle in _minute_path()
            if range_start <= candle.open_time and candle.close_time <= range_end
        )

    def funding(self, symbol: str, at: datetime) -> Decimal:
        del symbol, at
        raise LookupError("no boundary funding in this fixture")

    def mark_price(self, symbol: str, at: datetime) -> Decimal:
        assert symbol == _SYMBOL
        minutes = _minute_path()
        closed = [candle for candle in minutes if candle.close_time <= at]
        last = closed[-1] if closed else minutes[0]
        return Decimal(str(last.close))


class _Catalog(CatalogStore):
    """Hold registrations in memory; ``registered`` shows whether a run was ever issued an id."""

    def __init__(self) -> None:
        self.registered: list[str] = []
        self.runs: dict[str, Mapping[str, object]] = {}

    def register(self, run: object) -> str:
        assert isinstance(run, Mapping)
        run_id = f"BT_20260926_{len(self.registered) + 1:06d}_{run['run_name']}"
        self.registered.append(run_id)
        self.runs[run_id] = dict(run)
        return run_id

    def save_prereg(self, prereg: object) -> None:
        del prereg

    def upsert_summary(self, summary: object) -> None:
        del summary

    def record_harness_aggregate(
        self,
        run_id: str,
        *,
        oos_degradation: float | None,
        psr: float | None,
        harness_json: object,
    ) -> None:
        del run_id, oos_degradation, psr, harness_json

    def reconcile_orphaned(self) -> int:
        return 0

    def determinism_reference(
        self,
        run_id: str,
        config_hash: str,
        source_data_hash: str,
        evidence_schema_version: str,
    ) -> DeterminismReference:
        del source_data_hash, evidence_schema_version
        matches = self.runs[run_id]["config_hash"] == config_hash
        return DeterminismReference(matches, True, False, False, None, None)


class _DeployedRows(StrategyRegistry):
    """The registration row each discovered class would carry, minus lifecycle."""

    def get(self, strategy_id: str) -> dict[str, object]:
        cls = _DISCOVERED[strategy_id]
        return {
            "strategy_id": strategy_id,
            "class_name": cls.__name__,
            "module_path": cls.__module__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get(strategy_id) for strategy_id in _DISCOVERED]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError("read-only fixture")


def _manager() -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    for strategy_id, cls in _DISCOVERED.items():
        plugins.register(strategy_id, cls)
    return AdapterManager(_DeployedRows(), plugins, money_management_policies=_POLICIES)


def _run_config(
    combination: Combination,
    *,
    run_name: str,
    evaluation_bars: int | None = None,
) -> RunConfig:
    case = _ENGINE_CASES[combination.strategy_id]
    bars = _evaluation_bars(combination.timeframe) if evaluation_bars is None else evaluation_bars
    start = _END - bars * timedelta(milliseconds=timeframe_milliseconds(combination.timeframe))
    return RunConfig.model_validate(
        {
            "run_name": run_name,
            "strategy_id": combination.strategy_id,
            "params": dict(case.params),
            "symbol": _SYMBOL,
            "exchange": _EXCHANGE,
            "timeframe": combination.timeframe,
            "market_type": case.market_type,
            "data_source": "synthetic-engine-layer",
            "start": start,
            "end": _END,
            "initial_capital": Decimal("10000"),
            "risk_per_trade": 0.01,
            # Only the mode is submitted, so the strategy's declared settings are what runs.
            "money_management": {"mode": combination.mode},
            "cost_values": {
                "futures_taker_fee_rate": Decimal("0.0004"),
                "futures_entry_slippage_rate": Decimal("0"),
                "exit_slippage_rate": Decimal("0"),
                "funding_fallback_rate": Decimal("0"),
            },
            "profile_ref": _DISCOVERED[combination.strategy_id].get_metadata().profile.id,
            "seed": 7,
        }
    )


def _engine(root: Path, catalog: _Catalog, timeframe: str, config: RunConfig) -> Engine:
    costs = BacktestCostModel(config.cost_values)
    return Engine(
        _Feed(),
        BacktestBroker(costs),
        BacktestClock.from_candles(_path(timeframe)),
        costs,
        BacktestEvidenceSink(root),
        catalog,
        _manager(),
        prereg={
            "hypothesis": "the composition keeps every decision on finalized inputs",
            "primary_metric": "pf",
            "success_threshold": 1.3,
            "failure_threshold": 1.0,
            "edge_distinguishable": True,
            "higher_is_better": True,
        },
    )


# --- what the strategy received (design 16.4, check 1) -----------------------------------------


@dataclass(frozen=True)
class Observation:
    """One ``analyze`` call as the Engine made it."""

    decision_close: datetime
    last_candle_close: datetime
    latest_candle_close: datetime
    candle_timeframes: frozenset[str]
    indicator_keys: frozenset[str]


def _observing(cls: AdapterClass, observed: list[Observation]) -> Callable[..., object]:
    """Wrap the class's own ``analyze`` so every call is recorded before it runs."""
    original = cast(Callable[[Any, Mapping[str, object], Position | None], object], cls.analyze)

    def analyze(
        self: object, market_data: Mapping[str, object], current_position: Position | None
    ) -> object:
        candle = market_data["candle"]
        candles = market_data["candles"]
        indicators = market_data["indicators"]
        assert isinstance(candle, Candle)
        assert isinstance(candles, list) and candles
        assert isinstance(indicators, Mapping)
        observed.append(
            Observation(
                decision_close=candle.close_time,
                last_candle_close=candles[-1].close_time,
                latest_candle_close=max(item.close_time for item in candles),
                candle_timeframes=frozenset(item.timeframe for item in candles),
                indicator_keys=frozenset(str(key) for key in indicators),
            )
        )
        return original(self, market_data, current_position)

    return analyze


@dataclass(frozen=True)
class RunArtifacts:
    """One completed run and everything the checks read from it."""

    combination: Combination
    config: RunConfig
    result: RunResult
    observed: tuple[Observation, ...]
    catalog: _Catalog


Patch = Callable[[pytest.MonkeyPatch], None]


def _run(
    combination: Combination,
    root: Path,
    *,
    patch: Patch | None = None,
    evaluation_bars: int | None = None,
) -> RunArtifacts:
    cls = _DISCOVERED[combination.strategy_id]
    config = _run_config(
        combination, run_name=f"engine-layer-{combination.mode}", evaluation_bars=evaluation_bars
    )
    catalog = _Catalog()
    engine = _engine(root, catalog, combination.timeframe, config)
    observed: list[Observation] = []
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(cls, "analyze", _observing(cls, observed))
        if patch is not None:
            patch(monkeypatch)
        result = engine.run(config)
    return RunArtifacts(combination, config, result, tuple(observed), catalog)


def _rows(path: str, query: str, parameters: tuple[object, ...] = ()) -> list[tuple[Any, ...]]:
    with sqlite3.connect(path) as connection:
        return [tuple(row) for row in connection.execute(query, parameters).fetchall()]


def _defined_series(run: RunArtifacts) -> dict[str, str]:
    """The series keys the run defined for the strategy, each with its timeframe.

    ``INDICATOR_DEFINITION`` holds exactly the resolved specs the Engine updates and snapshots. A
    policy's own daily requirement (Turtle's N) is not among them: it is listed in
    ``resolved_indicators_json`` with its policy version, but it never reaches the strategy and
    leaves no snapshot rows. A daily series the strategy itself declares is among them.
    """
    rows = _rows(
        run.result.evidence_path,
        "SELECT indicator_key FROM INDICATOR_DEFINITION ORDER BY indicator_key",
    )
    return {str(key): str(key).rsplit("@", 1)[1] for (key,) in rows}


def _policy_owned_keys(run: RunArtifacts) -> set[str]:
    """The keys of the requirements the run's policy prepares outside the strategy's series."""
    policy = MoneyManagementFactory.create(run.config.money_management.model_dump(), _POLICIES)
    return {
        series_key_of(requirement.name, requirement.params, requirement.timeframe)
        for requirement in policy.required_indicators()
        if requirement.timeframe != "strategy"
    }


def _resolved_for_the_strategy(run: RunArtifacts) -> set[str]:
    """``resolved_indicators_json`` minus the policy-owned entries, keyed like the definitions."""
    (resolved_json,) = _rows(
        run.result.evidence_path, "SELECT resolved_indicators_json FROM BACKTEST_RUN_LOCAL"
    )[0]
    return {
        series_key_of(str(entry["name"]), entry["params"], str(entry["timeframe"]))
        for entry in json.loads(str(resolved_json))
    } - _policy_owned_keys(run)


def check_strategy_inputs(run: RunArtifacts) -> None:
    """The strategy saw only the confirmed prefix, on its own timeframe, with the defined keys."""
    resolved = _defined_series(run)
    assert set(resolved) == _resolved_for_the_strategy(run)
    assert run.observed, "the strategy was never called"
    for item in run.observed:
        assert item.last_candle_close == item.decision_close, (
            f"the last candle was not the deciding bar at {item.decision_close}"
        )
        assert item.latest_candle_close <= item.decision_close, (
            f"a candle closing at {item.latest_candle_close} reached the decision "
            f"at {item.decision_close}"
        )
        assert item.candle_timeframes == {run.combination.timeframe}
        assert item.indicator_keys == set(resolved), (
            f"strategy saw {sorted(item.indicator_keys)}, run resolved {sorted(resolved)}"
        )


# --- series timestamps (check 2) ----------------------------------------------------------------


def check_series_timestamps(run: RunArtifacts) -> None:
    """Every series value at a decision was finalized at or before the deciding bar closed.

    ``INDICATOR_SNAPSHOT`` holds one row per defined series per evaluated bar, in ``snapshot_seq``
    order, and the Engine records them immediately before it calls the strategy, so the k-th group
    of rows belongs to the k-th observed call.
    """
    resolved = _defined_series(run)
    rows = _rows(
        run.result.evidence_path,
        "SELECT indicator_key, feature_ts FROM INDICATOR_SNAPSHOT ORDER BY snapshot_seq",
    )
    width = len(resolved)
    if width == 0:
        assert rows == []
        return
    assert len(rows) == width * len(run.observed), (
        f"{len(rows)} snapshot rows for {len(run.observed)} calls and {width} series"
    )
    for index, item in enumerate(run.observed):
        group = rows[index * width : (index + 1) * width]
        assert {str(key) for key, _ in group} == set(resolved)
        decision_ms = epoch_milliseconds(item.decision_close)
        for key, feature_ts in group:
            assert int(feature_ts) <= decision_ms, (
                f"{key} finalized at {feature_ts} reached the decision at {decision_ms}"
            )
            if resolved[str(key)] == run.combination.timeframe:
                assert int(feature_ts) == decision_ms


# --- decisions and executions (check 3) ---------------------------------------------------------


_CLOSE_DECISION = "close-decision"
_OPEN_TRIGGER = "open-trigger"
_EXECUTION_KINDS = frozenset({_CLOSE_DECISION, _OPEN_TRIGGER})


def check_decisions_precede_executions(run: RunArtifacts) -> dict[str, int]:
    """Every execution follows its decision, lands where it was planned, and is of a known kind.

    A decision made at a bar's close (a signal order, or the close before a data gap) plans its
    execution one millisecond after that close. A protective exit triggered at a bar's open plans
    it at that bar's close. Anything else is a path this material does not exercise and the check
    refuses to classify silently. Returns how many executions of each kind the run made.
    """
    bar_ms = timeframe_milliseconds(run.combination.timeframe)
    executions = _rows(
        run.result.evidence_path,
        """
        SELECT d.decision_ts, d.planned_execution_ts, e.execution_ts, d.action
        FROM EXECUTION AS e
        JOIN DECISION AS d ON d.decision_id = e.decision_id
        ORDER BY e.execution_id
        """,
    )
    assert executions, "no execution carries a decision"
    kinds = {_CLOSE_DECISION: 0, _OPEN_TRIGGER: 0}
    for decision_ts, planned, execution_ts, action in executions:
        assert int(decision_ts) < int(execution_ts), (
            f"{action} executed at {execution_ts}, decided at {decision_ts}"
        )
        assert int(execution_ts) == int(planned), f"{action} did not execute where it was planned"
        if int(planned) == int(decision_ts) + 1:
            kinds[_CLOSE_DECISION] += 1
        elif int(planned) == int(decision_ts) + bar_ms:
            kinds[_OPEN_TRIGGER] += 1
        else:
            raise AssertionError(
                f"{action} decided at {decision_ts} and planned at {planned} is neither a "
                "close-time decision nor an open-time trigger"
            )
    decisionless = _rows(
        run.result.evidence_path,
        "SELECT exit_reason FROM EXECUTION WHERE decision_id IS NULL",
    )
    assert all(reason == "END_OF_DATA" for (reason,) in decisionless)
    decision_closes = {epoch_milliseconds(item.decision_close) for item in run.observed}
    signals = _rows(
        run.result.evidence_path,
        "SELECT decision_ts, feature_ts, candle_close_time FROM SIGNAL",
    )
    for decision_ts, feature_ts, candle_close_time in signals:
        assert int(decision_ts) == int(feature_ts) == int(candle_close_time)
        assert int(decision_ts) in decision_closes
    return kinds


def check_an_entry_was_filled(run: RunArtifacts) -> None:
    """The time checks are not vacuous: the combination entered at least once."""
    (entries,) = _rows(
        run.result.evidence_path, "SELECT COUNT(*) FROM EXECUTION WHERE reduce_only = 0"
    )[0]
    assert int(entries) >= 1, f"{run.combination.label} never entered on the synthetic path"


# --- Turtle daily N (check 4) -------------------------------------------------------------------


def check_turtle_uses_the_last_closed_daily_bar(run: RunArtifacts) -> None:
    """Each entry sized under Turtle used the daily N of the last bar closed by the decision.

    The expectation is re-derived from the daily input alone: the prefix of the served daily
    series closed at or before ``decision_ts``, and ``turtle_n_series`` over that prefix.
    """
    period = int(run.config.money_management.model_dump()["n_period"])
    daily = _daily_path()
    signals = _rows(
        run.result.evidence_path,
        """
        SELECT decision_ts, metadata_json
        FROM SIGNAL
        WHERE derived_intent IN ('enter', 'reverse')
        ORDER BY signal_id
        """,
    )
    assert signals, "no entry was sized under Turtle"
    stamps: set[datetime] = set()
    for decision_ts, metadata_json in signals:
        money_management = json.loads(str(metadata_json))["money_management"]
        stamp = datetime.fromisoformat(str(money_management["volatility_timestamp"]))
        prefix = [
            candle for candle in daily if epoch_milliseconds(candle.close_time) <= int(decision_ts)
        ]
        assert prefix, "no daily bar had closed by the decision"
        assert stamp == prefix[-1].close_time, (
            f"Turtle used the daily bar closed at {stamp}, the last one closed by the "
            f"decision at {decision_ts} closes at {prefix[-1].close_time}"
        )
        series = turtle_n_series(prefix, period=period)
        assert series and series[-1][0] == prefix[-1].close_time
        assert float(money_management["volatility"]) == pytest.approx(series[-1][1])
        stamps.add(stamp)
    assert len(stamps) >= 2, "the daily N never advanced inside the evaluation window"


# --- refusal of undeclared combinations (check 5) ------------------------------------------------

_TIMEFRAME_CANDIDATES = ("1d", "4h", "1h", "15m")
_TIMEFRAME_REFUSAL = "strategy does not support the configured timeframe"
# The runtime's own wording; "unsupported money-management mode" belongs to the policy registry
# and to ``default_settings`` validation, not to this path.
_POLICY_REFUSAL = "does not support money-management mode"


def _undeclared_timeframe(strategy_id: str) -> str:
    declared = set(_DISCOVERED[strategy_id].get_metadata().supported_timeframes)
    return next(candidate for candidate in _TIMEFRAME_CANDIDATES if candidate not in declared)


def _undeclared_modes(strategy_id: str) -> list[str]:
    declared = set(_DISCOVERED[strategy_id].get_metadata().money_management.supported)
    return sorted(set(_POLICIES) - declared)


def check_refused_before_registration(
    root: Path, combination: Combination, *, message: str, evaluation_bars: int = 48
) -> None:
    """``Engine.run`` refuses the combination with ``message`` before any run is registered.

    A ``ValueError`` with any other wording is a refusal for another reason and fails too.
    """
    config = _run_config(
        combination, run_name="engine-layer-refusal", evaluation_bars=evaluation_bars
    )
    catalog = _Catalog()
    sink = BacktestEvidenceSink(root)
    costs = BacktestCostModel(config.cost_values)
    engine = Engine(
        _Feed(),
        BacktestBroker(costs),
        BacktestClock.from_candles(_path(combination.timeframe)),
        costs,
        sink,
        catalog,
        _manager(),
        prereg={
            "hypothesis": "an undeclared combination is refused",
            "primary_metric": "pf",
            "success_threshold": 1.3,
            "failure_threshold": 1.0,
            "edge_distinguishable": True,
            "higher_is_better": True,
        },
    )
    try:
        engine.run(config)
    except ValueError as error:
        assert message in str(error), f"refused for another reason: {error}"
    else:
        raise AssertionError(f"{combination.label} was not refused")
    assert catalog.registered == [], "a refused combination was registered"
    assert sink.path is None, "a refused combination bound an Evidence file"


# --- the tests ----------------------------------------------------------------------------------


def test_discovery_and_the_engine_case_table_name_the_same_strategies() -> None:
    """Adding a strategy file without a case row is itself a failure (design section 3)."""
    assert _DISCOVERY_FAULTS == ()
    assert set(_DISCOVERED) == set(_ENGINE_CASES), (
        f"case rows missing: {sorted(set(_DISCOVERED) - set(_ENGINE_CASES))}; "
        f"rows without a strategy: {sorted(set(_ENGINE_CASES) - set(_DISCOVERED))}"
    )
    for strategy_id, case in _ENGINE_CASES.items():
        assert case.strategy_id == strategy_id


@pytest.fixture(scope="module")
def engine_runs(tmp_path_factory: pytest.TempPathFactory) -> Mapping[Combination, RunArtifacts]:
    """Run every combination once; each check reads the run it needs."""
    root = tmp_path_factory.mktemp("engine-layer")
    return {
        combination: _run(combination, root / combination.label) for combination in _COMBINATIONS
    }


@pytest.mark.parametrize("combination", _COMBINATIONS, ids=_COMBINATION_IDS)
def test_the_combination_entered_at_least_once(
    engine_runs: Mapping[Combination, RunArtifacts], combination: Combination
) -> None:
    check_an_entry_was_filled(engine_runs[combination])


@pytest.mark.parametrize("combination", _COMBINATIONS, ids=_COMBINATION_IDS)
def test_the_strategy_received_only_finalized_inputs(
    engine_runs: Mapping[Combination, RunArtifacts], combination: Combination
) -> None:
    check_strategy_inputs(engine_runs[combination])


@pytest.mark.parametrize("combination", _COMBINATIONS, ids=_COMBINATION_IDS)
def test_series_values_were_finalized_before_each_decision(
    engine_runs: Mapping[Combination, RunArtifacts], combination: Combination
) -> None:
    check_series_timestamps(engine_runs[combination])


@pytest.mark.parametrize("combination", _COMBINATIONS, ids=_COMBINATION_IDS)
def test_every_decision_precedes_its_execution(
    engine_runs: Mapping[Combination, RunArtifacts], combination: Combination
) -> None:
    check_decisions_precede_executions(engine_runs[combination])


def test_both_execution_kinds_were_exercised_across_the_combinations(
    engine_runs: Mapping[Combination, RunArtifacts],
) -> None:
    """Close-time decisions and open-time protective exits both occurred on this material."""
    totals = {kind: 0 for kind in _EXECUTION_KINDS}
    for run in engine_runs.values():
        for kind, count in check_decisions_precede_executions(run).items():
            totals[kind] += count
    assert all(count > 0 for count in totals.values()), totals


@pytest.mark.parametrize(
    "combination", _TURTLE_COMBINATIONS, ids=[item.label for item in _TURTLE_COMBINATIONS]
)
def test_turtle_sized_from_the_last_daily_bar_closed_by_the_decision(
    engine_runs: Mapping[Combination, RunArtifacts], combination: Combination
) -> None:
    check_turtle_uses_the_last_closed_daily_bar(engine_runs[combination])


@pytest.mark.parametrize("combination", _COMBINATIONS, ids=_COMBINATION_IDS)
def test_the_run_passed_the_evidence_audit(
    engine_runs: Mapping[Combination, RunArtifacts], combination: Combination
) -> None:
    assert engine_runs[combination].result.integrity_status == "passed"


@pytest.mark.parametrize("strategy_id", sorted(_ENGINE_CASES))
def test_an_undeclared_timeframe_is_refused_before_registration(
    tmp_path: Path, strategy_id: str
) -> None:
    default = _DISCOVERED[strategy_id].get_metadata().money_management.default
    assert default is not None
    check_refused_before_registration(
        tmp_path,
        Combination(strategy_id, _undeclared_timeframe(strategy_id), default),
        message=_TIMEFRAME_REFUSAL,
    )


@pytest.mark.parametrize("strategy_id", sorted(_ENGINE_CASES))
def test_an_undeclared_policy_is_refused_before_registration(
    tmp_path: Path, strategy_id: str
) -> None:
    modes = _undeclared_modes(strategy_id)
    if not modes:
        pytest.skip(f"{strategy_id} declares every deployed policy mode: {sorted(_POLICIES)}")
    timeframe = _DISCOVERED[strategy_id].get_metadata().supported_timeframes[0]
    for mode in modes:
        check_refused_before_registration(
            tmp_path / mode, Combination(strategy_id, timeframe, mode), message=_POLICY_REFUSAL
        )


# --- fault injection into the composition (design 16.5) ----------------------------------------


def _fault_future_candle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let the strategy see the next bar in ``candles`` at every decision."""
    original = Engine.step_close

    def step_close(self: Engine, candle: Candle) -> None:
        following = self._next_candle(candle)
        if following is None:
            original(self, candle)
            return
        self._confirmed.append(following)
        try:
            original(self, candle)
        finally:
            self._confirmed.remove(following)

    monkeypatch.setattr(Engine, "step_close", step_close)


def _fault_future_series(monkeypatch: pytest.MonkeyPatch) -> None:
    """Compute and record every execution-timeframe series from the next bar."""
    original = Engine._update_indicators

    def update_indicators(self: Engine, candle: Candle) -> None:
        following = self._next_candle(candle)
        original(self, candle if following is None else following)

    monkeypatch.setattr(Engine, "_update_indicators", update_indicators)


def _fault_same_bar_fill(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fill every order at the instant the deciding bar closed."""
    original = BacktestBroker.submit

    def submit(self: BacktestBroker, request: OrderRequest) -> Fill:
        fill = original(self, request)
        return replace(fill, timestamp=fill.timestamp - timedelta(milliseconds=1))

    monkeypatch.setattr(BacktestBroker, "submit", submit)


def _fault_latest_daily_n(monkeypatch: pytest.MonkeyPatch) -> None:
    """Size every Turtle entry from the newest daily N, whether or not its bar has closed."""
    original = Engine._money_management_volatility

    def volatility(
        self: Engine, candle: Candle, policy: MoneyManagementBase
    ) -> tuple[float, str, datetime]:
        value, label, timestamp = original(self, candle, policy)
        if self._turtle_n_values:
            timestamp, value = self._turtle_n_values[-1]
        return value, label, timestamp

    monkeypatch.setattr(Engine, "_money_management_volatility", volatility)


@dataclass(frozen=True)
class Fault:
    """One defect injected into the composition and the check that must catch it."""

    name: str
    patch: Patch
    combination: Combination
    check: Callable[[RunArtifacts], None]
    evaluation_bars: int


_CHEAP = Combination("three-bar-reversion", "1h", "manual")
_TURTLE = Combination("vessel-reference", "1h", "turtle")
_FAULTS = (
    Fault("future-candle", _fault_future_candle, _CHEAP, check_strategy_inputs, 48),
    Fault("future-series", _fault_future_series, _CHEAP, check_series_timestamps, 48),
    Fault(
        "latest-daily-n",
        _fault_latest_daily_n,
        _TURTLE,
        check_turtle_uses_the_last_closed_daily_bar,
        _evaluation_bars("1h"),
    ),
)


@pytest.mark.parametrize("fault", _FAULTS, ids=[fault.name for fault in _FAULTS])
def test_each_fault_is_caught_by_its_check(tmp_path: Path, fault: Fault) -> None:
    run = _run(
        fault.combination, tmp_path, patch=fault.patch, evaluation_bars=fault.evaluation_bars
    )
    with pytest.raises(AssertionError):
        fault.check(run)


def test_a_same_bar_fill_stops_the_engine_before_evidence(tmp_path: Path) -> None:
    """The order guard is the Engine's own; this layer shows it holds for a discovered strategy."""
    with pytest.raises(ValueError, match="feature_ts <= decision_ts < execution_ts"):
        _run(_CHEAP, tmp_path, patch=_fault_same_bar_fill, evaluation_bars=48)


def test_a_widened_timeframe_declaration_defeats_the_refusal_check(tmp_path: Path) -> None:
    """Without the Engine's timeframe refusal, check 5 fails because the run was not refused.

    The combination is one the daily feed can warm up (three bars of history, ATR 14 under manual,
    a ten-bar window), so the run goes through to the end and the check fails for that reason and
    not because something later refused it.
    """
    strategy_id = _CHEAP.strategy_id
    cls = _DISCOVERED[strategy_id]
    timeframe = _undeclared_timeframe(strategy_id)
    assert timeframe == "1d"
    original = cls.get_metadata

    def widened() -> Any:
        metadata = original()
        metadata.supported_timeframes = [*metadata.supported_timeframes, timeframe]
        return metadata

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(cls, "get_metadata", staticmethod(widened))
        with pytest.raises(AssertionError, match="was not refused"):
            check_refused_before_registration(
                tmp_path,
                Combination(strategy_id, timeframe, "manual"),
                message=_TIMEFRAME_REFUSAL,
                evaluation_bars=10,
            )
