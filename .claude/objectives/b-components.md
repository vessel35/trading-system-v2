# Stage b-components Objective — 설계서 §3 컴포넌트 다이어그램 (read-only inputs; design doc out)

> Set `DESIGN_STAGE=b-components`. Register the Done-when block below as a `/goal`.
> Precondition: b-skeleton done (§1-§2 exist in `backtest_v2_detailed_design.md`).
> Append §3.1-§3.3 to the SAME doc.

**Goal:** Author the component view — §3 of `backtest_v2_detailed_design.md` — one component diagram
per service, with definitions. Shared (core-lib) is separated into §3.1. dev_plan parts B3 (§3.1) +
B4 (§3.2) + B5 (§3.3).

**Inputs:** architecture §4.1·§13; dev_plan B3·B4·B5; §1-§2 of the design doc (b-skeleton), the
a-domain (A2/A3) + a-infra inventories.

**In scope:**
- **B3 → §3.1 core-lib 컴포넌트 (공유):** a mermaid component diagram of core-lib's components
  (`types` · `indicators` · `strategy`〈StrategyAdapter/Adaptee〉 · `sizing` · `costs` · `execution` ·
  `ports` · `eval` · `StrategyConfig` · `Adapter Manager`) + a definition (each component:
  responsibility · interface boundary · dependencies). This is the SHARED layer — defined once here,
  referenced by every consumer, not re-drawn.
- **B4 → §3.2 backtest-service 컴포넌트:** a mermaid component diagram (`Engine` · `ConfigLayer` ·
  `Harness` + the port-adapter implementations `DataFeed`/`Broker`/`Clock`/`CostModel`/
  `EvidenceSink`/`CatalogStore`) + definition (responsibility · where it consumes core-lib). This is
  where the §4.3 **port list is finalized** as concrete adapters.
- **B5 → §3.3 채택 컴포넌트 (signal/wallet):** the post-adoption component view of signal/wallet with
  their internal indicator/strategy/execution implementations replaced by `core_lib` imports +
  definition (replacement points · shim · behavior-unchanged). Design only — C7 executes it.

**Out of scope (escalate / do NOT do):**
- Class-level detail (that is b-corelib-classes / b-service-classes); DB schema (b-database); code.
- Mixing multiple services in one component diagram (one diagram per service).

**Done when:**
- §3.1, §3.2, §3.3 appended to `backtest_v2_detailed_design.md`, each a mermaid component diagram +
  definition; shared core-lib components are in §3.1 only (referenced, not duplicated).
- The port list (§4.3) is finalized as concrete backtest-service adapters in §3.2.
- SELF-CONTAINED (the reader builds the component picture from the doc alone); top-down (component
  under its already-defined service; no class-level identifier yet); NO foreign-document label
  (§N/BN/마이그N/diagrams) — actual names + own §1-§5, Traceability names each requirement.
- `spec-consistency-auditor` PASS (§4.1 component spec + dependency direction; one-diagram-per-service;
  document-structure) and `cto-reviewer` APPROVE in this transcript.
- Turn budget: ≤ <fill in> orchestrator turns. If exceeded → STOP and escalate.

**Register with /goal (example):**

Stage b-components is complete only when §3.1 (core-lib shared components), §3.2 (backtest-service
components with the finalized port list) and §3.3 (adoption view) are appended to
backtest_v2_detailed_design.md as mermaid component diagrams + definitions, shared components live in
§3.1 only, everything self-contained and top-down, spec-consistency-auditor returned PASS and
cto-reviewer returned APPROVE in this transcript. Until then, continue the named gaps. Do not declare
completion from a feeling of "enough".
