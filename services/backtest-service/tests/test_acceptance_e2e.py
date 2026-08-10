"""Acceptance-level audits of the operator-assembled backtest system."""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import ClassVar, Literal, cast

import psycopg
import pytest
from backtest_service.adapters.data_feed import BacktestDataFeed, ReadConnection
from backtest_service.config import RunConfig
from backtest_service.engine import RunResult
from backtest_service.runner import FeedDecorator, build_harness, run_backtest
from core_lib.ports import StrategyRegistry
from core_lib.strategy import (
    AdapterManager,
    FieldSpec,
    InProcessStrategyRegistry,
    ParameterSchema,
    ResolvedConfig,
    StrategyMetadata,
    StrategyProfile,
)
from core_lib.types import Candle, MarketType, Position, PositionSide, TradingSignal
from trading_plugins import registered_money_management
from trading_plugins.strategies.vessel_reference import STRATEGY_ID as VESSEL_STRATEGY_ID

pytestmark = pytest.mark.acceptance

_SYMBOL = "BTC/USDT:USDT"
_EXCHANGE = "binance"
_ZERO = Decimal("0")
_INTEGRITY_NAMES = {
    "accounting_identity",
    "timestamp_order",
    "cost_once",
    "net_of_cost",
    "deterministic",
    "evidence_complete",
}


class _Environment(dict[str, str]):
    """Keep connection values usable without rendering them in pytest failures."""

    def __repr__(self) -> str:
        return "<redacted PostgreSQL environment>"


def _env() -> _Environment:
    path = Path(__file__).parents[3] / ".env"
    if not path.exists():
        pytest.skip("repository .env is unavailable")
    values = _Environment()
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    required = {"PGHOST", "PGPORT", "PGUSER", "PGPASSWORD"}
    if not required <= values.keys():
        pytest.skip("repository .env lacks PostgreSQL connection keys")
    return values


def _connect(
    env: Mapping[str, str],
    database: str,
) -> psycopg.Connection[tuple[object, ...]]:
    return psycopg.connect(
        host=env["PGHOST"],
        port=int(env["PGPORT"]),
        user=env["PGUSER"],
        password=env["PGPASSWORD"],
        dbname=database,
        options="-c default_transaction_read_only=on",
    )


def _prereg(
    hypothesis: str,
    *,
    success: float = 1.3,
    failure: float = 1.0,
    edge_distinguishable: bool = True,
) -> dict[str, object]:
    return {
        "hypothesis": hypothesis,
        "primary_metric": "pf",
        "success_threshold": success,
        "failure_threshold": failure,
        "edge_distinguishable": edge_distinguishable,
        "higher_is_better": True,
        "declared_by": "pytest-acceptance",
    }


def _vessel_config(
    run_name: str,
    start: datetime,
    end: datetime,
    *,
    seed: int,
    indicator_mode: Literal["auto", "explicit", "all"] = "auto",
    explicit_indicators: list[dict[str, object]] | None = None,
) -> RunConfig:
    return RunConfig(
        run_name=run_name,
        strategy_id=VESSEL_STRATEGY_ID,
        params={},
        symbol=_SYMBOL,
        exchange=_EXCHANGE,
        timeframe="1h",
        market_type="futures",
        data_source="crypto_data.ohlcv_futures",
        start=start,
        end=end,
        initial_capital=Decimal("10000"),
        risk_per_trade=0.01,
        seed=seed,
        cost_values={
            "futures_taker_fee_rate": Decimal("0.0004"),
            "futures_entry_slippage_rate": Decimal("0.0005"),
            "exit_slippage_rate": Decimal("0.0001"),
            "funding_fallback_rate": Decimal("0.0001"),
        },
        indicator_mode=indicator_mode,
        explicit_indicators=[] if explicit_indicators is None else explicit_indicators,
        profile_ref="vessel-reference-v1",
    )


