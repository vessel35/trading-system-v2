---
name: execution-modeling
description: Apply this skill when modeling trade-execution realism in a crypto backtest — choosing a slippage model (fixed / linear / square-root impact), estimating market-impact cost, setting maker/taker/funding cost assumptions, simulating signal-to-fill delay, or running a cost-sensitivity sweep. Use it whenever a backtest's fill price or cost assumptions need justification, or when reviewing whether a strategy survives realistic transaction costs.
paths:
  - strategies/implementations/**/*.py
  - backtests/**
  - configs/execution-policy.yaml
---

# Execution Modeling Skill

Backtest-only. Makes fills and costs realistic so an edge that exists on paper still exists
after the spread, impact, and funding are paid. An idealized fill (at the close, zero
slippage) produces an over-optimistic backtest that loses money live.

This skill is methodology. The concrete cost defaults and the fill mechanism live in
`quant-backtest` (CLAUDE.md §8, NautilusTrader venue/fill config) and
`configs/execution-policy.yaml`. Money / price / size math here follows
`decimal-arithmetic-discipline` — **never `float` for a cost that touches PnL**.

## 1. Why a slippage model is required

Three real costs are absent from an idealized fill:

1. The order book has a bid-ask spread, so a market order never fills at the mid.
2. A large order walks the book (market impact).
3. There is latency from signal to fill (next-bar execution at the earliest).

A backtest with none of these overstates Sharpe. The execution model restores them.

## 2. Slippage models

### Fixed slippage

A constant haircut in basis points, applied against the trade direction.

```python
from decimal import Decimal

def fixed_slippage(price: Decimal, direction: int, bps: Decimal = Decimal("5")) -> Decimal:
    """direction: +1 buy, -1 sell. bps in basis points (1 bp = 0.01%)."""
    slip = price * bps / Decimal("10000")
    return price + Decimal(direction) * slip
```

Reference assumptions for crypto spot/perp (good liquidity venues such as Binance/OKX):

| Instrument | Suggested fixed slippage (bps) |
|---|---|
| BTC perp / spot (BTC-USDT) | 2–5 |
| ETH perp / spot (ETH-USDT) | 3–8 |
| Large-cap alts (top ~20) | 8–20 |
| Small-cap alts | 20–50+ (thin books, varies widely) |

Use fixed slippage only when the order is small relative to liquidity (see §3).

### Linear impact

Impact proportional to participation, the order size over average daily volume (ADV).

```python
def linear_impact(price: Decimal, direction: int, qty: Decimal, adv: Decimal,
                  coeff: Decimal = Decimal("0.1")) -> Decimal:
    participation = qty / adv
    impact = coeff * participation
    return price * (Decimal(1) + Decimal(direction) * impact)
```

Crypto `coeff` is typically 0.05–0.15 (24/7 volume is dispersed across the day).

### Square-root impact (Almgren-Chriss)

The academically best-supported form: `impact = eta * sigma * sqrt(qty / adv)`. Marginal
impact declines for larger orders, and the parameters can be fit from history.

```python
import numpy as np  # statistical estimation only — not an order-touching value

def sqrt_impact(price: Decimal, direction: int, qty: Decimal, adv: Decimal,
                daily_vol: Decimal, eta: Decimal = Decimal("0.5")) -> Decimal:
    participation = float(qty / adv)
    impact = eta * daily_vol * Decimal(str(np.sqrt(participation)))
    return price * (Decimal(1) + Decimal(direction) * impact)
```

`eta` is usually 0.3–0.8. `daily_vol` is the daily return standard deviation.

### Model selection decision tree

```
order notional vs the instrument's ADV:
  < 0.5% of ADV     -> fixed slippage (5 bps) is enough
  0.5% – 5% of ADV  -> linear impact model
  > 5% of ADV       -> square-root impact model (required)
```

A backtest that trades > 5% of ADV per order and still assumes fixed slippage is
producing fantasy fills. Flag it.

## 3. Signal-to-fill delay

Crypto trades continuously, so there is no T+1 rule, but a signal computed at a bar close
still cannot fill before the next bar opens. Model the delay explicitly (this is the same
next-bar-open rule enforced in `quant-backtest` §2).

```python
def delayed_signal(signal, delay_bars: int = 1):
    """delay_bars=1: fill at the open of the bar after the signal bar."""
    return signal.shift(delay_bars)
```

`delay_bars=0` is only defensible for a strategy that decides intrabar and fills within the
same bar with an explicit justification accepted by review.

## 4. Integrated transaction cost

```
total cost = explicit (maker/taker fee) + implicit (spread + impact)
```

Crypto reference (align exact numbers with `configs/execution-policy.yaml`):

| Cost item | Crypto perp (typical) |
|---|---|
| Taker fee (per side) | ~0.04% |
| Maker fee (per side) | ~0.02% (post-only fills) |
| Bid-ask spread | 0.01–0.05% on majors |
| Funding | 8h cycle, signed — see `crypto-derivatives` |
| Round-trip all-in (majors) | ~0.1–0.2% |

These mirror the `quant-backtest` cost defaults; do not set any of them to zero.

## 5. Cost-sensitivity sweep

Never report a single-slippage backtest. Sweep slippage and show the metric decay — it
tells you how much edge is cost-margin versus real.

```markdown
| Slippage (bps) | Annual return | Sharpe | Max DD |
|---|---|---|---|
| 0 (ideal)  | 15.2% | 1.35 | -18.5% |
| 5          | 12.9% | 1.15 | -19.2% |
| 10         | 11.1% | 0.98 | -19.8% |
| 20         | 7.5%  | 0.65 | -20.5% |
```

If the strategy's Sharpe falls below the `statistical-validation` promotion floor (1.0) at
a realistic slippage for its order size, it is not promotable.

### Annual cost-drag estimate

```
annual turnover     = annual round-trip count
annual cost drag    = annual turnover * round-trip all-in cost
net return          = gross return - annual cost drag
```

Example: 12 round trips/year at 0.15% = 1.8% drag. If gross return is 5%, costs eat
36% of it — a high-turnover edge can be entirely fee.

## 6. Acceptance checklist (paste into the review)

- [ ] Slippage model matches order size vs ADV (fixed / linear / sqrt per §2 tree)
- [ ] Maker/taker/spread/funding all non-zero and sourced from execution-policy.yaml
- [ ] Fill is next-bar-open (or delay justified and accepted)
- [ ] Order notional vs ADV stated; > 5% uses square-root impact
- [ ] Cost-sensitivity sweep included; edge survives realistic slippage
- [ ] All cost/price math is Decimal, not float

## Related skills

- `quant-backtest` — the NautilusTrader fill model, venue config, and §8 cost defaults
- `decimal-arithmetic-discipline` — Decimal-only cost / price arithmetic
- `crypto-derivatives` — funding-rate cost for perpetual positions
- `statistical-validation` — promotion floors the cost-adjusted metrics must clear

---
*Adapted from HKUDS/Vibe-Trading (`execution-model`, MIT). See `skills/ATTRIBUTIONS.md`.*
