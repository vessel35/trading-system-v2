# Stage b-corelib Objective — core-lib contracts (read-only inputs; design notes out)

> Set `DESIGN_STAGE=b-corelib`. Register the Done-when block below as a `/goal`.
> Precondition: BOTH a-domain and a-infra are complete (their notes are inputs).

**Goal:** Finalize the `core-lib` package contracts the architecture doc deferred to detailed
design — topology + packaging + ports + `StrategyAdapter` Protocol (B1), shared value types (B2),
indicator registry + contracts + 82-list (B3), StrategyConfig + Adapter Manager + registry (B4).
Output is design NOTES (signatures, fields, invariants, pseudocode), not code.

**Inputs:** architecture §0.1·§4.1·§4.2·§4.3·§5.1·§5.5·§5.8·§6.1·§7·§11.1·§12; dev_plan B1·B2·B3·B4;
the a-domain notes (A1 for B3, A2 for B4) and a-infra notes (A4 for B2). For a targeted code fact,
dispatch `reference-scout` (read-only).

**In scope:**
- **B1 topology + ports:** new-project form (fresh repo) → `core-lib` packaging (installable
  package, editable install; new backtest-service and later the kept services both depend on it) →
  `core_lib` package tree → **port signatures** (`DataFeed` bounded incl. 1m execution feed,
  `Broker`, `Clock`, `CostModel`, `EvidenceSink`, `CatalogStore`) → **`StrategyAdapter` Protocol**
  signatures (`get_metadata`/`get_parameter_schema`/`analyze`) → dependency direction (consumer →
  core_lib, one-way). **The port list is a §4.3-deferred item — finalize it here (do not leave it
  "미리 고정하지 않음").** Deliver `B1_topology_ports.md`.
- **B2 types:** `Candle`·`Order`·`Position`·`Trade`(+`r0`)·`Fill`·enums·`money`(quantize) field
  finalization → candle validation invariants (time monotonic, high/low) → **Decimal precision
  rule + the single-cast gate at `Broker.submit()`** stated as preserved. Deliver `B2_types_detail.md`.
- **B3 indicator registry/contracts:** `IndicatorSpec` (version·min_history·`§12` pinned rationale),
  `compute_batch`, `IndicatorState.update`, `assert_finalized(close_time≤T)` contracts → the final
  82-indicator list + params + pinned → vectorized↔incremental seed + warm-up rule. Reflect the A1
  gap. Deliver `B3_indicator_contracts.md`.
- **B4 StrategyConfig + Adapter Manager + registry:** `StrategyConfig`
  (`resolve`/`json_schema`/`serialize`/`version`) contract → `Adapter Manager`
  (`create`/`lifecycle`/`registry`) contract → the signal_db Adaptee registry schema → config
  validation (`extra=forbid`, defaults, cross-field) → registry access as an injected port
  (core_lib DB-independent). Boundary: schema DECLARED by Adaptee, RESOLVED by StrategyConfig,
  CREATED by Manager. Deliver `B4_strategyconfig_manager.md`.

**Out of scope (escalate / do NOT do):**
- Any code; the Engine loop / 1m walk (B5); Entity fields (B6); eval (B7); adoption (B8).
- Re-deciding an invariant (Decimal gate, look-ahead, statelessness) — state it preserved, don't relax it.

**Done when:**
- `B1_topology_ports.md`, `B2_types_detail.md`, `B3_indicator_contracts.md`,
  `B4_strategyconfig_manager.md` exist under `OUTPUT_DIR`.
- Each note is SELF-CONTAINED (standalone-implementable): every port method signature + semantics,
  every type field (name/type/constraint/default/nullability), every indicator-contract rule, and
  every config rule is written OUT IN FULL — a Phase C implementer builds from it without ever
  opening the guideline. §-citations appear only in each doc's closing Traceability table, never as a
  content-substitute in the body.
- The §4.3 port list is finalized (each port: purpose + method signatures + backtest/live impl split).
- The 82-indicator list is finalized and reconciled against the A1 gap.
- `spec-consistency-auditor` returned PASS (§0.1·#3·#7·#9·#10·#11·5.5·6.1 — 어댑터=포트, 전략=판단
  계약, schema=Adaptee·해석=StrategyConfig·생성=Manager, 용도 불변) in this transcript.
- `cto-reviewer` returned APPROVE and `cross-model-reviewer` (Codex) returned its critique with no
  open Must-fix, both in this transcript.
- Complete enough that Phase C parts C1-C5 implement from these contracts without re-deciding.
- Turn budget: ≤ <fill in> orchestrator turns. If exceeded → STOP and escalate.

**Register with /goal (example):**

Stage b-corelib is complete only when the four contract notes (B1 topology+ports, B2 types, B3
indicator contracts, B4 config+manager) exist under OUTPUT_DIR, the §4.3 port list and the
82-indicator list are finalized, every touched invariant is stated preserved (not relaxed),
spec-consistency-auditor returned PASS and both cto-reviewer + cross-model-reviewer returned no open
Must-fix in this transcript. Until then, continue the named gaps. Do not declare completion from a
feeling of "enough".