def _catalog_row(
    env: Mapping[str, str],
    run_id: str,
) -> dict[str, object]:
    with _connect(env, "backtest_db") as connection:
        cursor = connection.execute(
            """
            SELECT r.run_seq, r.run_id, r.status, r.evidence_path,
                   r.config_hash, r.evidence_hash, r.resolved_indicators_json,
                   r.fold_label, s.*
            FROM public.backtest_run AS r
            JOIN public.backtest_summary AS s USING (run_id)
            WHERE r.run_id = %s
            """,
            (run_id,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert cursor.description is not None
        return {
            description.name: value
            for description, value in zip(cursor.description, row, strict=True)
        }


def _integrity(path: str) -> dict[str, int]:
    with sqlite3.connect(path) as evidence:
        return dict(
            evidence.execute(
                "SELECT check_name, passed FROM INTEGRITY_CHECK ORDER BY check_name"
            ).fetchall()
        )


def _assert_six_integrity_checks(result: RunResult) -> None:
    checks = _integrity(result.evidence_path)
    assert checks == {name: 1 for name in _INTEGRITY_NAMES}
    assert result.integrity_status == "passed"


@pytest.fixture(scope="module")
def env() -> _Environment:
    return _env()


@pytest.fixture(scope="module")
def evidence_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("acceptance-evidence")


@pytest.fixture(scope="module")
def healthy_pair(
    env: dict[str, str],
    evidence_root: Path,
) -> tuple[RunResult, RunResult]:
    config = _vessel_config(
        "acc-healthy",
        datetime(2025, 8, 10, tzinfo=UTC),
        datetime(2025, 8, 13, tzinfo=UTC),
        seed=1201,
    )
    prereg = _prereg("registered Vessel completes the operator path")
    return (
        run_backtest(
            config,
            prereg,
            evidence_root=evidence_root / "healthy-first",
            env=env,
        ),
        run_backtest(
            config,
            prereg,
            evidence_root=evidence_root / "healthy-second",
            env=env,
        ),
    )


class _FixtureCatalog(StrategyRegistry):
    def __init__(self, strategy_id: str, strategy_class: type[object]) -> None:
        self._strategy_id = strategy_id
        self._strategy_class = strategy_class

    def get(self, strategy_id: str) -> dict[str, object]:
        if strategy_id != self._strategy_id:
            raise KeyError(strategy_id)
        return {
            "strategy_id": strategy_id,
            "class_name": self._strategy_class.__name__,
            "module_path": self._strategy_class.__module__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get(self._strategy_id)]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError("acceptance scenario catalogs are read-only")


def _fixture_manager(
    strategy_id: str,
    strategy_class: type[object],
) -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    plugins.register(strategy_id, strategy_class)  # type: ignore[arg-type]
    return AdapterManager(
        _FixtureCatalog(strategy_id, strategy_class),
        plugins,
        money_management_policies=registered_money_management(),
    )


_ROUTE_PROBE_ID = "acceptance-route-probe"
_ROUTE_DIRECTIONS: dict[datetime, str] = {}


class _RouteProbe:
    """Emit predeclared real-price round trips to exercise the genuine gate."""

    VERSION: ClassVar[str] = "1.0.0"

    def __init__(self, config: ResolvedConfig) -> None:
        if config.strategy_id != _ROUTE_PROBE_ID:
            raise ValueError("route probe received a mismatched strategy id")
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            required_indicators=[{"name": "EMA", "params": {"period": 9}}],
            min_history=9,
            supported_timeframes=["1h"],
            profile=StrategyProfile(
                id="acceptance-route-v1",
                family="verification",
                bar="1h",
                expected_win_rate=(0.0, 1.0),
                expected_payoff=(0.0, 1_000_000.0),
                tail_shape="right_fat",
                holding_horizon="intraday",
                primary_metric="pf",
                risk_adjusted_pref="sortino",
                profit_structure_to_preserve="acceptance-routing",
                envelope_tolerance=1.0,
                envelope_status="provisional",
            ),
        )

    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        return ParameterSchema(fields={})

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> TradingSignal | None:
        candle = market_data.get("candle")
        if not isinstance(candle, Candle):
            raise TypeError("market_data.candle must be Candle")
        if current_position is not None:
            return TradingSignal(
                symbol=candle.symbol,
                timestamp=candle.close_time,
                confidence=1.0,
                price=candle.close,
                stop_loss=None,
                take_profit=None,
                market_type=MarketType.FUTURES,
                leverage=1,
                reason="acceptance-route-exit",
                metadata={"adaptee": _ROUTE_PROBE_ID},
            )
        direction = _ROUTE_DIRECTIONS.get(candle.open_time)
        if direction is None:
            return None
        is_long = direction == "LONG"
        return TradingSignal(
            symbol=candle.symbol,
            timestamp=candle.close_time,
            confidence=1.0,
            price=candle.close,
            stop_loss=candle.close * (0.5 if is_long else 1.5),
            take_profit=candle.close * (10.0 if is_long else 0.1),
            market_type=MarketType.FUTURES,
            leverage=1,
            reason="acceptance-route-entry",
            metadata={"adaptee": _ROUTE_PROBE_ID},
        )


def _route_manager(_: ReadConnection) -> AdapterManager:
    return _fixture_manager(_ROUTE_PROBE_ID, _RouteProbe)


def _prepare_route_directions(
    env: Mapping[str, str],
    start: datetime,
    end: datetime,
) -> None:
    with _connect(env, "crypto_data") as connection:
        feed = BacktestDataFeed(
            cast(ReadConnection, connection),
            exchange=_EXCHANGE,
        )
        history = feed.candles(_SYMBOL, "1h", end)
    evaluation = [
        candle for candle in history if candle.open_time >= start and candle.close_time <= end
    ]
    _ROUTE_DIRECTIONS.clear()
    for index in range(len(evaluation) - 2):
        decision = evaluation[index]
        entry = evaluation[index + 1]
        exit_candle = evaluation[index + 2]
        if decision.close_time != entry.open_time or entry.close_time != exit_candle.open_time:
            continue
        if entry.open_time.hour in {0, 8, 16} or exit_candle.open_time.hour in {0, 8, 16}:
            continue
        _ROUTE_DIRECTIONS[decision.open_time] = "LONG" if exit_candle.open > entry.open else "SHORT"
    if len(_ROUTE_DIRECTIONS) < 60:
        raise AssertionError("route scenario needs at least sixty immutable decisions")


@dataclass(frozen=True, slots=True)
class _RouteRuns:
    results: Mapping[str, RunResult]


@pytest.fixture(scope="module")
def route_runs(
    env: dict[str, str],
    evidence_root: Path,
) -> _RouteRuns:
    start = datetime(2026, 2, 10, tzinfo=UTC)
    end = datetime(2026, 2, 20, tzinfo=UTC)
    _prepare_route_directions(env, start, end)
    cases = {
        "promote": (-1.0, -2.0, True),
        "abandon": (1.0, 0.0, False),
        "retest": (1.0, 0.0, True),
        "partial_keep": (1.0, -1.0, True),
    }
    results: dict[str, RunResult] = {}
    for offset, (route, (success, failure, edge)) in enumerate(cases.items()):
        config = RunConfig(
            run_name=f"acc-route-{route.replace('_', '-')}",
            strategy_id=_ROUTE_PROBE_ID,
            params={},
            symbol=_SYMBOL,
            exchange=_EXCHANGE,
            timeframe="1h",
            market_type="futures",
            data_source="crypto_data.ohlcv_futures",
            start=start,
            end=end,
            initial_capital=Decimal("10000"),
            risk_per_trade=0.01,
            seed=1301 + offset,
            cost_values={
                "futures_taker_fee_rate": _ZERO,
                "futures_entry_slippage_rate": _ZERO,
                "exit_slippage_rate": _ZERO,
                "funding_fallback_rate": _ZERO,
            },
            profile_ref="acceptance-route-v1",
        )
        results[route] = run_backtest(
            config,
            _prereg(
                f"genuine gate routes to {route}",
                success=success,
                failure=failure,
                edge_distinguishable=edge,
            ),
            evidence_root=evidence_root / f"route-{route}",
            env=env,
            manager_factory=_route_manager,
        )
    return _RouteRuns(results)


_FUNDING_PROBE_ID = "acceptance-funding-probe"
_FUNDING_ENTRY = datetime(2025, 6, 22, 14, tzinfo=UTC)


class _FundingProbe:
    """Hold one real-data long until measured funding consumes its margin."""

    VERSION: ClassVar[str] = "1.0.0"

    def __init__(self, config: ResolvedConfig) -> None:
        if config.strategy_id != _FUNDING_PROBE_ID:
            raise ValueError("funding probe received a mismatched strategy id")
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            required_indicators=[{"name": "EMA", "params": {"period": 9}}],
            min_history=9,
            supported_timeframes=["1h"],
            profile=StrategyProfile(
                id="acceptance-funding-v1",
                family="verification",
                bar="1h",
                expected_win_rate=(0.0, 1.0),
                expected_payoff=(0.0, 100.0),
                tail_shape="symmetric",
                holding_horizon="multi_boundary",
                primary_metric="calmar",
                risk_adjusted_pref="sortino",
                profit_structure_to_preserve="funding-accounting",
                envelope_tolerance=1.0,
                envelope_status="provisional",
            ),
        )

    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        return ParameterSchema(
            fields={
                "leverage": FieldSpec(type="integer", default=39, range=(1, 100)),
            }
        )

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> TradingSignal | None:
        candle = market_data.get("candle")
        if not isinstance(candle, Candle):
            raise TypeError("market_data.candle must be Candle")
        if candle.open_time != _FUNDING_ENTRY or current_position is not None:
            return None
        return TradingSignal(
            symbol=candle.symbol,
            timestamp=candle.close_time,
            confidence=1.0,
            price=candle.close,
            stop_loss=candle.close * 0.01,
            take_profit=candle.close * 10.0,
            market_type=MarketType.FUTURES,
            leverage=39,
            reason="acceptance-measured-funding",
            metadata={"adaptee": _FUNDING_PROBE_ID},
        )


