# Stage b-adoption Objective — core-lib adoption / reconciliation / regression (read-only inputs; design notes out)

> Set `DESIGN_STAGE=b-adoption`. Register the Done-when block below as a `/goal`.
> Precondition: all prior stages (a-domain, a-infra, b-corelib, b-engine-eval) are complete.

**Goal:** Finalize the plan (B8) by which the KEPT production services (signal-service = live/paper
signals, wallet-service = execution) adopt `core-lib` with behavior UNCHANGED, plus the new
backtest's validation baseline (the old↔new reconciliation is WAIVED per A6 — the old backtest is a
removal target), the regression re-verification scope, the `fill_timing` switch point, and the
credential rotation. This is the design bridge to Phase C part C7 and the direct answer to "keep
parts of Live/Paper, rebuild the rest". Output is a design NOTE + checklists, not code.

**Inputs:** architecture §13 (마이그7 adoption) + §2·§4.2.1·§9.2·§14; dev_plan
B8 + C7a/C7b; a-infra A6 (removal list + reconciliation waiver), a-domain A2·A3 (what is adopted),
b-corelib B1-B4 + b-engine-eval B5 (what the kept services adopt).

**In scope:**
- **Adoption points + shim:** where signal/wallet internal implementations (indicators, strategy,
  execution, sizing) are replaced by `core_lib` imports, and where a **re-export shim** sits so each
  service's internal call sites keep working with no downtime → the C7a sequence.
- **New-backtest validation baseline (reconciliation waived):** record that the old↔new 대사 is
  WAIVED (A6 — the old backtest is a removal target, not referenced) → in its place, specify how the
  new backtest is validated: its own golden/parity tests + the bias-fix port targets handed to Phase
  C (from A6) as the acceptance baseline, instead of a numeric old↔new 대사.
- **Regression scope:** which existing tests must still pass unchanged (wallet regression 1175) →
  the `fill_timing` default `immediate → next_bar` switch point + when it triggers a wallet
  re-verification (record the switch in meta) → the live-indicator equivalence check (first target
  `adx_14`: old precompute-table value ↔ `core_lib` incremental value).
- **Credential rotation:** the procedure for the plaintext-committed passwords found in A4.
- Deliver `B8_adoption_reconciliation_regression.md` (adoption points · shim placement · new-backtest
  validation baseline + reconciliation-waiver record · regression checklist · fill_timing switch ·
  credential rotation).

**Out of scope (escalate / do NOT do):**
- Any code; ANY modification of the production signal/wallet repos (design only — C7 executes it).
- Re-deciding B1-B7 contracts; reading the removed backtest to build an old↔new 대사 (waived per A6).
- Weakening the "adoption changes nothing observable in production" principle.

**Done when:**
- `B8_adoption_reconciliation_regression.md` exists under `OUTPUT_DIR` with all five sub-plans
  (adoption points, shim, new-backtest validation baseline + reconciliation waiver, regression,
  credential rotation).
- The note is SELF-CONTAINED (standalone-implementable): every adoption point, shim placement,
  regression item, and switch step is written OUT IN FULL — a Phase C implementer executes C7 from it
  without opening the guideline. §-citations only in a closing Traceability table.
- The plan preserves production behavior unchanged (wallet 1175 unchanged; fill_timing switch has an
  explicit re-verification trigger + meta record).
- The reconciliation waiver is stated explicitly (A6) and the new backtest's own validation baseline
  (golden/parity + bias-fix port targets) is named in its place.
- `spec-consistency-auditor` returned PASS (§13 채택 시 프로덕션 동작 불변 원칙; §4.2.1 governance;
  §9.2 계승) in this transcript.
- `cto-reviewer` returned APPROVE on the adoption/shim/regression plan (P1-P4: hidden assumptions
  about the kept services, no over-design, verification present).
- Complete enough that Phase C parts C7a/C7b execute from this plan without re-deciding.
- Turn budget: ≤ <fill in> orchestrator turns. If exceeded → STOP and escalate.

**Register with /goal (example):**

Stage b-adoption is complete only when B8_adoption_reconciliation_regression.md exists under
OUTPUT_DIR with the five sub-plans (adoption points, shim, new-backtest validation baseline +
reconciliation waiver, regression, credential
rotation), the plan preserves production behavior unchanged with an explicit fill_timing
re-verification trigger, spec-consistency-auditor returned PASS and cto-reviewer returned APPROVE in
this transcript, and no production repo was modified. Until then, continue the named gaps. Do not
declare completion from a feeling of "enough".
