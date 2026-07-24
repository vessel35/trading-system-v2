"""Verify catalog issuance and complete deterministic Evidence finalization."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from backtest_service.adapters.catalog_store import (
    BacktestCatalogStore,
    normalized_config_hash,
)
from backtest_service.adapters.evidence_schema import encode_eval_decision
from backtest_service.adapters.evidence_sink import BacktestEvidenceSink, EvidenceRecord
from backtest_service.adapters.ohlcv_gaps import OhlcvGapContract
from core_lib.ports import CatalogStore, EvidenceSink


def _local_values(run_seq: int) -> dict[str, object]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return {
        "run_seq": run_seq,
        "run_name": "determinism",
        "strategy_id": "fake-breakout",
        "strategy_name": "FakeBreakout",
        "strategy_version": "1.0.0",
        "params_json": {"period": 20},
        "resolved_indicators_json": [
            {"name": "EMA", "params": {"period": 9}, "version": "1.0.0"}
        ],
        "params_schema_version": "1.0.0",
        "symbol": "BTCUSDT",
        "exchange": "binance",
        "timeframe": "1h",
        "market_type": "futures",
        "period_start": start,
        "period_end": start + timedelta(hours=1),
        "warmup_candles": 20,
        "indicator_mode": "auto",
        "trigger_feed": "tf_candle",
        "fill_timing": "next_bar",
        "initial_capital": Decimal("10000"),
        "sizing_method": "risk_based",
        "risk_per_trade": 0.01,
        "framework_compliant": True,
        "cost_values_json": {"fee": Decimal("0.0005")},
        "seed": 7,
        "engine_version": "1.0.0",
        "core_lib_version": "0.1.0",
        "config_hash": "a" * 64,
        "profile_ref": "fake-profile",
        "strategy_profile_json": {"family": "breakout"},
        "envelope_status_declared": "provisional",
        "prereg_json": {
            "primary_metric": "pf",
            "success_threshold": 1.3,
            "failure_threshold": 1.0,
            "edge_distinguishable": True,
            "higher_is_better": True,
        },
        "evidence_schema_version": "1.0.0",
    }


def _portfolio_values() -> dict[str, object]:
    return {
        "equity_seq": 1,
        "ts": datetime(2026, 1, 1, 1, tzinfo=UTC),
        "cash_balance": Decimal("10000"),
        "position_value": Decimal("0"),
        "total_equity": Decimal("10000"),
        "unrealized_pnl": Decimal("0"),
        "fee_cum": Decimal("0"),
        "slippage_cum": Decimal("0"),
        "funding_cum": Decimal("0"),
        "peak_equity": Decimal("10000"),
        "drawdown_pct": 0.0,
        "open_positions": 0,
    }


def _finalize(
    root: Path,
    run_id: str,
    run_seq: int,
    *,
    decision_route: str = "promote",
    local_overrides: dict[str, object] | None = None,
) -> tuple[BacktestEvidenceSink, str]:
    sink = BacktestEvidenceSink(root)
    sink.bind(run_id)
    origin_hash = "e" * 64
    hourly_contract = OhlcvGapContract(
        timeframe_ms=3_600_000,
        normal_gap_close_times=(),
        partial_bucket_close_times=(),
        evaluation_grid_gap_close_times=(),
        origin_validation_status="verified",
        origin_minute_row_count=60,
        origin_timestamp_hash=origin_hash,
    )
    minute_contract = OhlcvGapContract(
        timeframe_ms=60_000,
        normal_gap_close_times=(),
        partial_bucket_close_times=(),
        evaluation_grid_gap_close_times=(),
        origin_validation_status="verified",
        origin_minute_row_count=60,
        origin_timestamp_hash=origin_hash,
    )
    local_values = _local_values(run_seq)
    local_values.update({} if local_overrides is None else local_overrides)
    sink.record(EvidenceRecord("BACKTEST_RUN_LOCAL", local_values))
    sink.record(
        EvidenceRecord(
            "SOURCE_DATA_SNAPSHOT",
            {
                "snapshot_id": 1,
                "source_kind": "ohlcv",
                "source_ref": "fixture",
                "symbol": "BTCUSDT",
                "exchange": "binance",
                "timeframe": "1h",
                "range_start": datetime(2026, 1, 1, tzinfo=UTC),
                "range_end": datetime(2026, 1, 1, 1, tzinfo=UTC),
                "row_count": 1,
                "content_hash": "b" * 64,
                "note": hourly_contract.encode(),
            },
        )
    )
    sink.record(
        EvidenceRecord(
            "SOURCE_DATA_SNAPSHOT",
            {
                "snapshot_id": 2,
                "source_kind": "ohlcv",
                "source_ref": "fixture",
                "symbol": "BTCUSDT",
                "exchange": "binance",
                "timeframe": "1m",
                "range_start": datetime(2026, 1, 1, tzinfo=UTC),
                "range_end": datetime(2026, 1, 1, 1, tzinfo=UTC),
                "row_count": 60,
                "content_hash": "d" * 64,
                "note": minute_contract.encode(),
            },
        )
    )
    sink.record(
        EvidenceRecord(
            "SOURCE_DATA_SNAPSHOT",
            {
                "snapshot_id": 3,
                "source_kind": "funding",
                "source_ref": "fixture",
                "symbol": "BTCUSDT",
                "exchange": "binance",
                "timeframe": None,
                "range_start": datetime(2026, 1, 1, tzinfo=UTC),
                "range_end": datetime(2026, 1, 1, 1, tzinfo=UTC),
                "row_count": 0,
                "content_hash": "c" * 64,
            },
        )
    )
    sink.record(
        EvidenceRecord(
            "INDICATOR_DEFINITION",
            {
                "indicator_key": "ema:period=9",
                "indicator_name": "EMA",
                "params_json": {"period": 9},
                "impl_version": "1.0.0",
                "pinned_impl": True,
                "min_history": 9,
                "computation_mode": "incremental",
                "enabled_reason": "auto",
            },
        )
    )
    sink.record(
        EvidenceRecord(
            "INDICATOR_SNAPSHOT",
            {
                "snapshot_seq": 1,
                "indicator_key": "ema:period=9",
                "feature_ts": datetime(2026, 1, 1, 1, tzinfo=UTC),
                "candle_open_time": datetime(2026, 1, 1, tzinfo=UTC),
                "candle_close_time": datetime(2026, 1, 1, 1, tzinfo=UTC),
                "value": 100.0,
                "is_warmup": False,
            },
        )
    )
    sink.record(EvidenceRecord("PORTFOLIO_PNL", _portfolio_values()))
    sink.set_eval_decision(
        encode_eval_decision(
            observed_value=1.5,
            edge_distinguishable=True,
            decision_route=decision_route,
            higher_is_better=True,
        )
    )
    return sink, sink.finalize(run_id)


def test_evidence_finalize_writes_complete_integrity_and_is_strict(
    tmp_path: Path,
) -> None:
    sink, evidence_hash = _finalize(
        tmp_path,
        "BT_20260101_000001_determinism",
        1,
    )

    assert isinstance(sink, EvidenceSink)
    assert len(evidence_hash) == 64
    assert sink.integrity_results == {
        "accounting_identity": True,
        "timestamp_order": True,
        "cost_once": True,
        "net_of_cost": True,
        "deterministic": True,
        "evidence_complete": True,
    }
    rows = sink.connection.execute(
        "SELECT check_name, passed FROM INTEGRITY_CHECK ORDER BY check_name"
    ).fetchall()
    assert len(rows) == 6
    with sqlite3.connect(sink.path or "") as second:
        assert second.execute("SELECT COUNT(*) FROM CHART_SUMMARY").fetchone() == (2,)
    sink.close()


def test_hash_ignores_only_instance_identity_and_keeps_logical_decision(
    tmp_path: Path,
) -> None:
    first, first_hash = _finalize(
        tmp_path / "one",
        "BT_20260101_000001_determinism",
        1,
    )
    second, second_hash = _finalize(
        tmp_path / "two",
        "BT_20260102_1234567_determinism",
        1_234_567,
        local_overrides={"run_name": "human-label"},
    )
    changed, changed_hash = _finalize(
        tmp_path / "three",
        "BT_20260103_000003_determinism",
        3,
        decision_route="retest",
    )
    logical_change, logical_change_hash = _finalize(
        tmp_path / "four",
        "BT_20260104_000004_determinism",
        4,
        local_overrides={"symbol": "ETHUSDT", "config_hash": "b" * 64},
    )

    assert first_hash == second_hash
    assert changed_hash != first_hash
    assert logical_change_hash != first_hash
    first.close()
    second.close()
    changed.close()
    logical_change.close()


def test_hash_ignores_prereg_wording_when_eval_decision_is_unchanged(
    tmp_path: Path,
) -> None:
    """Keep declaration prose outside the logical-result hash."""
    first, first_hash = _finalize(
        tmp_path / "one",
        "BT_20260101_000001_prereg-one",
        1,
        local_overrides={
            "prereg_json": {
                **cast(dict[str, object], _local_values(1)["prereg_json"]),
                "hypothesis": "EMA crossover should exceed the declared edge",
            }
        },
    )
    second, second_hash = _finalize(
        tmp_path / "two",
        "BT_20260102_000002_prereg-two",
        2,
        local_overrides={
            "prereg_json": {
                **cast(dict[str, object], _local_values(2)["prereg_json"]),
                "hypothesis": "Reworded declaration with the same decision criteria",
            }
        },
    )

    assert first_hash == second_hash
    first_payload = first.connection.execute(
        "SELECT prereg_json, eval_decision_json FROM BACKTEST_RUN_LOCAL"
    ).fetchone()
    second_payload = second.connection.execute(
        "SELECT prereg_json, eval_decision_json FROM BACKTEST_RUN_LOCAL"
    ).fetchone()
    assert first_payload is not None
    assert second_payload is not None
    assert first_payload[0] != second_payload[0]
    assert first_payload[1] == second_payload[1]
    first.close()
    second.close()


def test_eval_decision_rejects_noncanonical_or_incomplete_json(tmp_path: Path) -> None:
    sink = BacktestEvidenceSink(tmp_path)
    sink.bind("BT_20260101_000001_canonical")
    sink.record(EvidenceRecord("BACKTEST_RUN_LOCAL", _local_values(1)))

    with pytest.raises(ValueError, match="canonical"):
        sink.set_eval_decision(
            '{"observed_value": 1.5, "edge_distinguishable": true, '
            '"decision_route": "promote", "higher_is_better": true}'
        )
    with pytest.raises(ValueError, match="exactly"):
        sink.set_eval_decision('{"observed_value":1.5}')
    sink.close()


class _Result:
    def __init__(self, rows: list[Sequence[object]]) -> None:
        self._rows = iter(rows)

    def fetchone(self) -> Sequence[object] | None:
        return next(self._rows, None)


class _Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Sequence[object]]] = []
        self.commits = 0
        self.rollbacks = 0

    def execute(
        self,
        query: str,
        params: Sequence[object] = (),
    ) -> _Result:
        self.calls.append((query, params))
        if "RETURNING run_id" in query:
            return _Result([("BT_20260101_000042_catalog",)])
        return _Result([])

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _run_meta() -> dict[str, object]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    values: dict[str, object] = {
        "run_name": "catalog",
        "strategy_id": "fake-breakout",
        "strategy_name": "FakeBreakout",
        "strategy_version": "1.0.0",
        "params_json": {"period": 20},
        "resolved_indicators_json": [
            {"name": "EMA", "params": {"period": 9}, "version": "1.0.0"}
        ],
        "params_schema_version": "1.0.0",
        "symbol": "BTCUSDT",
        "exchange": "binance",
        "timeframe": "1h",
        "market_type": "FUTURES",
        "period_start": start,
        "period_end": start + timedelta(days=1),
        "warmup_start": None,
        "warmup_candles": 20,
        "data_source": "crypto_data",
        "indicator_mode": "auto",
        "trigger_feed": "tf_candle",
        "fill_timing": "next_bar",
        "initial_capital": Decimal("10000"),
        "sizing_method": "risk_based",
        "risk_per_trade": 0.01,
        "position_size_pct": None,
        "framework_compliant": True,
        "cost_values_json": {},
        "seed": 0,
        "engine_version": "1.0.0",
        "core_lib_version": "0.1.0",
        "config_hash": "",
        "profile_ref": "fake-profile",
        "strategy_profile_json": {"family": "breakout"},
        "envelope_status_declared": "provisional",
        "sweep_id": None,
        "fold_label": None,
    }
    values["config_hash"] = normalized_config_hash(values)
    return values


def test_catalog_register_uses_one_sequence_cte_before_any_filename() -> None:
    connection = _Connection()
    store = BacktestCatalogStore(connection)

    run_id = store.register(_run_meta())

    assert isinstance(store, CatalogStore)
    assert run_id == "BT_20260101_000042_catalog"
    query, params = connection.calls[0]
    assert "nextval('public.backtest_run_seq')" in query
    assert "greatest(6, length(run_seq::text))" in query
    assert "evidence_path" in query
    assert params[0] == "catalog"
    assert connection.commits == 1
    assert connection.rollbacks == 0
