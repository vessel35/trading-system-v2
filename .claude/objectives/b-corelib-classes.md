# Stage b-corelib-classes Objective — 설계서 §4.1-§4.3 core-lib 클래스 (read-only inputs; design doc out)

> Set `DESIGN_STAGE=b-corelib-classes`. Register the Done-when block below as a `/goal`.
> Precondition: b-skeleton + b-components done (§1-§3 exist). Append §4.1-§4.3 to the SAME doc.

**Goal:** Author the core-lib class design — §4.1-§4.3 of `backtest_v2_detailed_design.md` — one class
diagram per component, with full definitions; sequence/flow lives INSIDE the class definition.
dev_plan parts B6 (§4.1) + B7 (§4.2) + B8 (§4.3).

**Inputs:** architecture §4.1#1-8·§5.1·§5.5·§5.8·§6.1·§7·§8·§10·diagram §5; dev_plan B6·B7·B8;
§1-§3 of the design doc, a-domain (A1/A2/A3).

**In scope:**
- **B6 → §4.1 types·indicators:** class diagram + definition — `types` (`Candle`·`Order`·`Position`·
  `Trade`·`Fill`·enums·`money` with FULL fields: name·type·constraint·default·nullability +
  validation invariants) and `indicators` (`IndicatorSpec`·`registry`·`IndicatorState`·`contracts`,
  the finalized 82-list + seed/warm-up rule). Indicator compute FLOW inside the definition.
- **B7 → §4.2 strategy (+config sequence):** class diagram + definition — `StrategyAdapter` (Protocol)
  · `Adaptee` · `Adapter Manager` · `StrategyConfig` · `trailing` · `profile`, each method with FULL
  signature + semantics. The Adaptee-create + config-`resolve` SEQUENCE (mermaid) inside the
  definition. Boundary: schema DECLARED by Adaptee, RESOLVED by StrategyConfig, CREATED by Manager.
- **B8 → §4.3 execution·eval (+judgment flow):** class diagram + definition — `execution`
  (matcher·position_book·accounting·order_lifecycle), `costs` (fee·slippage·funding·liquidation),
  `sizing` (risk_money·turtle_unit·kelly), `ports` (the port ABCs), `eval`
  (metrics·integrity·hard_gate·decision·thresholds·profile — actual formulas + actual thresholds).
  The judgment pipeline (Integrity→Hard Gate→Decision) FLOW (mermaid) inside the eval definition.

**Out of scope (escalate / do NOT do):**
- backtest-service classes (b-service-classes); DB ERD/schema (b-database); code; DB connection.
- Re-deciding any of the 16 invariants (Decimal single-cast gate, look-ahead, statelessness, net,
  1R≤1%, etc.) — state each as an explicit rule the class enforces, never relax it.

**Done when:**
- §4.1, §4.2, §4.3 appended to `backtest_v2_detailed_design.md` — UML-FIRST: one mermaid
  `classDiagram` per component that CARRIES every attribute+type, every method/port signature
  (params + returns), and every relationship (inheritance/composition/dependency) + stereotype; the
  accompanying definition supplies ONLY the residue the diagram cannot encode — per attribute
  `constraint · default · nullable · validation`, per method `semantics`, the class `responsibility`,
  and the `invariant it enforces`. Do NOT restate the attribute/signature list in prose; do NOT leave
  a relationship out of the diagram. The config-resolve sequence and the judgment flow are mermaid
  diagrams INSIDE their class definitions (not separate chapters).
- The 82-indicator list, all metric formulas, and all Hard-Gate thresholds are written OUT IN FULL
  (actual numbers) — a Phase C implementer builds from the doc alone. NO foreign-document label
  (architecture §N / dev_plan BN·마이그N / diagrams §N) — actual names + own §1-§5 only; the closing
  Traceability table NAMES each requirement, never labels it.
- Each touched invariant is stated as an explicit class-level rule (preserved, not re-decided).
- `spec-consistency-auditor` PASS (§4.1#1-8·5.1·5.8·6.1·7·8·10; schema=Adaptee/resolve=Config/create=Manager;
  self-contained + full-absorption + document-structure) and `cto-reviewer` APPROVE, and
  `cross-model-reviewer` (Codex) returned no open Must-fix, all in this transcript.
- Turn budget: ≤ <fill in> orchestrator turns. If exceeded → STOP and escalate.

**Register with /goal (example):**

Stage b-corelib-classes is complete only when §4.1 (types·indicators), §4.2 (strategy + config
sequence) and §4.3 (execution·eval + judgment flow) are appended to backtest_v2_detailed_design.md as
one mermaid classDiagram per component with full attribute+method definitions, the 82-list/formulas/
thresholds written out in full, sequence & flow embedded in the class definitions, every invariant
stated as a class rule, and spec-consistency-auditor PASS + cto-reviewer APPROVE + cross-model-reviewer
no-open-Must-fix in this transcript. Until then, continue the named gaps. Do not declare completion
from a feeling of "enough".
