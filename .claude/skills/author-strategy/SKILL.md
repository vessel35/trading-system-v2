---
name: author-strategy
description: Turn a written strategy document into a deployed, registered, runnable strategy in trading-system-v2, or into a report of exactly what blocks it. Use when someone hands over a strategy description, a trading-idea write-up, a video transcript summary, or a research design and asks to implement, backtest, or assess whether it can be built here.
---

# Author a Strategy from a Document

The input is a document a person wrote. The output is either a strategy that runs and
appears on the screen, or a report saying what blocks it and what would unblock it.

**Never invent a value the document did not give, and never work around a capability the
platform does not have.** Both produce a backtest that answers a different question than the
one that was asked, and nothing in the result says so.

## 1. Read these before judging anything

1. `docs/strategy-authoring-contract.md`, completely. It owns the rules a strategy must
   follow and it is the only document that overrides this one.
2. `services/core-lib/core_lib/capabilities.py`. It records what the platform can express.
   Read the statements, not just the values.
3. The `develop-trading-strategies` skill, for the ownership boundary between a strategy, a
   money-management policy, and execution.

**Query inventory; do not read it out of a list.** What is registered right now changes
without any platform change, so ask the code:

```python
from core_lib.indicators.registry import build_default_registry
from core_lib.patterns import TALIB_PATTERN_REGISTRY
from trading_plugins.discovery import registered_money_management

{(spec.name, dict(spec.params)) for spec in build_default_registry().list()}
{spec.name for spec in TALIB_PATTERN_REGISTRY.list()}
set(registered_money_management())
```

**Do not infer a capability by reading runtime code.** `core_lib/sizing/exposure_limit.py`
offers `single_market`, `correlation_group`, and `single_direction`, which read like
per-market, per-correlation-group, and per-direction limits. They share one body and the
engine calls each with a single element, so nothing is ever aggregated. That is the kind of
mistake the capability list exists to prevent.

## 2. Turn the document into a structure

Write down, from the document alone: direction rule, entry conditions, exit rules, risk
rules, timeframes, symbol scope, and every series it needs. Record where each came from.

Then find the two kinds of hole:

- **Blank values.** Anything marked `TODO`, or a rule stated in words with no number.
- **Contradictions.** A document that says "1:2 reward" in one place and "1:3" in another,
  or that filters on a closing price and enters on a pullback without defining the distance.

## 3. Classify what blocks it

Sort every blocked requirement into exactly one of three kinds, and report all of them, not
just the first.

| Kind | How to tell | What to do |
|---|---|---|
| Blank value | The document has no number, or says `TODO`. | Ask. Do not choose a value yourself, and do not silently take a "typical" one. |
| Missing material | A needed indicator/parameter combination or pattern is not registered, or is registered under a name whose definition differs. | Report what has to be built first. This is platform work, not strategy work. |
| Missing capability | The document needs something `capabilities.py` records as unsupported. | Report it. Do not route around it. |

**A name in the registry is not a definition.** Indicators pin the standard section they were
ported from and every pattern is a port of TA-Lib 0.7.1, whose rules are stricter and
different from the informal ones documents usually give. `pat_hammer` is not "lower wick at
least twice the body"; it is TA-Lib's `CDLHAMMER`. Check the definition against
`docs/references/technical_indicators_calc_spec.md` and
`docs/references/candlestick_pattern_calc_spec.md` before treating a name as a match.

**A candle is not a series.** Anything computable from the run's own confirmed candles - body
size, wick ratio, the highest high of the last ten bars - is written in the strategy and
needs no registration. Only declare `min_history` large enough to look that far back.

**A new money-management policy is usually not a blockage.** Deploying a policy file is the
normal way to express a protection rule the shipped policies cannot. But the engine requires
every policy to declare exactly one volatility input, so a rule that needs no market input at
all - a fixed-percentage stop, for instance - is a missing capability, not a new file.

## 4. Report a partial answer when there is one

If the document sets out an experiment order, say how far it can be taken today.

**List every deviation and get them approved before implementing.** A step that is feasible
"except that fills land on the next bar rather than the trigger bar's close" is a different
measurement, and the person who wrote the document is the one who decides whether the answer
still counts. Silent substitution produces a number that answers a question nobody asked.

## 5. Ask once

When answers are needed, gather them: what has been settled, what is still unbuilt, and every
question, in one message. Finish everything that does not depend on an answer first.

## 6. Implement

Only with no blockages left, or with the deviations approved.

- Place the strategy in `services/trading-plugins/trading_plugins/strategies/`, and any new
  policy in `.../money_management/`. Declare `STRATEGY_ID` on the class itself.
- Keep entry and exit decisions in the strategy. Protection prices, quantity, and leverage
  belong to the policy; rounding, margin, and liquidation belong to execution.
- Put the code, the registration SQL, and the tests in one changeset. The contract's section
  9 lists the tests, and its closing checklist is the gate.
- Restart the services. A changed file that is already imported keeps its old body.

## 7. Finish at the screen

A strategy that only runs from code is not done. Select it in the interface, run it, and read
its result there. If a parameter needs a screen change, ask whether to fix the value inside
the strategy or widen the screen, and raise the screen work separately.

Then hand the result to `verify-strategy`. Performance never substitutes for verification.
