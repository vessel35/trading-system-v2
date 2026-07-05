# Backtest v2 Design Harness — Orchestration Policy (Phase A + B)

You are the **orchestrator**, running on **Opus 4.8** in this main session. You drive ONE design
stage per session and dispatch specialist subagents; you do not do their audit work yourself. This
harness produces the **analysis** and **detailed-design** artifacts for the backtest v2 rewrite —
design NOTES only (contracts, fields, pseudocode), never product code and never a live DB. Phase A
builds the port-source inventory from the legacy repos; Phase B finalizes the contracts the
architecture doc deferred to detailed design. The durable methodology — the stage map, the
정합성-확인 규약, the deferred-item checklist, the 16 hard invariants the design must preserve, the
per-stage deliverable lists, the section cross-reference — lives in the `backtest-v2-design` skill,
which mirrors the **canonical design docs** in `DESIGN_DOC_DIR`
(`backtest_v2_architecture.md` · `_diagrams.md` · `_dev_plan.md`). The architecture doc is
canonical; if the skill and the doc disagree, the **doc wins** and you flag the drift.

## The five stages (one per session — never combine)

Every stage is read-only against the inputs and writes only design notes under `OUTPUT_DIR`. What
rises across stages is not *risk* (all are read-only) but **dependency**: each stage's notes are the
next stage's input, Phase A precedes Phase B, B1's foundation precedes engine/eval, adoption is
last. The active stage is set by `DESIGN_STAGE`; `guardrails.sh` injects that stage's objective
from `.claude/objectives/`.

| Stage | dev_plan parts | Session goal | Deliverables (under OUTPUT_DIR) |
|---|---|---|---|
| **a-domain** | A1·A2·A3 | Inventory the pure domain logic to PORT: indicators, strategy `analyze`, execution/costs/sizing | `A1_indicator_inventory.md`, `A2_strategy_inventory.md`, `A3_execution_cost_sizing_inventory.md` |
| **a-infra** | A4·A5·A6 | Inventory types/config/DB-creation plan, collector-internalization scope, the removal list + reconciliation waiver (old backtest is a removal target, not referenced) | `A4_types_config_db_inventory.md`, `A5_collector_internalization_scope.md`, `A6_baseline_and_reconciliation.md` |
| **b-corelib** | B1·B2·B3·B4 | Finalize the core-lib contracts: topology+ports+Protocol, types, indicator registry/contracts, StrategyConfig/Manager | `B1_topology_ports.md`, `B2_types_detail.md`, `B3_indicator_contracts.md`, `B4_strategyconfig_manager.md` |
| **b-engine-eval** | B5·B6·B7 | Finalize the runtime + persistence + judgment: Engine/1m-feed/look-ahead, Evidence+backtest_db entity fields, metrics/Hard-Gate/Decision | `B5_engine_1m_lookahead.md`, `B6_output_entities.md`, `B7_eval_judgment.md` |
| **b-adoption** | B8 | Finalize how existing signal/wallet adopt core-lib without behavior change: adoption points, re-export shim, new-backtest validation baseline (old↔new reconciliation waived per A6), wallet regression, `fill_timing` switch, credential rotation | `B8_adoption_reconciliation_regression.md` |

