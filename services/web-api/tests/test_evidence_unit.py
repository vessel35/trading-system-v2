"""Hermetic Evidence reader, consistency, and failure-path contracts."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Never, cast

import psycopg
import pytest
from backtest_service.adapters.evidence_schema import (
    EVIDENCE_SCHEMA_VERSION,
    initialize_evidence_schema,
)
from fastapi.testclient import TestClient
from web_api.database import CatalogConfigurationError, get_settings
from web_api.evidence import EvidenceRepository, EvidenceUnavailableError, open_evidence
from web_api.main import app, repository
from web_api.models import RunSummary, RunSummaryResponse

RUN_ID = "BT_20260727_000001_unit"
BASE_TS = 1_750_000_000_000
SCALE = 100_000_000


@dataclass(frozen=True)
class UnitEvidence:
    root: Path
    path: Path
    run_id: str


def _insert_run(
    connection: sqlite3.Connection,
    *,
    evidence_schema_version: str = EVIDENCE_SCHEMA_VERSION,
) -> None:
    connection.execute(
        """
        INSERT INTO BACKTEST_RUN_LOCAL (
            run_id, run_seq, run_name, strategy_id, strategy_name,
            strategy_version, params_schema_version, symbol, exchange,
            timeframe, market_type, period_start, period_end, initial_capital,
            sizing_method, risk_per_trade, data_quality_criteria_json,
            engine_version, core_lib_version, config_hash,
            evidence_schema_version
        ) VALUES (?, 1, 'unit-evidence', 'unit-strategy', 'Unit Strategy',
                  '1.0.0', '1', 'BTC/USDT:USDT', 'binance', '1h',
                  'futures', ?, ?, ?, 'risk_based', 0.01, '{}',
                  'unit-engine', '0.2.0', ?, ?)
        """,
        (
            RUN_ID,
            BASE_TS,
            BASE_TS + 86_400_000,
            10_000 * SCALE,
            "a" * 64,
            evidence_schema_version,
        ),
    )


def _seed_trade(
    connection: sqlite3.Connection,
    *,
    trade_id: int,
    entry_execution_id: int,
    exit_execution_id: int,
    gross_pnl: int,
    total_fee: int,
    slippage: int,
    funding_cost: int,
    liquidation_penalty: int,
) -> None:
    decision_id = trade_id
    entry_ts = BASE_TS + trade_id * 10_000
    exit_ts = entry_ts + 5_000
    connection.execute(
        """
        INSERT INTO DECISION (
            decision_id, run_id, decision_ts, action, intended_side,
            intended_qty, sizing_method, framework_compliant,
            planned_execution_ts
        ) VALUES (?, ?, ?, 'enter', 'LONG', 1.0, 'risk_based', 1, ?)
        """,
        (decision_id, RUN_ID, entry_ts - 2_000, entry_ts - 1_000),
    )
    connection.executemany(
        """
        INSERT INTO EXECUTION (
            execution_id, run_id, decision_id, order_id, execution_ts,
            symbol, side, position_side, order_type, reference_price,
            price, quantity, notional, fee, slippage, liquidity,
            reduce_only, exit_reason, gap_filled, qty_truncated
        ) VALUES (?, ?, ?, ?, ?, 'BTC/USDT:USDT', ?, 'LONG', 'MARKET',
                  ?, ?, ?, ?, ?, ?, 'taker', ?, ?, 0, 0)
        """,
        (
            (
                entry_execution_id,
                RUN_ID,
                decision_id,
                f"entry-{trade_id}",
                entry_ts,
                "BUY",
                100 * SCALE,
                100 * SCALE,
                SCALE,
                100 * SCALE,
                total_fee // 2,
                slippage // 2,
                0,
                None,
            ),
            (
                exit_execution_id,
                RUN_ID,
                decision_id,
                f"exit-{trade_id}",
                exit_ts,
                "SELL",
                101 * SCALE,
                101 * SCALE,
                SCALE,
                101 * SCALE,
                total_fee - total_fee // 2,
                slippage - slippage // 2,
                1,
                "SIGNAL_EXIT",
            ),
        ),
    )
    net_pnl = gross_pnl - total_fee - slippage - funding_cost - liquidation_penalty
    connection.execute(
        """
        INSERT INTO TRADE (
            trade_id, run_id, backtest_run_id, symbol, side, market_type,
            entry_execution_id, exit_execution_id, entry_price,
            entry_quantity, entry_time, exit_price, exit_quantity, exit_time,
            exit_reason, gross_pnl, total_fee, slippage,
            liquidation_penalty, funding_cost, net_pnl, return_pct, r0,
            r_multiple, strategy_id, strategy_name, hold_duration_seconds,
            signal_confidence, reason
        ) VALUES (?, ?, ?, 'BTC/USDT:USDT', 'LONG', 'futures', ?, ?,
                  ?, ?, ?, ?, ?, ?, 'SIGNAL_EXIT', ?, ?, ?, ?, ?, ?,
                  0.01, ?, ?, 'unit-strategy', 'Unit Strategy', 5, 0.75,
                  'fixture identity')
        """,
        (
            trade_id,
            RUN_ID,
            RUN_ID,
            entry_execution_id,
            exit_execution_id,
            100 * SCALE,
            SCALE,
            entry_ts,
            101 * SCALE,
            SCALE,
            exit_ts,
            gross_pnl,
            total_fee,
            slippage,
            liquidation_penalty,
            funding_cost,
            net_pnl,
            SCALE,
            float(Decimal(net_pnl) / Decimal(SCALE)),
        ),
    )


def _create_evidence(path: Path, *, populated: bool) -> None:
    with sqlite3.connect(path) as connection:
        initialize_evidence_schema(connection)
        _insert_run(connection)
        if not populated:
            connection.commit()
            return

        connection.execute(
            """
            INSERT INTO SOURCE_DATA_SNAPSHOT (
                snapshot_id, run_id, source_kind, source_ref, symbol, exchange,
                timeframe, range_start, range_end, row_count, content_hash
            ) VALUES (1, ?, 'ohlcv', 'fixture', 'BTC/USDT:USDT', 'binance',
                      '1h', ?, ?, 24, ?)
            """,
            (RUN_ID, BASE_TS, BASE_TS + 86_400_000, "b" * 64),
        )
        connection.execute(
            """
            INSERT INTO INDICATOR_DEFINITION (
                indicator_key, run_id, indicator_name, params_json,
                impl_version, min_history, computation_mode,
                enabled_reason, series_kind, category, impl_note
            ) VALUES ('ema-20', ?, 'EMA', '{"length":20}', '1.2.3', 20,
                      'incremental', 'auto', 'indicator', 'trend',
                      'fixture implementation')
            """,
            (RUN_ID,),
        )
        connection.execute(
            """
            INSERT INTO INDICATOR_SNAPSHOT (
                snapshot_seq, run_id, indicator_key, feature_ts,
                candle_open_time, candle_close_time, value, is_warmup
            ) VALUES (1, ?, 'ema-20', ?, ?, ?, 101.25, 0)
            """,
            (RUN_ID, BASE_TS + 3_600_000, BASE_TS, BASE_TS + 3_600_000),
        )
        connection.execute(
            """
            INSERT INTO SIGNAL (
                signal_id, run_id, decision_ts, feature_ts, candle_open_time,
                candle_close_time, symbol, price, confidence, stop_loss,
                take_profit, market_type, leverage, reason, metadata_json,
                derived_intent, derived_side, is_warmup
            ) VALUES (1, ?, ?, ?, ?, ?, 'BTC/USDT:USDT', 100.25, 0.8,
                      99.0, 102.0, 'futures', 2, 'fixture signal',
                      '{"source":"unit"}', 'enter', 'LONG', 0)
            """,
            (
                RUN_ID,
                BASE_TS + 3_600_000,
                BASE_TS + 3_600_000,
                BASE_TS,
                BASE_TS + 3_600_000,
            ),
        )
        _seed_trade(
            connection,
            trade_id=1,
            entry_execution_id=1,
            exit_execution_id=2,
            gross_pnl=123_456_789,
            total_fee=10_000_001,
            slippage=20_000_002,
            funding_cost=30_000_003,
            liquidation_penalty=40_000_004,
        )
        _seed_trade(
            connection,
            trade_id=2,
            entry_execution_id=3,
            exit_execution_id=4,
            gross_pnl=-200_000_000,
            total_fee=10_000_000,
            slippage=10_000_000,
            funding_cost=10_000_000,
            liquidation_penalty=20_000_000,
        )
        _seed_trade(
            connection,
            trade_id=3,
            entry_execution_id=5,
            exit_execution_id=6,
            gross_pnl=10_000_000,
            total_fee=2_500_000,
            slippage=2_500_000,
            funding_cost=2_500_000,
            liquidation_penalty=2_500_000,
        )
        connection.execute(
            """
            INSERT INTO FUNDING_SETTLEMENT (
                settlement_id, run_id, trade_id, settled_at, symbol,
                position_side, funding_rate, rate_source, settle_price,
                settle_price_source, position_notional, payment_amount,
                theoretical_payment_amount
            ) VALUES (1, ?, 1, ?, 'BTC/USDT:USDT', 'LONG', 0.0001,
                      'measured', ?, 'boundary_open', ?, ?, ?)
            """,
            (
                RUN_ID,
                BASE_TS + 20_000,
                100 * SCALE,
                100 * SCALE,
                -1_000_001,
                -1_000_001,
            ),
        )
        connection.execute(
            """
            INSERT INTO POSITION (
                position_seq, run_id, trade_id, ts, symbol, side, quantity,
                average_price, total_cost, current_price, mark_price,
                mark_price_source, unrealized_pnl, leverage, margin_type,
                margin, entry_price, liquidation_price, funding_fee_total
            ) VALUES (1, ?, 1, ?, 'BTC/USDT:USDT', 'LONG', ?, ?, ?, ?, ?,
                      'measured', ?, 2, 'ISOLATED', ?, ?, ?, ?)
            """,
            (
                RUN_ID,
                BASE_TS + 15_000,
                SCALE,
                100 * SCALE,
                100 * SCALE,
                101 * SCALE,
                101 * SCALE,
                SCALE,
                50 * SCALE,
                100 * SCALE,
                50 * SCALE,
                -1_000_001,
            ),
        )
        equity_rows = [
            (
                seq,
                RUN_ID,
                BASE_TS + seq * 60_000,
                10_000 * SCALE + seq,
                0,
                10_000 * SCALE + seq,
                10_000 * SCALE + seq,
                seq,
                0,
                10_000_001,
                20_000_002,
                30_000_003,
                10_001 * SCALE,
                -0.01,
                0,
            )
            for seq in range(205, 0, -1)
        ]
        connection.executemany(
            """
            INSERT INTO PORTFOLIO_PNL (
                equity_seq, run_id, ts, cash_balance, position_value,
                total_equity, intrabar_low_equity, realized_pnl_cum,
                unrealized_pnl, fee_cum, slippage_cum, funding_cum,
                peak_equity, drawdown_pct, open_positions
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            equity_rows,
        )
        connection.execute(
            """
            INSERT INTO OUTCOME_BUCKET (
                bucket_id, run_id, subject_kind, subject_id, bucket_name,
                bucket_value, r_multiple, note
            ) VALUES (1, ?, 'trade', 1, 'outcome_class', 'normal_winner',
                      0.23456779, 'fixture bucket')
            """,
            (RUN_ID,),
        )
        connection.execute(
            """
            INSERT INTO INTEGRITY_CHECK (
                check_id, run_id, check_name, passed, detail_json,
                sample_ref, checked_at
            ) VALUES (1, ?, 'net_of_cost', 1, '{"checked":3}', 'TRADE', ?)
            """,
            (RUN_ID, BASE_TS + 99_000),
        )
        connection.execute(
            """
            INSERT INTO CHART_SUMMARY (
                summary_seq, run_id, series_name, bucket_ts, value,
                payload_json
            ) VALUES (1, ?, 'equity', ?, 10000.25,
                      '{"label":"first"}')
            """,
            (RUN_ID, BASE_TS),
        )
        connection.execute(
            """
            INSERT INTO CANDIDATE_EVENT (
                candidate_id, run_id, ts, symbol, trigger_rule,
                passed_filters_json, would_be_side, would_be_qty, realized,
                linked_trade_id
            ) VALUES (1, ?, ?, 'BTC/USDT:USDT', 'cross', '["trend","risk"]',
                      'LONG', ?, 1, 1)
            """,
            (RUN_ID, BASE_TS + 9_000, SCALE),
        )
        connection.execute(
            """
            INSERT INTO TRADE_FEATURE_SNAPSHOT (
                tfs_id, run_id, trade_id, phase, ts, features_json,
                regime_tag, excursion_r
            ) VALUES (1, ?, 1, 'entry', ?, '{"atr":1.25}', 'trend', 0.5)
            """,
            (RUN_ID, BASE_TS + 10_000),
        )
        connection.execute(
            """
            INSERT INTO DRAWDOWN_RUNUP_EPISODE (
                episode_id, run_id, kind, start_ts, end_ts, recovery_ts,
                peak_equity, trough_equity, depth_pct, duration_seconds,
                trade_count, contributing_trades_json
            ) VALUES (1, ?, 'drawdown', ?, ?, ?, ?, ?, -0.1, 3600, 2,
                      '[1,2]')
            """,
            (
                RUN_ID,
                BASE_TS,
                BASE_TS + 3_600_000,
                BASE_TS + 7_200_000,
                10_000 * SCALE,
                9_000 * SCALE,
            ),
        )
        connection.commit()