def _funding_manager(_: ReadConnection) -> AdapterManager:
    return _fixture_manager(_FUNDING_PROBE_ID, _FundingProbe)


@pytest.fixture(scope="module")
def funding_run(
    env: dict[str, str],
    evidence_root: Path,
) -> RunResult:
    config = RunConfig(
        run_name="acc-funding-exhaust",
        strategy_id=_FUNDING_PROBE_ID,
        params={"leverage": 39},
        symbol=_SYMBOL,
        exchange=_EXCHANGE,
        timeframe="1h",
        market_type="futures",
        data_source="crypto_data.ohlcv_futures",
        start=_FUNDING_ENTRY,
        end=datetime(2025, 11, 4, 10, tzinfo=UTC),
        initial_capital=Decimal("10000"),
        risk_per_trade=0.01,
        seed=1401,
        cost_values={
            "futures_taker_fee_rate": Decimal("0.0004"),
            "futures_entry_slippage_rate": Decimal("0.0005"),
            "exit_slippage_rate": Decimal("0.0001"),
            "funding_fallback_rate": _ZERO,
        },
        profile_ref="acceptance-funding-v1",
    )
    return run_backtest(
        config,
        _prereg("measured funding exhausts isolated margin", success=0.0, failure=-1.0),
        evidence_root=evidence_root / "funding-exhaustion",
        env=env,
        manager_factory=_funding_manager,
    )