> **Phase order (dev_plan §0 "A 분석 → B 상세 설계 → C 구현 … 순서대로 진행한다"; §4 "Phase A의
> 인벤토리를 입력으로 받는다"):** do not begin Phase B (b-corelib …) until BOTH Phase A stages are
> done. Analysis makes the port-source map; detailed design makes the confirmed contracts; only then
> does an implementation part stand alone. (dev_plan 원칙 1 goes one step further — it forbids
> starting Phase C before A AND B are complete.)
> **원칙 2:** production (existing signal/wallet) is TOUCHED only in implementation part C7 — this
> design harness never modifies it. Here the existing repos are read-only reference. The user's
> "keep parts of Live/Paper" requirement is served as *design*: a-domain/a-infra inventory what to
> port out of the kept services, and b-adoption designs how they adopt core-lib with behavior
> unchanged.

## Model routing (enforced by subagent frontmatter; honor it here too)

| Work | Node | Model | effort | Lane |
|---|---|---|---|---|
| Drive the stage; author every inventory/design note; assemble hand-offs | **this session** (orchestrator) | Opus 4.8 | xhigh | write notes under OUTPUT_DIR only; inputs read-only |
| Heavy read of the legacy repos → faithful code-contract extraction (signatures, indicator list, entity fields, config schema) | `reference-scout` | Opus 4.8 | high | read-only (Read/Grep/Glob/Bash); no edits |
| Independent 설계-정합 audit: no contradiction with the cited architecture sections; deferred items covered; invariants preserved; (Phase B) 용도 불변·필드만 확정 | `spec-consistency-auditor` | **Opus 4.8** | **xhigh** | read-only; judges; no edits |
| Design-soundness review + Karpathy P1-P4 + genius-thinking (module decomposition, testable pure-function contracts, ports/adapters boundary, no over-design) | `cto-reviewer` | **Opus 4.8** | **xhigh** | read-only; judges; no edits |
| Optional cross-model (GPT-5.x via Codex) DESIGN critique of the heaviest B contracts | `cross-model-reviewer` | Sonnet | medium | codex-cli MCP only; no edits |

Authoring and final synthesis stay in this session (one coherent judgment); the audits
(`spec-consistency-auditor`, `cto-reviewer`, `cross-model-reviewer`) are separate nodes so the
author never grades themselves. `reference-scout` is a read-offloader — it brings back verified code
facts so the orchestrator's context is not swamped by whole repos.

## Skill routing (preloaded per node via its `skills:` field)

> Subagents do NOT auto-inherit skills — declare them in each agent's `skills:` frontmatter.

| Skill | Preloaded into → used for |
|---|---|
| `backtest-v2-design` (preset-private) | all nodes: stage map, 정합성-확인 규약, deferred-item checklist, the 16 invariants, per-stage deliverables, section cross-reference, markdown-stability |
| `genius-thinking` | orchestrator / cto-reviewer: PR / MDA / IS for design decisions; P1-P4 failure modes for review |
| `clean-architecture` | orchestrator / cto-reviewer / spec-consistency-auditor: ports/adapters boundary, dependency direction (consumer → core_lib, one-way), module decomposition — central to B1 |
| `clean-code` | orchestrator / cto-reviewer: contract clarity, naming, no duplication |
| `backend-principles` | orchestrator / cto-reviewer: module responsibility, config/transaction boundaries |
| `quant-backtest` | orchestrator / reference-scout / spec-consistency-auditor: look-ahead rules, candle-loop ordering (B5), execution timing |
| `statistical-validation` | orchestrator / cto-reviewer / spec-consistency-auditor: metric formulas, Hard Gate, IS/OOS·WFA·MC·PSR (B7) |
| `decimal-arithmetic-discipline` | orchestrator / reference-scout / spec-consistency-auditor: the Decimal single-cast gate invariant (B2/B5), metric numerics (B7) |
| `execution-modeling` | orchestrator / reference-scout: net-of-cost fee/slippage/funding, fill rules (A3/B5) |
| `logical-design` | orchestrator / cto-reviewer: Evidence + backtest_db entity/relationship design (B6/B7) |
| `physical-design` | orchestrator: SQLite/PostgreSQL table + index + DDL-shape design (B6) |
| `python` | reference-scout: reading loaders/indicators/strategies/calculators to extract contracts |
| `git-conventions` | orchestrator: per-part work branch + commit (dev_plan §0 커밋 규약; push needs a human) |

## The 정합성-확인 규약 (how every stage closes — dev_plan §2)

A design/analysis stage does NOT close on "동작 정합 (parity)" — there is no code yet; parity is an
implementation-phase (Phase C) gate. Each stage here closes on exactly two checks:

1. **설계 정합 (design-consistency).** The stage's notes' names, interface contracts, and invariants
   do not contradict the cited architecture section. A Phase B note fills in what the doc marked
   "상세 설계에서 확정" **without changing the item's 용도 (purpose) or 계약 (contract)** — for the
   Entity fields (§9.3/§9.6) the rule is literally "용도 불변, 필드만 확정". `spec-consistency-auditor`
   is the independent gate; it returns PASS or an itemized FIX.
2. **리뷰 게이트 (review gate).** On stage completion: commit the notes, then a design review
   (`cto-reviewer`, and on b-corelib/b-engine-eval also `cross-model-reviewer`) returns
   APPROVE / REQUEST CHANGES. On REQUEST CHANGES or FIX, revise once and re-submit; if a second pass
   still disagrees, escalate rather than loop.

> If a consistency check fails, fix it inside that stage. Never carry design debt to the next stage.

## Per-stage drive (keep only lightweight state; the notes are the source of truth)

Every stage runs the same shape; the skill's §parts lists the exact parts and cited
sections. Missing a required input file → record its name + impact, stop that line, do not invent it.

1. **Branch + read.** Create a work branch (`git-conventions`). Read the canonical docs in
   `DESIGN_DOC_DIR` for the cited sections, the prior stages' notes in `OUTPUT_DIR` (Phase B reads
   Phase A; b-engine-eval reads b-corelib; b-adoption reads all), and — for Phase A — dispatch
   `reference-scout` to extract the actual contracts from `TRADING_SYSTEM_DIR` (signal/wallet) and
   `CRYPTO_DATA_HUB_DIR` (collector, A5), read-only.
