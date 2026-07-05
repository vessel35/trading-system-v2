# Stage b-engine-eval Objective — runtime + persistence + judgment (read-only inputs; design notes out)

> Set `DESIGN_STAGE=b-engine-eval`. Register the Done-when block below as a `/goal`.
> Precondition: a-domain, a-infra, and b-corelib are complete (their notes are inputs).

**Goal:** Finalize the Engine loop + 1m execution feed + look-ahead mechanics (B5), the output-layer
Entity FIELDS the doc left as "용도만" (B6 — the central deferred items §9.3/§9.6), and the
metrics + Hard Gate + Decision pipeline (B7). Output is design NOTES (pseudocode, field tables,
formulas, thresholds), not code and not executed DDL.

**Inputs:** architecture §6.2·§7·§8·§9(9.1-9.7)·§10(10.1-10.4)·§11.1·§14 + diagrams §2·§4·§5·§7;
dev_plan B5·B6·B7; a-domain A3 (for B5), a-infra A4 (for B6), b-corelib B1·B2 (the B1 port
signatures B5 consumes).
(Note: B6 and B7 are co-dependent — B6 fields must carry what B7 stores, B7 reads B6 entities —
so finalize them together in this session.)

**In scope:**
- **B5 Engine + 1m feed + look-ahead:** candle-loop pseudocode (§6.2 two moments: open / close) →
  how the bounded `DataFeed` structurally forbids future exposure → **1m execution-feed trigger
  walk** (stop / trailing / liquidation judged over the `t` interval's 1m sub-candles in time
  order) → where `decision_ts < execution_ts` is enforced → warm-up preload rule. Deliver
  `B5_engine_1m_lookahead.md` (loop + 1m-trigger pseudocode). State the trailing-parity tolerance
  vs the live 1m path (the §14 / diagram-4 deferred "평가 주기 갭").
- **B6 output-layer Entity fields (the core deferred items):** **Evidence SQLite Entity fields**
  (basic 13 + extended 7) → **`backtest_db` meta 4-table fields** (backtest_run / backtest_summary /
  backtest_prereg / backtest_tag) → the normalized Evidence hash rule (row bytes not file bytes,
  wall-clock excluded) → `EvidenceSink` / `CatalogStore` contracts. **Rule: keep each Entity's §9
  purpose unchanged — finalize FIELDS only (용도 불변, 필드만 확정).** Deliver `B6_output_entities.md`.
- **B7 judgment/eval:** metric formulas (√365 daily-resample Sharpe·Sortino·SQN·intrabar MDD·
  Calmar/MAR·RoR MC) → Integrity check items → **Hard Gate (A)** threshold canonical location +
  (B) profile check → **Decision** routing (promote / partial_keep / retest / abandon) →
  `envelope_status` maturity logic. No Scorecard; 3-stage; forensics loop. Deliver
  `B7_eval_judgment.md` (eval contract + golden cases).

**Out of scope (escalate / do NOT do):**
- Any code, any live DB connection, any executed DDL (design the schema; do not run it).
- Adoption / reconciliation / regression (B8); re-deciding B1-B4 contracts.
- Changing any Entity's §9 PURPOSE (only fields are finalized here).

**Done when:**
- `B5_engine_1m_lookahead.md`, `B6_output_entities.md`, `B7_eval_judgment.md` exist under `OUTPUT_DIR`.
- Each note is SELF-CONTAINED (standalone-implementable): every Entity field (name/type/constraint/
  default/nullability), every metric formula (expression/units/edge cases), every Hard-Gate threshold
  (actual number + where tuned), and the full 1m trigger-walk pseudocode are written OUT IN FULL — a
  Phase C implementer builds from it without opening the guideline. §-citations only in a closing
  Traceability table, never as a content-substitute in the body.
- Every §9.3 meta field and every §9.6 SQLite Entity field is finalized (types + constraints), with
  each Entity's stated 용도 unchanged; the normalized-hash rule is specified.
- The 1m trigger-walk pseudocode enforces `decision_ts < execution_ts` and the conservative
  same-touch priority (stop before TP); the trailing-parity tolerance is stated.
- `spec-consistency-auditor` returned PASS (§6.2·§7·§9·§10.2·§11.1 + diagrams §2·§5·§7; look-ahead
  order invariant; 용도 불변) in this transcript.
- `cto-reviewer` returned APPROVE and `cross-model-reviewer` (Codex) returned its critique with no
  open Must-fix, both in this transcript.
- Complete enough that Phase C parts C6a/C6b/C6c and C8/C9 implement from these fields/formulas.
- Turn budget: ≤ <fill in> orchestrator turns. If exceeded → STOP and escalate.

**Register with /goal (example):**

Stage b-engine-eval is complete only when the three notes (B5 engine+1m+look-ahead, B6 output
entity fields, B7 eval/judgment) exist under OUTPUT_DIR, every §9.3 and §9.6 field is finalized with
purpose unchanged, the 1m trigger-walk enforces decision_ts<execution_ts + stop-before-TP,
spec-consistency-auditor returned PASS and both cto-reviewer + cross-model-reviewer returned no open
Must-fix in this transcript. Until then, continue the named gaps. Do not declare completion from a
feeling of "enough".