_REVERSAL_PROBE_ID = "acceptance-reversal-probe"
_REVERSAL_START = datetime(2025, 8, 20, tzinfo=UTC)


class _ReversalProbe:
    """Emit a real-price long followed by an opposite-side signal."""

    VERSION: ClassVar[str] = "1.0.0"

    def __init__(self, config: ResolvedConfig) -> None:
        if config.strategy_id != _REVERSAL_PROBE_ID:
            raise ValueError("reversal probe received a mismatched strategy id")
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            required_indicators=[{"name": "EMA", "params": {"period": 9}}],
            min_history=9,
            supported_timeframes=["1h"],
            profile=StrategyProfile(
                id="acceptance-reversal-v1",
                family="verification",
                bar="1h",
                expected_win_rate=(0.0, 1.0),
                expected_payoff=(0.0, 100.0),
                tail_shape="symmetric",
                holding_horizon="intraday",
                primary_metric="pf",
                risk_adjusted_pref="sortino",
                profit_structure_to_preserve="reversal-accounting",
                envelope_tolerance=1.0,
                envelope_status="provisional",
            ),
        )

    @classmethod
    def get_parameter_schema(cls) -> ParameterSchema:
        return ParameterSchema(fields={})

    def analyze(
        self,
        market_data: dict[str, object],
        current_position: Position | None,
    ) -> TradingSignal | None:
        candle = market_data.get("candle")
        if not isinstance(candle, Candle):
            raise TypeError("market_data.candle must be Candle")
        if candle.open_time == _REVERSAL_START and current_position is None:
            stop_loss, take_profit, reason = (
                candle.close * 0.01,
                candle.close * 10.0,
                "acceptance-reversal-long",
            )
        elif (
            candle.open_time == _REVERSAL_START + timedelta(days=1)
            and current_position is not None
            and current_position.side is PositionSide.LONG
        ):
            stop_loss, take_profit, reason = (
                candle.close * 10.0,
                candle.close * 0.01,
                "acceptance-reversal-short",
            )
        else:
            return None
        return TradingSignal(
            symbol=candle.symbol,
            timestamp=candle.close_time,
            confidence=1.0,
            price=candle.close,
            stop_loss=stop_loss,
            take_profit=take_profit,
            market_type=MarketType.FUTURES,
            leverage=3,
            reason=reason,
            metadata={"adaptee": _REVERSAL_PROBE_ID},
        )


def _reversal_manager(_: ReadConnection) -> AdapterManager:
    return _fixture_manager(_REVERSAL_PROBE_ID, _ReversalProbe)


@pytest.fixture(scope="module")
def reversal_run(
    env: dict[str, str],
    evidence_root: Path,
) -> RunResult:
    config = RunConfig(
        run_name="acc-reversal",
        strategy_id=_REVERSAL_PROBE_ID,
        params={},
        symbol=_SYMBOL,
        exchange=_EXCHANGE,
        timeframe="1h",
        market_type="futures",
        data_source="crypto_data.ohlcv_futures",
        start=_REVERSAL_START,
        end=_REVERSAL_START + timedelta(days=3),
        initial_capital=Decimal("10000"),
        risk_per_trade=0.01,
        seed=1501,
        cost_values={
            "futures_taker_fee_rate": Decimal("0.0004"),
            "futures_entry_slippage_rate": Decimal("0.0005"),
            "exit_slippage_rate": Decimal("0.0001"),
            "funding_fallback_rate": _ZERO,
        },
        profile_ref="acceptance-reversal-v1",
    )
    return run_backtest(
        config,
        _prereg("opposite signal closes before its replacement", success=0.0, failure=-1.0),
        evidence_root=evidence_root / "reversal",
        env=env,
        manager_factory=_reversal_manager,
    )


@pytest.fixture(scope="module")
def coverage_failure_run(
    env: dict[str, str],
    evidence_root: Path,
    declared_gap_decorator: Callable[[frozenset[datetime]], FeedDecorator],
    coverage_failure_withheld: frozenset[datetime],
) -> RunResult:
    config = _vessel_config(
        "acc-coverage-fail",
        datetime(2026, 4, 25, tzinfo=UTC),
        datetime(2026, 5, 25, tzinfo=UTC),
        seed=1601,
    )
    return run_backtest(
        config,
        _prereg("large immutable source gap blocks promotion"),
        evidence_root=evidence_root / "coverage-failure",
        env=env,
        feed_decorator=declared_gap_decorator(coverage_failure_withheld),
    )


