"""Verify the 21-entity Evidence SQLite schema and storage contracts."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from backtest_service.adapters.evidence_schema import (
    BASIC_TABLES,
    DECISION_CONTRACT_KEYS,
    ENTITY_SORT_KEYS,
    EVAL_DECISION_KEYS,
    EVIDENCE_TABLES,
    EXTENSION_TABLES,
    HASH_EXCLUDED_COLUMNS,
    HASH_EXCLUDED_ROWS,
    HASH_EXCLUDED_TABLES,
    HASH_GLOBAL_EXCLUDED_COLUMNS,
    HASH_TABLES,
    INTEGRITY_CHECK_NAMES,
    OPTIONAL_DECISION_CONTRACT_KEYS,
    OPTIONAL_INTEGRITY_CHECK_NAMES,
    TIMESTAMP_ORDER_AUDIT_SQL,
    WRITER_CONTRACT_COLUMNS,
    canonical_json,
    encode_eval_decision,
    initialize_evidence_schema,
    restore_decimal,
    restore_decision_contract,
    scale_decimal,
)

RUN_ID = "bt_20260724_000001"
HASH = "a" * 64
EXPECTED_COLUMNS = {
    "BACKTEST_RUN_LOCAL": """
        run_id run_seq run_name strategy_id strategy_name strategy_version params_json
        resolved_indicators_json params_schema_version symbol exchange timeframe market_type
        period_start period_end
        warmup_start warmup_candles indicator_mode trigger_feed fill_timing initial_capital
        sizing_method risk_per_trade position_size_pct framework_compliant cost_values_json
        seed engine_version core_lib_version config_hash profile_ref strategy_profile_json
        envelope_status_declared prereg_json eval_decision_json evidence_schema_version created_at
    """.split(),
    "SOURCE_DATA_SNAPSHOT": """
        snapshot_id run_id source_kind source_ref symbol exchange timeframe resampled_from
        range_start range_end row_count gap_count fallback_used fallback_count content_hash note
    """.split(),
    "INDICATOR_DEFINITION": """
        indicator_key run_id indicator_name params_json impl_version pinned_impl min_history
        computation_mode enabled_reason
    """.split(),
    "INDICATOR_SNAPSHOT": """
        snapshot_seq run_id indicator_key feature_ts candle_open_time candle_close_time value
        value_json is_warmup
    """.split(),
    "SIGNAL": """
        signal_id run_id decision_ts feature_ts candle_open_time candle_close_time symbol price
        confidence stop_loss take_profit market_type leverage reason metadata_json derived_intent
        derived_side is_warmup
    """.split(),
    "DECISION": """
        decision_id run_id signal_id decision_ts action skip_reason intended_side intended_qty
        stop_price take_profit_price risk_amount stop_distance sizing_method framework_compliant
        planned_execution_ts
    """.split(),
    "EXECUTION": """
        execution_id run_id decision_id order_id execution_ts trigger_subcandle_ts symbol side
        position_side order_type reference_price price quantity notional fee slippage liquidity
        reduce_only exit_reason gap_filled qty_truncated
    """.split(),
    "FUNDING_SETTLEMENT": """
        settlement_id run_id trade_id settled_at symbol position_side funding_rate rate_source
        settle_price settle_price_source position_notional payment_amount
    """.split(),
    "TRADE": """
        trade_id run_id backtest_run_id source_type symbol side market_type entry_execution_id
        exit_execution_id entry_price entry_quantity entry_time exit_price exit_quantity exit_time
        exit_reason gross_pnl total_fee slippage liquidation_penalty funding_cost net_pnl return_pct
        r0 r_multiple leverage liquidated strategy_id strategy_name hold_duration_seconds
        signal_confidence reason
    """.split(),
    "POSITION": """
        position_seq run_id trade_id ts symbol side quantity average_price total_cost current_price
        mark_price mark_price_source unrealized_pnl leverage margin_type margin entry_price
        liquidation_price funding_fee_total
    """.split(),
    "PORTFOLIO_PNL": """
        equity_seq run_id ts cash_balance position_value total_equity intrabar_low_equity
        realized_pnl_cum unrealized_pnl fee_cum slippage_cum funding_cum peak_equity drawdown_pct
        open_positions
    """.split(),
    "OUTCOME_BUCKET": """
        bucket_id run_id subject_kind subject_id bucket_name bucket_value r_multiple note
    """.split(),
    "INTEGRITY_CHECK": """
        check_id run_id check_name passed detail_json sample_ref checked_at
    """.split(),
    "CHART_SUMMARY": """
        summary_seq run_id series_name bucket_ts value payload_json
    """.split(),
    "CANDIDATE_EVENT": """
        candidate_id run_id ts symbol trigger_rule passed_filters_json blocked_by would_be_side
        would_be_qty realized linked_trade_id
    """.split(),
    "TRADE_FEATURE_SNAPSHOT": """
        tfs_id run_id trade_id phase ts features_json regime_tag excursion_r
    """.split(),
    "CONDITION_SIGNATURE": """
        signature_key run_id taxonomy_version definition_json subject_kind sample_count
    """.split(),
    "CONDITIONAL_EXPECTANCY": """
        ce_id run_id signature_key sample_count win_rate payoff expectancy_r pf ci_low ci_high
        is_significant
    """.split(),
    "MISSED_OPPORTUNITY": """
        miss_id run_id ts symbol source_rule missing_reason potential_r potential_move_pct
        nearest_candidate_id
    """.split(),
    "DRAWDOWN_RUNUP_EPISODE": """
        episode_id run_id kind start_ts end_ts recovery_ts peak_equity trough_equity depth_pct
        duration_seconds trade_count contributing_trades_json
    """.split(),
    "FINDING_CLAIM": """
        finding_id run_id claim evidence_ref_json confidence proposed_change next_prereg_ref
        created_at
    """.split(),
}


@pytest.fixture
def evidence_db(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """Create one isolated Evidence file and initialize its schema."""
    connection = sqlite3.connect(tmp_path / f"{RUN_ID}.sqlite")
    initialize_evidence_schema(connection)
    yield connection
    connection.close()


def _insert_run(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO BACKTEST_RUN_LOCAL (
            run_id,
            run_seq,
            run_name,
            strategy_id,
            strategy_name,
            strategy_version,
            params_schema_version,
            symbol,
            exchange,
            timeframe,
            market_type,
            period_start,
            period_end,
            warmup_start,
            warmup_candles,
            initial_capital,
            sizing_method,
            risk_per_trade,
            engine_version,
            core_lib_version,
            config_hash,
            prereg_json,
            evidence_schema_version
        ) VALUES (?, 1, 'run', 'fake', 'Fake', '1.0', '1', 'BTCUSDT', 'BINANCE',
                  '1h', 'futures', 1000, 5000, 0, 10, 100000000000,
                  'risk_based', 0.01, '1.0', '1.0', ?, ?, '1.0.0')
        """,
        (
            RUN_ID,
            HASH,
            canonical_json(
                {
                    "failure_threshold": 0.2,
                    "hypothesis": "edge persists",
                    "higher_is_better": True,
                    "primary_metric": "profit_factor",
                    "success_threshold": 1.5,
                }
            ),
        ),
    )


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row[1]) for row in connection.execute(f'SELECT * FROM pragma_table_info("{table}")')
    }


