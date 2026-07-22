# Stage b-database Objective — 데이터베이스 설계서 §5 (read-only inputs; design doc out)

> Set `DESIGN_STAGE=b-database`. Register the Done-when block below as a `/goal`.
> Precondition: b-skeleton…b-service-classes done (§1-§4 exist in `backtest_v2_detailed_design.md`).
> Per 원칙 4, the database is described by ERD, SEPARATE from the §4 classes.
>
> **DOCUMENT-SPLIT divergence (user-confirmed 2026-07-22).** The harness default "Phase B produces ONE
> document" is OVERRIDDEN for this stage: `backtest_v2_detailed_design.md` has grown past ~3.4k lines
> and re-reading it whole degrades analysis. The database design is therefore authored as a SEPARATE
> sibling file `backtest_v2_detailed_design_database.md` in `OUTPUT_DIR`, NOT appended to the main doc.
> Section numbers stay **§5.1-§5.3** so every existing cross-reference in §1-§4 ("데이터베이스 상세는
> §5") remains valid without renumbering prior sections. The main doc's 읽기 지도 table gets its §5 row
> repointed to the new file (and its stale "§4.4~§4.5 예정" status corrected) — that edit is the ONLY
> change to the main doc in this stage. The two files are ONE design set: the DB doc may name the main
> doc by its actual title and its own §-numbers; that is a sibling deliverable, never a guideline
> reference, and the no-foreign-label rule (architecture §N / dev_plan BN / diagrams §N) still holds.

**Goal:** Author the database design — §5, in its own file `backtest_v2_detailed_design_database.md` —
as ER diagrams + field definition tables, DB by DB. This stage owns the two central deferred items
(backtest_db fields §9.3, Evidence Entity fields §9.6). dev_plan parts B11 (§5.1) + B12 (§5.2) + B13 (§5.3).

**Inputs:** architecture §5·§9(9.2·9.3·9.5·9.6)·diagram §7; dev_plan B11·B12·B13 + 원칙 4;
§1-§4 of the design doc (esp. §4.5 `EvidenceSink`/`CatalogStore` write contracts), a-infra (A4/A5).

**In scope:**
- **문서 서두 — 제약사항·방향 (split 때문에 필수):** the DB doc opens with its own 목적·범위, the
  invariants the SCHEMA enforces (연구/운영 DB 분리 · 확정 캔들만 적재해 look-ahead를 뒷받침 ·
  run_id 단일 발급 · 정규화 해시 결정성 · 모든 손익 net 필드 의미), and a 읽기 지도 for §5.1-§5.3.
  Without it the split file is not standalone-implementable.
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
- **Main-doc 읽기 지도 repoint:** the §5 row of `backtest_v2_detailed_design.md`'s 문서 구성 table names
  the new file and its state; the §4 row's status is corrected to 확정. Nothing else in the main doc changes.

**Out of scope (escalate / do NOT do):**
- Class internals (already in §4); executed DDL (design the schema, don't run it); code.
- Changing any Entity's §9 PURPOSE (용도 불변 — only fields are finalized). Duplicating the ER as
  prose (it must be a mermaid erDiagram).
- Renumbering §1-§4 or moving any existing section into the new file; rewriting main-doc content
  beyond the two 읽기 지도 rows.

**Done when:**
- `backtest_v2_detailed_design_database.md` exists in `OUTPUT_DIR` with 제약사항·방향 + §5.1 + §5.2 +
  §5.3 — UML-FIRST: each a mermaid `erDiagram` that CARRIES every entity's fields with `name · type`,
  its primary/foreign keys, and its relationship cardinality; the accompanying field table supplies
  ONLY the residue the ER notation cannot hold — per field `constraint · nullable · default ·
  semantics`. Together they write every §9.3 backtest_db field and every §9.6 Evidence Entity field
  OUT IN FULL, with each Entity's 용도 unchanged. Do NOT restate `name·type·key` in prose (they are in
  the erDiagram); do NOT leave a field or key out of the erDiagram.
- The normalized-hash / run_id single-issue / FK-not-enforced rules are stated.
- SELF-CONTAINED **as a split volume**: a Phase C implementer creates the whole schema from this file
  alone, without opening the guideline AND without needing §1-§4 for any field, type, constraint or
  rule. DB separated from classes per 원칙 4; NO foreign-document label (architecture §N / dev_plan
  BN·마이그N / diagrams §N) — actual names + own §-numbers only; the closing Traceability table NAMES
  each requirement, never labels it.
- The main doc's 읽기 지도 §5 row points to the new file; no other main-doc content changed.
- `spec-consistency-auditor` PASS (§9.2·9.3·9.6·diagram §7; 용도 불변; DB-by-ERD; document-structure;
  split-file self-containment) and `cto-reviewer` APPROVE (+ `cross-model-reviewer` no open Must-fix,
  since §5 carries the central deferred fields) in this transcript.
- Turn budget: ≤ 40 orchestrator turns. If exceeded → STOP and escalate.

**Register with /goal (example):**

Stage b-database is complete only when the separate file backtest_v2_detailed_design_database.md
carries 제약사항·방향 + §5.1 (DB overview + crypto_data/signal_db ERDs) + §5.2 (backtest_db ERD + full
table definitions) + §5.3 (Evidence SQLite ERD + full Entity definitions) as mermaid erDiagrams + full
field tables, every §9.3 and §9.6 field written out in full with purpose unchanged, standalone-
implementable without §1-§4, the main doc's 읽기 지도 §5 row repointed to it, and spec-consistency-
auditor PASS + cto-reviewer APPROVE in this transcript. Until then, continue the named gaps. Do not
declare completion from a feeling of "enough".
