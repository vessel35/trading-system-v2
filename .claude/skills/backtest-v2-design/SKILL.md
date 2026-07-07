---
name: backtest-v2-design
description: >
  Apply this skill for the backtest v2 rewrite's DESIGN phases — Phase A (analysis / port-source
  inventory) and Phase B (detailed design). It is the single source of truth for the harness's
  methodology: the eight grouped stages (a-domain / a-infra / b-skeleton / b-components / b-corelib-classes / b-service-classes / b-database / b-adoption)
  and which dev_plan parts + architecture sections each owns; the 정합성-확인 규약 (설계 정합 + 리뷰
  게이트, parity is Phase C only); the TOP RULE that every Phase B deliverable is self-contained /
  standalone-implementable (the guideline is the STANDARD to absorb, never a reference the
  implementer consults); the top-down UML-first document standard (제약사항·방향 first, then
  service→component→class→sequence/flow, DB as ER, structure in the mermaid diagram and prose only for
  what UML cannot encode — references/design-doc-standard.md);
  the deferred-item checklist the doc left for detailed design (backtest_db
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
- **NO foreign-document label anywhere in the deliverable.** The design document / inventories must
  NOT use another document's label to point at content — not the architecture doc's `§N`/`#N`, not
  the dev_plan's `AN`/`BN`/`CN`/`마이그N`, not `다이어그램 §N`. Refer to everything by its ACTUAL NAME
  (the class, table, column, port, method, rule) and by the design document's OWN section numbers
  (§1-§5, which are the design doc's own structure). "finalize the §9.3 fields", "per B7", "see
  마이그5" are all DEFECTS — write the actual `backtest_run`/… columns, the actual `StrategyConfig`
  class, the actual execution-port contract. (Foreign labels belong ONLY in the harness/skill
  instructions that tell the AGENT what to read — never in the deliverable.)
- **Absorb the guideline completely.** Every guideline rule that applies to the part is present and
  satisfied in the design — nothing left implicit "because the architecture doc says so". The
  guideline is the standard the design embodies, not a document the reader chases.
- **Self-check before closing:** could someone with NO access to the guideline (or to the dev_plan /
  diagrams) implement this part correctly from this doc alone? If not, it is not done.

Each design doc ends with a short **Traceability** section — a table mapping its own sections to the
guideline requirements they satisfy **BY NAME** (e.g. "look-ahead prevention", "net-of-cost P&L", "the
backtest_db catalog tables"), NEVER by a foreign label like `§11.1` or `B12`. That table is for the
compliance audit; naming the requirement (not labeling it) keeps even the provenance self-contained.

## Detailed-design document standard (top-down, UML-first — the structure rule)

Self-containment fixes *completeness*; this fixes *readability*. Every Phase B design doc is written
TOP-DOWN and UML-FIRST so the reader grasps the big structure first and never jumps to another
doc/chapter to follow the current point. Full standard: `references/design-doc-standard.md`. In short:

- **Lead with 제약사항·방향 (Constraints & Direction).** State only the binding invariants, the design
  direction + why, and the scope — before any class-level detail.
- **Descend the levels in order:** 서비스 다이어그램·정의서 → 컴포넌트 다이어그램·정의서 (per service)
  → 클래스 다이어그램·정의서 (per component) → 시퀀스/플로우 (inside the class definition). Big
  structure before detail; a concept is introduced above where it is used.
- **Separate:** one component diagram per service, one class diagram per component; shared
  components/classes in their own 공통 section (referenced, not re-drawn).
- **DB entities as ER diagrams** (+ field definition tables).
- **UML-first — the diagram is the primary representation.** Express the design IN the mermaid diagram
  (`classDiagram`/`sequenceDiagram`/`flowchart`/`erDiagram`/`graph`, per `mermaid-conventions`); use
  prose ONLY for what UML cannot encode. Attributes+types, method/port signatures, relationships+
  cardinality, stereotypes, ER fields+keys, and interaction/flow order live INSIDE the diagram; prose
  supplements ONLY the residue — constraints, defaults, nullability, formulas (expr·units·bounds),
  thresholds + tuning source, enforced invariants, semantics, service/component responsibility, and
  rationale. Never restate the diagram in prose; never hide structure the diagram could carry. The
  diagram + its residual prose together ARE the full content.
- **Doc ownership (dev_plan §4 outline):** the single doc's sections map to dev_plan parts —
  §1 서비스(B1)·§2 코드 트리(B2) = b-skeleton; §3.1-§3.3 컴포넌트(B3-B5) = b-components;
  §4.1-§4.3 core-lib 클래스(B6-B8) = b-corelib-classes; §4.4-§4.5 backtest-service 클래스(B9-B10) =
  b-service-classes; §5.1-§5.3 DB ERD(B11-B13) = b-database; appendix(B14) = b-adoption.

## The eight grouped stages (one per session) — Phase B builds ONE top-down doc

Each stage is read-only against inputs and writes only under `OUTPUT_DIR`. Run in order; Phase A
precedes Phase B (dev_plan §0 "A → B → C … 순서대로 진행"; §4; 원칙 1 extends to forbid Phase C before
A+B). **Phase B produces a SINGLE document `backtest_v2_detailed_design.md`, built top-down (원칙 3):
b-skeleton CREATES it (§1-§2 + the §1-§5 reading map); every later b-* stage APPENDS its §-sections.**

1. **a-domain** (A1·A2·A3) — port-source inventory of the pure domain logic (indicators, strategy
   `analyze`, execution/costs/sizing/trailing). Deliver `A1/A2/A3_*_inventory.md`.
2. **a-infra** (A4·A5·A6) — inventory of shared types + config + DB-creation plan, collector
   internalization scope (ingest-only, from `CRYPTO_DATA_HUB_DIR`), removal list + reconciliation
   waiver (old backtest is a removal target, not referenced). Deliver `A4/A5/A6_*.md`.
3. **b-skeleton** (B1·B2) — 설계서 §1 service diagram + definition, §2 project code tree. CREATES
   `backtest_v2_detailed_design.md` + the §1-§5 reading map.
4. **b-components** (B3·B4·B5) — 설계서 §3: one component diagram per service — §3.1 core-lib (shared,
   defined once), §3.2 backtest-service (finalizes the port list), §3.3 adoption (signal/wallet).
5. **b-corelib-classes** (B6·B7·B8) — 설계서 §4.1-§4.3: core-lib class diagrams + definitions —
   types·indicators, strategy (+config resolve sequence), execution·eval (+judgment flow). The
   82-list, metric formulas, and Hard-Gate thresholds are written OUT IN FULL here.
6. **b-service-classes** (B9·B10) — 설계서 §4.4-§4.5: backtest-service class diagrams — Engine (+candle
   loop + 1m trigger-walk sequence + trailing-parity tolerance) and output (+run-save sequence).
7. **b-database** (B11·B12·B13) — 설계서 §5.1-§5.3: DB ER diagrams + field tables — crypto_data/
   signal_db, backtest_db (the §9.3 fields), Evidence SQLite (the §9.6 fields). DB by ERD (원칙 4).
8. **b-adoption** (B14) — appendix: adoption points + shim, new-backtest validation baseline
   (reconciliation WAIVED per A6), regression, credential rotation.

Full per-part spine (목적 · 입력 · 작업 · 산출물 · 정합성-확인) and the section cross-reference: see
`references/stages-and-invariants.md`; the document standard: `references/design-doc-standard.md`.

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
   rule, a foreign-document label in the deliverable (§N / BN / 마이그N / 다이어그램 §N), or a doc that
   is not standalone-implementable is a FIX.
2. **리뷰 게이트 (review gate).** On completion: commit the notes, then `cto-reviewer` (design
   soundness + Karpathy P1-P4) and — on b-corelib-classes/b-service-classes/b-database — `cross-model-reviewer` (Codex,
   optional) → APPROVE / REQUEST CHANGES. On FIX/REQUEST CHANGES, revise once and re-submit; a second
   disagreement escalates rather than loops.

> If a check fails, fix it inside that stage. Never carry design debt forward.

## The deferred items — what Phase B MUST finalize

The architecture doc explicitly defers exactly these to detailed design. Write each OUT IN FULL in
the deliverable (the actual fields / list / signatures / number — not a reference); keep its 용도:

- **§9.3 — backtest_db meta table fields** (b-database / B12, 설계서 §5.2): `backtest_run`,
  `backtest_summary`, `backtest_prereg`, `backtest_tag` — "용도만 정의, 필드·타입·제약은 상세 설계에서
  확정". Rendered as a mermaid `erDiagram` + full field table.
- **§9.6 — SQLite Evidence Entity fields** (b-database / B13, 설계서 §5.3): basic 13 + extended 7 —
  same rule, as an `erDiagram` + field table.
- **§4.3 / §4.1#7 — the port list** (b-components / B4 = 설계서 §3.2 finalizes the concrete adapter
  list; b-corelib-classes / B8 = 설계서 §4.3 gives the port ABCs): "어떤 관심사가 포트가 되는지는 상세
  설계에서 정하며 미리 목록을 고정하지 않는다." §4.3 names a representative six (`DataFeed`, `Broker`,
  `Clock`, `CostModel`, `EvidenceSink`, `CatalogStore`) — finalize the actual list + method signatures.
- **§14 / diagram 4 — trailing-parity tolerance** (b-service-classes / B9, 설계서 §4.4): the
  evaluation-period gap between candle-unit backtest and the live 1m sub-candle trailing watermark.
  The 2026-07-03 decision adopted a 1m execution feed; finalize the allowed deviation + parity
  criterion (§12 트레일링 충실도).

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

No nested triple-backtick fences. Diagrams use top-level ` ```mermaid ` fences (never nested inside
another fence). Use `BEGIN_JSON`/`END_JSON`, `BEGIN_SQL`/`END_SQL`, `BEGIN_PSEUDOCODE`/`END_PSEUDOCODE`
markers for those blocks. Keep long JSON/SQL/pseudocode out of Markdown tables. Filenames,
table/column/port/method names, and status values in inline backticks. Every design doc follows the
top-down UML-first standard (§Detailed-design document standard) — structure in the mermaid diagram,
prose only for the residue — carries its full content inline (self-contained), uses NO foreign-document label (architecture §N / dev_plan AN·BN·마이그N / diagrams
§N) — only its own §1-§5 numbers and actual names — and ends with a **Traceability** table mapping
each design section to the guideline requirement it satisfies BY NAME, never by a foreign label.

## Missing-input fallback

If a required legacy file is absent under `TRADING_SYSTEM_DIR` or `CRYPTO_DATA_HUB_DIR`, or the
canonical doc did not decide something a deferred item needs: record the name + impact in the stage's
note as a blocker, stop that line, and continue the independent lines. Do NOT invent the repo layout,
a symbol, or a decision the doc never made.
