# Detailed Design Document Standard (UML-first, top-down, mermaid)

Every Phase B design document follows this standard. Goal: the reader grasps the BIG STRUCTURE first
and reads strictly top-down, never jumping to another doc or a later chapter to understand the
current point. All UML/diagrams are **mermaid** (apply the `mermaid-conventions` skill). This standard
COMPOSES with self-containment: the diagrams + their residual prose ARE the full content, so a
Phase C implementer builds from the doc alone.

## UML-first (the primary representation rule)

The detailed design is expressed **in UML by default; prose is only for what UML cannot encode.** The
mermaid diagram is the PRIMARY carrier of the design — structure and behavior go INTO the diagram, and
prose is a SUPPLEMENT for the residue the notation genuinely cannot hold.

- **Put in the diagram (UML can express it):** class attributes with their types and visibility;
  method / port signatures (parameters + return types); class relationships (inheritance, composition,
  aggregation, dependency) with cardinality; `«interface»` / `«abstract»` stereotypes; ER entities
  with attributes, primary/foreign keys, and relationship cardinality; sequence interactions
  (participants, message order, `alt`/`opt`/`loop`); control flow and state transitions. If UML can
  show it, it lives in the diagram — not in a prose table that restates the diagram.
- **Put in prose (UML cannot encode it), as a short supplement under the diagram:** value constraints
  and validation rules; default values and nullability semantics; numeric thresholds + where they are
  tuned; formulas (expression · units · boundary conditions); the invariants a class/method enforces;
  error / edge-case behavior; responsibility and boundary text at the service/component level (UML
  shows the "what/how-connected", not the "why"); config-key meanings; design rationale and direction.
- **Two prohibitions.** Do NOT restate in prose what the diagram already shows (no attribute/method/
  entity list duplicated as a table when it is in the `classDiagram`/`erDiagram`). Do NOT push into
  prose what the diagram could show (no attributes/signatures/relationships hidden in paragraphs
  because drawing them was easier to skip). The diagram + its residual prose together are the full,
  self-contained contract — with no overlap and no gap.

## Residual-prose clarity (two rules — the residue must READ, not just list)

The residual prose under each diagram is what a reader actually reads for the why / constraints /
to-do. These two rules keep it legible. They REFINE the UML-first "prose for residue" split above —
they do not license restating the diagram (the diagram-restatement prohibition still holds in full).

1. **No bare term-lists — every item must carry its own meaning.** Do not string together bare nouns
   or identifiers (`A·B·C·D`) the reader cannot decode. Give each item its point — what it is, what it
   becomes, or what it is for: write `` `Adapter Manager`(생성)·`StrategyConfig`(파라미터 해석) `` , not
   `manager·config`. This holds inside a table cell too — a cell of undecodable tokens is still a
   defect. (Do not put diagram node-IDs like `MGR`/`REG` in prose; use the real names.)
2. **Separate the POINT from the TO-DO — never mix them in a run-on paragraph.** When a passage carries
   both "what this is / changes" and "what must be done / verified", split them so each is one
   scannable line, not buried in a paragraph:
   - a **change / replacement** with several targets → a residual-prose table whose columns name the
     axes (`대상 · 현행 · 바꾼 뒤 · 확인`). This table describes a mapping no diagram carries, so it is
     NOT a diagram restatement — but keep it to residual content (never duplicate a diagram's
     attributes/relationships as a table).
   - the **actions / gates** that follow → an explicit `해야 할 것` outline, each action its own bullet,
     kept apart from the descriptive text.
   - only one or two items → a short topic-labeled outline (개조식) is enough; reserve tables for a
     GENUINE multi-item side-by-side (a one-row table is a smell — use a sentence or an outline).

   Prefer a topic-labeled outline over a wall of paragraphs: give each note a bold lead-in that names
   its subject, so the reader sees at a glance what each block is about.

## Mandatory section order (every design doc)

1. **제약사항·방향 (Constraints & Direction)** — FIRST, before any detail. State ONLY: the binding
   constraints (the invariants this part must satisfy — look-ahead, `decision_ts<execution_ts`, the
   Decimal single-cast gate, etc., each as an explicit rule), the design direction (the approach
   chosen + why, briefly), and the scope (what this doc covers / excludes). No class-level detail
   here — this frames the top-down read.
2. **서비스 다이어그램 & 정의서 (Service)** — in the system-overview doc (B1) only: a mermaid diagram
   of the services/packages (`core_lib`, `backtest-service`, the kept signal/wallet) + their
   relations, and a definition table (each service: responsibility · boundary · dependencies · what
   it owns). Every other doc states its place in this map in ONE line, then drops to its own level.
3. **컴포넌트 다이어그램 & 정의서 (Component)** — per service, a SEPARATE component diagram (mermaid)
   of the components inside it, + a definition (each component: responsibility · public interface ·
   dependencies · the classes it holds). One diagram per service — never mix services in one diagram.
