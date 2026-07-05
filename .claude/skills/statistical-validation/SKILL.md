---
name: statistical-validation
description: Apply this skill when validating backtest results, running gate G6 through G12, building bootstrap confidence intervals, performing walk-forward cross-validation, or correcting for multiple testing.
paths:
  - validation/**/*.md
  - validation/**/*.py
  - backtests/reports/**
  - tests/recompute/**/*.py
---

# Statistical Validation Skill

Operationalizes gates G6 through G12 of the validation matrix. The
validation-auditor agent and the execution-realism-auditor agent both load
this skill.

## 1. Effect size before significance

A statistically significant edge with no economically meaningful effect
size is **not** a tradeable result. Report effect size first.

| Metric | Direction | Floor for promotion | Note |
|---|---|---|---|
| Sharpe ratio (annualized) | higher | `>= 1.0` after costs | use daily returns; annualization factor 252 for crypto-perp daily, 365 for hourly aggregated to daily |
| Sortino ratio | higher | `>= 1.5` after costs | downside deviation in denominator |
| Calmar (return / max drawdown) | higher | `>= 0.5` after costs | use absolute drawdown, not duration |
| Max drawdown | smaller | `<= 30 %` of equity | the §8 circuit breaker is 50 %; promotion floor is stricter |
| Win rate | informational | none | high win rate with low payoff is not edge |
| Profit factor | higher | `>= 1.3` | gross profit / gross loss |

All values are **after** costs (taker, maker, slippage, funding).

## 2. Bootstrap confidence interval (gate G6)

For any reported scalar metric (Sharpe, win rate, mean return), emit a
bootstrap CI. Plain percentile bootstrap is the default; BCa is
acceptable when the metric distribution is visibly skewed.

```python
import numpy as np

def bootstrap_ci(samples: np.ndarray, statistic, n_boot: int = 10_000,
                 alpha: float = 0.05, rng: np.random.Generator | None = None
                 ) -> tuple[float, float, float]:
    rng = rng or np.random.default_rng(seed=42)
    n = len(samples)
    point = statistic(samples)
    draws = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        draws[b] = statistic(samples[idx])
    lo = float(np.quantile(draws, alpha / 2))
    hi = float(np.quantile(draws, 1 - alpha / 2))
    return float(point), lo, hi
```

Reporting rule: every promoted metric in the cycle report carries the
form `value [lo, hi]` (95 % CI). A CI that crosses the no-edge threshold
(Sharpe CI crossing 0, profit factor CI crossing 1) is a FAIL.

## 3. Walk-forward cross-validation (gate G7)

Time-series data violates iid; k-fold shuffle CV is **forbidden** for
strategy validation. Use expanding-window walk-forward:

```text
train [---------------]            test [---]
train [-----------------]          test [---]
train [-------------------]        test [---]
...
```

| Parameter | Default | Note |
|---|---|---|
| Initial train window | 6 months of bars | enough to estimate covariance |
| Test window | 1 month | crypto regimes shift fast |
| Step | 1 month | expanding, not sliding |
| Embargo | 1 bar between train and test | prevents fill leakage |
| Purge | indicator lookback length | drops bars whose features touch the embargo |

The auditor emits a per-fold metric table. The aggregate metric is the
**weighted mean** by test-window length, not a simple mean.

## 4. Shuffle ablation (gate G7 anti-leakage)

A core diagnostic. Build features and signals identically, then shuffle
the **labels** (next-bar return signs). If the strategy still produces a
significant Sharpe, the apparent edge is leakage, not signal.

```python
def shuffle_ablation(df, build_fn, signal_fn, n_runs=30, rng=None):
    rng = rng or np.random.default_rng(seed=42)
    real = run_strategy(df, build_fn, signal_fn)["sharpe"]
    placebo = []
    for _ in range(n_runs):
        shuffled = df.copy()
        shuffled["next_ret"] = rng.permutation(shuffled["next_ret"].values)
        placebo.append(run_strategy(shuffled, build_fn, signal_fn)["sharpe"])
    return real, np.array(placebo)
```

FAIL criterion: real Sharpe falls within the 95 % envelope of the
placebo Sharpe distribution. Promotion requires real strictly above
the placebo 97.5 % quantile.

## 5. p-values are not effect sizes

State p-values explicitly with the test name and degrees of freedom. A
small p with a tiny effect is publication-worthy at best, never
tradeable.

```python
from scipy import stats

# Daily returns vs zero
t_stat, p_val = stats.ttest_1samp(daily_returns, popmean=0.0)
# Report: t = ..., dof = ..., p = ..., effect = mean / sd
```

## 6. Multiple testing correction

If the cycle generates K hypotheses, K parallel tests inflate the false
positive rate. Apply correction:

| Method | When to use | Effect |
|---|---|---|
| Bonferroni | K < 20, conservative | `alpha_per_test = alpha / K` |
| Holm | K up to ~50 | step-down, less conservative than Bonferroni |
| Benjamini-Hochberg (BH) | K > 20, controls FDR | softer; accepts small FDR |

The default for this project is **Bonferroni at K** because the
strategy-selector promotes a small shortlist; a low false positive rate
matters more than power.

```python
from statsmodels.stats.multitest import multipletests

pvals = np.array([h.p for h in hypotheses])
reject, p_adj, _, _ = multipletests(pvals, alpha=0.05, method="bonferroni")
```

## 7. Sharpe / Sortino / Calmar formulas (canonical)

