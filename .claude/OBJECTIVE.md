# Current Objective

> Edit this each sprint. `guardrails.sh` injects it at SessionStart.
> After editing, register the Done-when block as a `/goal` so each turn auto-evaluates.

**Goal:** 인수 테스트가 드러낸 계약-구현 갭 두 건을 후속 스프린트로 닫는다. 둘 다 프로덕션
변경이라 앞 스프린트에서 미조치로 남긴 것이며, 설계가 규정했으나 빠진 동작을 이행한다.
설계 내용이 있으므로 설계 루프(strategy-architect가 두 수정을 설계 → 교차 리뷰 → 확정) 다음에
구현 루프(Codex 구현 → QA → 독립 Claude 인수)로 진행한다. 새 브랜치 `fix/harness-persist-golden`.

**In scope (두 갭):**
- **F-1. Harness 과최적화 집계의 대표-run 카탈로그 영속화.** 설계(데이터베이스 §5.2.3·상세 §4.4.4)는
  oos_degradation·psr·harness_json을 번들 대표 run의 backtest_summary에 저장하도록 규정한다.
  카탈로그 컬럼·`upsert_summary` 저장능력·Harness 계산은 모두 있으나, 집계를 계산하는
  Harness(is_oos·walk_forward·monte_carlo·psr)가 대표 run summary에 써넣는 경로가 없다. 그 배선을
  더한다(어느 run이 대표인지·무엇을 어떤 형태로 저장하는지는 설계가 정한다). 인수 스위트 E1~E3를
  대표-run 카탈로그 집계 관측까지 승격한다.
- **F-2. 지표 수식 골든 확립.** 정본 표준 참조
  `/Users/vincent/Documents/X2.Mine/01.Trading/트레이딩시스템_개발지침/50_metrics_reference.md`가
  존재하며 골든 입력(거래 손익 배열·월간 수익률 배열)과 NumPy 검증 기준값(PF 3.4118·SQN 1.6647·
  Sortino 2.4910·MDD −3.50%·Calmar 3.2102 등)을 담는다. 설계는 이를 "구현까지 유지되는 표준 참조
  파일"로 규정했는데 저장소에 미러되지 않았다. (a) 참조 파일을 저장소로 미러하고, (b) eval 지표
  표준이 이 골든을 재현하는지 검증하는 수식 골든 테스트를 더한다. **주의(설계에서 확정할 점):**
  생산 `metrics.compute`는 자산곡선을 일별 리샘플·√365 연율화하고 SQN은 거래 30건 이상을 요구한다.
  참조 예시는 월간 √12·거래 10건이다. 참조 파일 자체가 "크립토 일봉은 √365 연율화"라고 명시하므로
  생산 규약이 옳다. 연율화 무관 값(PF·MDD·Calmar)은 그대로 재현되나, 연율화 의존 값(Sortino·Sharpe)과
  SQN은 규약·게이트가 다르다. 골든을 **정직하게** 검증하는 방식(공식 수준 재현 대 생산 래퍼 규약의
  분리)을 설계가 정한다. 값 위조·근사로 통과시키지 않는다.

**Out of scope (escalate if needed):**
- `wallet_db` 접근, `crypto_data` 쓰기·스키마 변경, `signal_db`의 레지스트리 외 테이블.
- 참조 파일의 값·규약을 임의로 바꾸는 것(정본은 개발지침 디렉터리, 저장소는 미러).
- 비밀번호 평문을 코드·커밋·보고서에 쓰는 것(`.env` 참조만).
- 설계가 정하지 않은 새 판정 규약을 임의로 도입하는 것.

**Done when (transcript-verifiable, turn-capped):**
- **설계 루프**: strategy-architect(Opus 4.8, xhigh)가 F-1·F-2 두 수정의 설계를 산출하고,
  교차 리뷰(review-agent 또는 독립 리뷰)를 거쳐 확정됨이 이 transcript에서 관찰된다. F-2의 연율화·
  게이트 규약 처리 방식이 설계에서 확정된다.
- **구현 루프**: Codex 워커의 worker_done이 관찰된다 — F-1 배선 + F-2 미러·수식 골든 테스트 구현,
  관련 테스트 green. F-1로 Harness 워크플로가 대표 run backtest_summary에 oos_degradation·psr·
  harness_json을 실제로 쓰고, 인수 E1~E3가 그것을 카탈로그에서 관측함이 수치와 함께 보인다.
  F-2 수식 골든이 참조 기준값을 재현함(연율화 무관 값은 정확히, 연율화 의존 값은 설계가 정한
  방식대로)이 수치와 함께 보인다.
- 저장소 루트 기본 `pytest services`가 마커 경고·수집 실패 없이 exit 0, ruff·ruff format·mypy exit 0.
  기존 `-m acceptance`·`-m integration` 회귀 없음.
- **인수 리뷰 1회**(독립 Claude Opus 4.8 터미널)의 worker_done이 APPROVE(Blocking 0건)로 관찰된다 —
  두 수정이 설계대로이고 값 위조가 없으며 회귀가 없음을 적대적으로 확인.
- Turn budget: ≤ 55 orchestrator turns. If exceeded → STOP and escalate.

**Register with /goal:**

```
/goal Close the two contract-vs-implementation gaps the acceptance testing surfaced (F-1 Harness aggregate persistence to the representative run's backtest_summary per design DB §5.2.3; F-2 mirror the golden metrics reference and add a formula-golden test), via a design loop (strategy-architect designs both, cross-reviewed) then a build loop (Codex implements, QA, independent Claude acceptance).
  DONE iff (a) a design for both fixes is produced and cross-reviewed in this transcript, with F-2's
  annualization/gate reconciliation decided, (b) a Codex worker_done shows F-1 wiring + F-2 mirror and
  formula-golden test with the tests green, Harness workflows actually persisting oos_degradation/psr/
  harness_json to the representative run and acceptance E1-E3 observing them in the catalog, and the
  formula golden reproducing the reference values (annualization-independent exactly; annualization-
  dependent per the decided method) — all shown with numbers, (c) repository-root `pytest services` exit 0
  with no marker warnings and ruff+ruff-format+mypy exit 0, with no regression in `-m acceptance` or
  `-m integration`, and (d) one independent Claude Opus 4.8 acceptance-review worker_done states APPROVE
  with zero Blocking after confirming no value fabrication and no regression.
  Hard stop at 55 orchestrator turns; report and wait.
```
