# Stage b-adoption Objective — 설계서 부록 채택·회귀 절차 (read-only inputs; design doc out)

> Set `DESIGN_STAGE=b-adoption`. Register the Done-when block below as a `/goal`.
> Precondition: all prior Phase B stages done (§1-§5 exist). Append the Appendix to the SAME doc.

**Goal:** Author the adoption / regression procedure — the Appendix of `backtest_v2_detailed_design.md`
— by which the KEPT production services (signal-service = live/paper, wallet-service = execution)
adopt `core_lib` with behavior UNCHANGED. dev_plan part B14. **The old↔new backtest reconciliation is
WAIVED (A6 decision — the old backtest is a removal target, not referenced); this supersedes the
dev_plan B14/C6c 대사 lines.**

**Inputs:** architecture §13·§4.2.1·§9.2; dev_plan B14 (adoption/regression portions only — 대사
waived); §1-§5 of the design doc (esp. §3.3 adoption components; **§4.3.2 `Liquidation` 강제청산
출처·수렴 계약 + §4.1.1 `Fill`·`Trade.liquidated`** — the carry-in below), a-domain A2·A3, a-infra A6
(removal list + reconciliation waiver).

**In scope:**
- **Adoption points + shim:** where signal/wallet internal implementations (indicators, strategy,
  execution, sizing) are replaced by `core_lib` imports, and where a re-export shim sits for
  no-downtime — the C7a sequence, as a mermaid sequence diagram + step list.
- **라이브 강제청산 수신 절차 (§4.3.2가 명시적으로 남긴 인계 항목 — 누락 금지):** 강제청산은 라이브에서 **거래소가
  조건을 판정해 자동 집행**하고 우리는 그것을 **받아서 정리만** 한다(§4.3.2 확정). 그 수신 메커니즘은 wallet의
  라이브 인프라 소관이라 §4가 계약만 정하고 절차를 **의도적으로 비워 두었으므로**, 이 단계가 확정한다.
  - (a) **수신 경로** — 거래소 청산 통지를 받는 이벤트 핸들러(WebSocket 등)가 어디에 붙는지.
  - (b) **Fill 변환 지점** — 그 통지를 §4.1.1 계약대로 `Fill(exit_reason=LIQUIDATION)`(`order_id`=거래소가 발행한
    청산 주문 id, `liquidity`=taker, `reduce_only`=TRUE)으로 만들어 `core_lib.execution`(position_book·accounting)에
    넘기는 지점. 백테스트에서 Matcher가 만드는 Fill과 **같은 모양**이어야 회계 경로가 하나로 유지된다.
  - (c) **누락 복구** — 재접속·다운타임 중 놓친 청산 통지를 뒤늦게 반영하는 절차(거래소 조회로 메움).
  - (d) **실측 대사** — 거래소 실측 청산가·수수료와 `costs.Liquidation` 추정(`Entry×(1−1/lev+mmr)`, last-price
    근사)의 차이를 대사하는 절차. 이 대사는 A6이 waive한 구↔신 backtest 대사와 **별개**다.
  - 백테스트·페이퍼는 Matcher가 청산을 검출하므로 이 항목은 **라이브 채택에만** 해당한다.
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
- The Appendix is appended to `backtest_v2_detailed_design.md` with all five sub-plans (adoption
  points + shim, **라이브 강제청산 수신 절차**, new-backtest validation baseline + reconciliation waiver,
  regression, credential rotation), the adoption + regression rendered as mermaid sequence/flow.
- **라이브 강제청산 수신이 빠지지 않았다** — 수신 경로·`Fill(exit_reason=LIQUIDATION)` 변환 지점(§4.1.1 계약과
  동일 모양)·누락 복구·거래소 실측 대사 넷이 모두 적혔고, "거래소가 집행하고 우리는 수신·정리만 한다"는 §4.3.2
  계약과 어긋나지 않는다.
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

Stage b-adoption is complete only when the Appendix (adoption points + shim, 라이브 강제청산 수신 절차,
new-backtest validation baseline with reconciliation WAIVED, regression, credential rotation) is
appended to backtest_v2_detailed_design.md with adoption/regression as mermaid sequence/flow, the live
liquidation reception covering 수신 경로·Fill(exit_reason=LIQUIDATION) 변환·누락 복구·실측 대사, production
behavior preserved unchanged with an explicit fill_timing re-verification trigger, and
spec-consistency-auditor PASS + cto-reviewer APPROVE in this transcript. Until then, continue the named
gaps. Do not declare completion from a feeling of "enough".
