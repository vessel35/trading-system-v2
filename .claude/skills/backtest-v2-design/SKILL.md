---
name: backtest-v2-design
description: >
  Apply this skill for the backtest v2 rewrite's DESIGN phases — Phase A (analysis / port-source
  inventory) and Phase B (detailed design). It is the single source of truth for the harness's
  methodology: the five grouped stages (a-domain / a-infra / b-corelib / b-engine-eval / b-adoption)
  and which dev_plan parts + architecture sections each owns; the 정합성-확인 규약 (설계 정합 + 리뷰
  게이트, parity is Phase C only); the TOP RULE that every Phase B deliverable is self-contained /
  standalone-implementable (the guideline is the STANDARD to absorb, never a reference the
  implementer consults); the deferred-item checklist the doc left for detailed design (backtest_db
  meta fields §9.3, SQLite Entity fields §9.6, the port list §4.3, the trailing-parity tolerance
  §14/diagram 4); the 16 hard invariants every contract must preserve; the per-stage deliverable
  lists; the section cross-reference; and the Markdown-stability + Traceability rules. Used by the
  orchestrator, reference-scout, spec-consistency-auditor, cto-reviewer, and cross-model-reviewer.
  The guideline docs in DESIGN_DOC_DIR are the standard; this skill mirrors them. Long checklists
  (invariants, deferred items, deliverables, section map) live in references/stages-and-invariants.md.
---

# Backtest v2 — Design-Phase Contract

