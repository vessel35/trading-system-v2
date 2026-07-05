---
name: quant-backtest
description: Apply this skill when implementing, reviewing, or debugging quantitative backtests on NautilusTrader 1.225.0+, especially when writing strategies, configuring engines, building features, or guarding against look-ahead bias.
paths:
  - strategies/implementations/**/*.py
  - strategies/rules/**/*.md
  - backtests/**
  - validation/recompute/**/*.py
  - tests/recompute/**/*.py
  - configs/execution-policy.yaml
  - configs/backtest-framework.yaml
---

# Quantitative Backtest Skill

This skill operationalizes CLAUDE.md sections 6, 7, 8, and 15 for any agent
that emits backtest code or audits a backtest run.

## 1. Framework contract (CLAUDE.md §15)

| Item | Value |
|---|---|
| Framework | `nautilus_trader` |
| Minimum version | `1.225.0` (asserted at run start) |
| Python | `>=3.11` |
| Install | `pip install 'nautilus_trader>=1.225.0'` |
| Spec file | `configs/backtest-framework.yaml` |

Vectorized pandas backtests, custom event loops, and ad-hoc PnL math are
**forbidden**. Use the NautilusTrader engine for every backtest.

The version assertion belongs at the entry point of every backtest:

```python
from importlib.metadata import version
from packaging.version import Version

MIN_NT = Version("1.225.0")
NT_VERSION = Version(version("nautilus_trader"))
assert NT_VERSION >= MIN_NT, f"nautilus_trader>={MIN_NT} required, got {NT_VERSION}"
```

Persist `NT_VERSION` to both:
- `backtests/reports/H<NNN>_run<RUN_ID>.json` under `framework_version`
- `backtests/artifacts/H<NNN>_run<RUN_ID>_nt_version.txt`

## 2. Anti-look-ahead (CLAUDE.md §7) — HARD REJECT

The following six patterns are immediate REJECT triggers. The
`lookahead_grep.sh` hook is the local advisory; the validation-auditor
is the authoritative gate.

```python
# REJECT: forward shift by any positive N
y = df["close"].shift(-1)

# REJECT: positive-future-index access on any axis
x = arr.iloc[i + 1]

# REJECT: future-inclusive rolling window
m = s.rolling(window=10, closed="right").mean()  # acceptable
m = s.rolling(window=10, center=True).mean()     # REJECT: center peeks forward

# REJECT: backward fill on feature columns
df["feat"] = df["feat"].fillna(method="bfill")

# REJECT: two-sided interpolation on feature columns
df["feat"] = df["feat"].interpolate(method="polynomial", limit_direction="both")

# REJECT: hardcoded post-hoc datetime filter
df = df[df.index.isin(["2024-06-13", "2024-10-12"])]  # selection-by-hindsight
```

### Signal timing rule (atomic)

1. A signal is computed only **after** the bar closes.
2. An order fills **no earlier than the open** of the bar that follows the
   signal bar, unless the implementation provides an explicit justification
   that the validation-auditor accepts.
3. No future bar data may participate in the signal.
4. The same bar's high or low must not leak into the signal.

Express the rule in code with an explicit `t-1` lag on features:

```python
# Build features for bar t using only data closed at bar t-1
features_t = build_features(df.iloc[: t])  # exclusive upper bound — slice ends at t-1
signal_t   = decide(features_t)            # signal seen at close of bar t-1
fill_price = bar_open(t)                   # order fills at open of bar t
```

## 3. Strategy subclass skeleton

```python
from nautilus_trader.trading.strategy import Strategy, StrategyConfig
from nautilus_trader.model.data import Bar

class MyStrategyConfig(StrategyConfig):
    instrument_id: str
    bar_type: str
    risk_pct: Decimal  # never float

class MyStrategy(Strategy):
    def __init__(self, config: MyStrategyConfig) -> None:
        super().__init__(config)
        self._last_signal_ts = None

    def on_start(self) -> None:
        self.subscribe_bars(self.config.bar_type)

    def on_bar(self, bar: Bar) -> None:
        # Bar.ts_close is the close-time of the bar — use ONLY closed bars
        if not bar.is_revision and bar.ts_close <= self.clock.timestamp_ns():
            self._consider_signal(bar)
```

The strategy never reads `bar.open` or `bar.high` of the **current** bar
inside `on_bar` for decision logic; only `bar.close` of the closed bar.

## 4. BacktestRunConfig + BacktestNode

```python
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.backtest.config import (
    BacktestRunConfig, BacktestEngineConfig,
    BacktestDataConfig, BacktestVenueConfig,
)

run_config = BacktestRunConfig(
    engine=BacktestEngineConfig(
        trader_id="BACKTESTER-001",
        log_level="INFO",
        risk_engine={"bypass": False},          # always enforce
    ),
    data=[
        BacktestDataConfig(
            catalog_path="raw_data/catalog/",
            data_cls="nautilus_trader.model.data:Bar",
            instrument_id="ETHUSDT-PERP.BINANCE",
            start_time=START_TS,
            end_time=END_TS,
        ),
    ],
    venues=[
        BacktestVenueConfig(
            name="BINANCE",
            oms_type="NETTING",
            account_type="MARGIN",
            base_currency="USDT",
            starting_balances=["10_000 USDT"],
        ),
    ],
    strategies=[
        ("my_pkg.strategy:MyStrategy", "my_pkg.strategy:MyStrategyConfig", {...}),
    ],
)

node = BacktestNode(configs=[run_config])
results = node.run()
```

Never instantiate `BacktestEngine` directly with hand-crafted
`add_data()` / `add_venue()` calls in production code. The `BacktestNode`
path guarantees determinism, artifact emission, and the version pin.