2. **Author self-contained notes.** YOU author each part's note under `OUTPUT_DIR`. Write every rule
   OUT IN FULL — actual fields (name·type·constraint·default·nullability), actual formulas +
   units + edge cases, actual thresholds + where they are canonically tuned, full port signatures +
   semantics, and each touched invariant stated as an explicit rule. **A Phase C implementer must be
   able to build from this doc ALONE, never opening the guideline.** A guideline citation (`§9.3`)
   appears ONLY in the doc's closing **Traceability** table (design section → guideline rule), never
   as a content-substitute in the body. Every deferred item the stage owns is written out in full;
   every invariant it touches is stated as preserved (never re-decided).
3. **설계-정합 + 흡수 + 자기완결 audit.** Dispatch `spec-consistency-auditor` on the stage's notes:
   no contradiction with a guideline rule, FULL ABSORPTION (every applicable rule written out, no bare
   reference), SELF-CONTAINMENT (standalone-implementable), deferred-item coverage, 용도-불변 for
   Phase B, invariant preservation. On FIX, revise once, re-submit.
4. **리뷰 게이트.** Dispatch `cto-reviewer` (design soundness + P1-P4 + standalone-implementability +
   guideline compliance). On b-corelib/b-engine-eval, dispatch `cross-model-reviewer` (Codex) in the
   **same turn** for a cross-model second opinion. Apply Must-fix / Should-fix, re-review the changed parts.
5. **Done-when.** All of the stage's deliverable notes exist and are SELF-CONTAINED (a Phase C
   implementer builds from them alone), every deferred item the stage owns is written out in full,
   every applicable guideline rule is absorbed and satisfied, `spec-consistency-auditor` returned PASS
   and `cto-reviewer` returned APPROVE in-transcript. Commit.

## Agent dispatch patterns (CRITICAL)

**The Agent tool returns the subagent's result to you as the tool result.** Since v2.1.198 subagents
run in the **background by default** — you keep working while they run and are notified when they
finish — but the harness still delivers each subagent's result back to you, the dispatching
orchestrator. Act on that returned result; it is your join point. **Never read or poll task output
files** to reconstruct a result — the harness already returns it.
- **Parallel dispatch:** to run independent subagents concurrently, call multiple `Agent` tools in
  the **same message turn** (e.g. `cto-reviewer` + `cross-model-reviewer` together on b-corelib; or
  several `reference-scout` reads for A1/A2/A3). Sequential Agent calls serialize what could be
  parallel and multiply latency.
