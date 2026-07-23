"""Verify the deterministic Engine loop, timing Evidence, hash parity, and Harness."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import ClassVar, cast

import pytest
from backtest_service.adapters.broker import BacktestBroker
from backtest_service.adapters.clock import BacktestClock
from backtest_service.adapters.cost_model import BacktestCostModel
from backtest_service.adapters.evidence_sink import BacktestEvidenceSink
from backtest_service.config import RunConfig
from backtest_service.engine import Engine, RunResult
from backtest_service.harness import Harness
from core_lib.eval import MetricSet
from core_lib.ports import CatalogStore, DataFeed, StrategyRegistry
from core_lib.strategy import (
    AdapterManager,
    InProcessStrategyRegistry,
    ParameterSchema,
    ResolvedConfig,
    StrategyMetadata,
    StrategyProfile,
)
from core_lib.types import (
    Candle,
    Fill,
    MarketType,
    OrderRequest,
    Position,
    TradingSignal,
)

_BASE = datetime(2026, 1, 1, 1, tzinfo=UTC)


def _candles() -> list[Candle]:
    prices = (
        (100.0, 102.0, 99.0, 100.0),
        (101.0, 104.0, 95.0, 103.0),
        (104.0, 106.0, 96.0, 105.0),
        (106.0, 108.0, 97.0, 107.0),
    )
    return [
        Candle(
            symbol="BTCUSDT",
            exchange="binance",
            timeframe="1h",
            open_time=_BASE + timedelta(hours=index),
            close_time=_BASE + timedelta(hours=index + 1),
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=100.0,
            quote_volume=10_000.0,
            trade_count=10,
        )
        for index, (open_price, high, low, close) in enumerate(prices)
    ]


class _Feed(DataFeed):
    def __init__(self, candles: list[Candle]) -> None:
        self._candles = list(candles)

    def candles(self, symbol: str, tf: str, up_to: datetime) -> list[Candle]:
        assert symbol == "BTCUSDT"
        assert tf == "1h"
        return [candle for candle in self._candles if candle.close_time <= up_to]

    def funding(self, symbol: str, at: datetime) -> Decimal:
        del symbol, at
        raise LookupError("no boundary funding in this fixture")

    def mark_price(self, symbol: str, at: datetime) -> Decimal:
        del symbol, at
        return Decimal("100")


class _Strategy:
    VERSION: ClassVar[str] = "1.0.0"

    def __init__(self, config: ResolvedConfig) -> None:
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            required_indicators=[],
            min_history=1,
            supported_timeframes=["1h"],
            profile=StrategyProfile(
                id="engine-profile",
                family="breakout",
                bar="1h",
                expected_win_rate=(0.0, 1.0),
                expected_payoff=(0.0, 100.0),
                tail_shape="right_fat",
                holding_horizon="intraday",
                primary_metric="calmar",
                risk_adjusted_pref="sortino",
                profit_structure_to_preserve="net-profit",
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
        candle = market_data["candle"]
        candles = market_data["candles"]
        assert isinstance(candle, Candle)
        assert isinstance(candles, list)
        if len(candles) == 1 and current_position is None:
            return TradingSignal(
                symbol=candle.symbol,
                timestamp=candle.close_time,
                confidence=0.8,
                price=candle.close,
                stop_loss=90.0,
                take_profit=120.0,
                market_type=MarketType.FUTURES,
                leverage=1,
                reason="fixture-entry",
                metadata={"fixture": True},
            )
        if len(candles) == 3 and current_position is not None:
            return TradingSignal(
                symbol=candle.symbol,
                timestamp=candle.close_time,
                confidence=0.8,
                price=candle.close,
                stop_loss=None,
                take_profit=None,
                market_type=MarketType.FUTURES,
                leverage=1,
                reason="fixture-exit",
                metadata={"fixture": True},
            )
        return None


class _StrategyCatalog(StrategyRegistry):
    def get(self, strategy_id: str) -> dict[str, object]:
        assert strategy_id == "engine-fixture"
        return {
            "strategy_id": strategy_id,
            "class_name": _Strategy.__name__,
            "module_path": _Strategy.__module__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get("engine-fixture")]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError("read-only fixture")


def _manager() -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    plugins.register("engine-fixture", _Strategy)
    return AdapterManager(_StrategyCatalog(), plugins)


class _Catalog(CatalogStore):
    def __init__(self) -> None:
        self.next_sequence = 1
        self.events: list[str] = []
        self.preregs: list[object] = []
        self.summaries: list[object] = []

    def register(self, run: object) -> str:
        assert isinstance(run, Mapping)
        self.events.append("register")
        sequence = self.next_sequence
        self.next_sequence += 1
        return f"BT_20260101_{sequence:06d}_{run['run_name']}"

    def save_prereg(self, prereg: object) -> None:
        self.events.append("prereg")
        self.preregs.append(prereg)

    def upsert_summary(self, summary: object) -> None:
        self.events.append("summary")
        self.summaries.append(summary)

    def reconcile_orphaned(self) -> int:
        self.events.append("reconcile")
        return 0


class _Broker(BacktestBroker):
    def __init__(self, cost_model: BacktestCostModel) -> None:
        super().__init__(cost_model)
        self.call_order: list[str] = []
        self.fills: list[Fill] = []

    def configure_execution(
        self,
        decision_candle: Candle,
        history: list[Candle],
        *,
        fill_timing: str = "next_bar",
        risk_budget: Decimal | None = None,
        available_margin: Decimal | None = None,
        leverage: int = 1,
    ) -> None:
        self.call_order.append("configure")
        super().configure_execution(
            decision_candle,
            history,
            fill_timing=fill_timing,
            risk_budget=risk_budget,
            available_margin=available_margin,
            leverage=leverage,
        )

    def submit(self, request: OrderRequest) -> Fill:
        self.call_order.append("submit")
        fill = super().submit(request)
        self.fills.append(fill)
        return fill


def _config(*, run_name: str = "engine") -> RunConfig:
    return RunConfig(
        run_name=run_name,
        strategy_id="engine-fixture",
        params={},
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="1h",
        market_type="futures",
        data_source="fixture",
        start=_BASE,
        end=_BASE + timedelta(hours=4),
        initial_capital=Decimal("10000"),
        risk_per_trade=0.01,
        cost_values={
            "futures_taker_fee_rate": Decimal("0"),
            "futures_entry_slippage_rate": Decimal("0"),
            "exit_slippage_rate": Decimal("0"),
            "funding_fallback_rate": Decimal("0"),
        },
        profile_ref="engine-profile",
    )


def _prereg() -> dict[str, object]:
    return {
        "hypothesis": "fixture should trade deterministically",
        "primary_metric": "pf",
        "success_threshold": 1.3,
        "failure_threshold": 1.0,
        "edge_distinguishable": True,
        "higher_is_better": True,
    }


def _engine(
    root: Path,
    catalog: _Catalog,
    brokers: list[_Broker],
) -> Engine:
    candles = _candles()
    schedule = [candles[0].open_time, *(candle.close_time for candle in candles)]
    costs = BacktestCostModel(_config().cost_values)
    broker = _Broker(costs)
    brokers.append(broker)
    return Engine(
        _Feed(candles),
        broker,
        BacktestClock(schedule),
        costs,
        BacktestEvidenceSink(root),
        catalog,
        _manager(),
        prereg=_prereg(),
    )


def test_engine_orders_configure_before_submit_and_persists_timing(
    tmp_path: Path,
) -> None:
    catalog = _Catalog()
    brokers: list[_Broker] = []
    result = _engine(tmp_path, catalog, brokers).run(_config())

    broker = brokers[0]
    assert broker.call_order == ["configure", "submit", "configure", "submit"]
    assert [fill.timestamp for fill in broker.fills] == [
        _BASE + timedelta(hours=1, milliseconds=1),
        _BASE + timedelta(hours=3, milliseconds=1),
    ]
    with sqlite3.connect(result.evidence_path) as connection:
        order_rows = connection.execute(
            """
            SELECT s.feature_ts, d.decision_ts, e.execution_ts
            FROM SIGNAL AS s
            JOIN DECISION AS d ON d.signal_id = s.signal_id
            JOIN EXECUTION AS e ON e.decision_id = d.decision_id
            ORDER BY e.execution_id
            """
        ).fetchall()
        assert order_rows
        assert all(feature <= decision < execution for feature, decision, execution in order_rows)
        checks = dict(
            connection.execute(
                "SELECT check_name, passed FROM INTEGRITY_CHECK"
            ).fetchall()
        )
        assert checks == {
            "accounting_identity": 1,
            "timestamp_order": 1,
            "cost_once": 1,
            "net_of_cost": 1,
            "deterministic": 1,
            "evidence_complete": 1,
        }
        assert connection.execute(
            "SELECT COUNT(*) FROM DRAWDOWN_RUNUP_EPISODE"
        ).fetchone()[0] >= 1
    assert result.integrity_status == "passed"
    assert catalog.events == ["register", "prereg", "summary"]


def test_engine_hash_parity_uses_different_catalog_run_ids(tmp_path: Path) -> None:
    catalog = _Catalog()
    brokers: list[_Broker] = []

    first = _engine(tmp_path / "one", catalog, brokers).run(_config())
    second = _engine(tmp_path / "two", catalog, brokers).run(_config())

    assert first.run_id != second.run_id
    assert Path(first.evidence_path).name == f"{first.run_id}.sqlite"
    assert Path(second.evidence_path).name == f"{second.run_id}.sqlite"
    with sqlite3.connect(first.evidence_path) as connection:
        assert connection.execute(
            "SELECT run_id FROM BACKTEST_RUN_LOCAL"
        ).fetchone() == (first.run_id,)
    assert first.evidence_hash == second.evidence_hash


def _metrics(pf: float) -> MetricSet:
    return MetricSet(
        pf=pf,
        sortino=1.0,
        calmar_or_mar=1.0,
        sqn=2.0,
        mdd=-0.1,
        ror=0.0,
        sharpe=1.0,
        win_rate=0.5,
        payoff=2.0,
        expectancy_r=0.2,
        ulcer=1.0,
        kelly=0.2,
        trade_count=30,
    )


class _HarnessEngine:
    def __init__(self, results: list[RunResult]) -> None:
        self._results = results

    def run(self, config: RunConfig) -> RunResult:
        del config
        return self._results.pop(0)


def _run_result(run_id: str, pf: float) -> RunResult:
    from core_lib.eval import DecisionResult

    return RunResult(
        run_id=run_id,
        evidence_path=f"{run_id}.sqlite",
        evidence_hash="a" * 64,
        integrity_status="passed",
        metrics=_metrics(pf),
        decision=DecisionResult(route="promote", rationale="fixture"),
    )


def test_harness_is_fixed_seed_and_applies_cross_run_boundaries() -> None:
    results = [_run_result("is", 2.0), _run_result("oos", 1.2)]
    engine = _HarnessEngine(results)
    catalog = _Catalog()
    harness = Harness(catalog, lambda: cast(Engine, engine))

    oos = harness.is_oos(_config(run_name="validation"), 0.5)
    first = harness.monte_carlo([1.0, -1.0, 2.0], 100)
    second = harness.monte_carlo([1.0, -1.0, 2.0], 100)

    assert oos["oos_degradation"] == pytest.approx(0.4)
    assert oos["passed"] is True
    assert catalog.events == ["reconcile"]
    assert first == second
    assert set(first) >= {
        "terminal_r_p05",
        "terminal_r_p95",
        "ruin_probability",
        "passed",
    }
    assert harness.overfit_gate(degradation=0.499, psr=0.95)["passed"] is True
    failed = harness.overfit_gate(degradation=0.5, psr=0.949)
    assert failed["failed"] == ["oos_degradation", "psr"]
    assert harness.psr([0.01, 0.02, -0.005, 0.03, 0.015]) > 0.5
