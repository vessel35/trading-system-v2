# Stage b-service-classes Objective — 설계서 §4.4-§4.5 backtest-service 클래스 (read-only inputs; design doc out)

> Set `DESIGN_STAGE=b-service-classes`. Register the Done-when block below as a `/goal`.
> Precondition: b-skeleton + b-components + b-corelib-classes done (§1-§4.3 exist). Append §4.4-§4.5.

**Goal:** Author the backtest-service class design — §4.4-§4.5 of `backtest_v2_detailed_design.md` —
the Engine + adapter implementations + output classes, with the candle-loop / 1m-feed / run-save
SEQUENCE inside the class definitions. dev_plan parts B9 (§4.4) + B10 (§4.5).

**Inputs:** architecture §6.2·§7·§9·§11.1·§14; dev_plan B9·B10; §1-§4.3 of the design doc,
b-corelib-classes (the core-lib classes these consume), a-domain A3 (fill/cost).

**In scope:**
- **B9 → §4.4 Engine (+candle-loop·1m sequence):** class diagram + definition — `Engine`, the
  `DataFeed`/`Broker`/`Clock`/`CostModel` port IMPLEMENTATIONS, `ConfigLayer`, `Harness`. Inside the
  Engine definition: the candle-loop (§6.2 two moments) SEQUENCE, the 1m execution-feed trigger-walk
  SEQUENCE/FLOW (stop/trailing/liq over the `t` interval's 1m sub-candles in time order), and the
  look-ahead ordering (`decision_ts < execution_ts`), all as mermaid. **Finalize the trailing-parity
  tolerance vs the live 1m path** here (the §14 / diagram-4 deferred item), stated as a rule.
- **B10 → §4.5 output (+run-save sequence):** class diagram + definition — `EvidenceSink` (writes
  Evidence SQLite) and `CatalogStore` (writes `backtest_db`): responsibilities + full interface. The
  run-save / finalize SEQUENCE (mermaid) inside the definition. The ACTUAL table/Entity schemas are
  NOT here — they are ER diagrams in b-database (§5); §4.5 states only the write contract each class
  has against those schemas.

**Out of scope (escalate / do NOT do):**
- The DB ERD/field schema (b-database owns §5); core-lib class internals (already in §4.1-§4.3); code.
- Weakening look-ahead order or the same-touch stop-before-TP rule.

**Done when:**
- §4.4, §4.5 appended to `backtest_v2_detailed_design.md` — one mermaid classDiagram per component +
  full definitions; the candle-loop, 1m trigger-walk, and run-save SEQUENCES are mermaid diagrams
  INSIDE the class definitions.
- The 1m trigger-walk enforces `decision_ts < execution_ts` and the conservative same-touch priority
  (stop before TP); the trailing-parity tolerance is finalized as an explicit rule.
- SELF-CONTAINED + full inline content; NO foreign-document label (§N/BN/마이그N/diagrams) — actual
  names + own §1-§5, Traceability names each requirement; top-down (Engine/output
  under their already-defined §3.2 components; DB schema deferred to §5, referenced not inlined).
- `spec-consistency-auditor` PASS (§6.2·7·11.1·14; look-ahead order invariant; document-structure)
  and `cto-reviewer` APPROVE, and `cross-model-reviewer` (Codex) no open Must-fix, in this transcript.
- Turn budget: ≤ <fill in> orchestrator turns. If exceeded → STOP and escalate.

**Register with /goal (example):**

Stage b-service-classes is complete only when §4.4 (Engine + candle-loop/1m sequences) and §4.5
(output + run-save sequence) are appended to backtest_v2_detailed_design.md as mermaid classDiagrams +
full definitions with the sequences embedded, the 1m walk enforces decision_ts<execution_ts +
stop-before-TP, the trailing-parity tolerance is finalized, and spec-consistency-auditor PASS +
cto-reviewer APPROVE + cross-model-reviewer no-open-Must-fix in this transcript. Until then, continue
the named gaps. Do not declare completion from a feeling of "enough".
