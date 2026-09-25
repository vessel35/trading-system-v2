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
2. The recorded platform capability list. Query it with the command below, and read the
   statements, not just the values.
3. The `develop-trading-strategies` skill, for the ownership boundary between a strategy, a
   money-management policy, and execution.

These commands are the interface this procedure relies on. They call the facts module
directly, and no long-running server is required.

```console
.venv/bin/python -m trading_plugins.facts capabilities
```

**Query inventory; do not read it out of a list.** What is registered or deployed right now
changes without any platform change, so ask the code:

```console
.venv/bin/python -m trading_plugins.facts series
.venv/bin/python -m trading_plugins.facts deployed strategy
.venv/bin/python -m trading_plugins.facts deployed money_management
.venv/bin/python -m trading_plugins.facts declaration strategy <deployed-strategy-identifier>
.venv/bin/python -m trading_plugins.facts declaration money_management <deployed-money-management-identifier>
```

Use the identifier returned by the matching `deployed` lookup when reading a declaration.
The final two commands use identifiers from the current deployed inventory.

**Do not infer a capability by reading runtime code.** `core_lib/sizing/exposure_limit.py`
offers `single_market`, `correlation_group`, and `single_direction`, which read like
per-market, per-correlation-group, and per-direction limits. They share one body and the
engine calls each with a single element, so nothing is ever aggregated. That is the kind of
mistake the capability list exists to prevent.

## 2. Turn the document into a structure

Write down, from the document alone: direction rule, entry conditions, exit rules, risk
rules, timeframes, symbol scope, and every series it needs. Record where each came from:
the page and the sentence. A sentence that belongs to a study-wide description or to another
page of the same source is not a statement of this strategy's page; mark it as such rather
than presenting it as the page's own claim.

Then write down two more things the document never states but the implementation will carry:

- **Profile values.** `StrategyProfile` has twelve fields (expected win rate, expected payoff,
  tail shape, holding horizon, primary metric, and the rest). Every one of them is a blank the
  author fills. Take what the source's reported results support (a reported win rate and
  profit factor bound the expected win rate and payoff) and say which values were chosen
  without support. Record each in the difference table.
- **Platform-fixed rules.** Read the capability list for every rule that changes what the
  backtest measures: when a decision fills (`run.fill_timing`), from which bar protection is
  checked (`execution.protection_checked_from_bar_after_fill`), what happens when stop and
  target are touched in one bar (`execution.simultaneous_stop_and_target`), how many positions
  a run holds (`run.concurrent_directional_positions`), and how much series history a strategy
  sees. Record each with its capability id. Where the source fixes the same thing differently,
  it is a difference, not a platform detail.

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

**A name in the registry is not a definition.** Read a deployed plugin's `declaration` to find
the registry names it declares, then query each name with `series <name>`. The series lookup
carries the pinned adoption record for an indicator. For a pattern, it says that the
candlestick calculation standard still has to be read. Indicators pin the standard section
they were ported from and every pattern is a port of TA-Lib 0.7.1, whose rules are stricter
and different from the informal ones documents usually give. `pat_hammer` is not "lower wick
at least twice the body"; it is TA-Lib's `CDLHAMMER`. Check the definition against
`docs/references/technical_indicators_calc_spec.md` and
`docs/references/candlestick_pattern_calc_spec.md` before treating a name as a match.

**A candle is not a series, but this is a narrow allowance.** A comparison of raw candle
values - this bar's body against its wicks, the highest high of the last ten bars, the gap
between two closes - is written in the strategy and needs no registration; declare
`min_history` large enough to look that far back. **Never recompute a registered indicator or
pattern inside a strategy.** If the rule is an EMA, an ATR, a Stochastic RSI, or a named
candlestick pattern, declare it and read it, even when the formula looks short enough to
inline. Reimplementing one puts a second definition of the same thing in the repository, and
the two drift without anything failing. When the document's rule resembles a registered
series but is not identical, say so and let the user choose which one is being measured.

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
- **Declare no more than the document states.** `supported_timeframes` holds the timeframes
  the document tested, symbol and market scope follow the document, and a parameter exists
  only where the document names a value. Advertising a timeframe or a market the document
  never mentions is a second strategy nobody asked for.
- **Put the document's protection values into `default_settings`.** When the document fixes a
  policy setting - a stop multiple, a reward-to-risk ratio, a leverage - declare it in
  `MoneyManagementSupport.default_settings` under the supported mode, so a run submitted
  without settings and the screen's prefilled values reproduce the document instead of the
  policy's own defaults. The run's Evidence records what the strategy declared.
- Keep entry and exit decisions in the strategy. Protection prices, quantity, and leverage
  belong to the policy; rounding, margin, and liquidation belong to execution.
- Put the code, the registration SQL, and the tests in one changeset. The contract's section
  9 lists the tests, and its closing checklist is the gate.
- Restart the services. A changed file that is already imported keeps its old body.

## 7. Finish at the screen

A strategy that only runs from code is not done. Select it in the interface, run it, and read
its result there. If a parameter needs a screen change, ask whether to fix the value inside
the strategy or widen the screen, and raise the screen work separately.

**Restarting a service and driving the screen need authority you may not have.** Both touch
running processes outside the repository, so ask before doing either, and if you cannot,
report the strategy as unfinished with the step that is left rather than as done.

Then hand the result to `verify-strategy`. Performance never substitutes for verification.
