"""Lock one trade's money arithmetic to values worked out by hand.

Every other engine test runs with all cost rates set to zero, so fees, slippage and
their interaction with the recorded profit have never been checked against an
independent calculation. This module fixes one fully specified trade and states each
expected amount as a literal that a reader can verify with a calculator, rather than
as an expression that mirrors the implementation.

The scenario, all of it chosen so the arithmetic stays exact in decimal:

    initial capital            10_000
    risk per trade             1%              → 100 of risk budget
    entry reference price      100             (next-bar open after the signal)
    stop-loss price            98              → 2 of stop distance
    quantity                   100 / 2 = 50    → 5_000 of reference notional
    take-profit price          104
    taker fee rate             0.0004
    entry slippage rate        0.0005
    exit slippage rate         0.0001
    funding                    none            (the window crosses no 8h boundary)

Worked out from those inputs:

    entry slippage    5_000 × 0.0005                     = 2.50
    entry fill price  100 + 2.50 / 50                    = 100.05
    entry fee         100.05 × 50 × 0.0004               = 2.001
    exit notional     104 × 50                           = 5_200
    exit slippage     5_200 × 0.0001                     = 0.52
    exit fill price   104 − 0.52 / 50                    = 103.9896
    exit fee          103.9896 × 50 × 0.0004             = 2.079792
    total fee         2.001 + 2.079792                   = 4.080792
    total slippage    2.50 + 0.52                        = 3.02
    gross profit      (104 − 100) × 50                   = 200
    net profit        200 − 4.080792 − 3.02              = 192.899208

Gross profit uses the reference prices, which is what keeps slippage from being
charged twice: the adverse fill is carried once, as its own cost.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import ClassVar, cast

import pytest
from backtest_service.adapters.broker import BacktestBroker
from backtest_service.adapters.catalog_store import DeterminismReference
from backtest_service.adapters.clock import BacktestClock
from backtest_service.adapters.cost_model import BacktestCostModel
from backtest_service.adapters.evidence_sink import BacktestEvidenceSink
from backtest_service.config import RunConfig
from backtest_service.engine import Engine
from core_lib.execution.matcher import _protection_reference
from core_lib.money_management.models import PolicyIndicatorRequirement
from core_lib.money_management.policies import MoneyManagementBase
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
    ExitReason,
    MarginType,
    MarketType,
    Position,
    PositionSide,
    TradingSignal,
)

# 01:00 UTC so the four-hour run window crosses none of the 00:00/08:00/16:00 funding
# boundaries; funding is exercised separately from this arithmetic.
_BASE = datetime(2026, 1, 1, 1, tzinfo=UTC)
_SYMBOL = "BTCUSDT"
_EVIDENCE_SCALE = Decimal(10) ** 8

ENTRY_REFERENCE = Decimal("100")
STOP_LOSS = Decimal("98")
TAKE_PROFIT = Decimal("104")
QUANTITY = Decimal("50")

EXPECTED_ENTRY_FILL_PRICE = Decimal("100.05")
EXPECTED_EXIT_FILL_PRICE = Decimal("103.9896")
EXPECTED_TOTAL_FEE = Decimal("4.080792")
EXPECTED_TOTAL_SLIPPAGE = Decimal("3.02")
EXPECTED_GROSS_PNL = Decimal("200")
EXPECTED_NET_PNL = Decimal("192.899208")


def _candles() -> list[Candle]:
    # Nine flat preload bars satisfy the strategy's declared history, then the
    # evaluation bars: signal, entry at the next open, and a bar that reaches the target.
    preload = [(100.0, 100.0, 100.0, 100.0) for _ in range(9)]
    evaluation = [
        (100.0, 100.0, 100.0, 100.0),  # signal bar
        (100.0, 101.0, 99.5, 100.5),  # entry fills at this open, 100
        (100.5, 105.0, 100.0, 104.5),  # reaches the 104 target
        (104.5, 105.0, 104.0, 104.5),
    ]
    prices = preload + evaluation
    start = _BASE - timedelta(hours=9)
    return [
        Candle(
            symbol=_SYMBOL,
            exchange="binance",
            timeframe="1h",
            open_time=start + timedelta(hours=index),
            close_time=start + timedelta(hours=index + 1),
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


def _minute_candles(candles: list[Candle]) -> list[Candle]:
    minutes: list[Candle] = []
    for candle in candles:
        for offset in range(60):
            open_time = candle.open_time + timedelta(minutes=offset)
            minutes.append(
                Candle(
                    symbol=candle.symbol,
                    exchange=candle.exchange,
                    timeframe="1m",
                    open_time=open_time,
                    close_time=open_time + timedelta(minutes=1),
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume / 60,
                    quote_volume=(
                        None if candle.quote_volume is None else candle.quote_volume / 60
                    ),
                    trade_count=1,
                )
            )
    return minutes


class _Feed(DataFeed):
    def __init__(self, candles: list[Candle]) -> None:
        self._candles = list(candles)
        self._minutes = _minute_candles(candles)

    def candles(self, symbol: str, tf: str, up_to: datetime) -> list[Candle]:
        assert symbol == _SYMBOL
        source = self._minutes if tf == "1m" else self._candles
        return [candle for candle in source if candle.close_time <= up_to]

    def source_candles(
        self,
        symbol: str,
        range_start: datetime,
        range_end: datetime,
    ) -> tuple[Candle, ...]:
        assert symbol == _SYMBOL
        return tuple(
            candle
            for candle in self._minutes
            if range_start <= candle.open_time and candle.close_time <= range_end
        )

    def funding(self, symbol: str, at: datetime) -> Decimal:
        del symbol, at
        raise LookupError("this fixture crosses no funding boundary")

    def mark_price(self, symbol: str, at: datetime) -> Decimal:
        del symbol, at
        return ENTRY_REFERENCE


class _Strategy:
    VERSION: ClassVar[str] = "1.0.0"

    def __init__(self, config: ResolvedConfig) -> None:
        self.config = config

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            # The engine requires at least one resolved indicator; this one plays no
            # part in the arithmetic under test.
            required_indicators=[{"name": "EMA", "params": {"period": 9}}],
            min_history=1,
            supported_timeframes=["1h"],
            profile=StrategyProfile(
                id="money-golden-profile",
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
        assert isinstance(candle, Candle)
        if candle.open_time == _BASE and current_position is None:
            return TradingSignal(
                symbol=candle.symbol,
                timestamp=candle.close_time,
                confidence=1.0,
                price=candle.close,
                stop_loss=float(STOP_LOSS),
                take_profit=float(TAKE_PROFIT),
                market_type=MarketType.FUTURES,
                leverage=1,
                reason="money-golden-entry",
                metadata={"fixture": True},
            )
        return None


class _Catalog(StrategyRegistry):
    def get(self, strategy_id: str) -> dict[str, object]:
        assert strategy_id == "money-golden"
        return {
            "strategy_id": strategy_id,
            "class_name": "_Strategy",
            "module_path": __name__,
            "is_active": True,
            "is_deprecated": False,
        }

    def list(self) -> list[dict[str, object]]:
        return [self.get("money-golden")]

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        del strategy_id, meta
        raise PermissionError("golden fixtures are read-only")


class _RunCatalog(CatalogStore):
    """Issue run identifiers in memory so the golden needs no database."""

    def __init__(self) -> None:
        self.summaries: list[dict[str, object]] = []

    def register(self, run: object) -> str:
        del run
        return "BT_20260101_000001_money-golden"

    def save_prereg(self, prereg: object) -> None:
        del prereg

    def upsert_summary(self, summary: object) -> None:
        assert isinstance(summary, dict)
        self.summaries.append(summary)

    def reconcile_orphaned(self) -> int:
        return 0

    def record_harness_aggregate(
        self,
        run_id: str,
        *,
        oos_degradation: float | None,
        psr: float | None,
        harness_json: object,
    ) -> None:
        del run_id, oos_degradation, psr, harness_json

    def determinism_reference(
        self,
        run_id: str,
        config_hash: str,
        source_data_hash: str,
        evidence_schema_version: str,
    ) -> DeterminismReference:
        del run_id, config_hash, source_data_hash, evidence_schema_version
        # No earlier run exists in this fixture, so nothing is compared against.
        return DeterminismReference(True, True, False, False, None, None)


def _manager() -> AdapterManager:
    plugins = InProcessStrategyRegistry()
    plugins.register("money-golden", _Strategy)
    return AdapterManager(_Catalog(), plugins)


def _config() -> RunConfig:
    return RunConfig(
        run_name="money-golden",
        strategy_id="money-golden",
        params={},
        symbol=_SYMBOL,
        exchange="binance",
        timeframe="1h",
        market_type="futures",
        data_source="fixture",
        start=_BASE,
        end=_BASE + timedelta(hours=4),
        initial_capital=Decimal("10000"),
        risk_per_trade=0.01,
        cost_values={
            "futures_taker_fee_rate": Decimal("0.0004"),
            "futures_entry_slippage_rate": Decimal("0.0005"),
            "exit_slippage_rate": Decimal("0.0001"),
            "funding_fallback_rate": Decimal("0"),
        },
        profile_ref="money-golden-profile",
    )


@pytest.fixture
def completed_trade(tmp_path: Path) -> dict[str, Decimal]:
    config = _config()
    candles = _candles()
    costs = BacktestCostModel(config.cost_values, market_type=MarketType.FUTURES)
    engine = Engine(
        _Feed(candles),
        BacktestBroker(costs),
        BacktestClock.from_candles(candles),
        costs,
        BacktestEvidenceSink(tmp_path),
        _RunCatalog(),
        _manager(),
        prereg={
            "hypothesis": "one trade's money arithmetic is fixed",
            "primary_metric": "pf",
            "success_threshold": 1.3,
            "failure_threshold": 1.0,
            "edge_distinguishable": True,
            "higher_is_better": True,
        },
    )
    result = engine.run(config)
    # Read the persisted Evidence rather than engine memory: that file is what the
    # console and every later audit read, so it is the value worth fixing.
    with sqlite3.connect(result.evidence_path) as evidence:
        rows = evidence.execute(
            """
            SELECT entry_price, entry_quantity, exit_price, exit_quantity,
                   gross_pnl, total_fee, slippage, funding_cost, net_pnl
            FROM TRADE
            ORDER BY trade_id
            """
        ).fetchall()
    assert len(rows) == 1, "the golden scenario must produce exactly one trade"
    columns = (
        "entry_price",
        "entry_quantity",
        "exit_price",
        "exit_quantity",
        "gross_pnl",
        "total_fee",
        "slippage",
        "funding_cost",
        "net_pnl",
    )
    # Evidence stores money as integers scaled by 10^8.
    return {
        name: Decimal(value) / _EVIDENCE_SCALE for name, value in zip(columns, rows[0], strict=True)
    }


def test_quantity_follows_the_risk_budget_and_stop_distance(
    completed_trade: dict[str, Decimal],
) -> None:
    # 1% of 10_000 is 100 of risk; a 2-wide stop buys 50 units of exposure.
    assert completed_trade["entry_quantity"] == QUANTITY
    assert completed_trade["exit_quantity"] == QUANTITY


def test_reference_prices_are_the_unslipped_market_prices(
    completed_trade: dict[str, Decimal],
) -> None:
    assert completed_trade["entry_price"] == ENTRY_REFERENCE
    assert completed_trade["exit_price"] == TAKE_PROFIT


def test_gross_profit_excludes_slippage(completed_trade: dict[str, Decimal]) -> None:
    # (104 − 100) × 50. Charging the slipped fills here would count slippage twice,
    # once inside the price and once again as the recorded cost below.
    assert completed_trade["gross_pnl"] == EXPECTED_GROSS_PNL


def test_fees_are_charged_on_the_filled_notional(completed_trade: dict[str, Decimal]) -> None:
    # 100.05 × 50 × 0.0004 = 2.001 on entry, 103.9896 × 50 × 0.0004 = 2.079792 on exit.
    assert completed_trade["total_fee"] == EXPECTED_TOTAL_FEE


def test_slippage_is_the_adverse_amount_on_both_fills(completed_trade: dict[str, Decimal]) -> None:
    # 5_000 × 0.0005 = 2.50 entering, 5_200 × 0.0001 = 0.52 leaving.
    assert completed_trade["slippage"] == EXPECTED_TOTAL_SLIPPAGE


def test_no_funding_is_charged_when_no_boundary_is_crossed(
    completed_trade: dict[str, Decimal],
) -> None:
    assert completed_trade["funding_cost"] == Decimal("0")


def test_net_profit_is_gross_less_every_cost(completed_trade: dict[str, Decimal]) -> None:
    # 200 − 4.080792 − 3.02 = 192.899208
    assert completed_trade["net_pnl"] == EXPECTED_NET_PNL


def _protection_case(
    side: PositionSide,
    level: Decimal,
    open_price: Decimal,
    reason: ExitReason,
) -> tuple[Decimal, bool]:
    candle = Candle(
        symbol=_SYMBOL,
        exchange="binance",
        timeframe="1h",
        open_time=_BASE,
        close_time=_BASE + timedelta(hours=1),
        open=float(open_price),
        high=float(max(open_price, level)),
        low=float(min(open_price, level)),
        close=float(open_price),
        volume=1.0,
        quote_volume=1.0,
        trade_count=1,
    )
    notional = ENTRY_REFERENCE * QUANTITY
    position = Position(
        symbol=_SYMBOL,
        side=side,
        quantity=QUANTITY,
        average_price=ENTRY_REFERENCE,
        current_price=open_price,
        leverage=1,
        market_type=MarketType.FUTURES,
        wallet_id=None,
        total_cost=notional,
        unrealized_pnl=Decimal("0"),
        margin_type=MarginType.ISOLATED,
        margin=notional,
        entry_price=ENTRY_REFERENCE,
        mark_price=open_price,
        liquidation_price=Decimal("0"),
        funding_fee_total=Decimal("0"),
    )
    return _protection_reference(position, candle, level, reason)


def test_a_target_inside_the_bar_fills_at_the_target() -> None:
    # The ordinary case: the bar opens away from the target and reaches it intrabar.
    # Filling at the open here books less than the target on every winning trade.
    assert _protection_case(
        PositionSide.LONG, Decimal("104"), Decimal("100.5"), ExitReason.TAKE_PROFIT
    ) == (Decimal("104"), False)
    assert _protection_case(
        PositionSide.SHORT, Decimal("96"), Decimal("99.5"), ExitReason.TAKE_PROFIT
    ) == (Decimal("96"), False)


def test_a_bar_opening_past_the_target_fills_at_that_open() -> None:
    # The position could not have been closed before the bar opened, so the fill is the
    # open and the run records that it was a gap.
    assert _protection_case(
        PositionSide.LONG, Decimal("104"), Decimal("106"), ExitReason.TAKE_PROFIT
    ) == (Decimal("106"), True)
    assert _protection_case(
        PositionSide.SHORT, Decimal("96"), Decimal("94"), ExitReason.TAKE_PROFIT
    ) == (Decimal("94"), True)


def test_a_stop_inside_the_bar_fills_at_the_stop() -> None:
    assert _protection_case(
        PositionSide.LONG, Decimal("98"), Decimal("99.5"), ExitReason.STOP_LOSS
    ) == (Decimal("98"), False)
    assert _protection_case(
        PositionSide.SHORT, Decimal("102"), Decimal("100.5"), ExitReason.STOP_LOSS
    ) == (Decimal("102"), False)


def test_a_bar_opening_past_the_stop_fills_at_that_worse_open() -> None:
    # The adverse gap is charged rather than assumed away.
    assert _protection_case(
        PositionSide.LONG, Decimal("98"), Decimal("95"), ExitReason.STOP_LOSS
    ) == (Decimal("95"), True)
    assert _protection_case(
        PositionSide.SHORT, Decimal("102"), Decimal("105"), ExitReason.STOP_LOSS
    ) == (Decimal("105"), True)


def test_the_history_floor_covers_a_policy_declared_daily_requirement() -> None:
    """A daily N over twenty days needs far more calendar history than a 1h warm-up.

    The floor is derived from every declared requirement rather than the strategy
    timeframe alone. Reading only the strategy's span starved the daily series, and
    the shortfall surfaced as a missing daily history at run start rather than as a
    short read.
    """
    config = _config()
    engine = Engine.__new__(Engine)
    engine.config = config
    engine._indicator_specs = []
    engine._money_management = cast(MoneyManagementBase, _TurtlePolicyStub())
    engine._required_warmups = Engine._warmups_by_timeframe(engine, strategy_min_history=9)

    # Nine 1h bars of warm-up span barely over a day; twenty daily bars span twenty.
    span = Engine._warmup_span(engine)

    assert span >= timedelta(days=20), "the daily requirement must widen the floor"


class _TurtlePolicyStub:
    """Declare the daily requirement a turtle money-management policy carries."""

    def required_indicators(self) -> list[PolicyIndicatorRequirement]:
        return [
            PolicyIndicatorRequirement(
                name="TURTLE_N",
                params={"period": 20},
                timeframe="1d",
                min_history=20,
            )
        ]