@pytest.fixture
def unit_evidence(tmp_path: Path) -> UnitEvidence:
    path = tmp_path / "unit-evidence.sqlite3"
    _create_evidence(path, populated=True)
    return UnitEvidence(root=tmp_path, path=path, run_id=RUN_ID)


def _repo(path: Path) -> EvidenceRepository:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return EvidenceRepository(connection)


def test_repository_reads_correct_tables_columns_and_exact_values(
    unit_evidence: UnitEvidence,
) -> None:
    reader = _repo(unit_evidence.path)

    trade = reader.trades(
        after_seq=0,
        limit=10,
        exit_reason="SIGNAL_EXIT",
        side="LONG",
        liquidated=False,
        entry_time_from=None,
        entry_time_to=None,
    ).data[0]
    assert trade.trade_id == 1
    assert trade.entry_price == "100"
    assert trade.gross_pnl == "1.23456789"
    assert trade.total_fee == "0.10000001"
    assert trade.slippage == "0.20000002"
    assert trade.funding_cost == "0.30000003"
    assert trade.liquidation_penalty == "0.40000004"
    assert trade.net_pnl == "0.23456779"

    execution = reader.executions(after_seq=0, limit=1, trade_id=1).data[0]
    assert (execution.execution_id, execution.trade_id) == (1, 1)
    assert execution.price == "100"
    assert execution.reduce_only is False

    settlement = reader.funding_settlements(after_seq=0, limit=1, trade_id=1).data[0]
    assert settlement.payment_amount == "-0.01000001"
    assert settlement.settle_price == "100"

    equity = reader.equity(after_seq=0, limit=1).data[0]
    assert equity.equity_seq == 1
    assert equity.fee_cum == "0.10000001"

    chart = reader.chart_summaries(after_seq=0, limit=1, series_name="equity").data[0]
    assert chart.payload_json == {"label": "first"}

    position = reader.positions(after_seq=0, limit=1, trade_id=1).data[0]
    assert position.funding_fee_total == "-0.01000001"
    assert position.mark_price_source == "measured"

    integrity = reader.integrity_checks(after_seq=0, limit=1).data[0]
    assert integrity.passed is True
    assert integrity.detail_json == {"checked": 3}

    outcome = reader.outcome_buckets(
        after_seq=0,
        limit=1,
        subject_kind="trade",
        subject_id=1,
        bucket_name="outcome_class",
    ).data[0]
    assert outcome.bucket_value == "normal_winner"

    episode = reader.drawdown_episodes(
        after_seq=0,
        limit=1,
        kind="drawdown",
    ).data[0]
    assert episode.peak_equity == "10000"
    assert episode.contributing_trades_json == [1, 2]

    feature = reader.trade_features(
        after_seq=0,
        limit=1,
        trade_id=1,
        phase="entry",
    ).data[0]
    assert feature.features_json == {"atr": 1.25}

    candidate = reader.candidate_events(
        after_seq=0,
        limit=1,
        linked_trade_id=1,
        realized=True,
    ).data[0]
    assert candidate.passed_filters_json == ["trend", "risk"]
    assert candidate.would_be_qty == "1"

    signal = reader.signals(
        after_seq=0,
        limit=1,
        derived_intent="enter",
        derived_side="LONG",
        is_warmup=False,
        decision_time_from=None,
        decision_time_to=None,
    ).data[0]
    assert signal.metadata_json == {"source": "unit"}

    decision = reader.decisions(
        after_seq=0,
        limit=1,
        action="enter",
        skip_reason=None,
        signal_id=None,
        decision_time_from=None,
        decision_time_to=None,
    ).data[0]
    assert decision.framework_compliant is True

    snapshot = reader.indicator_snapshots(
        after_seq=0,
        limit=1,
        indicator_key="ema-20",
        is_warmup=False,
        feature_time_from=None,
        feature_time_to=None,
    ).data[0]
    assert snapshot.indicator_name == "EMA"
    assert snapshot.params_json == {"length": 20}
    assert "pinned_impl" not in snapshot.model_dump()
    assert snapshot.series_kind == "indicator"
    assert snapshot.category == "trend"
    assert snapshot.impl_note == "fixture implementation"

    definitions = reader.indicator_definitions()
    assert [definition.model_dump() for definition in definitions] == [
        {
            "indicator_key": "ema-20",
            "indicator_name": "EMA",
            "series_kind": "indicator",
            "impl_version": "1.2.3",
        }
    ]

    source_from, source_to = reader.source_range("1h")
    assert int(source_from.timestamp() * 1000) == BASE_TS
    assert int(source_to.timestamp() * 1000) == BASE_TS + 86_400_000