def test_schema_creates_14_basic_and_7_extension_strict_tables(
    evidence_db: sqlite3.Connection,
) -> None:
    """Create all declared entities as STRICT tables and remain idempotent."""
    initialize_evidence_schema(evidence_db)
    rows = evidence_db.execute(
        """
        SELECT name, strict
        FROM pragma_table_list
        WHERE schema = 'main' AND type = 'table' AND name NOT LIKE 'sqlite_%'
        """
    ).fetchall()
    assert len(BASIC_TABLES) == 14
    assert len(EXTENSION_TABLES) == 7
    assert {row[0] for row in rows} == set(EVIDENCE_TABLES)
    assert all(row[1] == 1 for row in rows)
    assert evidence_db.execute("PRAGMA foreign_keys").fetchone() == (1,)
    assert evidence_db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert evidence_db.execute("PRAGMA foreign_key_check").fetchall() == []
    for table in EVIDENCE_TABLES:
        assert "run_id" in _table_columns(evidence_db, table)


def test_declared_column_order_matches_database_design(
    evidence_db: sqlite3.Connection,
) -> None:
    """Keep every declared field in hash-significant table-definition order."""
    assert set(EXPECTED_COLUMNS) == set(EVIDENCE_TABLES)
    for table, expected in EXPECTED_COLUMNS.items():
        actual = [
            str(row[1])
            for row in evidence_db.execute(f'SELECT * FROM pragma_table_info("{table}")')
        ]
        assert actual == expected