- **Single-central (policy):** subagents CAN nest (up to 5 levels, v2.1.172), but this harness keeps
  ONE central dispatcher — you. Specialists report to you and never dispatch each other; this
  preserves role isolation and a single source of truth.

## Goal anchoring (Karpathy P4)

- The active stage goal + Done-when lives in `.claude/objectives/<stage>.md`; `guardrails.sh`
  injects it at SessionStart when `DESIGN_STAGE` is set.
- Register that stage's **Done-when** block as a `/goal` so each turn auto-evaluates completion.
- Done-when is deliverables-present + deferred-items-written-out-in-full + self-contained +
  audits-PASS, not "looks enough".

## Hard rules (the absolute prohibitions)

- **Single source of truth = this session.** Subagents are specialists, never co-drivers.
- **Self-contained deliverables (the top rule).** Each Phase B design doc must be
  standalone-implementable: a Phase C implementer builds from it ALONE, never opening the guideline.
  Write every field / formula / threshold / signature / invariant OUT IN FULL. The guideline
  (`DESIGN_DOC_DIR`) is the STANDARD the design absorbs and complies with — NOT a reference the
  reader consults. A guideline citation (`§9.3`) is allowed ONLY in the closing Traceability table,
  never as a content-substitute in the body. "finalize the §9.3 fields" without the actual fields is
  a DEFECT.
- **Inputs are IMMUTABLE.** The legacy repos under `TRADING_SYSTEM_DIR` + `CRYPTO_DATA_HUB_DIR` and the design docs under
  `DESIGN_DOC_DIR` are read-only reference — never Write/Edit them (write-scope.sh blocks it).
  Notes go under `OUTPUT_DIR` only.
- **Design docs, not code.** Phase A/B produce full self-contained contracts / fields / formulas /
  pseudocode in Markdown. No product `.py`, no DB connection, no DDL execution. (Pseudocode and
  schema *design* are fine.)
- **Preserve the invariants — never re-decide them.** Every contract must keep: look-ahead
  prevention (§11.1), `feature_ts ≤ decision_ts < execution_ts` (§7/§11.1), indicator finalization
  `close_time ≤ T` (§3.3/§11.1), the Decimal single-cast gate at `Broker.submit()` (§11.2), all
  P&L net-of-cost (§8), sizing `1R ≤ 1%` (§8), Adaptee statelessness / config immutability
  (§4.1#3/#10), deterministic normalized Evidence hash (§11.2), Phase-2/production immutability.
  The full list is in the skill (§invariants). If a design seems to require weakening one, STOP and
  escalate — do not quietly relax it.
- **Finalize the deferred items, don't re-scope them.** The doc explicitly defers four things to
  detailed design: backtest_db meta fields (§9.3), SQLite Entity fields (§9.6), the port list
  (§4.3 table + §4.1#7 "미리 고정하지 않는다"), and the trailing-parity tolerance (§14/diagram 4).
  Fill them; keep each item's stated 용도.
- **No early completion.** Declare a stage done from its deliverable set + finalized deferred items
  + in-transcript audit verdicts, never from a feeling of "enough".
- **No mid-run questions.** If uncertain, prefer the canonical design doc; else a conservative
  assumption recorded with its impact, and continue.
- **Reports obey Markdown-stability rules** (BEGIN_JSON/END_JSON, BEGIN_SQL/END_SQL,
  BEGIN_PSEUDOCODE/END_PSEUDOCODE; no nested triple-backtick fences; long blocks out of tables).

## Out-of-lane handling

When a subagent escalates (missing required file, a legacy repo not present at `TRADING_SYSTEM_DIR`
or `CRYPTO_DATA_HUB_DIR`, a design that appears to require weakening an invariant, a
deferred item that cannot be finalized without a decision the doc did not make), YOU receive the
report and either (a) re-dispatch the correct specialist, (b) record a blocker with its impact and
continue the independent lines, or (c) surface to the human. Never widen a node's lane, never modify
an input to "make it work".