## 5. Cost and risk defaults (CLAUDE.md §8) — configurable, never zero

Every backtest must materialize these into the venue and risk configuration.
Defaults (configurable in `configs/execution-policy.yaml`):

| Item | Default | Note |
|---|---|---|
| Taker fee | 0.04 % per side | symmetric on entry and exit |
| Maker fee | 0.02 % per side | applied when post-only fill |
| Slippage per leg | max(1 bp, book impact at >25 % of L1 top) | book impact requires depth data |
| Funding | 8 h cycle, signed | apply at funding-clock time, not bar close |
| Liquidation guard | always on | enforced at sizing time, not after fill |
| Per-trade max loss | per `configs/risk-policy.yaml` | risk-manager owns the value |
| Equity DD circuit breaker | 50 % | trading halts; no re-entry within the run |

Absence of any item is an automatic FAIL at the validation-auditor.

## 6. Determinism (CLAUDE.md §6) — 5 pinned entropy sources

Every run **must** pin all five:

```python
# 1. Random seed
config.seed = seed_from_config()  # from configs/execution-policy.yaml

# 2. Data snapshot — verified at load time
sha = sha256_of_parquet(catalog_path)
assert sha == manifest["data_sha256"], "data drift since manifest"

# 3. Code commit — recorded at run start
git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
if subprocess.call(["git", "diff-index", "--quiet", "HEAD"]) != 0:
    warn("WARN: dirty working tree")  # warning, not fatal

# 4. Library versions
write_artifact(f"H{H_ID}_run{RUN_ID}_pipfreeze.txt",
               subprocess.check_output(["pip", "freeze"]).decode())

# 5. Framework version
write_artifact(f"H{H_ID}_run{RUN_ID}_nt_version.txt", str(NT_VERSION))
```

Missing any one → `[FAILURE]` at gate G5
(`validation/reproducibility-rules.md`).

## 7. ParquetDataCatalog — lazy queries

Always go through the catalog, never read parquet directly inside a
Strategy. Catalog construction is the data-engineer's responsibility:

```python
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from pathlib import Path

catalog = ParquetDataCatalog(path=Path("raw_data/catalog/"))
catalog.write_data(bars, basename_template="bars-{i}")
```

The Strategy code consumes the catalog through `BacktestDataConfig` — it
never opens parquet files.

## 8. Feature engineering — pure function reference

The feature-engineer agent's preferred output is a **pure function**:

```python
def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """No I/O. No global state. No future access. Deterministic given df."""
    out = pd.DataFrame(index=df.index)
    out["sma_20"] = df["close"].rolling(20).mean()
    out["atr_14"] = atr(df["high"], df["low"], df["close"], n=14)
    return out
```

If the team uses a NautilusTrader `Indicator` subclass for production
performance, a pure-function reference implementation under
`validation/recompute/<indicator>.py` is still required (G_CALC reference,
see `decimal-arithmetic-discipline` skill).

## 9. Failure-symptom diagnosis

When a backtest runs but the result looks wrong, classify the symptom before touching code.
Read `backtests/reports/H<NNN>_run<RUN_ID>.json` (metrics) and the equity/trades artifacts,
then map the symptom to its likely root cause:

| Symptom | Likely root cause | Where to look |
|---|---|---|
| `trade_count == 0` | signal-logic bug — entry conditions too strict, signal stuck at 0 | inspect the signal series; is it all zeros? |
| First trade > 2 years after start | data-filter / warmup bug — lookback too long or initial segment dropped | shorten the window; check overly aggressive `dropna` |
| Capital utilization < 50% (mostly flat) | position-sizing bug — triggers too sparse or sizing wrong | signal frequency and the sizing logic |
| Open position at backtest end | exit-timing bug — missing forced flat / exit doesn't cover the tail | exit logic on the final segment |
| `NaN` in the equity series | indicator warmup / gap-fill leaking NaN into PnL | feature build; add explicit fill at source (not `bfill`) |

### Repair discipline

- Fix **one** issue at a time, then re-run — never batch fixes.
- At most **3 repair iterations**; if still failing, escalate with the evidence rather than
  thrashing parameters.
- Fix the bug only; do not change strategy logic to make a run "pass" unless explicitly
  asked (that is the backtest-runner's anti-tuning rule).

### Not-a-code-bug list

If the failure is a data-source condition — empty provider response, `rate limit`,
`API limit`, stale catalog — **do not edit strategy code**. The fix is upstream: refresh
the catalog, check the data SHA against the manifest, or wait out the quota. Editing the
strategy to mask a data problem hides the real defect.

Action items from a diagnosis are concrete: `"Change X from A to B in <file>:<line>"` or
`"Add <guard> after <step>"` — specific to parameter, file, and function, at least two of
them.

## 10. Acceptance checklist (paste into every backtest PR)

- [ ] `nautilus_trader>=1.225.0` asserted at run start
- [ ] 5-tuple entropy pinned (seed, data sha, git sha, pip freeze, NT version)
- [ ] No `shift(-N>0)`, no `iloc[i+1]`, no `rolling(center=True)`, no `bfill`/two-sided interpolate on features
- [ ] Signal computed from closed-bar features; fill at next-bar open
- [ ] Taker, maker, slippage, funding, liquidation guard all set (no zeros)
- [ ] Drawdown circuit breaker present and configured
- [ ] Strategy goes through `BacktestRunConfig` + `BacktestNode`, not raw engine
- [ ] Feature build reachable through both prod path and pure-function reference

## Related skills

- `decimal-arithmetic-discipline` — Decimal-only arithmetic for fees, PnL, indicators
- `statistical-validation` — gate G6–G12 verification procedures
- `python` — language-level conventions and version targets
