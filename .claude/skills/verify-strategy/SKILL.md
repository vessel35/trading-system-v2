---
name: verify-strategy
description: Independently check that an implemented strategy computes what its source document says, by recomputing series, hand-checking decisions, and reconciling Evidence. Use before adopting a strategy, after a backtest has run, or whenever a result needs to be trusted rather than admired.
---

# Verify a Strategy's Calculations

This is a read-only pass. **Do not edit the implementation.** What you find goes back to
`author-strategy` as work, and the verification is redone afterwards.

**Recompute from the document and the contract, never from the implementation.** Reading the
strategy's code and confirming it does what it does proves nothing: the misreading that put a
wrong rule into the code will put the same wrong rule into the check. Take the rule from the
source document, take the definitions from the calculation standards, and derive the expected
number yourself.

**Know the limit of this pass when one session does both jobs.** Deriving values independently
narrows the shared-misreading problem but does not remove it. The independent gate is the
cross-model code review; this procedure does not replace it. Say so in the report rather than
implying more assurance than the pass gives.

## What to check

### 1. The series the strategy consumed

For a handful of bars, recompute each declared series from the candles and the standard that
owns it - `docs/references/technical_indicators_calc_spec.md` for indicators,
`docs/references/candlestick_pattern_calc_spec.md` for patterns - and compare against
`INDICATOR_SNAPSHOT` in the run's Evidence. Check the execution key too: a key carries the
timeframe it was computed on, so `ema:period=200@4h` and `ema:period=200@15m` are different
series and a strategy reading the wrong one still runs.

### 2. Representative decisions

Take one entry and one exit and work them by hand from the document's rule. Confirm the bar
that triggered, the direction, and that a bar the rule excludes did not trigger. A strategy
that enters on every bar its filter allows is easy to confuse with one whose filter never
binds; find a bar where the filter should have blocked an entry and confirm it did.

### 3. Evidence arithmetic

Reconcile, per trade: entry and exit price against the fill records, fees, slippage, funding
settlements, the protection prices the policy produced, and the realized profit. Then check
the run total against the equity curve's last value. A trade that closed on a stop should
show that stop as its exit reference, not a price the rule never named.

### 4. Timing integrity

Confirm the decision timestamp is the deciding bar's close, that the fill is on the following
bar, and that no value used at a decision was finalized after it - especially for a series on
a higher timeframe, where only the last fully closed higher bar may be used. Run the same
configuration twice and confirm the run hash and results are identical.

### 5. Declaration against reality

Confirm that what the class declares, what the registration row says, and what actually ran
agree: the series list, warm-up, supported timeframes, the policy that was attached, and the
policy version recorded in Evidence. Confirm the strategy read every series it declared and
declared every series it read.

## Reporting

State each check as passed or failed with the numbers that show it. A failed check blocks
adoption regardless of the strategy's performance. If a check could not be run, say which and
why; do not report it as passed.