@pytest.fixture(scope="module")
def normal_gap_run(
    env: dict[str, str],
    evidence_root: Path,
    declared_gap_decorator: Callable[[frozenset[datetime]], FeedDecorator],
    normal_gap_withheld: frozenset[datetime],
) -> RunResult:
    config = _vessel_config(
        "acc-normal-gaps",
        datetime(2025, 7, 1, tzinfo=UTC),
        datetime(2026, 4, 30, tzinfo=UTC),
        seed=1701,
    )
    return run_backtest(
        config,
        _prereg("bounded normal gaps preserve complete long-window Evidence"),
        evidence_root=evidence_root / "normal-gaps",
        env=env,
        feed_decorator=declared_gap_decorator(normal_gap_withheld),
    )


@dataclass(frozen=True, slots=True)
class _HarnessFacts:
    is_oos: Mapping[str, object]
    walk_forward: Mapping[str, object]
    monte_carlo_first: Mapping[str, object]
    monte_carlo_second: Mapping[str, object]
    robust_psr: float


@pytest.fixture(scope="module")
def harness_facts(
    env: dict[str, str],
    evidence_root: Path,
) -> _HarnessFacts:
    config = _vessel_config(
        "acc-walk-forward",
        datetime(2025, 11, 20, tzinfo=UTC),
        datetime(2025, 12, 2, tzinfo=UTC),
        seed=1801,
    )
    with build_harness(
        config,
        _prereg("chronological folds complete through fresh engines"),
        evidence_root=evidence_root / "harness",
        env=env,
        seed=29,
    ) as harness:
        is_oos = harness.is_oos(config, 0.5)
        walk = harness.walk_forward(config, 3)
        first = harness.monte_carlo([1.0, -0.5, 0.75, 1.5], 500)
        second = harness.monte_carlo([1.0, -0.5, 0.75, 1.5], 500)
        robust_psr = harness.psr([0.03, 0.02, 0.04, 0.01, 0.025, 0.035, 0.015])
    return _HarnessFacts(is_oos, walk, first, second, robust_psr)


def test_a1_healthy_operator_run_is_evaluated_and_complete(
    healthy_pair: tuple[RunResult, RunResult],
    env: dict[str, str],
) -> None:
    """§4.4.1/§5.3.3 A1: a registered strategy reaches EVALUATED with six checks."""
    result = healthy_pair[0]
    row = _catalog_row(env, result.run_id)
    assert row["status"] == "EVALUATED"
    assert row["integrity_status"] == "passed"
    assert row["decision_route"] == result.decision.route == "retest"
    _assert_six_integrity_checks(result)


def test_a2_determinism_and_two_layer_identity_match(
    healthy_pair: tuple[RunResult, RunResult],
    env: dict[str, str],
) -> None:
    """부록.5/§5.3.1 A2: identical input hashes and file/catalog identities agree."""
    first, second = healthy_pair
    first_row = _catalog_row(env, first.run_id)
    second_row = _catalog_row(env, second.run_id)
    assert first.evidence_hash == second.evidence_hash
    assert first_row["config_hash"] == second_row["config_hash"]
    assert first_row["evidence_hash"] == second_row["evidence_hash"] == first.evidence_hash
    assert len(cast(list[object], first_row["resolved_indicators_json"])) == 3
    for result, row in ((first, first_row), (second, second_row)):
        assert Path(result.evidence_path).name == f"{result.run_id}.sqlite"
        assert row["run_id"] == result.run_id
        assert row["evidence_path"] == f"{result.run_id}.sqlite"
        with sqlite3.connect(result.evidence_path) as evidence:
            local = evidence.execute(
                "SELECT run_id, config_hash FROM BACKTEST_RUN_LOCAL"
            ).fetchone()
            detail = json.loads(
                evidence.execute(
                    """
                    SELECT detail_json FROM INTEGRITY_CHECK
                    WHERE check_name = 'deterministic'
                    """
                ).fetchone()[0]
            )
        assert local == (result.run_id, row["config_hash"])
        assert detail["current_evidence_hash"] == result.evidence_hash
    with sqlite3.connect(second.evidence_path) as evidence:
        detail = json.loads(
            evidence.execute(
                """
                SELECT detail_json FROM INTEGRITY_CHECK
                WHERE check_name = 'deterministic'
                """
            ).fetchone()[0]
        )
    assert detail["status"] == "matched"


def test_a3_net_pnl_identities_hold_in_catalog_and_every_trade(
    healthy_pair: tuple[RunResult, RunResult],
    env: dict[str, str],
) -> None:
    """§4.3.5/§5.2.3 A3: net PnL and cash+position identities have no double cost."""
    result = healthy_pair[0]
    row = _catalog_row(env, result.run_id)
    gross = cast(Decimal, row["gross_pnl_total"])
    fee = cast(Decimal, row["total_fee"])
    slippage = cast(Decimal, row["total_slippage"])
    funding = cast(Decimal, row["total_funding"])
    penalty = cast(Decimal, row["total_liquidation_penalty"])
    assert row["net_pnl_total"] == (gross - fee - slippage - funding - penalty)
    assert fee >= 0
    assert slippage >= 0
    with sqlite3.connect(result.evidence_path) as evidence:
        assert evidence.execute(
            """
            SELECT COUNT(*) FROM TRADE
            WHERE net_pnl <> (
                gross_pnl - total_fee - slippage
                - funding_cost - liquidation_penalty
            )
            """
        ).fetchone() == (0,)
        assert evidence.execute(
            """
            SELECT COUNT(*) FROM PORTFOLIO_PNL
            WHERE total_equity <> cash_balance + position_value
            """
        ).fetchone() == (0,)
        evidence_mdd = evidence.execute("SELECT min(drawdown_pct) FROM PORTFOLIO_PNL").fetchone()[0]
    assert evidence_mdd <= 0
    assert cast(float, row["mdd"]) >= 0


