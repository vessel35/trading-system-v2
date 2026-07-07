# Stage b-skeleton Objective — 설계서 §1 서비스 + §2 코드 트리 (read-only inputs; design doc out)

> Set `DESIGN_STAGE=b-skeleton`. Register the Done-when block below as a `/goal`.
> Precondition: BOTH a-domain and a-infra are complete (their inventories are inputs).
> This stage CREATES the single detailed-design document `backtest_v2_detailed_design.md` under
> `OUTPUT_DIR` and writes its top two sections. Every later Phase B stage appends to THIS doc.

**Goal:** Author the TOP of the top-down detailed design — the service view and the project code
tree — as §1 and §2 of `backtest_v2_detailed_design.md`. This is the skeleton every later section
hangs off. dev_plan parts B1 (§1) + B2 (§2).

**Inputs:** architecture §0.1·§4.1·§4.2; dev_plan §0·§0.2·B1·B2 + 원칙 1-4; the a-domain + a-infra
inventories under `OUTPUT_DIR`. (§N = architecture doc; dev_plan part = AN/BN — see dev_plan §0.2.)

**In scope:**
- **B1 → §1 서비스 다이어그램 + 정의서:** a mermaid diagram of the services/stores (`core-lib`
  package · `backtest-service` · existing `signal-service`/`wallet-service` · stores `crypto_data`,
  `backtest_db`, `signal_db`, Evidence SQLite) with dependency direction, + a service definition
  table (each service/store: responsibility · boundary · what it consumes · packaging;
  core-lib = installable shared package). backtest/replay are NOT services here (removal targets).
- **B2 → §2 프로젝트 코드 트리:** the full new-project tree — `core-lib`'s
  `core_lib/{types,indicators,strategy,sizing,costs,execution,ports,eval}` + `backtest-service` tree
  — each path with a one-line role. The tree nodes map 1:1 to the components later drawn in
  b-components (§3).
- Write the document's 목차 (the fixed §1-§5 + appendix outline from dev_plan §4) as a reading map so
  the reader sees the whole structure up front.

**Out of scope (escalate / do NOT do):**
- Any component-internal or class-level detail (that is b-components / b-corelib-classes onward);
  any code; any DB connection.
- Introducing an identifier (class/field/file) before its containing unit (service→component) is
  defined — 정의 우선 (dev_plan §0, 원칙 3).

**Done when:**
- `backtest_v2_detailed_design.md` exists under `OUTPUT_DIR` with §1 (service diagram + definition)
  and §2 (code tree) filled, plus the full §1-§5 + appendix 목차/reading map.
- Both diagrams are mermaid; every service/store and every tree path has its definition (SELF-CONTAINED
  — the reader needs no other doc). UML-FIRST at this level: the service diagram CARRIES the services/
  stores and their dependency direction (arrows); prose supplies ONLY what it cannot — each service's
  responsibility, boundary, and packaging. Don't put a dependency in prose that the diagram should
  draw. NO foreign-document label (architecture §N / dev_plan BN·마이그N /
  diagrams §N) — actual names + own §1-§5 only; the closing Traceability table NAMES each requirement.
- Reads strictly top-down: service before tree; nothing references a not-yet-defined lower unit.
- `spec-consistency-auditor` returned PASS (§0.1·§4.1 dependency direction; §4.2 tree↔component 1:1;
  정의 우선; document-structure standard) and `cto-reviewer` returned APPROVE in this transcript.
- Turn budget: ≤ <fill in> orchestrator turns. If exceeded → STOP and escalate.

**Register with /goal (example):**

Stage b-skeleton is complete only when backtest_v2_detailed_design.md exists under OUTPUT_DIR with a
mermaid service diagram + service definition table (§1) and the full code tree with per-path roles
(§2) and the §1-§5 reading map, everything self-contained and top-down (service before tree, no
forward-referenced identifier), spec-consistency-auditor returned PASS and cto-reviewer returned
APPROVE in this transcript. Until then, continue the named gaps. Do not declare completion from a
feeling of "enough".
