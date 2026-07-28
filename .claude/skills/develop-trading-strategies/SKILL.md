---
name: develop-trading-strategies
description: Develop, refactor, or review trading strategies and reusable money-management policies in trading-system-v2. Use when working on StrategyAdapter or Adaptee implementations, strategy metadata and parameter schemas, manual or Turtle money management, sizing or leverage ownership, strategy registration and runtime composition, strategy-facing API or UI schemas, Evidence fields, or their contract tests.
---

# Develop Trading Strategies

Apply the repository's strategy-authoring contract without moving account, sizing, or
execution responsibilities into strategy code.

## Start with the canonical contract

Read `docs/strategy-authoring-contract.md` completely before designing, editing, or
reviewing relevant code. Treat it as the single source of truth. Do not duplicate or
silently reinterpret its rules in another document.

This repository currently uses its own `core_lib` and `backtest_service` runtime. Do not
introduce NautilusTrader or another engine merely because a generic backtest skill
mentions it. A framework migration requires a separate approved design.

Then inspect the current implementations relevant to the task:

- `services/core-lib/core_lib/strategy/base.py`
- `services/core-lib/core_lib/strategy/config.py`
- `services/core-lib/core_lib/strategy/factory.py`
- `services/core-lib/core_lib/types/signal.py`
- `services/core-lib/core_lib/sizing/`
- `services/backtest-service/backtest_service/config/run_config.py`
- `services/backtest-service/backtest_service/engine/engine.py`

State whether the touched path still uses the legacy `TradingSignal` contract or the
target `DecisionIntent` and `MoneyManagementPolicy` contract. Never assume a target type
exists merely because the canonical document specifies it.

## Classify the task

Choose one primary class and keep the changeset bounded:

- A new or modified strategy changes entry or exit decisions.
- A money-management policy changes protection, sizing, or requested leverage.
- Runtime composition changes policy resolution, capability checks, or Engine ordering.
- A compatibility migration preserves legacy manual behavior.
- API or UI work exposes policy selection or Evidence without reimplementing rules.

Do not combine a strategy edge change with a policy or execution refactor unless an
approved design explicitly requires both.

## Enforce the ownership boundary

For strategy work, allow decision logic, metadata, required indicators, supported
timeframes, warm-up, and strategy-owned parameters. Reject strategy code that reads
account equity, computes quantity or margin, selects final leverage, performs I/O, reads
future data, or imports a service package.

For policy work, allow stateless protection and position-plan calculations. Reject policy
code that creates entry signals, expands global risk limits, sends orders, or reads
external state.

Keep final exchange rounding, margin validation, and liquidation safety in execution.
Keep account-wide approval in the common risk governor.

## Preserve compatibility before adding Turtle mode

When changing the contract:

- Implement and test the manual compatibility policy first.
- Normalize absent `money_management` and legacy flat fields to manual mode.
- Prove existing golden outputs remain unchanged.
- Record submitted and resolved configuration versions in Evidence.
- Add Turtle policy only after manual parity is green.
- Keep the existing risk-per-trade hard cap authoritative.

Do not label a strategy-timeframe ATR approximation as the historical daily Turtle `N`.
Require an explicit multi-timeframe input contract or use a different policy name.

## Test the contract

Add the smallest tests that prove the affected boundary:

- Strategy tests must prove determinism, declared indicator parity, valid exits, and no
  policy-dependent decision drift.
- Policy tests must cover formulas, invalid values, risk caps, minimum leverage, margin,
  and liquidation safety.
- Composition tests must cover capability rejection, indicator union, warm-up, and policy
  version Evidence.
- Compatibility tests must compare legacy and manual resolved behavior.
- API and UI tests must prove discriminated mode fields and complete submitted payloads.

Keep all tests dry-run. Do not place live orders, call an exchange, or write production
data.

## Review gate

Before reporting completion, verify every applicable item in the canonical document's
“전략 개발 완료 체크리스트.” Report any unmet item as a blocker rather than weakening
the contract or adding a silent fallback.
