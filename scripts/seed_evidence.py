#!/usr/bin/env python3
"""Create a reproducible, real dry-run Evidence artifact for WebUI development."""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from backtest_service.config import RunConfig
from backtest_service.runner import run_backtest
from core_lib.strategy.adaptees import STRATEGY_ID

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def repository_env() -> dict[str, str]:
    """Read the repository .env without changing or printing process secrets."""

    values = dict(os.environ)
    path = REPOSITORY_ROOT / ".env"
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the real deterministic backtest runner against read-only market/signal "
            "data and write only backtest_db plus var/evidence."
        )
    )
    parser.add_argument("--run-name", default="p1-seed-btc-60d")
    parser.add_argument("--start", default="2025-07-01T00:00:00+00:00")
    parser.add_argument("--days", type=int, default=62)
    parser.add_argument("--seed", type=int, default=976)
    parser.add_argument("--atr-stop-multiple", type=float)
    parser.add_argument("--reward-risk", type=float)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=REPOSITORY_ROOT / "var" / "evidence",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = datetime.fromisoformat(args.start).astimezone(UTC)
    end = start + timedelta(days=args.days)
    params = {
        key: value
        for key, value in {
            "atr_stop_multiple": args.atr_stop_multiple,
            "reward_risk": args.reward_risk,
        }.items()
        if value is not None
    }
    config = RunConfig(
        run_name=args.run_name,
        strategy_id=STRATEGY_ID,
        params=params,
        symbol="BTC/USDT:USDT",
        exchange="binance",
        timeframe="1h",
        market_type="futures",
        data_source="crypto_data.ohlcv_futures",
        start=start,
        end=end,
        initial_capital=Decimal("10000"),
        risk_per_trade=0.01,
        seed=args.seed,
        cost_values={
            "futures_taker_fee_rate": Decimal("0.0004"),
            "futures_entry_slippage_rate": Decimal("0.0005"),
            "exit_slippage_rate": Decimal("0.0001"),
            "funding_fallback_rate": Decimal("0.0001"),
        },
        profile_ref="vessel-reference-v1",
    )
    prereg = {
        "hypothesis": "Reproducible WebUI Evidence seed",
        "primary_metric": "pf",
        "success_threshold": 1.3,
        "failure_threshold": 1.0,
        "edge_distinguishable": True,
        "higher_is_better": True,
        "declared_by": "scripts/seed_evidence.py",
    }
    result = run_backtest(
        config,
        prereg,
        evidence_root=args.evidence_root.resolve(),
        env=repository_env(),
    )
    print(f"run_id={result.run_id}")
    print(f"evidence_path={result.evidence_path}")
    print(f"integrity_status={result.integrity_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
