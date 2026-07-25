---
name: risk-and-hedging
description: Apply this skill when measuring portfolio risk or designing a hedge for a crypto strategy — computing Value-at-Risk (VaR) / Conditional VaR / max drawdown, running a Monte Carlo or historical-scenario stress test, fitting tail risk, calculating a hedge ratio (OLS / minimum-variance / EWMA), choosing a hedge instrument (perp short / options / stablecoin rotation), or judging whether a hedge's cost is worth its protection. Use it for risk-model design and for sanity-checking a backtest's risk profile.
paths:
  - validation/**/*.md
  - validation/**/*.py
  - backtests/reports/**
  - strategies/rules/**/*.md
---

# Risk & Hedging Skill

Two linked jobs: **measure** the risk a strategy carries, then **design** a hedge that
exchanges an unknown loss for a known cost. Core principle: hedging does not remove risk,
it converts it. Backtest/research scope only — no live execution.

Statistical math (VaR quantiles, volatility, regression betas) may use `float`; any value
that becomes an order size, price, or PnL figure follows `decimal-arithmetic-discipline`.

## Part A — Risk measurement

### 1. Value-at-Risk (VaR)

Maximum expected loss over a horizon at a confidence level. Three methods:

| Method | How | Caveat |
|---|---|---|
| Historical simulation | sort historical returns, take the quantile | depends on the sample window |
| Parametric (normal) | `VaR = -(mu + z_alpha * sigma)` | assumes normality — underestimates fat tails |
| Monte Carlo | simulate N paths, take the quantile | compute-heavy |

```python
import numpy as np

def historical_var(returns, confidence=0.95, horizon=1):
    sorted_r = np.sort(returns)
    idx = int((1 - confidence) * len(sorted_r))
    return -sorted_r[idx] * np.sqrt(horizon)  # sqrt-time only valid under iid
```

Crypto returns are fat-tailed; parametric normal VaR **understates** risk. Prefer
historical or Monte Carlo, and report kurtosis alongside.

### 2. Conditional VaR (CVaR / Expected Shortfall)

The mean loss beyond the VaR threshold — more conservative and sub-additive (usable for
portfolio risk decomposition). CVaR is typically 1.3–1.8x VaR.

```python
def historical_cvar(returns, confidence=0.95):
    var = historical_var(returns, confidence)
    tail = returns[returns < -var]
    return -tail.mean() if len(tail) else var
```

### 3. Maximum drawdown

```python
def max_drawdown(equity):
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    return float(dd.min())  # negative
```

Report peak date, trough date, recovery date, and underwater duration — the duration
often hurts a strategy's deployability more than the depth.

### 4. Monte Carlo (geometric Brownian motion)

```python
def monte_carlo_gbm(s0, mu, sigma, days=252, n_paths=10_000, seed=42):
    rng = np.random.default_rng(seed)   # pin the seed — see statistical-validation §8
    dt = 1/252
    z = rng.standard_normal((n_paths, days))
    log_r = (mu - 0.5*sigma**2)*dt + sigma*np.sqrt(dt)*z
    return s0 * np.exp(np.cumsum(log_r, axis=1))
```

Use ≥ 10,000 paths and a pinned seed for reproducibility. GBM understates crypto tails;
treat it as a baseline, not the truth.

### 5. Stress testing

Apply historical or hypothetical shocks to current positions and check the loss against the
risk budget. Crypto historical scenarios worth replaying:

| Scenario | Approx BTC drawdown |
|---|---|
| 2020 COVID liquidity shock (Mar) | ~-50% |
| 2021 May deleveraging | ~-50% |
| 2022 hiking cycle + LUNA/FTX | ~-65% to -77% peak-to-trough |
| Single-day liquidation cascade | -15% to -30% intraday |

Hypothetical shocks (apply to the book): `funding spike`, `stablecoin depeg`,
`exchange outage during a move`, `-30% gap with liquidity evaporation`.

### 6. Tail risk (extreme value theory)

