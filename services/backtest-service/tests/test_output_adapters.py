"""Verify catalog issuance and complete deterministic Evidence finalization."""

from __future__ import annotations

import hashlib
import json
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
from backtest_service.adapters.evidence_schema import EVIDENCE_SCHEMA_VERSION, encode_eval_decision
from backtest_service.adapters.evidence_sink import BacktestEvidenceSink, EvidenceRecord
from backtest_service.adapters.ohlcv_gaps import OhlcvGapContract
from backtest_service.config.run_config import (
    ManualMoneyManagementConfig,
    TurtleMoneyManagementConfig,
)
from core_lib.money_management import MONEY_MANAGEMENT_SCHEMA_VERSION
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
            {
                "name": "EMA",
                "params": {"period": 9},
                "timeframe": "1h",
                "version": "1.0.0",
            }
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
        "data_quality_criteria_json": {
            "min_coverage_ratio": 0.95,
            "max_consecutive_gap_seconds": 86_400,
        },
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
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
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
                "indicator_key": "ema:period=9@1h",
                "indicator_name": "EMA",
                "params_json": {"period": 9},
                "impl_version": "1.0.0",
                "pinned_impl": True,
                "series_kind": "indicator",
                "category": "trend",
                "impl_note": "fixture implementation",
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
                "indicator_key": "ema:period=9@1h",
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


def test_hash_seals_data_quality_criteria_outside_preregistration(
    tmp_path: Path,
) -> None:
    first, first_hash = _finalize(
        tmp_path / "first",
        "BT_20260101_000001_quality",
        1,
    )
    changed, changed_hash = _finalize(
        tmp_path / "changed",
        "BT_20260102_000002_quality",
        2,
        local_overrides={
            "data_quality_criteria_json": {
                "min_coverage_ratio": 0.96,
                "max_consecutive_gap_seconds": 86_400,
            }
        },
    )

    assert changed_hash != first_hash
    first.close()
    changed.close()


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
            {
                "name": "EMA",
                "params": {"period": 9},
                "timeframe": "1h",
                "version": "1.0.0",
            }
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
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "config_hash": "",
        "profile_ref": "fake-profile",
        "strategy_profile_json": {"family": "breakout"},
        "envelope_status_declared": "provisional",
        "sweep_id": None,
        "fold_label": None,
    }
    values["config_hash"] = normalized_config_hash(values)
    return values


def test_profile_ref_remains_outside_the_config_hash_inputs() -> None:
    values = _run_meta()
    original_hash = normalized_config_hash(values)

    values["profile_ref"] = "a-different-declared-profile"

    assert normalized_config_hash(values) == original_hash


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
    assert "evidence_schema_version" in query
    assert EVIDENCE_SCHEMA_VERSION in params
    assert params[0] == "catalog"
    assert connection.commits == 1
    assert connection.rollbacks == 0


def test_catalog_determinism_reference_filters_by_evidence_schema_version() -> None:
    """Guard SQL text presence only; an ``OR TRUE`` mutation can pass this fake."""

    class DeterminismConnection(_Connection):
        def execute(
            self,
            query: str,
            params: Sequence[object] = (),
        ) -> _Result:
            self.calls.append((query, params))
            if "UPDATE public.backtest_run" in query:
                assert "evidence_schema_version = %s" in query
                assert params == (
                    "b" * 64,
                    "BT_current",
                    EVIDENCE_SCHEMA_VERSION,
                    "b" * 64,
                )
                return _Result([("a" * 64, "b" * 64)])
            if "SELECT run_id, evidence_hash" in query:
                assert "evidence_schema_version <> 'unknown'" in query
                return _Result([("BT_previous", "c" * 64)])
            if "evidence_schema_version = %s" in query:
                assert "evidence_schema_version <> 'unknown'" in query
                return _Result([(True,)])
            if "SELECT EXISTS" in query:
                assert "evidence_schema_version <> 'unknown'" in query
                return _Result([(True,)])
            return _Result([])

    connection = DeterminismConnection()
    store = BacktestCatalogStore(connection)

    reference = store.determinism_reference(
        "BT_current",
        "a" * 64,
        "b" * 64,
        EVIDENCE_SCHEMA_VERSION,
    )

    assert reference.comparison_run_id == "BT_previous"
    assert reference.comparison_hash == "c" * 64
    assert reference.same_config_run_exists is True
    assert reference.same_schema_run_exists is True
    comparison_query, comparison_params = connection.calls[1]
    assert "evidence_schema_version = %s" in comparison_query
    assert comparison_params == (
        "a" * 64,
        "b" * 64,
        EVIDENCE_SCHEMA_VERSION,
        "BT_current",
    )


