---
name: behavioral-finance
description: Apply this skill when designing signals or risk rules around market psychology in crypto — translating overreaction / underreaction theory into momentum and reversal signals, building a composite sentiment score, detecting positioning extremes for contrarian entries, and applying a cognitive-bias checklist to debias both the strategy and the strategy designer. Use it during strategy design and during design review.
---

# Behavioral Finance Skill

Turns market-psychology theory into testable signals and into a debiasing checklist for the
designer. Core premise: participants deviate from rationality in systematic, partly
predictable ways. Research/design scope. Signal math is `float`; nothing here touches an
order directly.

> Crypto sentiment indicators below are practical proxies, not calibrated constants. Treat
> every threshold as an **unvalidated heuristic** to out-of-sample test
> (`statistical-validation`), not a fact.

## 1. Overreaction and underreaction

**Underreaction → momentum.** Anchoring and conservatism make participants update too
slowly to new information, so a move continues. In crypto: post-listing or post-upgrade
drift, continuation after a funding-flush. Signal: strong recent return + confirmation
(price above a trend filter) → hold for the momentum window.

**Overreaction → reversal.** Representativeness and recency make participants extrapolate a
trend too far; panic and euphoria push price past what fundamentals support. In crypto:
sharp bounces after a liquidation cascade; deeply oversold majors mean-revert. Signal:
extreme short-horizon move against the trend → fade for a short window.

The same instrument shows momentum at one horizon and reversal at another:

| Effect | Horizon | Information type |
|---|---|---|
| Underreaction (momentum) | days–weeks | clear events (listings, upgrades, ETF flows) |
| Overreaction (reversal) | intraday–days, or very long | ambiguous (sentiment, leverage flushes) |

Crypto momentum windows are **shorter** than equities — 24/7 trading and high retail
attention accelerate both the move and its exhaustion.

## 2. Cognitive-bias checklist (debias the strategy)

| Bias | How it shows up in a strategy | Quant detection | Debias |
|---|---|---|---|
| Loss aversion | holding losers, cutting winners early | losing holds 2–3x longer than winning holds | mechanical pre-set stop, executed without override |
| Overconfidence | overtrading, concentration | turnover too high, single-position weight too large | cap trades/period and max position weight |
| Anchoring | anchoring to entry or prior high | clustering of decisions near entry price | use relative valuation/z-scores, not absolute price |
| Confirmation | only reading supporting evidence | single-source signal, ignored counter-signal | force the opposing read (review-agent's job) |
| Recency | overweighting the latest bars | position size driven by last few outcomes | lengthen the evaluation window (≥ 60 bars) |

This table is also a **design-review lens**: the cognitive-bias check is part of the
genius-thinking reflection (TE) loop. Ask whether the design itself encodes one of these
biases.

## 3. Composite sentiment score (crypto proxies)

Build a 0–100 score (50 = neutral) from normalized crypto sentiment inputs. Replace the
A-share retail metrics of the source with crypto-native ones:

| Input | Signal direction |
|---|---|
| Perp funding rate (aggregate) | high positive = greed; deeply negative = fear |
| Open interest vs price | rising OI into a stalling price = leverage buildup |
| Exchange net flows (stablecoin in, coin out) | inflows of stablecoins = dry powder (bullish) |
| Long/short liquidation balance | one-sided liquidations = capitulation extreme |
| A published fear/greed index | direct sentiment proxy |

```
> 80  extreme greed  -> cut exposure
60-80 optimistic     -> normal exposure
40-60 neutral        -> unchanged
20-40 pessimistic    -> add gradually
< 20  extreme fear   -> increase exposure
```

Funding, OI, and flow inputs come from `crypto-derivatives` and the data-agent's queries.

## 4. Contrarian extremes

Require multiple confirmations before acting on a sentiment extreme (any 3+):

```
Extreme-fear (accumulate):
  - aggregate funding deeply negative for several periods
  - one-sided long-liquidation cascade just occurred
  - fear/greed index in its bottom decile
  - stablecoin balances on exchanges rising (dry powder building)

Extreme-greed (de-risk):
  - aggregate funding extremely positive for several periods
  - open interest at a local extreme with price stalling
  - fear/greed index in its top decile
```

Extreme sentiment is rare (a few times a year), so this is a low-frequency overlay, not a
standalone strategy — capacity is limited.

## 5. Behavioral momentum refinements

- Separate sentiment-driven momentum (no fundamental support → reverses) from
  flow/adoption-driven momentum (can persist). Prefer the latter.
- Attention-weighting: when a coin's turnover spikes far above average, shorten the
  momentum holding period — high-attention names reverse faster.
- Combine cross-sectional (relative strength vs peers) and time-series (absolute trend)
  momentum; require both for a full-size signal, half size if only one fires.

## Acceptance checklist

- [ ] Momentum vs reversal horizon stated and matched to the signal
- [ ] Sentiment inputs are crypto-native (funding/OI/flows/index), not equity proxies
- [ ] Contrarian entries require ≥ 3 confirmations
- [ ] Cognitive-bias checklist applied to BOTH the strategy and the design
- [ ] All thresholds marked as heuristics and slated for out-of-sample testing

## Notes

- Behavioral stories are easy to fit after the fact; out-of-sample validation is mandatory.
- Behavioral factors correlate with momentum/reversal factors — control collinearity.
- Crypto regimes shift fast; sentiment thresholds calibrated in one regime decay in the next.

## Related skills

- `genius-thinking` — the TE reflection loop the bias checklist plugs into
- `crypto-derivatives` — funding/OI/flow inputs for the sentiment score
- `statistical-validation` — out-of-sample testing of every threshold
- `risk-and-hedging` — sizing down on greed extremes

---
*Adapted from HKUDS/Vibe-Trading (`behavioral-finance`, MIT). See `skills/ATTRIBUTIONS.md`.*
