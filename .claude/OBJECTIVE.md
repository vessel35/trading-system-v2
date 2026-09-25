# Current Objective

> Edit this each sprint. `guardrails.sh` injects it at SessionStart.
> After editing, register the Done-when block as a `/goal` so each turn is auto-evaluated.
> 세 단계 전체 계획은 `docs/roadmap-stage-3.md`에, 3-1의 실행 계획과 경과는
> `docs/roadmap-stage-3-1-plan.md`와 `docs/fullspec/stage_3_1_acceptance_three_strategies.md`에
> 있다. 이 파일은 목표와 완료 조건만 담는다.

**Goal:** 3-1의 절차는 완성됐다(전략 작성 Agent가 여섯 회차 가운데 마지막 둘을 개입 없이
통과, PR #47·#48 병합). 남은 것은 **검증 층**이다. 사람이 읽는 절차와 기록표가 아니라 프로그램이
잡는 검사를 두 승인된 설계대로 세운다.

**끝난 것(2026-09-25 확인).** 전략 일곱(vessel-reference와 문서 출처 여섯)이 배포·등록·실행되고,
`MoneyManagementSupport.default_settings`로 원문의 보호 값이 배포에 실리며, 절차
`author-strategy`·`verify-strategy`가 기록 규칙까지 갖췄다. 3-1 완료 기준 열두 가운데 열하나가
달성이고 하나(공통 규범 검사)가 미구현이다.

**In scope:**

- **V-1. 공통 규범 검사, 전략 단위 층.** `docs/fullspec/strategy_contract_suite_design.md`를
  검증 층별로 구현한다(2026-09-25 사용자 결정). 첫 층은 전략 단위다. 발견된 전략 전체를 방식
  사례표로 매개변수화하고, 결정성 두 갈래, 정책 독립성(생산 입력 모양), 방어적 시간 무결성, 금지된
  의존(정적·실행 중), 선언과 접근의 일치(추적 Mapping), 진입과 청산의 대응, 시그니처, 결함 주입
  검증을 둔다. 둘째 층(Engine 조합: 시간 무결성 주 검사, 지원하지 않는 조합의 거부)은 그 뒤다.
- **V-2. 배포 전 검사와 초안 생성기.** `docs/fullspec/author_check_and_scaffold_design.md`의
  changeset 여섯을 순서대로 구현한다. 첫 changeset은 식별자 모듈과 능력 항목 둘
  (`series.history_depth`, `plugin.identifier_format`)과 절차 규칙("부딪힌 제약은 같은 changeset에서
  항목과 시험을 더한다")이다. 닫힘 기준의 대상은 배포된 전략 일곱이다.
- **V-3. 설계가 남긴 갭의 반영.** 차이 기록표의 종류 어휘를 Agent가 실제로 쓴 분류(플랫폼 고정,
  값은 원문대로이나 정의는 채움)를 담게 고치고, `verify-strategy`가 기록표 행마다 확인하게 한다.
  시장 종류·종목 범위 선언 자리는 `author_check` 2단계와 같은 자리이므로 그 설계에 붙인다.

**Out of scope (필요하면 에스컬레이션):**

- 화면의 mode별 선언 값(z8nrz7e40t), 체결 뒤 청산 안전성 재검사(z8nrz7e3k8), 공통 리스크
  가드(z8nrz7bxn5). 별도 항목이다.
- 3-2(`claude -p` 분석 파이프라인)와 증거의 빈 엔티티 넷.
- 전략을 새로 만드는 것. 검증 층을 세운 뒤 Agent 회차를 한 번 더 도는 것은 확인 절차이지 이
  스프린트의 산출물이 아니다.

**Done when (transcript-verifiable, turn-capped):**

- V-1: 발견된 전략 일곱 전부에 공통 검사가 자동으로 적용되고 발견 목록과 사례표의 id 집합이 같다.
  결함 주입 전략 일곱 종류(클래스 전역 상태, 호출 횟수, 입력·설정 변경, 숨은 계열 접근, 금지된
  의존, 방향이 어긋난 청산 증거, 지원하지 않는 정책·자금관리 소유 필드)가 각각 대응하는 검사에서
  실패하는 것이 transcript에 보인다. 검사 설명이 전략 단위 층의 한계(Engine 조합의 시간 보증을
  대체하지 않음)를 적는다.
- V-2: `python -m backtest_service.author_check <id>`가 전략 일곱에 대해 exit 0이고, 설계 6장의
  닫힘 기준(결함 주입 셋, 규범 예시 시험, 식별자 시험, 능력 항목 둘, 초안 생성기 산출물이 1~5단계와
  7단계를 통과)이 transcript에서 확인된다.
- V-3: 기록표 종류 어휘와 `verify-strategy`의 행별 확인 규칙이 두 skill과 규범에서 grep으로
  확인되고, 시장·종목 범위 선언이 설계 문서에 들어간다.
- 독립 리뷰(Codex)가 각 changeset에서 Blocking 0으로 관찰된다.
- 저장소 루트에서 `.venv/bin/python -m pytest services -q` exit 0, ruff·ruff format·바뀐 서비스의
  mypy exit 0. 배포된 전략 일곱의 기존 시험과 Evidence golden이 변하지 않는다.
- Turn budget: ≤ 80 orchestrator turns. 초과하면 중단하고 보고한다.

**Register with /goal:**

```
/goal Stand up the 3-1 verification layers from the two approved designs. V-1: implement the
  strategy-unit layer of docs/fullspec/strategy_contract_suite_design.md — a suite parametrized
  over every discovered strategy through a test-only scenario table whose id set must equal the
  discovery set, with both determinism paths, policy-independence on production-shaped inputs,
  a defensive time-integrity check that states its limit, static and runtime forbidden-dependency
  checks, a tracing Mapping for declared-versus-actual series and parameter access, per-direction
  entry/exit correspondence, signature checks, and seven fault-injection strategies each caught
  by its check. V-2: implement the six changesets of
  docs/fullspec/author_check_and_scaffold_design.md in order, starting with the identifier module,
  the two capability entries (series.history_depth, plugin.identifier_format) and the
  add-a-capability-when-you-hit-a-wall rule in the author-strategy skill; the closing criteria
  apply to all seven deployed strategies. V-3: fix the difference-table vocabulary to cover
  platform-fixed rules and partially filled rows, add the per-row check to verify-strategy, and
  fold market/symbol scope declaration into the author_check design.
  DONE iff (a) every discovered strategy passes the suite and each of the seven fault strategies
  fails its check in the transcript, (b) author_check exits 0 for all seven strategies and the
  design's closing criteria are observed, (c) the vocabulary and per-row rule are grep-visible in
  both skills and the contract, (d) each changeset's Codex review shows zero Blocking, and (e)
  repository-root pytest, ruff, ruff format, and per-service mypy exit 0 with existing goldens
  unchanged. Hard stop at 80 orchestrator turns; report and wait.
```