def test_catalog_records_only_harness_aggregates_on_the_representative() -> None:
    connection = _Connection()
    store = BacktestCatalogStore(connection)

    store.record_harness_aggregate(
        "BT_20260101_000042_catalog",
        oos_degradation=0.25,
        psr=0.96,
        harness_json={"workflow": "overfit_defense", "seed": 29},
    )

    query, params = connection.calls[0]
    assert "UPDATE public.backtest_summary" in query
    assert "RETURNING run_id" in query
    assert params == (
        0.25,
        0.96,
        '{"seed":29,"workflow":"overfit_defense"}',
        "BT_20260101_000042_catalog",
    )
    assert connection.commits == 1
    assert connection.rollbacks == 0


def test_catalog_rejects_a_missing_representative_summary() -> None:
    class MissingSummaryConnection(_Connection):
        def execute(
            self,
            query: str,
            params: Sequence[object] = (),
        ) -> _Result:
            self.calls.append((query, params))
            return _Result([])

    connection = MissingSummaryConnection()
    store = BacktestCatalogStore(connection)

    with pytest.raises(
        RuntimeError,
        match="representative run summary is absent",
    ):
        store.record_harness_aggregate(
            "BT_20260101_999999_missing",
            oos_degradation=None,
            psr=None,
            harness_json={"workflow": "walk_forward"},
        )

    assert connection.commits == 0
    assert connection.rollbacks == 1


def test_catalog_tag_mutations_are_parameterized_and_idempotent() -> None:
    class TagConnection(_Connection):
        def __init__(self) -> None:
            super().__init__()
            self.tag_present = False

        def execute(
            self,
            query: str,
            params: Sequence[object] = (),
        ) -> _Result:
            self.calls.append((query, params))
            if "INSERT INTO public.backtest_tag" in query:
                if self.tag_present:
                    return _Result([])
                self.tag_present = True
                return _Result([(1,)])
            if "DELETE FROM public.backtest_tag" in query:
                if not self.tag_present:
                    return _Result([])
                self.tag_present = False
                return _Result([(1,)])
            return _Result([])

    connection = TagConnection()
    store = BacktestCatalogStore(connection)

    assert store.add_tag("BT_tag", "purpose", "grid-review") is True
    assert store.add_tag("BT_tag", "purpose", "grid-review") is False
    assert store.remove_tag("BT_tag", "purpose", "grid-review") is True
    assert store.remove_tag("BT_tag", "purpose", "grid-review") is False

    assert all(params == ("BT_tag", "purpose", "grid-review") for _, params in connection.calls)
    assert "ON CONFLICT (run_id, tag_type, tag_value) DO NOTHING" in connection.calls[0][0]
    assert connection.commits == 4
    assert connection.rollbacks == 0


# Keyed by MONEY_MANAGEMENT_SCHEMA_VERSION and append-only, like the Evidence pins.
_MONEY_CONFIG_SURFACE: dict[str, str] = {
    "1.0.0": "fb89fc1be12e54134c8027f997b6801f6e3e454fed6944087903ddb442bf0f56",
}


def _money_config_fingerprint() -> str:
    """Fingerprint every name, default, and range a submitted config is read with."""
    surface = {
        mode: {
            name: {
                "default": repr(field.default),
                "constraints": sorted(repr(item) for item in field.metadata),
            }
            for name, field in model.model_fields.items()
        }
        for mode, model in (
            ("manual", ManualMoneyManagementConfig),
            ("turtle", TurtleMoneyManagementConfig),
        )
    }
    blob = json.dumps(surface, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def test_money_config_interpretation_is_pinned_to_its_schema_version() -> None:
    """Catch an interpretation change that the factory's own version would miss.

    A submitted ``money_management`` mapping is read by two layers: these Pydantic
    models fill defaults and enforce ranges first, and only the normalized result
    reaches ``MoneyManagementFactory``. Changing a default here alters what an
    unchanged stored configuration means, while the factory version stays put. The
    version has to name both layers or it names nothing useful.
    """
    expected = _MONEY_CONFIG_SURFACE.get(MONEY_MANAGEMENT_SCHEMA_VERSION)
    assert expected is not None, (
        f"no pinned surface for MONEY_MANAGEMENT_SCHEMA_VERSION "
        f"{MONEY_MANAGEMENT_SCHEMA_VERSION}; add a new entry, do not edit an old one"
    )
    assert _money_config_fingerprint() == expected, (
        "how a submitted money_management config is read changed; bump "
        f"MONEY_MANAGEMENT_SCHEMA_VERSION (now {MONEY_MANAGEMENT_SCHEMA_VERSION}) "
        "and add a new pin entry for it"
    )