def test_large_cursor_pages_are_sorted_stable_and_complete(
    unit_evidence: UnitEvidence,
) -> None:
    reader = _repo(unit_evidence.path)
    seen: list[int] = []
    after_seq = 0

    while True:
        result = reader.equity(after_seq=after_seq, limit=37)
        ids = [point.equity_seq for point in result.data]
        assert ids == sorted(ids)
        assert result.page.total == 205
        assert result.page.after_seq == after_seq
        seen.extend(ids)
        if not result.page.has_more:
            assert result.page.next_after_seq == 205
            break
        assert result.page.next_after_seq is not None
        assert result.page.next_after_seq > after_seq
        after_seq = result.page.next_after_seq

    assert seen == list(range(1, 206))
    exhausted = reader.equity(after_seq=205, limit=37)
    assert exhausted.data == []
    assert exhausted.page.total == 205
    assert exhausted.page.has_more is False
    assert exhausted.page.next_after_seq is None


def test_open_evidence_success_is_physically_read_only(
    unit_evidence: UnitEvidence,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEBAPI_EVIDENCE_ROOT", str(unit_evidence.root))
    get_settings.cache_clear()
    try:
        with open_evidence(unit_evidence.path.name) as connection:
            assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                connection.execute("UPDATE BACKTEST_RUN_LOCAL SET run_name = 'forbidden'")
    finally:
        get_settings.cache_clear()


def test_empty_evidence_returns_empty_collections(tmp_path: Path) -> None:
    path = tmp_path / "empty.sqlite3"
    _create_evidence(path, populated=False)
    reader = _repo(path)
    results: list[Any] = [
        reader.trades(
            after_seq=0,
            limit=5,
            exit_reason=None,
            side=None,
            liquidated=None,
            entry_time_from=None,
            entry_time_to=None,
        ),
        reader.executions(after_seq=0, limit=5, trade_id=None),
        reader.funding_settlements(after_seq=0, limit=5, trade_id=None),
        reader.equity(after_seq=0, limit=5),
        reader.chart_summaries(after_seq=0, limit=5, series_name=None),
        reader.positions(after_seq=0, limit=5, trade_id=None),
        reader.integrity_checks(after_seq=0, limit=5),
        reader.outcome_buckets(
            after_seq=0,
            limit=5,
            subject_kind=None,
            subject_id=None,
            bucket_name=None,
        ),
        reader.drawdown_episodes(after_seq=0, limit=5, kind=None),
        reader.trade_features(after_seq=0, limit=5, trade_id=None, phase=None),
        reader.candidate_events(
            after_seq=0,
            limit=5,
            linked_trade_id=None,
            realized=None,
        ),
        reader.signals(
            after_seq=0,
            limit=5,
            derived_intent=None,
            derived_side=None,
            is_warmup=None,
            decision_time_from=None,
            decision_time_to=None,
        ),
        reader.decisions(
            after_seq=0,
            limit=5,
            action=None,
            skip_reason=None,
            signal_id=None,
            decision_time_from=None,
            decision_time_to=None,
        ),
        reader.indicator_snapshots(
            after_seq=0,
            limit=5,
            indicator_key=None,
            is_warmup=None,
            feature_time_from=None,
            feature_time_to=None,
        ),
    ]
    assert all(result.data == [] for result in results)
    assert all(result.page.total == 0 for result in results)
    assert all(result.page.next_after_seq is None for result in results)
    assert all(result.page.has_more is False for result in results)
    assert reader.indicator_definitions() == []


def test_unimplemented_phase3_extension_writers_are_documented_as_absent(
    unit_evidence: UnitEvidence,
) -> None:
    """These empty reads document missing producers; they are not a completeness claim."""

    reader = _repo(unit_evidence.path)
    missed = reader.missed_opportunities(
        after_seq=0,
        limit=5,
        missing_reason=None,
        time_from=None,
        time_to=None,
    )
    conditional = reader.conditional_expectancy(
        after_seq=0,
        limit=5,
        subject_kind=None,
        is_significant=None,
        min_sample_count=None,
    )
    findings = reader.findings(after_seq=0, limit=5, confidence=None)
    with sqlite3.connect(unit_evidence.path) as connection:
        producerless_counts = {
            table: int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
            for table in (
                "MISSED_OPPORTUNITY",
                "CONDITION_SIGNATURE",
                "CONDITIONAL_EXPECTANCY",
                "FINDING_CLAIM",
            )
        }

    # Phase 3 must add recording paths before any of these can be treated as
    # populated product contracts. For now the reader honestly exposes absence.
    assert producerless_counts == {
        "MISSED_OPPORTUNITY": 0,
        "CONDITION_SIGNATURE": 0,
        "CONDITIONAL_EXPECTANCY": 0,
        "FINDING_CLAIM": 0,
    }
    assert missed.data == []
    assert conditional.data == []
    assert findings.data == []
    assert findings.meta.hash_excluded is True


def _summary_from_fixture(path: Path) -> RunSummaryResponse:
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        totals = connection.execute(
            """
            SELECT count(*) AS trade_count,
                   sum(net_pnl > 0) AS win_count,
                   sum(net_pnl < 0) AS loss_count,
                   sum(net_pnl = 0) AS r_excluded_count,
                   sum(net_pnl) AS net_pnl_total,
                   sum(gross_pnl) AS gross_pnl_total,
                   sum(total_fee) AS total_fee,
                   sum(slippage) AS total_slippage,
                   sum(funding_cost) AS total_funding,
                   sum(liquidation_penalty) AS total_liquidation_penalty
            FROM TRADE
            WHERE net_pnl IS NOT NULL
            """
        ).fetchone()
        assert totals is not None

    def exact(column: str) -> str:
        return format(Decimal(int(totals[column])) / Decimal(SCALE), "f")

    initial_capital = Decimal("10000")
    net_pnl = Decimal(exact("net_pnl_total"))
    summary = RunSummary(
        run_id=RUN_ID,
        trade_count=int(totals["trade_count"]),
        win_count=int(totals["win_count"]),
        loss_count=int(totals["loss_count"]),
        r_excluded_count=int(totals["r_excluded_count"]),
        pf=None,
        sortino=None,
        calmar_or_mar=None,
        calmar_basis=None,
        sqn=None,
        mdd=None,
        ror=None,
        sharpe=None,
        win_rate=1 / 2,
        payoff=None,
        expectancy_r=None,
        ulcer=None,
        kelly=None,
        annualization="calendar",
        initial_capital=format(initial_capital, "f"),
        final_equity=format(initial_capital + net_pnl, "f"),
        net_pnl_total=format(net_pnl, "f"),
        gross_pnl_total=exact("gross_pnl_total"),
        total_fee=exact("total_fee"),
        total_slippage=exact("total_slippage"),
        total_funding=exact("total_funding"),
        total_liquidation_penalty=exact("total_liquidation_penalty"),
        integrity_passed=True,
        integrity_status="passed",
        integrity_failed_json=None,
        gate_passed=None,
        gate_stage=None,
        gate_verdict=None,
        gate_failed_json=None,
        envelope_result=None,
        envelope_deviated_json=None,
        decision_route=None,
        decision_rationale=None,
        oos_degradation=None,
        psr=None,
        harness_json=None,
        computed_at=datetime(2026, 7, 27, tzinfo=UTC),
        expected_candle_count=100,
        observed_candle_count=98,
        source_absent_gap_count=1,
        partial_bucket_count=1,
        data_coverage_ratio=98 / 100,
        max_consecutive_gap_bars=1,
        max_consecutive_gap_seconds=60,
        data_coverage_passed=True,
        unobservable_funding_boundary_count=0,
        data_gap_exit_count=0,
    )
    return RunSummaryResponse(
        run_id=RUN_ID,
        run_status="SUCCEEDED",
        summary_status="available",
        summary=summary,
    )


class _FakeEvidenceCatalog:
    def __init__(
        self,
        *,
        evidence_path: str | None,
        summary: RunSummaryResponse | None = None,
        found: bool = True,
    ) -> None:
        self.evidence_path = evidence_path
        self.summary = summary
        self.found = found

    def get_evidence_path(self, _run_id: str) -> tuple[bool, str | None]:
        return self.found, self.evidence_path

    def get_summary(self, _run_id: str) -> RunSummaryResponse | None:
        return self.summary if self.found else None


def _client_for(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
    fake_catalog: _FakeEvidenceCatalog,
    *,
    raise_server_exceptions: bool = True,
) -> TestClient:
    monkeypatch.setenv("WEBAPI_EVIDENCE_ROOT", str(root))
    get_settings.cache_clear()
    app.dependency_overrides[repository] = lambda: fake_catalog
    return TestClient(
        app,
        raise_server_exceptions=raise_server_exceptions,
    )


def _create_legacy_indicator_evidence(path: Path, schema_version: str) -> None:
    """Create a complete file using the pre-1.5 Evidence table shapes."""
    with sqlite3.connect(path) as connection:
        initialize_evidence_schema(connection)
        connection.execute(
            """
            ALTER TABLE INDICATOR_DEFINITION
            ADD COLUMN pinned_impl INTEGER NOT NULL DEFAULT 0
                CHECK (pinned_impl IN (0, 1))
            """
        )
        for column in ("series_kind", "category", "impl_note"):
            connection.execute(f"ALTER TABLE INDICATOR_DEFINITION DROP COLUMN {column}")
        _insert_run(connection, evidence_schema_version=schema_version)
        connection.executemany(
            """
            INSERT INTO INDICATOR_DEFINITION (
                indicator_key, run_id, indicator_name, params_json,
                impl_version, pinned_impl, min_history, computation_mode,
                enabled_reason
            ) VALUES (?, ?, ?, ?, ?, 1, ?, 'incremental', 'auto')
            """,
            (
                (
                    "pat_doji",
                    RUN_ID,
                    "pat_doji",
                    "{}",
                    "2.0.0+talib.0.7.1",
                    11,
                ),
                (
                    "ema:period=9",
                    RUN_ID,
                    "ema",
                    '{"period":9}',
                    "1.0.0",
                    9,
                ),
            ),
        )
        connection.executemany(
            """
            INSERT INTO INDICATOR_SNAPSHOT (
                snapshot_seq, run_id, indicator_key, feature_ts,
                candle_open_time, candle_close_time, value_json, is_warmup
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                (
                    1,
                    RUN_ID,
                    "pat_doji",
                    BASE_TS + 3_600_000,
                    BASE_TS,
                    BASE_TS + 3_600_000,
                    '{"pat_doji":1,"pat_doji_confirm":0,"pat_doji_dir":1,"pat_doji_strength":1}',
                ),
                (
                    2,
                    RUN_ID,
                    "ema:period=9",
                    BASE_TS + 3_600_000,
                    BASE_TS,
                    BASE_TS + 3_600_000,
                    "101.25",
                ),
            ),
        )


@pytest.mark.parametrize("schema_version", ["1.3.0", "1.4.0"])
def test_pre_v15_evidence_file_restores_series_kind_through_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    schema_version: str,
) -> None:
    path = tmp_path / f"legacy-v{schema_version}.sqlite3"
    _create_legacy_indicator_evidence(path, schema_version)
    client = _client_for(
        monkeypatch,
        tmp_path,
        _FakeEvidenceCatalog(evidence_path=path.name),
    )
    try:
        with client:
            response = client.get(
                f"/api/v1/runs/{RUN_ID}/indicator-snapshots",
                params={"limit": 10},
            )
            definitions_response = client.get(f"/api/v1/runs/{RUN_ID}/indicator-definitions")
        assert response.status_code == 200
        assert definitions_response.status_code == 200
        snapshots = {item["indicator_key"]: item for item in response.json()["data"]}
        assert snapshots["pat_doji"]["series_kind"] == "pattern"
        assert snapshots["ema:period=9"]["series_kind"] == "indicator"
        for snapshot in snapshots.values():
            assert snapshot["category"] is None
            assert snapshot["impl_note"] is None
        definitions = {item["indicator_key"]: item for item in definitions_response.json()}
        assert definitions["pat_doji"] == {
            "indicator_key": "pat_doji",
            "indicator_name": "pat_doji",
            "series_kind": "pattern",
            "impl_version": "2.0.0+talib.0.7.1",
        }
        assert definitions["ema:period=9"]["series_kind"] == "indicator"
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_summary_and_trade_cost_breakdowns_share_fixture_identities(
    unit_evidence: UnitEvidence,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated_summary = _summary_from_fixture(unit_evidence.path)
    client = _client_for(
        monkeypatch,
        unit_evidence.root,
        _FakeEvidenceCatalog(
            evidence_path=unit_evidence.path.name,
            summary=generated_summary,
        ),
    )
    try:
        with client:
            trades_response = client.get(
                f"/api/v1/runs/{unit_evidence.run_id}/trades",
                params={"limit": 10},
            )
            summary_response = client.get(f"/api/v1/runs/{unit_evidence.run_id}/summary")
        assert trades_response.status_code == 200
        assert summary_response.status_code == 200

        trades = cast(list[dict[str, Any]], trades_response.json()["data"])
        summary = cast(dict[str, Any], summary_response.json()["summary"])

        def total(field: str) -> Decimal:
            return sum((Decimal(str(row[field])) for row in trades), start=Decimal())

        gross = total("gross_pnl")
        fee = total("total_fee")
        slip = total("slippage")
        funding = total("funding_cost")
        penalty = total("liquidation_penalty")
        net = total("net_pnl")

        assert net == gross - fee - slip - funding - penalty
        assert Decimal(summary["net_pnl_total"]) == net
        assert Decimal(summary["gross_pnl_total"]) == gross
        assert Decimal(summary["total_fee"]) == fee
        assert Decimal(summary["total_slippage"]) == slip
        assert Decimal(summary["total_funding"]) == funding
        assert Decimal(summary["total_liquidation_penalty"]) == penalty
        assert Decimal(summary["net_pnl_total"]) == Decimal(summary["gross_pnl_total"]) - Decimal(
            summary["total_fee"]
        ) - Decimal(summary["total_slippage"]) - Decimal(summary["total_funding"]) - Decimal(
            summary["total_liquidation_penalty"]
        )
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_summary_counts_and_coverage_are_internally_consistent(
    unit_evidence: UnitEvidence,
) -> None:
    summary = _summary_from_fixture(unit_evidence.path).summary
    assert summary is not None
    assert summary.trade_count == summary.win_count + summary.loss_count + summary.r_excluded_count
    assert 0.0 <= summary.data_coverage_ratio <= 1.0
    assert summary.data_coverage_ratio == (
        summary.observed_candle_count / summary.expected_candle_count
    )
    assert summary.source_absent_gap_count + summary.partial_bucket_count == (
        summary.expected_candle_count - summary.observed_candle_count
    )
    assert Decimal(summary.final_equity or "0") == (
        Decimal(summary.initial_capital) + Decimal(summary.net_pnl_total or "0")
    )


@pytest.mark.parametrize(
    ("evidence_path", "reason"),
    [
        (None, "catalog_evidence_path_missing"),
        ("/", "catalog_evidence_path_invalid"),
        ("does-not-exist.sqlite3", "evidence_file_missing"),
    ],
)
def test_open_evidence_rejects_missing_invalid_and_absent_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    evidence_path: str | None,
    reason: str,
) -> None:
    monkeypatch.setenv("WEBAPI_EVIDENCE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    with pytest.raises(EvidenceUnavailableError, match=reason) as raised:
        with open_evidence(evidence_path):
            pass
    assert raised.value.reason == reason
    get_settings.cache_clear()


def test_open_evidence_rejects_non_sqlite_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid = tmp_path / "invalid.sqlite3"
    invalid.write_text("not a sqlite database", encoding="utf-8")
    monkeypatch.setenv("WEBAPI_EVIDENCE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    with pytest.raises(EvidenceUnavailableError) as raised:
        with open_evidence(invalid.name):
            pass
    assert raised.value.reason == "evidence_file_invalid"
    get_settings.cache_clear()


def test_open_evidence_rejects_malformed_schema_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid = tmp_path / "invalid-schema-version.sqlite3"
    with sqlite3.connect(invalid) as connection:
        initialize_evidence_schema(connection)
        _insert_run(connection, evidence_schema_version="1.4")
    monkeypatch.setenv("WEBAPI_EVIDENCE_ROOT", str(tmp_path))
    get_settings.cache_clear()

    with pytest.raises(EvidenceUnavailableError) as raised:
        with open_evidence(invalid.name):
            pass

    assert raised.value.reason == "evidence_schema_version_invalid"
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("found", "evidence_path", "status", "code", "reason"),
    [
        (False, None, 404, "run_not_found", None),
        (True, None, 409, "evidence_unavailable", "catalog_evidence_path_missing"),
        (True, "/", 409, "evidence_unavailable", "catalog_evidence_path_invalid"),
        (True, "missing.sqlite3", 409, "evidence_unavailable", "evidence_file_missing"),
        (True, "invalid.sqlite3", 409, "evidence_unavailable", "evidence_file_invalid"),
    ],
)
def test_evidence_endpoint_errors_use_standard_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    found: bool,
    evidence_path: str | None,
    status: int,
    code: str,
    reason: str | None,
) -> None:
    (tmp_path / "invalid.sqlite3").write_text("not sqlite", encoding="utf-8")
    client = _client_for(
        monkeypatch,
        tmp_path,
        _FakeEvidenceCatalog(evidence_path=evidence_path, found=found),
    )
    try:
        with client:
            response = client.get(f"/api/v1/runs/{RUN_ID}/trades")
        assert response.status_code == status
        error = response.json()["error"]
        assert error["code"] == code
        assert isinstance(error["message"], str)
        assert error["message"]
        if reason is not None:
            assert error["details"] == {"reason": reason}
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_sqlite_query_failure_uses_standard_evidence_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    incomplete = tmp_path / "incomplete.sqlite3"
    with sqlite3.connect(incomplete) as connection:
        connection.execute("CREATE TABLE BACKTEST_RUN_LOCAL (evidence_schema_version TEXT)")
        connection.execute("INSERT INTO BACKTEST_RUN_LOCAL VALUES ('1.3.0')")
    client = _client_for(
        monkeypatch,
        tmp_path,
        _FakeEvidenceCatalog(evidence_path=incomplete.name),
    )
    try:
        with client:
            response = client.get(f"/api/v1/runs/{RUN_ID}/trades")
        assert response.status_code == 409
        assert response.json() == {
            "error": {
                "code": "evidence_unavailable",
                "message": "Detailed Evidence for this run is unavailable.",
                "details": {"reason": "evidence_query_failed"},
            }
        }
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest.mark.parametrize(
    "exception_factory",
    [
        pytest.param(
            lambda: psycopg.OperationalError("unit catalog failure"),
            id="psycopg-error-handler",
        ),
        pytest.param(
            lambda: CatalogConfigurationError("unit configuration failure"),
            id="configuration-error-handler",
        ),
    ],
)
def test_catalog_wide_exception_handlers_use_standard_error(
    exception_factory: Callable[[], Exception],
) -> None:
    def failing_repository() -> Never:
        raise exception_factory()

    app.dependency_overrides[repository] = failing_repository
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(f"/api/v1/runs/{RUN_ID}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "catalog_unavailable",
            "message": "The backtest catalog is unavailable.",
            "details": None,
        }
    }


def test_query_validation_error_uses_standard_error() -> None:
    app.dependency_overrides[repository] = lambda: _FakeEvidenceCatalog(evidence_path=None)
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/runs/{RUN_ID}/trades",
                params={"limit": 0},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_query"
    assert error["message"] == "The request query is invalid."
    assert error["details"][0]["field"] == "query.limit"
