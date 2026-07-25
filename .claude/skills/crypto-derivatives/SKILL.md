---
name: crypto-derivatives
description: Apply this skill when analyzing or designing around crypto derivatives — perpetual funding rates (regime, annualization, carry), spot-futures basis and term structure (contango / backwardation), cash-and-carry delta-neutral trades, cross-exchange funding arbitrage, open-interest × funding signals, and options (Greeks, volatility smile / skew, common structures). Use it to read funding/basis/OI data, design a derivatives strategy, or interpret leverage-positioning signals. Research/backtest scope only.
---

# Crypto Derivatives Skill

Funding rates, basis, and options are the highest-information microstructure signals in
crypto — they reveal real-time leverage positioning and crowd sentiment. Research scope
only; no live execution. Any value that becomes an order size, price, fee, or funding
payment follows `decimal-arithmetic-discipline`.

> Several signal thresholds and historical "probability" figures below are **unvalidated
> heuristics** — treat them as hypotheses to be out-of-sample tested (`statistical-validation`),
> not as established facts.

## 1. Funding rate mechanics

Perpetual futures have no expiry. A funding payment is exchanged between longs and shorts
(every 8h on most venues; some venues use 1h or 4h) to anchor the perp to spot.

```
perp > spot  -> funding positive -> longs pay shorts
perp < spot  -> funding negative -> shorts pay longs
```

Annualize an 8h rate: `annualized = rate_8h * 3 * 365`. So a 0.01% 8h rate ≈ 10.95%/yr.

## 2. Funding-rate signal framework (heuristic)

| 8h funding | Annualized | Positioning | Signal (contrarian) |
|---|---|---|---|
| > +0.05% | > +54.75% | extreme long crowding | reduce longs / fade |
| +0.01% to +0.05% | +11% to +55% | long bias | carry viable |
| -0.01% to +0.01% | -11% to +11% | balanced | neutral |
| < -0.02% | < -21.9% | short crowding | reduce shorts / fade |

Extremely high funding is a **cost** for longs and a sign of crowding, not a bullish
signal. Regime detection from a 7-day history (average + run of consecutive same-sign
periods) classifies `overheated_long` / `bullish_carry` / `neutral` / `bearish_carry` /
`overheated_short`.

## 3. Spot-futures basis

`basis = futures - spot`. For dated futures, annualize: `basis_pct * 365 / days_to_expiry`.

| Annualized basis | State | Read |
|---|---|---|
| > 30% | extreme contango, euphoric leverage | top warning, sell basis |
| 15–30% | elevated contango | carry attractive |
| 5–15% | normal contango | mild bullish |
| < 0% (backwardation) | bearish / forced selling | extreme pessimism, contrarian |

## 4. Cash-and-carry (delta-neutral)

Buy spot + short an equal-notional perp → net delta ~0. PnL comes purely from collecting
positive funding.

```
1. Buy spot (e.g. BTC-USDT)
2. Short equal-notional perp (BTC-USDT-SWAP)
3. Net delta = 0
4. Collect positive funding each cycle
5. Close both legs when funding turns negative or basis compresses
```

Risks: funding can flip negative (carry becomes a cost); the short perp can be liquidated
without enough margin (keep leverage ≤ 3–5x and margin > 50%); exchange counterparty
risk; basis can widen before mean-reverting (mark-to-market loss on the short leg).

## 5. Cross-exchange funding arbitrage

Same asset, different funding across venues. Short the perp on the highest-funding venue,
long it on the lowest. Net carry = the funding spread. Risk is execution cost plus the
rates converging or flipping.

## 6. Open-interest × funding matrix

Combining 24h OI change with funding reads the kind of leverage building:

| OI change | Funding | State |
|---|---|---|
| up > 5% | > +0.03% | leveraged long buildup (squeeze risk) |
| up > 5% | < -0.01% | leveraged short buildup (squeeze risk) |
| down > 5% | > 0 | long liquidation (forced closing) |
| down > 5% | < 0 | short liquidation |

Funding-vs-price divergences are the most useful: new price highs with declining funding =
distribution (bearish divergence); new lows with rising (less negative) funding =
accumulation (bullish divergence).

## 7. Term structure

```
contango:        far > near > spot   (bull / normal)
backwardation:   far < near < spot   (bear / spot shortage, post-crash)
```

Strategies: cash-and-carry (long spot + short future) in significant contango; calendar
spread (long near + short far) expecting contango convergence.

## 8. Options (Deribit dominates BTC/ETH; OKX second)

### Greeks, crypto specifics

- Delta: BTC moves fast, so delta shifts quickly.
- Theta: crypto trades 24/7 — time decay never pauses for weekends.
- Vega: BTC implied volatility is often 50–120%, far above traditional assets.

### Volatility smile / skew

`25-delta risk reversal = IV(25d call) - IV(25d put)`. Usually negative (put IV > call IV,
downside-protection demand); positive in euphoric bull phases. The larger the absolute
value, the steeper the skew.

### Common structures

| Structure | Build | Use when |
|---|---|---|
| Short straddle | sell ATM call + put | IV too high, expect range-bound (collect theta) |
| Protective put | spot + long OTM put | protect a long, willing to pay premium |
| Iron butterfly | sell ATM call+put, buy OTM wings | low-vol expectation, capped risk |
| Vol arbitrage | long/short IV vs realized, delta-hedged | IV ≠ realized vol |

BTC IV reference for vol trades (heuristic): `< 40%` extremely low (long vol),
`60–80%` normal, `> 120%` extremely high (short vol, but tail risk large).

## 9. Strategy selection decision tree

```
high funding (>0.05%) + high IV (>80%)  -> cash-carry + short volatility
low funding + low IV (<50%)             -> stay out of carry + long volatility
significant contango (annualized >20%)  -> cash-and-carry
backwardation                            -> reduce exposure / buy protective puts
```

## Data access

Funding history, current funding, and open interest come from the venue's public API
(e.g. OKX `/api/v5/public/funding-rate-history`, `/funding-rate`, `/open-interest`). In
this harness the data-agent queries the trading databases; report the exact source and the
data_as_of timestamp with any funding/basis reading.

## Acceptance checklist

- [ ] Funding annualized correctly for the venue's settlement period (8h/4h/1h)
- [ ] Extreme funding read as crowding/cost, not as directional confirmation
- [ ] Cash-carry designs state leverage cap, margin floor, and funding-flip exit
- [ ] Any "probability" / threshold cited is marked as an unvalidated heuristic
- [ ] Order/size/funding math is Decimal, not float

## Related skills

- `risk-and-hedging` — option/perp hedges built from these instruments
- `execution-modeling` — funding is a per-cycle cost in the cost model
- `statistical-validation` — out-of-sample testing for the heuristic thresholds
- `decimal-arithmetic-discipline` — Decimal funding/size/price math

---
*Adapted from HKUDS/Vibe-Trading (`perp-funding-basis` + `crypto-derivatives`, MIT). See `skills/ATTRIBUTIONS.md`.*
