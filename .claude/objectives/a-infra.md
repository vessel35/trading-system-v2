# Stage a-infra Objective — Port-Source Inventory: types / data infra / baseline (read-only)

> Set `DESIGN_STAGE=a-infra`. Register the Done-when block below as a `/goal`.

**Goal:** Inventory the shared types + config + DB creation plan (A4), the collector internalization
scope (A5), and the removal list + reconciliation decision (A6). Output is the type-port list, the
DB-creation plan, the collector "take vs drop" boundary, and the removal/reconciliation record — not
code and not design.

**Inputs:** architecture §4.1#1·§9.2·§3.3·§14·§2·§4.1#9; dev_plan A4·A5·A6; legacy (READ-ONLY): under
`TRADING_SYSTEM_DIR` — wallet `entities/`·`value_objects.py`, signal `TradingSignal`, each
`core/config.py`, `init-scripts/` (01~03); under `CRYPTO_DATA_HUB_DIR` — the collector service (for
A5). **backtest/replay under `TRADING_SYSTEM_DIR` are removal targets — do NOT read them** (this
supersedes the dev_plan A4/A6 lines that read `services/backtest/`). Dispatch `reference-scout` for
the extractions (it resolves each repo's exact layout).

**In scope:**
- **A4 types/config/DB:** shared-type port list → the new project's `backtest_db` creation approach
  (init-scripts numbering + `backtest-service/` migration dir) sourced from `init-scripts/` + infra,
  NOT from the removed backtest service (the old backtest is a removal target, so any prior
  `backtest_db`/`backtest_writer` there is legacy-to-clean, not a live inheritance source — record
  whether the new project keeps or renames the DB name/role) → identify plaintext-committed passwords
  for rotation. Deliver `A4_types_config_db_inventory.md`.
- **A5 collector:** in `CRYPTO_DATA_HUB_DIR`, split what the collector does into **OHLCV ingest** vs
  **indicator precompute** → list dependencies / config / credentials → fix the boundary: take
  **ingest only** into an internal `OHLCV 수집기`, DROP indicator precompute + the
  `technical_indicators` table read → confirm 1m + strategy-TF OHLCV ingest range (1m data from
  2025-03, for the 1m execution feed). Deliver `A5_collector_internalization_scope.md`
  (take / drop / deps / credential rotation). If a needed collector file is absent, record it as a
  blocker with its path — do not invent the repo layout.
- **A6 removal list + reconciliation decision:** list the removal targets NOT referenced by this
  build (the old `services/backtest/` engine·CLI·mock·sys.path swap·harness·indicator 복제, and
  `replay`) → **the old↔new backtest reconciliation baseline is WAIVED** (recorded with rationale:
  the old backtest is a removal target the team opted not to reference; a numeric old↔new 대사 is not
  performed) → note the bias-fix 31 test scenarios (on the `feat/vessel-reversion-short-only` branch
  of the removed backtest) as a **port target handed to Phase C** — identified by name/branch, NOT
  read here. Deliver `A6_baseline_and_reconciliation.md` (removal list + reconciliation-waiver record
  + bias-fix port-target handoff).

**Out of scope (escalate / do NOT do):**
- Deciding entity FIELDS (that is B6) or the port list of ports (B1); any code; modifying legacy files.
- Reading `services/backtest/` or `replay` — they are removal targets, not referenced; the old↔new
  reconciliation baseline is waived, not built here.

**Done when:**
- `A4_types_config_db_inventory.md`, `A5_collector_internalization_scope.md`,
  `A6_baseline_and_reconciliation.md` exist under `OUTPUT_DIR`.
- Each inventory is SELF-CONTAINED: it states the actual extracted content (the real type/field,
  config key, ingest boundary, removal item) inline with its `file:symbol` provenance — not a bare
  pointer — so b-corelib/b-engine-eval design from the inventory itself.
- The `backtest_db` creation plan (A4) is sourced from `init-scripts/` + infra (cited), with the
  keep-or-rename DB-name/role decision recorded; credential-rotation targets are listed.
- `spec-consistency-auditor` returned PASS (§9.2 DB-creation 규약, §14 "collector는 적재만",
  and the A6 reconciliation-waiver is explicit + rationalized, not silently dropped) in this transcript.
- `cto-reviewer` returned APPROVE on the DB-creation plan + collector boundary + removal/waiver record.
- Complete enough that b-corelib (B2 types from A4) and b-engine-eval (B6 fields from A4) and
  b-adoption (B8 reads the A6 removal list + reconciliation waiver) proceed without re-inventorying.
- Turn budget: ≤ <fill in> orchestrator turns. If exceeded → STOP and escalate.

**Register with /goal (example):**

Stage a-infra is complete only when the three notes (A4 types/config/DB, A5 collector scope, A6
removal list + reconciliation waiver) exist under OUTPUT_DIR, the backtest_db creation plan is
sourced from init-scripts + infra (not the removed backtest), the A6 reconciliation waiver is
explicit and rationalized, spec-consistency-auditor returned PASS and cto-reviewer returned APPROVE
in this transcript, and no legacy file was modified (backtest/replay were not read). Until then,
continue the named gaps. Do not declare completion from a feeling of "enough".