def test_schema_marks_deterministic_hash_boundaries() -> None:
    """Expose exact sort and exclusion metadata to the future hash finalizer."""
    assert HASH_EXCLUDED_TABLES == {"FINDING_CLAIM"}
    assert HASH_GLOBAL_EXCLUDED_COLUMNS == {"run_id", "backtest_run_id"}
    assert HASH_EXCLUDED_COLUMNS == {
        "BACKTEST_RUN_LOCAL": {"run_seq", "run_name", "created_at"},
        "INTEGRITY_CHECK": {"checked_at"},
        "FINDING_CLAIM": {"created_at"},
    }
    assert HASH_EXCLUDED_ROWS == {
        "INTEGRITY_CHECK": ("check_name <> 'deterministic'",)
    }
    assert HASH_TABLES == tuple(sorted(set(EVIDENCE_TABLES) - HASH_EXCLUDED_TABLES))
    assert set(ENTITY_SORT_KEYS) == set(HASH_TABLES)
    assert "eval_decision_json" not in HASH_EXCLUDED_COLUMNS["BACKTEST_RUN_LOCAL"]


def test_fixed_precision_never_crosses_float() -> None:
    """Scale only already-normalized Decimal values and restore them exactly."""
    value = Decimal("1234.50000000")
    assert scale_decimal(value) == 123_450_000_000
    assert restore_decimal(123_450_000_000) == value
    with pytest.raises(TypeError, match="Decimal"):
        scale_decimal(1234.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="quantized"):
        scale_decimal(Decimal("0.000000001"))
    with pytest.raises(OverflowError, match="range"):
        scale_decimal(Decimal("92233720368.54775808"))


def test_canonical_json_uses_sorted_utf8_and_plain_shortest_numbers() -> None:
    """Use the §5.3.1 canonical JSON representation, including no exponent."""
    assert canonical_json({"한글": 1e-7, "a": [1.0, True, None]}) == (
        '{"a":[1,true,null],"한글":0.0000001}'
    )
    with pytest.raises(ValueError, match="non-finite"):
        canonical_json({"bad": float("nan")})


def test_one_run_per_file_and_strict_integer_storage(
    evidence_db: sqlite3.Connection,
) -> None:
    """Reject a second run and non-integral values in INTEGER evidence fields."""
    _insert_run(evidence_db)
    with pytest.raises(sqlite3.IntegrityError, match="exactly one run"):
        evidence_db.execute(
            """
            INSERT INTO BACKTEST_RUN_LOCAL (
                run_id, run_seq, run_name, strategy_id, strategy_name,
                strategy_version, params_schema_version, symbol, exchange,
                timeframe, market_type, period_start, period_end,
                initial_capital, risk_per_trade, engine_version, core_lib_version,
                config_hash, evidence_schema_version
            ) VALUES (
                'other', 2, 'other', 'fake', 'Fake', '1.0', '1', 'BTCUSDT',
                'BINANCE', '1h', 'futures', 1000, 5000, 1, 0.01, '1.0', '1.0',
                ?, '1.0.0'
            )
            """,
            (HASH,),
        )
    with pytest.raises(sqlite3.IntegrityError, match="INTEGER"):
        evidence_db.execute(
            """
            INSERT INTO SOURCE_DATA_SNAPSHOT (
                snapshot_id, run_id, source_kind, source_ref, symbol, exchange,
                timeframe, range_start, range_end, row_count, content_hash
            ) VALUES (1, ?, 'ohlcv', 'crypto_data.ohlcv_futures', 'BTCUSDT',
                      'BINANCE', '1h', 0, 1, 1.5, ?)
            """,
            (RUN_ID, HASH),
        )