@pytest.mark.parametrize("route", ["promote", "abandon", "retest", "partial_keep"])
def test_b1_b4_all_preregistered_decision_routes_cross_the_real_gate(
    route_runs: _RouteRuns,
    route: str,
    env: dict[str, str],
) -> None:
    """§4.3.5 B1–B4: genuine passing metrics route to all four prereg outcomes."""
    result = route_runs.results[route]
    row = _catalog_row(env, result.run_id)
    assert row["gate_verdict"] == "pass"
    assert row["gate_passed"] is True
    assert cast(int, row["trade_count"]) >= 30
    assert math.isinf(result.metrics.pf)
    assert math.isinf(result.metrics.sortino)
    assert row["pf"] is None
    assert row["sortino"] is None
    assert cast(float, row["calmar_or_mar"]) >= 0.8
    assert cast(float, row["sqn"]) >= 1.6
    assert cast(float, row["mdd"]) <= 0.30
    assert cast(float, row["ror"]) < 0.001
    assert row["decision_route"] == result.decision.route == route
    _assert_six_integrity_checks(result)


def test_b5_insufficient_sample_is_not_promotable(
    healthy_pair: tuple[RunResult, RunResult],
    env: dict[str, str],
) -> None:
    """§4.3.5 B5: a real short run below N=30 records Hard Gate A failure."""
    result = healthy_pair[0]
    row = _catalog_row(env, result.run_id)
    assert cast(int, row["trade_count"]) < 30
    assert row["gate_verdict"] == "not_promotable"
    assert any(
        str(item).startswith("trade_count:") for item in cast(list[object], row["gate_failed_json"])
    )
    assert row["decision_route"] == "retest"


def test_c1_excessive_missing_data_blocks_promotion_but_not_integrity(
    coverage_failure_run: RunResult,
    env: dict[str, str],
) -> None:
    """§5.2.3 C1: low coverage independently forces not_promotable/retest."""
    row = _catalog_row(env, coverage_failure_run.run_id)
    assert row["integrity_status"] == coverage_failure_run.integrity_status == "passed"
    assert cast(float, row["data_coverage_ratio"]) < 0.95
    assert row["data_coverage_passed"] is False
    assert cast(int, row["max_consecutive_gap_seconds"]) > 86_400
    assert row["gate_verdict"] == "not_promotable"
    assert row["decision_route"] == coverage_failure_run.decision.route == "retest"
    assert {"data_coverage_ratio", "max_consecutive_gap"} <= set(
        cast(list[str], row["gate_failed_json"])
    )
    _assert_six_integrity_checks(coverage_failure_run)


def test_c2_long_window_with_bounded_partial_gaps_remains_complete(
    normal_gap_run: RunResult,
    env: dict[str, str],
) -> None:
    """§4.4.1/§5.3.3 C2: the one long run retains verified bounded gap Evidence."""
    row = _catalog_row(env, normal_gap_run.run_id)
    assert row["expected_candle_count"] == 7_272
    assert row["observed_candle_count"] == 7_264
    assert row["source_absent_gap_count"] == 0
    assert row["partial_bucket_count"] == 8
    assert row["data_coverage_ratio"] == pytest.approx(7_264 / 7_272)
    assert row["max_consecutive_gap_seconds"] == 18_000
    assert row["data_coverage_passed"] is True
    assert cast(int, row["data_gap_exit_count"]) >= 1
    assert Path(normal_gap_run.evidence_path).stat().st_size <= 50 * 1024 * 1024
    _assert_six_integrity_checks(normal_gap_run)


def test_d1_measured_funding_exhaustion_liquidates_once(
    funding_run: RunResult,
) -> None:
    """§4.4.1/§5.3.3 D1: measured funding exhaustion converges to one liquidation."""
    with sqlite3.connect(funding_run.evidence_path) as evidence:
        final_settlement = evidence.execute(
            """
            SELECT payment_amount, theoretical_payment_amount
            FROM FUNDING_SETTLEMENT ORDER BY settled_at DESC LIMIT 1
            """
        ).fetchone()
        trade = evidence.execute(
            """
            SELECT liquidated, exit_reason, total_fee,
                   funding_cost, liquidation_penalty, net_pnl,
                   gross_pnl - total_fee - slippage
                       - funding_cost - liquidation_penalty
            FROM TRADE
            """
        ).fetchone()
        execution_fees = evidence.execute("SELECT sum(fee) FROM EXECUTION").fetchone()[0]
        assert final_settlement is not None
        assert trade is not None
        assert abs(final_settlement[0]) < abs(final_settlement[1])
        assert trade[:2] == (1, "LIQUIDATION")
        assert trade[2] == execution_fees
        assert trade[4] == 0
        assert trade[5] == trade[6]
        assert evidence.execute("SELECT min(cash_balance) >= 0 FROM PORTFOLIO_PNL").fetchone() == (
            1,
        )
    _assert_six_integrity_checks(funding_run)