4. **클래스 다이어그램 & 정의서 (Class)** — per component, a SEPARATE mermaid `classDiagram` that
   CARRIES the structure: every class with its attributes+types, its method/port signatures
   (params + returns), and its relationships (inheritance/composition/dependency) + stereotypes. The
   accompanying definition adds ONLY the UML-inexpressible residue per member — `constraint · default ·
   nullable · validation`, method `semantics`, the class `responsibility`, and the `invariants it
   enforces`. Do not restate the attribute/signature list in prose; do not leave a structural relation
   out of the diagram. One diagram per component.
5. **공통 (Shared / common)** — shared components and shared classes live in their OWN section with
   their own diagrams, referenced by the services/components that use them — NEVER duplicated inline
   per consumer.
6. **시퀀스·플로우 (Sequence / Flow)** — described WITHIN the relevant class's definition (NOT a
   separate top-level chapter): a mermaid `sequenceDiagram` or `flowchart` for that class's key
   method interaction / control flow (e.g. the Engine candle loop, the 1m trigger walk, the judgment
   pipeline, the write transaction).
7. **DB 엔티티 (Database entities)** — as a mermaid `erDiagram` that CARRIES each entity's fields with
   their `name · type` and primary/foreign `key`s plus relationship cardinality. The accompanying
   field table adds ONLY what the ER notation cannot hold — `constraint · nullable · default ·
   semantics` per field. Evidence SQLite and `backtest_db` each get their own ER diagram.

## Rules

- **Top-down, no forward jumps.** The reader never opens another doc or scrolls to a later chapter to
  understand the current point. Big structure (service → component) precedes detail (class → method);
  any concept a detail needs was introduced above it.
- **Diagram + residual prose always paired.** Every diagram is immediately followed by the prose that
  supplies what the diagram cannot encode (constraints, defaults, formulas, thresholds, invariants,
  semantics, rationale). A diagram with no residual prose (where residue exists), or prose that
  restates the diagram or that hides structure the diagram should carry, is incomplete. UML-first
  (above) governs the split.
- **All UML in mermaid.** `classDiagram` / `sequenceDiagram` / `flowchart` / `erDiagram` / `graph`,
  in ` ```mermaid ` fences (top-level, never nested inside another fence). No ASCII art; no
  prose-only structure where a diagram is expected. Follow the `mermaid-conventions` skill.
- **One service per component diagram; one component per class diagram.** Do not cram multiple
  services' components, or multiple components' classes, into a single diagram.
- **Shared elements separated once.** Common components/classes are defined once in the shared
  section and referenced — not re-drawn per consumer.
- **Composes with self-containment.** The diagram (structure) + its residual prose (constraints,
  defaults, formulas, thresholds, invariants, semantics) together carry the actual fields / signatures
  / values in full. NO foreign-document label appears anywhere in the deliverable — not the architecture doc's
  `§N`/`#N`, not the dev_plan's `AN`/`BN`/`마이그N`, not `다이어그램 §N`. Use actual names + the design
  doc's own `§1`-`§5` numbers. The closing Traceability table names the guideline requirement it
  satisfies (e.g. "look-ahead prevention"), never labels it.

## One document, built top-down (dev_plan §4 / 원칙 3)

Phase B produces a SINGLE document `backtest_v2_detailed_design.md`. Its section order IS the part
order; each stage appends the next sections. Because it is ONE document read top-down, an internal
reference to an already-written earlier section (e.g. "§3.1 core-lib components") is FINE — that is
top-down structure, not a jump to another doc. Self-containment forbids referencing the GUIDELINE for
content, not referencing an earlier section of this same doc.

## Which stage owns which section (dev_plan part → 설계서 절)

- **b-skeleton** — §1 SERVICE diagram + definition (B1); §2 code tree (B2); + the §1-§5 reading map.
  CREATES the doc. This is the ENTRY.
- **b-components** — §3.1 core-lib COMPONENT diagram (B3, shared — defined once here); §3.2
  backtest-service components (B4, finalizes the concrete port list); §3.3 adoption components (B5).
- **b-corelib-classes** — §4.1 types·indicators CLASS diagrams (B6); §4.2 strategy classes + the
  config-resolve SEQUENCE (B7); §4.3 execution·eval classes + the judgment-pipeline FLOW (B8).
- **b-service-classes** — §4.4 Engine class + the candle-loop & 1m-trigger-walk SEQUENCE (B9); §4.5
  output classes (`EvidenceSink`/`CatalogStore`) + the run-save SEQUENCE (B10).
- **b-database** — §5.1 DB overview + crypto_data/signal_db ER (B11); §5.2 backtest_db ER + table
  defs (B12); §5.3 Evidence SQLite ER + Entity defs (B13). DB by ERD, separate from §4 classes (원칙 4).
- **b-adoption** — appendix: adoption + shim SEQUENCE, regression FLOW, credential rotation (B14).

> Phase A inventories are analysis, not detailed design — but use the same diagram vocabulary where
> it clarifies (e.g. a component/class sketch of the legacy code being ported, an ER of a legacy
> table), and always lead with 제약사항·방향.