def test_foreign_keys_and_representative_checks_are_enforced(
    evidence_db: sqlite3.Connection,
) -> None:
    """Reject missing parents, invalid booleans, and a broken accounting identity."""
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        evidence_db.execute(
            """
            INSERT INTO INDICATOR_DEFINITION (
                indicator_key, run_id, indicator_name, impl_version, min_history,
                enabled_reason
            ) VALUES ('ema:period=200', 'missing', 'ema', '1', 200, 'auto')
            """
        )
    _insert_run(evidence_db)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        evidence_db.execute(
            """
            INSERT INTO INDICATOR_DEFINITION (
                indicator_key, run_id, indicator_name, impl_version, pinned_impl,
                min_history, enabled_reason
            ) VALUES ('ema:period=200', ?, 'ema', '1', 2, 200, 'auto')
            """,
            (RUN_ID,),
        )
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        evidence_db.execute(
            """
            INSERT INTO PORTFOLIO_PNL (
                equity_seq, run_id, ts, cash_balance, position_value,
                total_equity, peak_equity
            ) VALUES (1, ?, 1000, 100, 50, 151, 151)
            """,
            (RUN_ID,),
        )


def test_integrity_names_match_m6_contract(
    evidence_db: sqlite3.Connection,
) -> None:
    """Persist the six M6 names plus only the optional trailing parity check."""
    _insert_run(evidence_db)
    names = INTEGRITY_CHECK_NAMES + OPTIONAL_INTEGRITY_CHECK_NAMES
    evidence_db.executemany(
        """
        INSERT INTO INTEGRITY_CHECK (check_id, run_id, check_name, passed)
        VALUES (?, ?, ?, 1)
        """,
        [(index, RUN_ID, name) for index, name in enumerate(names, start=1)],
    )
    assert {row[0] for row in evidence_db.execute("SELECT check_name FROM INTEGRITY_CHECK")} == set(
        names
    )
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        evidence_db.execute(
            """
            INSERT INTO INTEGRITY_CHECK (check_id, run_id, check_name, passed)
            VALUES (99, ?, 'determinism', 1)
            """,
            (RUN_ID,),
        )


def test_preregistration_and_finalize_decision_output_restore_m6_contract(
    evidence_db: sqlite3.Connection,
) -> None:
    """Keep preregistration immutable while storing canonical finalize output."""
    _insert_run(evidence_db)
    before = evidence_db.execute(
        "SELECT prereg_json, eval_decision_json FROM BACKTEST_RUN_LOCAL"
    ).fetchone()
    assert before is not None
    assert before[1] is None

    eval_json = encode_eval_decision(
        observed_value=Decimal("1.6250"),
        edge_distinguishable=True,
        decision_route="promote",
        higher_is_better=True,
    )
    evidence_db.execute(
        "UPDATE BACKTEST_RUN_LOCAL SET eval_decision_json = ? WHERE run_id = ?",
        (eval_json, RUN_ID),
    )
    after = evidence_db.execute(
        "SELECT prereg_json, eval_decision_json FROM BACKTEST_RUN_LOCAL"
    ).fetchone()
    assert after is not None
    assert after[0] == before[0]
    assert after[1] == (
        '{"decision_route":"promote","edge_distinguishable":true,'
        '"higher_is_better":true,"observed_value":1.625}'
    )
    restored = restore_decision_contract(str(after[0]), str(after[1]))
    assert set(restored) == (
        set(DECISION_CONTRACT_KEYS) | set(OPTIONAL_DECISION_CONTRACT_KEYS) | {"decision_route"}
    )
    assert restored["primary_metric"] == "profit_factor"
    assert restored["observed_value"] == 1.625
    assert set(EVAL_DECISION_KEYS) == {
        "observed_value",
        "edge_distinguishable",
        "decision_route",
        "higher_is_better",
    }

    mismatched = encode_eval_decision(
        observed_value=Decimal("1.6250"),
        edge_distinguishable=True,
        decision_route="promote",
        higher_is_better=False,
    )
    with pytest.raises(ValueError, match="authoritative prereg_json"):
        restore_decision_contract(str(after[0]), mismatched)