> **The guideline docs in `DESIGN_DOC_DIR` (`backtest_v2_architecture.md` + `_diagrams.md` +
> `_dev_plan.md`) are the STANDARD — the rules the detailed design must fully COMPLY WITH and fully
> ABSORB. They are NOT a reference the implementer consults.** The Phase B deliverable must be
> self-contained, so a Phase C implementer builds from the design doc ALONE, never opening the
> guideline. This skill mirrors the guideline so every node has the rules preloaded; if the skill and
> a guideline doc disagree, the guideline wins — flag the drift and stop that line. Section numbers
> (§N.M, §4.1#K) in THIS skill and in the harness instructions tell the AGENT what to read — they are
> NEVER a substitute for content in a deliverable (see "Self-contained deliverables" below).

## What the design phase does

The backtest v2 rewrite builds a strategy-agnostic backtest / evaluation / improvement platform in a
FRESH project, with a shared installable package `core_lib` that the new backtest-service and — later
— the KEPT production services (signal-service = live/paper signals, wallet-service = execution)
both import. This harness runs the two DESIGN phases before any implementation:

- **Phase A (analysis):** read the two legacy repos — `TRADING_SYSTEM_DIR` (signal-service +
  wallet-service) and `CRYPTO_DATA_HUB_DIR` (collector), READ-ONLY — and build the **port-source
  map**: what pure logic to PORT into `core_lib`, what is a GAP (new), and the removal list. The
  backtest/replay services under `TRADING_SYSTEM_DIR` are removal targets — NOT referenced — and the
  old↔new reconciliation baseline is WAIVED (A6).
- **Phase B (detailed design):** write the full, self-contained contracts — every signature, field,
  formula, threshold, and pseudocode spelled out — so each Phase C implementation part builds from the
  design doc ALONE, never opening the guideline.

**Iron rule:** the design produces self-contained Markdown design documents (full contracts / fields
/ formulas / pseudocode). No product code, no live DB, no executed DDL. The design NEVER re-decides a
hard invariant or re-scopes a deferred item — it fills them in while preserving each item's stated
용도. And it is IMPLEMENTABLE STANDALONE (see next section).

## Self-contained deliverables (지침 완전 흡수 — the top rule)

The Phase B design documents must be implementable from THEMSELVES ALONE. A competent Phase C
implementer builds the code reading only the design doc — never opening the guideline
(`backtest_v2_architecture.md` / `_dev_plan.md` / `_diagrams.md`). Therefore:

- **Write every rule out IN FULL.** Every field (name · type · constraint · default · nullability),
  every formula (the actual expression + units + edge cases), every threshold (the actual number +
  where it is canonically tuned), every port method (full signature + semantics), and every invariant
  the part touches (stated as an explicit rule the code must satisfy) — spelled out in the design doc
  in concrete terms. NOT "per §9.3", NOT "as the architecture doc defines" — the actual content.
- **A section reference is provenance, never content.** A guideline citation (`§9.3`, dev_plan part)
  may appear ONLY as a traceability annotation ALONGSIDE the full content — never as a stand-in for
  it. A deliverable that says "finalize the §9.3 fields" WITHOUT listing the actual fields is a
  DEFECT, not a design.
- **Absorb the guideline completely.** Every guideline rule that applies to the part is present and
  satisfied in the design — nothing left implicit "because the architecture doc says so". The
  guideline is the standard the design embodies, not a document the reader chases.
- **Self-check before closing:** could someone with NO access to the guideline implement this part
  correctly from this doc alone? If not, it is not done.

Each design doc ends with a short **Traceability** section — a table mapping its own sections to the
guideline rules (§N / dev_plan part) they satisfy. That table is for the compliance audit, not for
the implementer (who never needs it because the body is complete).

## The five grouped stages (one per session)

Each stage is read-only against inputs and writes only design notes under `OUTPUT_DIR`. Run them in
order — each stage's notes are the next stage's input; Phase A precedes Phase B (dev_plan §0 stage
order "A → B → C … 순서대로 진행한다"; §4 "Phase B takes Phase A inventories as input"; 원칙 1
extends this to forbid Phase C before A+B).

1. **a-domain** (dev_plan A1·A2·A3) — port-source inventory of the pure domain logic: indicators,
   strategy `analyze` judgment, execution/costs/sizing/trailing. Deliver `A1_indicator_inventory.md`,
   `A2_strategy_inventory.md`, `A3_execution_cost_sizing_inventory.md`.
2. **a-infra** (A4·A5·A6) — inventory of shared types + config + the DB-creation plan, the collector
   internalization scope (ingest-only, from `CRYPTO_DATA_HUB_DIR`), and the removal list +
   reconciliation waiver (the old backtest is a removal target, not referenced; old↔new 대사 waived).
   Deliver `A4_types_config_db_inventory.md`, `A5_collector_internalization_scope.md`,
   `A6_baseline_and_reconciliation.md`.
3. **b-corelib** (B1·B2·B3·B4) — the core-lib contracts: topology + packaging + ports +
   `StrategyAdapter` Protocol, value types, indicator registry/contracts + 82-list, StrategyConfig +
   Adapter Manager + registry. Deliver `B1_topology_ports.md`, `B2_types_detail.md`,
   `B3_indicator_contracts.md`, `B4_strategyconfig_manager.md`.
4. **b-engine-eval** (B5·B6·B7) — Engine loop + 1m execution feed + look-ahead; the Evidence +
   backtest_db Entity FIELDS (the central deferred items); metrics + Hard Gate + Decision. Deliver
   `B5_engine_1m_lookahead.md`, `B6_output_entities.md`, `B7_eval_judgment.md`.
5. **b-adoption** (B8) — how the kept signal/wallet adopt `core_lib` with behavior unchanged: adoption
   points, re-export shim, the new-backtest validation baseline (old↔new reconciliation waived per
   A6), wallet regression, `fill_timing` switch, credential rotation. Deliver
   `B8_adoption_reconciliation_regression.md`.

Full per-part spine (목적 · 입력 · 작업 · 산출물 · 정합성-확인) and the section cross-reference: see
`references/stages-and-invariants.md`.

## The 정합성-확인 규약 (how every stage closes)

A design stage does NOT close on 동작 정합 (parity) — there is no code yet; parity is a Phase C gate.
Each stage closes on exactly two checks (dev_plan §2):

1. **설계 정합 + 완전 흡수 + 자기완결 (design-consistency, full-absorption, self-containment).** The
   notes (a) do not contradict any guideline rule, (b) ABSORB every applicable guideline rule in full
   — every field/formula/threshold/signature written out, nothing left as a bare reference, and (c)
   are SELF-CONTAINED: a Phase C implementer could build from the doc alone with no access to the
   guideline. A Phase B note fills a deferred item **without changing its 용도 or 계약**; for the
   Entity fields (§9.3/§9.6) the rule is "용도 불변, 필드만 확정". `spec-consistency-auditor` is the
   independent gate → PASS or itemized FIX. A bare content-substituting reference, a missing guideline
   rule, or a doc that is not standalone-implementable is a FIX.
2. **리뷰 게이트 (review gate).** On completion: commit the notes, then `cto-reviewer` (design
   soundness + Karpathy P1-P4) and — on b-corelib/b-engine-eval — `cross-model-reviewer` (Codex,
   optional) → APPROVE / REQUEST CHANGES. On FIX/REQUEST CHANGES, revise once and re-submit; a second
   disagreement escalates rather than loops.

> If a check fails, fix it inside that stage. Never carry design debt forward.

## The deferred items — what Phase B MUST finalize

The architecture doc explicitly defers exactly these to detailed design. Write each OUT IN FULL in
the deliverable (the actual fields / list / signatures / number — not a reference); keep its 용도:

- **§9.3 — backtest_db meta table fields** (b-engine-eval / B6): `backtest_run`, `backtest_summary`,
  `backtest_prereg`, `backtest_tag` — "용도만 정의, 필드·타입·제약은 상세 설계에서 확정".
- **§9.6 — SQLite Evidence Entity fields** (b-engine-eval / B6): basic 13 + extended 7 — same rule.
- **§4.3 / §4.1#7 — the port list** (b-corelib / B1): "어떤 관심사가 포트가 되는지는 상세 설계에서 정하며 미리
  목록을 고정하지 않는다." §4.3 names a representative six (`DataFeed`, `Broker`, `Clock`,
  `CostModel`, `EvidenceSink`, `CatalogStore`) — finalize the actual list + method signatures.