def test_d2_reversal_closes_before_the_opposite_entry(
    reversal_run: RunResult,
) -> None:
    """§4.4.1 D2: reversal emits close then opposite entry at one execution instant."""
    with sqlite3.connect(reversal_run.evidence_path) as evidence:
        decision = evidence.execute(
            "SELECT decision_id FROM DECISION WHERE action = 'reverse'"
        ).fetchone()
        assert decision is not None
        fills = evidence.execute(
            """
            SELECT execution_id, execution_ts, position_side, reduce_only, exit_reason
            FROM EXECUTION WHERE decision_id = ? ORDER BY execution_id
            """,
            decision,
        ).fetchall()
        assert len(fills) == 2
        assert fills[0][1] == fills[1][1]
        assert fills[0][0] < fills[1][0]
        assert fills[0][2:] == ("LONG", 1, "REVERSAL")
        assert fills[1][2:] == ("SHORT", 0, None)
        assert evidence.execute(
            "SELECT COUNT(*) FROM TRADE WHERE exit_reason = 'REVERSAL'"
        ).fetchone() == (1,)
    _assert_six_integrity_checks(reversal_run)


def test_d3_explicit_indicators_reject_missing_requirements_and_accept_cover(
    env: dict[str, str],
    evidence_root: Path,
) -> None:
    """§4.4.3 D3: incomplete explicit indicators fail red, complete cover runs green."""
    start = datetime(2025, 9, 10, tzinfo=UTC)
    end = start + timedelta(days=3)
    incomplete = _vessel_config(
        "acc-explicit-red",
        start,
        end,
        seed=1901,
        indicator_mode="explicit",
        explicit_indicators=[{"name": "EMA", "params": {"period": 9}}],
    )
    with pytest.raises(
        ValueError,
        match="explicit_indicators missing strategy-required indicators",
    ):
        run_backtest(
            incomplete,
            _prereg("incomplete explicit requirements are refused"),
            evidence_root=evidence_root / "explicit-red",
            env=env,
        )
    with _connect(env, "backtest_db") as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM public.backtest_run WHERE run_name = %s",
            ("acc-explicit-red",),
        ).fetchone() == (0,)

    complete = _vessel_config(
        "acc-explicit-green",
        start,
        end,
        seed=1902,
        indicator_mode="explicit",
        explicit_indicators=[
            {"name": "EMA", "params": {"period": 9}},
            {"name": "EMA", "params": {"period": 21}},
            {"name": "ATR", "params": {"period": 14}},
        ],
    )
    result = run_backtest(
        complete,
        _prereg("complete explicit requirements traverse the system"),
        evidence_root=evidence_root / "explicit-green",
        env=env,
    )
    with sqlite3.connect(result.evidence_path) as evidence:
        assert evidence.execute("SELECT COUNT(*) FROM INDICATOR_DEFINITION").fetchone() == (3,)
    _assert_six_integrity_checks(result)


def test_e1_walk_forward_runs_three_real_folds_and_catalogs_representative(
    harness_facts: _HarnessFacts,
    env: dict[str, str],
    evidence_root: Path,
) -> None:
    """§4.4.4 E1: three folds persist and only the representative carries WF evidence."""
    walk = harness_facts.walk_forward
    folds = cast(list[dict[str, object]], walk["folds"])
    assert len(folds) == 3
    assert len({cast(str, fold["run_id"]) for fold in folds}) == 3
    assert len(cast(list[float], walk["degradations"])) == 2
    representative = cast(str, walk["representative_run_id"])
    assert representative == folds[-1]["run_id"]
    for index, fold in enumerate(folds, start=1):
        row = _catalog_row(env, cast(str, fold["run_id"]))
        assert row["status"] == "EVALUATED"
        assert row["fold_label"] == f"wf-{index}"
        assert (evidence_root / "harness" / cast(str, row["evidence_path"])).is_file()
        if fold["run_id"] == representative:
            assert row["oos_degradation"] == pytest.approx(walk["maximum_degradation"])
            assert row["psr"] is None
            harness_json = cast(Mapping[str, object], row["harness_json"])
            assert harness_json["workflow"] == "walk_forward"
            assert len(cast(list[object], harness_json["folds"])) == 3
            assert len(cast(list[object], harness_json["degradations"])) == 2
        else:
            assert row["oos_degradation"] is None
            assert row["psr"] is None
            assert row["harness_json"] is None


