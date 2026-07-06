# Stage b-adoption Objective — 설계서 부록 채택·회귀 절차 (read-only inputs; design doc out)

> Set `DESIGN_STAGE=b-adoption`. Register the Done-when block below as a `/goal`.
> Precondition: all prior Phase B stages done (§1-§5 exist). Append the Appendix to the SAME doc.

**Goal:** Author the adoption / regression procedure — the Appendix of `backtest_v2_detailed_design.md`
— by which the KEPT production services (signal-service = live/paper, wallet-service = execution)
adopt `core_lib` with behavior UNCHANGED. dev_plan part B14. **The old↔new backtest reconciliation is
WAIVED (A6 decision — the old backtest is a removal target, not referenced); this supersedes the
dev_plan B14/C6c 대사 lines.**

**Inputs:** architecture §13·§4.2.1·§9.2; dev_plan B14 (adoption/regression portions only — 대사
waived); §1-§5 of the design doc (esp. §3.3 adoption components), a-domain A2·A3, a-infra A6
(removal list + reconciliation waiver).

**In scope:**
- **Adoption points + shim:** where signal/wallet internal implementations (indicators, strategy,
  execution, sizing) are replaced by `core_lib` imports, and where a re-export shim sits for
  no-downtime — the C7a sequence, as a mermaid sequence diagram + step list.
- **New-backtest validation baseline (reconciliation WAIVED):** record that the old↔new 대사 is
  waived (A6); in its place, state how the new backtest is validated — its own golden/parity tests +
  the bias-fix port targets handed to Phase C — as the acceptance baseline.
- **Regression scope:** which existing tests must still pass unchanged (wallet regression 1175);
  the `fill_timing` default `immediate → next_bar` switch point + its re-verification trigger (meta
  record); the live-indicator equivalence check (first target `adx_14`) — as a mermaid flowchart.
- **Credential rotation:** the procedure for the plaintext-committed passwords found in A4.

**Out of scope (escalate / do NOT do):**
- Any code; ANY modification of the production signal/wallet repos (design only — C7 executes it).
- Reading the removed backtest to build an old↔new 대사 (waived per A6).
- Re-deciding §1-§5 contracts.

**Done when:**
- The Appendix is appended to `backtest_v2_detailed_design.md` with all four sub-plans (adoption
  points + shim, new-backtest validation baseline + reconciliation waiver, regression, credential
  rotation), the adoption + regression rendered as mermaid sequence/flow.
- The plan preserves production behavior unchanged (wallet 1175 unchanged; fill_timing switch has an
  explicit re-verification trigger + meta record); the reconciliation waiver is explicit + rationalized.
- SELF-CONTAINED (a Phase C implementer executes C7 from the doc alone); NO foreign-document label
  (§N/BN/마이그N/diagrams) — actual names + own §1-§5, Traceability names each requirement.
- `spec-consistency-auditor` PASS (§13 채택 시 프로덕션 동작 불변; §4.2.1 governance; document-structure;
  A6 waiver honored) and `cto-reviewer` APPROVE in this transcript.
- Turn budget: ≤ <fill in> orchestrator turns. If exceeded → STOP and escalate.
- This closes Phase B: `backtest_v2_detailed_design.md` now holds §1-§5 + Appendix, complete enough
  that Phase C parts implement from it alone.

**Register with /goal (example):**

Stage b-adoption is complete only when the Appendix (adoption points + shim, new-backtest validation
baseline with reconciliation WAIVED, regression, credential rotation) is appended to
backtest_v2_detailed_design.md with adoption/regression as mermaid sequence/flow, production behavior
preserved unchanged with an explicit fill_timing re-verification trigger, and spec-consistency-auditor
PASS + cto-reviewer APPROVE in this transcript. Until then, continue the named gaps. Do not declare
completion from a feeling of "enough".