Fit a generalized Pareto distribution to the worst X% of returns; the shape parameter xi
tells you the tail type (`xi > 0` = fat tail = dangerous). Track kurtosis (`>3` = fat
tail; crypto majors are routinely 5–10), skewness, and the tail ratio (worst 5% / best 5%).

## Part B — Hedge design

### 1. Beta hedge (perpetual futures)

Hedge a portfolio's systematic exposure with a short perp while keeping idiosyncratic
alpha. `hedge_notional = beta * portfolio_value`, with beta from OLS of portfolio returns
on the hedge-asset returns. In crypto the natural hedge asset is a BTC or ETH perp.

### 2. Option hedges (Deribit / OKX options)

| Structure | Build | Trade-off |
|---|---|---|
| Protective put | hold spot + long OTM put | premium cost (~1–3%/mo), full downside protection below strike |
| Collar | long OTM put + short OTM call | near zero cost, caps upside |
| Put spread | long higher-strike put + short lower-strike put | cheaper, protects only between strikes |
| Tail hedge | far-OTM put (delta ~ -0.05 to -0.10) | expires worthless most months, large payoff in a crash |

Crypto note: BTC/ETH implied volatility is often 50–120%, far above equities, so option
premiums are expensive — size tail hedges as a small continuous spend, not a large one.

### 3. Cross-asset / stablecoin rotation

Rotating into stablecoins is the crypto cash hedge: it removes market exposure at the cost
of giving up upside. Correlations across alts trend toward 1 in a crash, so diversifying
across coins is a weak hedge exactly when you need it.

### 4. Hedge-ratio methods

```python
from scipy import stats
slope, *_ = stats.linregress(hedge_returns, portfolio_returns)  # OLS
mv = np.cov(portfolio_returns, hedge_returns)[0][1] / np.var(hedge_returns)  # min-variance
# EWMA (RiskMetrics lambda=0.94) for a dynamic hedge that adapts to regime
```

Static (periodic rebalance) hedge → OLS. Dynamic (frequent rebalance) → EWMA.

### 5. Cost-benefit decision

```
expected_loss = expected_loss_without_hedge * prob_of_loss
hedge worth it if  hedge_cost_annual < expected_loss   (plus a tail-risk premium)
```

A hedge slightly more expensive than the expected loss can still be worth it purely for the
tail. State that trade-off explicitly rather than hiding it in a single number.

### 6. Five-step hedge design

1. Identify the risk — systematic (beta) or idiosyncratic (single-coin event)?
2. Choose the instrument — linear (perp) or nonlinear (option)?
3. Calculate the ratio — number of contracts / option size.
4. Evaluate the cost — annualized; acceptable against the budget?
5. Monitor — beta drifts and options expire; re-evaluate at least monthly.

## Acceptance checklist

- [ ] VaR and CVaR both reported (not VaR alone); method stated
- [ ] Fat tails acknowledged — kurtosis reported; parametric-normal VaR not used standalone
- [ ] Stress test covers ≥ 3 historical + 2 hypothetical crypto scenarios
- [ ] Monte Carlo uses ≥ 10k paths and a pinned seed
- [ ] Hedge design states instrument, ratio, method, annualized cost, and the cost-benefit
- [ ] Correlation-goes-to-1-in-crisis caveat addressed for any diversification claim

## Notes

- VaR is not the maximum loss — the tail beyond it can be far worse.
- Correlations observed in calm markets collapse toward 1 in a crash; diversification
  benefit is least available exactly when needed.
- Beta is unstable (lower in rallies, higher in selloffs), so a beta hedge is least
  sufficient precisely when the market falls.
- Tail hedges lose money most of the time; abandoning one because it "feels wasteful" is
  the exact failure mode they protect against.

## Related skills

- `statistical-validation` — bootstrap CIs and seed discipline for the risk metrics
- `crypto-derivatives` — perp/option mechanics the hedges are built from
- `decimal-arithmetic-discipline` — Decimal sizing for any hedge that becomes an order
- `execution-modeling` — the cost of putting a hedge on

---
*Adapted from HKUDS/Vibe-Trading (`risk-analysis` + `hedging-strategy`, MIT). See `skills/ATTRIBUTIONS.md`.*