def test_separate_feature_decision_execution_times_support_post_hoc_audit(
    evidence_db: sqlite3.Connection,
) -> None:
    """Preserve M5's +1 ms order so the integrity query can prove strict order."""
    _insert_run(evidence_db)
    evidence_db.execute(
        """
        INSERT INTO INDICATOR_DEFINITION (
            indicator_key, run_id, indicator_name, impl_version, min_history,
            enabled_reason
        ) VALUES ('ema:period=200', ?, 'ema', '1', 200, 'auto')
        """,
        (RUN_ID,),
    )
    evidence_db.execute(
        """
        INSERT INTO INDICATOR_SNAPSHOT (
            snapshot_seq, run_id, indicator_key, feature_ts, candle_open_time,
            candle_close_time, value
        ) VALUES (1, ?, 'ema:period=200', 1000, 0, 1000, 100.0)
        """,
        (RUN_ID,),
    )
    evidence_db.execute(
        """
        INSERT INTO SIGNAL (
            signal_id, run_id, decision_ts, feature_ts, candle_open_time,
            candle_close_time, symbol, price, confidence, stop_loss, market_type,
            reason, derived_intent, derived_side
        ) VALUES (1, ?, 1000, 1000, 0, 1000, 'BTCUSDT', 100.0, 1.0, 99.0,
                  'futures', 'entry', 'enter', 'LONG')
        """,
        (RUN_ID,),
    )
    evidence_db.execute(
        """
        INSERT INTO DECISION (
            decision_id, run_id, signal_id, decision_ts, action, intended_side,
            intended_qty, stop_price, risk_amount, stop_distance,
            planned_execution_ts
        ) VALUES (1, ?, 1, 1000, 'enter', 'LONG', 1.0, 99.0, 1.0, 1.0, 1001)
        """,
        (RUN_ID,),
    )
    evidence_db.execute(
        """
        INSERT INTO EXECUTION (
            execution_id, run_id, decision_id, order_id, execution_ts, symbol,
            side, position_side, reference_price, price, quantity, notional
        ) VALUES (1, ?, 1, 'order-1', 1001, 'BTCUSDT', 'BUY', 'LONG',
                  10000000000, 10000000000, 100000000, 10000000000)
        """,
        (RUN_ID,),
    )
    assert evidence_db.execute(TIMESTAMP_ORDER_AUDIT_SQL).fetchall() == []

    evidence_db.execute(
        """
        INSERT INTO DECISION (
            decision_id, run_id, decision_ts, action, intended_side,
            intended_qty, stop_price, risk_amount, stop_distance,
            planned_execution_ts
        ) VALUES (2, ?, 1000, 'enter', 'LONG', 1.0, 99.0, 1.0, 1.0, 1001)
        """,
        (RUN_ID,),
    )
    evidence_db.execute(
        """
        INSERT INTO EXECUTION (
            execution_id, run_id, decision_id, order_id, execution_ts, symbol,
            side, position_side, reference_price, price, quantity, notional
        ) VALUES (2, ?, 2, 'order-2', 1000, 'BTCUSDT', 'BUY', 'LONG',
                  10000000000, 10000000000, 100000000, 10000000000)
        """,
        (RUN_ID,),
    )
    assert evidence_db.execute(TIMESTAMP_ORDER_AUDIT_SQL).fetchall() == [("execution", 2)]


