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

Confirm the decision timestamp is not later than the deciding bar's close - the engine refuses
a later one, and an earlier one is allowed - that the fill is on the following bar, and that
no value used at a decision was finalized after it, especially for a series on a higher
timeframe, where only the last fully closed higher bar may be used. Run the same configuration
twice and confirm the run hash and results are identical.

### 5. Declaration against reality

Confirm that what the class declares, what the registration row says, and what actually ran
agree: the series list, warm-up, supported timeframes, the policy that was attached, and the
policy version recorded in Evidence. Confirm the strategy read every series it declared and
declared every series it read.

### 6. The difference table, row by row

Take the strategy document's "원문 대비 차이 기록표" (contract section 6.6) and, for every row,
confirm that the implementation does what the platform-expression column says, with a check
that fits the kind of difference:

- `능력 부재로 강제됨` and `근사함`: show the stand-in rule at work where it differs from the
  source. A cross read as a state must show the re-entries the cross rule would not have made
  (count the entries that followed a stop-out without a new flip); a zero-line condition read on
  the deciding bar must show a bar where the previous-bar reading would have differed, or say
  that none occurred. Confirm the row was approved, or is marked "승인 대기".
- `빈 값을 정함` and `값은 원문대로이나 정의는 채움`: confirm the chosen value or definition is
  the one the code and the Evidence actually used (the period in the series key, the price the
  rule compares, the settings recorded under `money_management_json`).
- `플랫폼 고정`: confirm the capability id exists in `facts capabilities` and that the Evidence
  shows that behavior (the fill on the next bar, protection checked from the bar after the
  fill).
- `차이 없음`: confirm the rule carried over in the representative decisions of check 2.

A row the table lacks for a difference you found is a failure of the table, and a row whose
check cannot be run is reported as not run, never as passed. Confirm the same table is in the
strategy module's docstring.

## Reporting

State each check as passed or failed with the numbers that show it, and list the difference
table's rows with each row's verdict. A failed check blocks adoption regardless of the
strategy's performance. If a check could not be run, say which and why; do not report it as
passed.