```python
def sharpe(returns: np.ndarray, periods_per_year: int = 252,
           rf_per_period: float = 0.0) -> float:
    excess = returns - rf_per_period
    sd = excess.std(ddof=1)
    return 0.0 if sd == 0 else (excess.mean() / sd) * np.sqrt(periods_per_year)

def sortino(returns: np.ndarray, periods_per_year: int = 252,
            target: float = 0.0) -> float:
    excess = returns - target
    downside = excess[excess < 0]
    dd = np.sqrt((downside ** 2).mean()) if downside.size > 0 else 0.0
    return 0.0 if dd == 0 else (excess.mean() / dd) * np.sqrt(periods_per_year)

def max_drawdown(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    return float(dd.min())  # negative value

def calmar(returns: np.ndarray, equity: np.ndarray,
           periods_per_year: int = 252) -> float:
    ann_return = returns.mean() * periods_per_year
    mdd = abs(max_drawdown(equity))
    return 0.0 if mdd == 0 else ann_return / mdd
```

The validation-auditor's independent recompute uses these formulas
verbatim. Any divergence beyond tolerance is a FAIL.

## 8. Variance-reduction: do not over-fit by tuning the seed

A single seed sweep that "finds" a Sharpe is over-fitting on noise. Run
at least N=10 seeds and report the median plus the IQR. The cycle
report carries the median; a single-seed Sharpe is rejected at the
auditor.

## 9. Sample-size sanity

| Metric | Minimum bars / trades |
|---|---|
| Mean return inference | 250 trades |
| Sharpe inference | 250 trades; CI is wide below this |
| Max drawdown reliability | 1 year of bars at the trading timeframe |
| Walk-forward CV folds | at least 6 folds (e.g. 12 months of test windows) |

Below the floor, the auditor downgrades verdicts to `WARN` and the
metric label carries `[underpowered]`.

## 10. Time-series & regression diagnostics

Net-new methods for strategies that rest on a statistical relationship (pair trading,
volatility timing, factor regressions). All math here is statistical (`float` is fine); it
never touches an order. Needs `statsmodels` (and `arch` for GARCH).

### Stationarity (ADF unit-root test)

Regressing non-stationary series produces spurious results. Test before modeling.

```python
from statsmodels.tsa.stattools import adfuller

def adf_test(series, significance=0.05):
    r = adfuller(series.dropna(), autolag="AIC")
    return {"adf": r[0], "p_value": r[1], "is_stationary": r[1] < significance}
```

Price series are non-stationary → model **log returns** (stationary). `p > 0.10`: difference
and retest. This is the precondition for the cointegration test below.

### Cointegration + half-life (pair trading)

Two non-stationary price series can share a long-run equilibrium; that is the basis of a
pair trade. Engle-Granger two-step:

```python
import numpy as np
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint

def hedge_ratio_and_half_life(y, x):
    score, p_value, _ = coint(y, x)                  # H0: no cointegration
    beta = sm.OLS(y, sm.add_constant(x)).fit().params[1]
    spread = y - beta * x
    lag = spread.shift(1)
    delta = (spread - lag).dropna()
    theta = sm.OLS(delta, sm.add_constant(lag.dropna())).fit().params[1]
    half_life = -np.log(2) / theta                    # mean-reversion speed (bars)
    return {"coint_p": p_value, "hedge_ratio": beta, "half_life": half_life}
```

Trade the spread z-score (`z = (spread - mean) / std`): enter near `|z| > 2`, exit near
`|z| ~ 0`. Cointegration can break down — monitor it continuously, do not assume it persists.
This is the rigorous version of a naive equal-weight pair trade.

### GARCH(1,1) volatility modeling

```python
from arch import arch_model

def fit_garch(returns_pct):                          # returns in percent
    res = arch_model(returns_pct, vol="Garch", p=1, q=1, dist="normal").fit(disp="off")
    a, b = res.params["alpha[1]"], res.params["beta[1]"]
    return {"alpha": a, "beta": b, "persistence": a + b,
            "forecast_vol_5d": np.sqrt(res.forecast(horizon=5).variance.values[-1, :])}
```

`alpha + beta` is volatility persistence (usually 0.95–0.99). For BTC, `alpha` ≈ 0.05–0.20
(shocks matter), `beta` ≈ 0.75–0.90, shocks more symmetric than equities. Forecast accuracy
decays fast beyond 5–10 days. Use EGARCH/GJR-GARCH when down-moves raise vol more than
up-moves.

### Regression diagnostics

When a signal comes from a regression, check the residuals before trusting the coefficients:

| Test | Checks | Fix |
|---|---|---|
| White / Breusch-Pagan | heteroskedasticity | HAC (Newey-West) standard errors |
| Durbin-Watson / Ljung-Box | residual autocorrelation | Newey-West, or add lag terms |
| Variance inflation factor (VIF) | multicollinearity (VIF > 10 severe, > 5 watch) | drop/orthogonalize collinear factors |

Financial residuals are almost always heteroskedastic → use HAC standard errors by default
(`model.fit(cov_type="HAC", cov_kwds={"maxlags": 5})`).

### Granger causality

`grangercausalitytests` tests whether lagged x helps predict y. Note: Granger causality is
**predictive**, not true causality — never present it as a causal claim.

## 11. Acceptance checklist (paste into the audit report)

- [ ] Effect sizes reported before p-values
- [ ] Every scalar metric carries a 95 % bootstrap CI
- [ ] Walk-forward CV used; no shuffled k-fold; embargo and purge applied
- [ ] Shuffle ablation run with ≥ 30 placebo runs
- [ ] Multiple-testing correction stated and applied
- [ ] N ≥ 10 seed runs, median + IQR reported
- [ ] Sample size meets the floor for each claimed inference

## Related skills

- `quant-backtest` — the backtest run from which metrics come
- `decimal-arithmetic-discipline` — the underlying PnL math
- `python` — language-level conventions
