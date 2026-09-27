"""Run the document-sourced strategies through the Engine on a synthetic feed.

This is the stage 3-1 acceptance regression: a strategy placed as a file, with the policy it
declares, must load through the deployed-plugin registry, trade, and leave complete Evidence,
without touching a database. The synthetic feed, the in-memory catalog, the discovery-based
registration rows, and the run configuration live in
``backtest_service.diagnostics.synthetic_dry_run`` (design
``docs/fullspec/author_check_and_scaffold_design.md`` section 3.4.1); this module keeps only
the expectations the four strategies were accepted against.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from backtest_service.diagnostics.synthetic_dry_run import run_strategy as _dry_run_strategy
from backtest_service.engine import RunResult

_STRATEGIES = (
    "supertrend-ema200-flip",
    "macd-ema200-zero-line",
    "bollinger-rsi-reversion",
    "donchian-breakout-atr",
)
# The longest declared warm-up: EMA 200 for the two trend strategies, Bollinger 20 for the
# reversion strategy, and the 21 bars the breakout strategy reads back from the candles.
_EXPECTED_WARMUP = {
    "supertrend-ema200-flip": 200,
    "macd-ema200-zero-line": 200,
    "bollinger-rsi-reversion": 20,
    "donchian-breakout-atr": 21,
}
# Strategies whose document leaves every exit to the policy's stop and target.
_PROTECTION_ONLY = {"macd-ema200-zero-line", "donchian-breakout-atr"}
_MONEY_MANAGEMENT: dict[str, dict[str, object]] = {
    "supertrend-ema200-flip": {
        "mode": "signal-exit-atr",
        "atr_period": 14,
        "atr_stop_multiple": 2.5,
        "leverage_cap": 5,
    },
    "macd-ema200-zero-line": {
        "mode": "manual",
        "leverage": 1,
        "reward_risk": 1.5,
        "atr_stop_multiple": 2.5,
    },
    "bollinger-rsi-reversion": {
        "mode": "signal-exit-atr",
        "atr_period": 14,
        "atr_stop_multiple": 2.5,
        "leverage_cap": 5,
    },
    "donchian-breakout-atr": {
        "mode": "manual",
        "leverage": 1,
        "reward_risk": 2.0,
        "atr_stop_multiple": 1.5,
    },
}
_DECLARED_KEYS: dict[str, set[str]] = {
    "supertrend-ema200-flip": {"supertrend:multiplier=3,period=10@1h", "ema:period=200@1h"},
    "macd-ema200-zero-line": {
        "macd:fast_period=12,signal_period=9,slow_period=26@1h",
        "ema:period=200@1h",
    },
    "bollinger-rsi-reversion": {
        "bollinger_bands:multiplier=2,period=20@1h",
        "rsi:period=14@1h",
    },
    # The breakout strategy declares no series; only the policy's ATR reaches the run.
    "donchian-breakout-atr": set(),
}


def run_strategy(strategy_id: str, root: Path, *, run_name: str | None = None) -> RunResult:
    """Run one accepted strategy with the settings it was accepted under."""
    return _dry_run_strategy(strategy_id, _MONEY_MANAGEMENT[strategy_id], root, run_name=run_name)


def _rows(path: str, query: str) -> list[tuple[object, ...]]:
    with sqlite3.connect(path) as connection:
        return connection.execute(query).fetchall()


@pytest.mark.parametrize("strategy_id", sorted(_STRATEGIES))
def test_document_sourced_strategy_runs_end_to_end_with_complete_evidence(
    tmp_path: Path, strategy_id: str
) -> None:
    result = run_strategy(strategy_id, tmp_path / "first")
    assert result.integrity_status == "passed"

    definitions = _rows(result.evidence_path, "SELECT indicator_key FROM INDICATOR_DEFINITION")
    defined = {row[0] for row in definitions}
    assert _DECLARED_KEYS[strategy_id] <= defined
    assert "atr:period=14@1h" in defined

    (local,) = _rows(
        result.evidence_path,
        "SELECT strategy_id, money_management_json, warmup_candles FROM BACKTEST_RUN_LOCAL",
    )
    assert local[0] == strategy_id
    assert str(_MONEY_MANAGEMENT[strategy_id]["mode"]) in str(local[1])
    assert local[2] == _EXPECTED_WARMUP[strategy_id]

    trades = _rows(
        result.evidence_path,
        "SELECT side, exit_reason, entry_price, exit_price, net_pnl FROM TRADE ORDER BY entry_time",
    )
    assert trades, "the synthetic path must produce at least one trade"
    exit_reasons = {row[1] for row in trades}
    if strategy_id in _PROTECTION_ONLY:
        assert exit_reasons <= {"STOP_LOSS", "TAKE_PROFIT", "END_OF_DATA"}
        assert exit_reasons & {"STOP_LOSS", "TAKE_PROFIT"}
    else:
        assert "SIGNAL_EXIT" in exit_reasons

    skip_reasons = {
        row[0]
        for row in _rows(
            result.evidence_path,
            "SELECT DISTINCT skip_reason FROM DECISION WHERE action = 'skip'",
        )
    }
    assert skip_reasons, "held and filtered bars must leave their reasons"

    again = run_strategy(strategy_id, tmp_path / "second", run_name=f"again-{strategy_id}")
    assert again.evidence_hash == result.evidence_hash
    assert again.integrity_status == "passed"


def test_the_three_strategies_trade_differently_on_the_same_path(tmp_path: Path) -> None:
    counts = {}
    for strategy_id in _STRATEGIES:
        result = run_strategy(strategy_id, tmp_path / strategy_id)
        counts[strategy_id] = len(_rows(result.evidence_path, "SELECT trade_id FROM TRADE"))
    assert all(count >= 1 for count in counts.values()), counts
    assert len(set(counts.values())) >= 2, counts