- **§14 / diagram 4 — trailing-parity tolerance** (b-engine-eval / B5): the evaluation-period gap
  between candle-unit backtest and the live 1m sub-candle trailing watermark. The 2026-07-03 decision
  adopted a 1m execution feed; finalize the allowed deviation + parity criterion (§12 트레일링 충실도).

> Nuance on "용도 불변": for the Entity items, §9.3/§9.6 say "이 목록과 용도도 그때 조정될 수 있다" —
> the list AND purpose *may* be adjusted in detailed design. The default is preserve-purpose-finalize
> -fields (dev_plan B6 "용도 불변, 필드만 확정"); a genuine purpose/list change is allowed but must be
> recorded with its rationale, not made silently. spec-consistency-auditor treats a silent, unexplained
> purpose change as a FIX — an explicit, justified one is not.

Everything else in §5 (input schemas), §4.3 (port method signatures where already named), and §10.1
(metric formulas) is a stated contract, not a deferred item — the design reflects it, it does not
re-open it.

## The 16 hard invariants — preserve, never re-decide

Every contract must keep all of these. If a design seems to require weakening one, STOP and escalate.
Full statement + section per invariant: see `references/stages-and-invariants.md §invariants`.

Look-ahead prevention (§11.1) · `feature_ts ≤ decision_ts < execution_ts` (§7/§11.1) · recursive
indicators on finalized candles only, `close_time ≤ T` (§3.3) · Evidence hash = normalized
serialization, wall-clock excluded (§11.2) · Hard Gate thresholds canonical in `eval/thresholds.py` ↔
`20_thresholds.md` (§10.2) · the Decimal single-cast gate at `Broker.submit()`, never `Decimal(float)`
(§11.2) · Adaptee stateless / config immutable (§4.1#3/#10) · research data never in production DBs
(§1-7/§9) · accounting identity `cash + position = equity`, cost charged once (§6.2/§12) · all P&L
net-of-cost (§8) · sizing 1R ≤ 1% of account (§8) · candle type-layer validation (§5.1) · warm-up
signals discarded (§5.6) · no retroactive self-fill-candle check (§7) · conservative same-touch
priority = stop before TP (§7) · deterministic (same input+seed → same normalized Evidence) (§11.2).

## Key architectural decisions the design must honor

- **Strategy pattern split three ways:** `StrategyAdapter` (a `typing.Protocol`, not an ABC) +
  `Adaptee` (judgment only — `analyze`, no read/store/loop) (§4.1#3); `Adapter Manager` (factory /
  lifecycle / signal_db registry, DB only via injected port) (§4.1#9); `StrategyConfig` (resolve /
  validate / serialize / JSON-schema — schema DECLARED by Adaptee, values by caller) (§4.1#10).
- **Engine owns the ports and PUSHES data to the Adaptee** (§4.1#11, §6.2): the Engine confirms
  data up to the current finalized candle via `DataFeed`, calls `Adaptee.analyze()`, fills via
  `Broker`, records via `EvidenceSink` + `backtest_db`. The Adaptee never pulls future data.
- **Six representative ports** (finalize the list at B1): `DataFeed` (bounded, incl. 1m feed),
  `Broker`, `Clock`, `CostModel`, `EvidenceSink`, `CatalogStore`. `analyze` / sizing / execution /
  cost formulas are 100% identical code in backtest and live; only fill-time / cost-assumption /
  clock differ, isolated behind ports (§4.3).
- **1m execution feed** (§5.1/§6.2/§7/§14): signals on the strategy TF, but stop/trailing/liq judged
  by walking the `t` interval's 1m sub-candles in time order (matches live per-minute polling).
- **collector = ingest only** (§4.1#16/§14): internalize OHLCV ingest; DROP indicator precompute and
  the `technical_indicators` table read; indicators computed by `core_lib` incrementally in live.
- **core-lib as an installable package** `core_lib` (§4.2): editable install, no `sys.path` swaps;
  governance = review gate + re-duplication guard test + pinned release for live (§4.2.1).

## Domain glossary (one line each)

Evidence (per-run SQLite of all point-in-time records) · backtest_db (separate PostgreSQL meta DB:
catalog + prereg + decision + SQLite path/hash) · Hard Gate ((A) evaluation thresholds + (B) profile
range; failing ≠ end, → forensics) · Integrity Check (the only stop-point; fail → diagnostic_only,
fix data & rerun) · Decision routing (promote / partial_keep / retest / abandon) · forensics (why it
won/lost, per-trade; the主 목적 기능 B) · bias-fix (the 31 regression tests on
`feat/vessel-reversion-short-only` of the removed backtest — a Phase-C port target, not read here) ·
parity (vectorized↔incremental, backtest↔live analyze) · reconciliation (old↔new backtest 대사 —
WAIVED in this build per A6, since the old backtest is a removal target) · WFA/MC/PSR
(over-fit defense harness) · breadth (market-breadth indicators; inactive without a breadth input
channel) · pinned indicators (one authoritative impl for source-divergent indicators, §12) · 82
indicators (all built once in `core_lib`, no "add later") · Vessel strategies (the first reference
strategies, each ported to an Adaptee).

## Markdown-stability rules (all notes)

No nested triple-backtick fences. Use `BEGIN_JSON`/`END_JSON`, `BEGIN_SQL`/`END_SQL`,
`BEGIN_PSEUDOCODE`/`END_PSEUDOCODE` markers. Keep long JSON/SQL/pseudocode out of Markdown tables.
Filenames, table/column/port/method names, and status values in inline backticks. Every design doc
carries its full content inline (self-contained) and ends with a **Traceability** table (design
section → guideline rule satisfied); a reference is provenance in that table only, never a
content-substitute in the body.

## Missing-input fallback

If a required legacy file is absent under `TRADING_SYSTEM_DIR` or `CRYPTO_DATA_HUB_DIR`, or the
canonical doc did not decide something a deferred item needs: record the name + impact in the stage's
note as a blocker, stop that line, and continue the independent lines. Do NOT invent the repo layout,
a symbol, or a decision the doc never made.