def test_e2_overfit_gate_rejects_boundary_and_accepts_robust_values(
    harness_facts: _HarnessFacts,
    env: dict[str, str],
    evidence_root: Path,
) -> None:
    """§4.4.4 E2: OOS/PSR gate works and the OOS run carries split evidence."""
    config = _vessel_config(
        "acc-overfit-gate",
        datetime(2025, 12, 3, tzinfo=UTC),
        datetime(2025, 12, 6, tzinfo=UTC),
        seed=2001,
    )
    with build_harness(
        config,
        _prereg("overfit boundary audit"),
        evidence_root=evidence_root / "overfit-gate",
        env=env,
    ) as harness:
        rejected = harness.overfit_gate(degradation=0.50, psr=0.949)
        accepted = harness.overfit_gate(
            degradation=0.49,
            psr=harness_facts.robust_psr,
        )
        observed = harness.overfit_gate(
            degradation=cast(float, harness_facts.is_oos["oos_degradation"]),
            psr=harness_facts.robust_psr,
        )
    assert rejected["passed"] is False
    assert rejected["failed"] == ["oos_degradation", "psr"]
    assert harness_facts.robust_psr >= 0.95
    assert accepted["passed"] is True
    assert harness_facts.is_oos["passed"] == (
        cast(float, harness_facts.is_oos["oos_degradation"]) < 0.50
    )
    assert observed["passed"] == (cast(float, harness_facts.is_oos["oos_degradation"]) < 0.50)
    for key in ("in_sample_run_id", "out_of_sample_run_id"):
        run_id = cast(str, harness_facts.is_oos[key])
        row = _catalog_row(env, run_id)
        assert row["status"] == "EVALUATED"
        assert (evidence_root / "harness" / cast(str, row["evidence_path"])).is_file()
        if key == "out_of_sample_run_id":
            assert row["oos_degradation"] == pytest.approx(harness_facts.is_oos["oos_degradation"])
            assert row["psr"] is None
            harness_json = cast(Mapping[str, object], row["harness_json"])
            assert harness_json["workflow"] == "is_oos"
        else:
            assert row["oos_degradation"] is None
            assert row["psr"] is None
            assert row["harness_json"] is None


def test_e3_monte_carlo_is_fixed_seed_deterministic(
    harness_facts: _HarnessFacts,
) -> None:
    """§4.4.4 E3: Monte Carlo evidence is fixed-seed deterministic."""
    first = harness_facts.monte_carlo_first
    second = harness_facts.monte_carlo_second
    assert first == second
    assert first["seed"] == 29
    assert first["iterations"] == 500
    assert math.isfinite(cast(float, first["terminal_r_p05"]))
    assert math.isfinite(cast(float, first["terminal_r_p95"]))
    assert 0.0 <= cast(float, first["ruin_probability"]) <= 1.0


def test_e4_overfit_defense_bundle_persists_all_three_aggregates(
    env: dict[str, str],
    evidence_root: Path,
) -> None:
    """§4.4.4 E4: the last fold alone carries the complete overfit-defense bundle."""
    start = datetime(2026, 2, 10, tzinfo=UTC)
    end = datetime(2026, 2, 20, tzinfo=UTC)
    _prepare_route_directions(env, start, end)
    config = RunConfig(
        run_name="acc-overfit-defense",
        strategy_id=_ROUTE_PROBE_ID,
        params={},
        symbol=_SYMBOL,
        exchange=_EXCHANGE,
        timeframe="1h",
        market_type="futures",
        data_source="crypto_data.ohlcv_futures",
        start=start,
        end=end,
        initial_capital=Decimal("10000"),
        risk_per_trade=0.01,
        seed=2002,
        cost_values={
            "futures_taker_fee_rate": _ZERO,
            "futures_entry_slippage_rate": _ZERO,
            "exit_slippage_rate": _ZERO,
            "funding_fallback_rate": _ZERO,
        },
        profile_ref="acceptance-route-v1",
    )
    with build_harness(
        config,
        _prereg("complete overfit-defense bundle is cataloged once"),
        evidence_root=evidence_root / "overfit-defense",
        env=env,
        seed=29,
        manager_factory=_route_manager,
    ) as harness:
        bundle = harness.evaluate_overfit_defense(config, folds=3)

    walk_forward = cast(Mapping[str, object], bundle["walk_forward"])
    folds = cast(list[dict[str, object]], walk_forward["folds"])
    representative = cast(str, bundle["representative_run_id"])
    assert representative == folds[-1]["run_id"]
    for fold in folds:
        row = _catalog_row(env, cast(str, fold["run_id"]))
        if fold["run_id"] == representative:
            assert row["oos_degradation"] is not None
            assert row["psr"] is not None
            assert 0.0 <= cast(float, row["psr"]) <= 1.0
            harness_json = cast(Mapping[str, object], row["harness_json"])
            assert harness_json["workflow"] == "overfit_defense"
            assert cast(Mapping[str, object], harness_json["walk_forward"])["folds"]
            monte_carlo = cast(Mapping[str, object], harness_json["monte_carlo"])
            for key in ("ruin_probability", "terminal_r_p05", "terminal_r_p95"):
                assert key in monte_carlo
            assert harness_json["psr"] == pytest.approx(row["psr"])
        else:
            assert row["oos_degradation"] is None
            assert row["psr"] is None
            assert row["harness_json"] is None