def test_writer_contract_columns_match_section_5_3_7(
    evidence_db: sqlite3.Connection,
) -> None:
    """Keep Fill, Trade, and funding facts available to the Evidence adapter."""
    assert WRITER_CONTRACT_COLUMNS == {
        "Fill": {"reference_price", "gap_filled", "qty_truncated"},
        "Trade": {"liquidation_penalty"},
        "FundingSettlement": {
            "settled_at",
            "funding_rate",
            "settle_price",
            "settle_price_source",
            "position_notional",
            "payment_amount",
        },
    }
    assert WRITER_CONTRACT_COLUMNS["Fill"] <= _table_columns(evidence_db, "EXECUTION")
    assert WRITER_CONTRACT_COLUMNS["Trade"] <= _table_columns(evidence_db, "TRADE")
    assert WRITER_CONTRACT_COLUMNS["FundingSettlement"] <= _table_columns(
        evidence_db, "FUNDING_SETTLEMENT"
    )


def test_funding_settlement_allows_nonzero_rate_rounded_to_zero(
    evidence_db: sqlite3.Connection,
) -> None:
    """Allow a valid sub-precision payment to persist as scaled integer zero."""
    _insert_run(evidence_db)
    evidence_db.execute(
        """
        INSERT INTO DECISION (
            decision_id, run_id, decision_ts, action, intended_side,
            intended_qty, planned_execution_ts
        ) VALUES (1, ?, 1000, 'enter', 'LONG', 0.00000001, 1001)
        """,
        (RUN_ID,),
    )
    evidence_db.execute(
        """
        INSERT INTO EXECUTION (
            execution_id, run_id, decision_id, order_id, execution_ts, symbol,
            side, position_side, reference_price, price, quantity, notional
        ) VALUES (1, ?, 1, 'order-1', 1001, 'BTCUSDT', 'BUY', 'LONG',
                  10000000000, 10000000000, 1, 100)
        """,
        (RUN_ID,),
    )
    evidence_db.execute(
        """
        INSERT INTO TRADE (
            trade_id, run_id, backtest_run_id, source_type, symbol, side,
            market_type, entry_execution_id, entry_price, entry_quantity,
            entry_time, leverage, liquidated, strategy_id, strategy_name
        ) VALUES (1, ?, ?, 'backtest', 'BTCUSDT', 'BUY', 'FUTURES',
                  1, 10000000000, 1, 1001, 1, 0, 'fake', 'Fake')
        """,
        (RUN_ID, RUN_ID),
    )
    evidence_db.execute(
        """
        INSERT INTO FUNDING_SETTLEMENT (
            settlement_id, run_id, trade_id, settled_at, symbol, position_side,
            funding_rate, settle_price, position_notional, payment_amount
        ) VALUES (1, ?, 1, 2000, 'BTCUSDT', 'LONG', 0.000001,
                  10000000000, 1, 0)
        """,
        (RUN_ID,),
    )
    assert evidence_db.execute(
        "SELECT payment_amount FROM FUNDING_SETTLEMENT"
    ).fetchone() == (0,)


def test_finding_claim_requires_explicit_nonempty_evidence_references(
    evidence_db: sqlite3.Connection,
) -> None:
    """Keep the M7 claim guard satisfiable by removing its invalid empty default."""
    _insert_run(evidence_db)
    columns = {
        str(row[1]): row
        for row in evidence_db.execute('SELECT * FROM pragma_table_info("FINDING_CLAIM")')
    }
    assert columns["evidence_ref_json"][4] is None
    with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
        evidence_db.execute(
            """
            INSERT INTO FINDING_CLAIM (finding_id, run_id, claim)
            VALUES (1, ?, 'unsupported claim')
            """,
            (RUN_ID,),
        )
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        evidence_db.execute(
            """
            INSERT INTO FINDING_CLAIM (
                finding_id, run_id, claim, evidence_ref_json
            ) VALUES (2, ?, 'unsupported claim', '[]')
            """,
            (RUN_ID,),
        )
