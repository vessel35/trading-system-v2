# Stage b-database Objective — 설계서 §5 데이터베이스 ERD (read-only inputs; design doc out)

> Set `DESIGN_STAGE=b-database`. Register the Done-when block below as a `/goal`.
> Precondition: b-skeleton…b-service-classes done (§1-§4 exist). Append §5.1-§5.3 to the SAME doc.
> Per 원칙 4, the database is described by ERD, SEPARATE from the §4 classes.

**Goal:** Author the database design — §5 of `backtest_v2_detailed_design.md` — as ER diagrams +
field definition tables, DB by DB. This stage owns the two central deferred items (backtest_db fields
§9.3, Evidence Entity fields §9.6). dev_plan parts B11 (§5.1) + B12 (§5.2) + B13 (§5.3).

**Inputs:** architecture §5·§9(9.2·9.3·9.5·9.6)·diagram §7; dev_plan B11·B12·B13 + 원칙 4;
§1-§4 of the design doc (esp. §4.5 `EvidenceSink`/`CatalogStore` write contracts), a-infra (A4/A5).

**In scope:**
- **B11 → §5.1 DB 전체 구성 + crypto_data·signal_db:** a mermaid diagram of all stores
  (`crypto_data`〈shared·read〉 · `backtest_db`〈new·meta〉 · `signal_db`〈existing + Adaptee registry〉 ·
  Evidence SQLite〈per-run〉) with role · access(read/write) · boundary; + a mermaid `erDiagram` +
  field table for the `crypto_data` tables the backtest reads (ohlcv strategy-TF · 1m execution feed ·
  funding) and for the **Adaptee registry** to add to `signal_db`.
- **B12 → §5.2 backtest_db ERD + 테이블 정의서:** a mermaid `erDiagram` of `backtest_db`
  (`backtest_run` · `backtest_summary` · `backtest_prereg` · `backtest_tag`, `run_id` 1:1/0..1/N) +
  a definition table per table (**every column: name·type·constraint·key·nullable·default** — the
  §9.3 deferred fields written OUT IN FULL, 용도 불변) + the `run_id` single-issue / normalized-hash /
  FK-not-enforced rules.
- **B13 → §5.3 Evidence SQLite ERD + Entity 정의서:** a mermaid `erDiagram` of the Evidence SQLite
  (basic 13 Entities + extended 7, with relations) + a definition table per Entity (**every column:
  name·type·constraint·key·nullable·default** — the §9.6 deferred fields written OUT IN FULL, 용도
  불변) + the run-self-contained (local Backtest Run copy) / `backtest_run_id` reference rules.

**Out of scope (escalate / do NOT do):**
- Class internals (already in §4); executed DDL (design the schema, don't run it); code.
- Changing any Entity's §9 PURPOSE (용도 불변 — only fields are finalized). Duplicating the ER as
  prose (it must be a mermaid erDiagram).

**Done when:**
- §5.1, §5.2, §5.3 appended to `backtest_v2_detailed_design.md` — each a mermaid `erDiagram` + a
  full field-definition table; every §9.3 backtest_db field and every §9.6 Evidence Entity field is
  written OUT IN FULL (type + constraint + key + nullable + default), with each Entity's 용도 unchanged.
- The normalized-hash / run_id single-issue / FK-not-enforced rules are stated.
- SELF-CONTAINED (a Phase C implementer creates the schema from the doc alone); DB separated from
  classes per 원칙 4; NO foreign-document label (architecture §N / dev_plan BN·마이그N / diagrams §N) —
  actual names + own §1-§5 only; the closing Traceability table NAMES each requirement, never labels it.
- `spec-consistency-auditor` PASS (§9.2·9.3·9.6·diagram §7; 용도 불변; DB-by-ERD; document-structure)
  and `cto-reviewer` APPROVE (+ `cross-model-reviewer` no open Must-fix, since §5 carries the central
  deferred fields) in this transcript.
- Turn budget: ≤ <fill in> orchestrator turns. If exceeded → STOP and escalate.

**Register with /goal (example):**

Stage b-database is complete only when §5.1 (DB overview + crypto_data/signal_db ERDs), §5.2
(backtest_db ERD + full table definitions) and §5.3 (Evidence SQLite ERD + full Entity definitions)
are appended to backtest_v2_detailed_design.md as mermaid erDiagrams + full field tables, every §9.3
and §9.6 field written out in full with purpose unchanged, and spec-consistency-auditor PASS +
cto-reviewer APPROVE in this transcript. Until then, continue the named gaps. Do not declare
completion from a feeling of "enough".
