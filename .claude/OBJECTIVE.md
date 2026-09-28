# Current Objective

> Edit this each sprint. `guardrails.sh` injects it at SessionStart.
> After editing, register the Done-when block as a `/goal` so each turn is auto-evaluated.
> 세 단계 전체 계획은 `docs/roadmap-stage-3.md`에, 3-1의 실행 계획과 경과는
> `docs/roadmap-stage-3-1-plan.md`와 `docs/fullspec/stage_3_1_acceptance_three_strategies.md`에
> 있다. 이 파일은 목표와 완료 조건만 담는다.

**Goal:** 검증 층 위에서 **일곱째 Agent 회차**를 돌린다. 사용자가 준 전략(가브리엘 레이바의
"오렌지 매매 지표(Orange Web3)"를 쓰는 5분봉 밴드 돌파·리테스트 시스템)을 author-strategy Agent가
**내 개입 없이** 구현하거나, 정확히 무엇이 막는지 보고하게 한다. 회차의 목적은 이 전략 자체가
아니라, 지난 스프린트에 세운 도구가 실제 회차에서 닫히는지 확인하는 것이다. 초안 생성기
(`python -m trading_plugins.scaffold`), 배포 전 검사 명령(`python -m backtest_service.author_check`,
아홉 단계), 원문 대비 차이 기록표(규범 6.6절, 종류 여섯과 승인 상태), 공통 규범 검사 두 층의
사례표, `verify-strategy`의 행별 확인이다.

**끝난 것(2026-09-28 확인).** 3-1 인수(PR #47부터 #50)와 배포 전 검사 설계의 changeset 여섯
(PR #52, #54부터 #58)이 main에 있다. 배포된 전략 일곱이 `author_check` 아홉 단계를 exit 0으로
지나고, 공통 규범 검사 두 층이 발견된 전략 전체에 자동으로 걸린다. 앞선 스프린트의 OBJECTIVE
V-1·V-2·V-3은 모두 달성됐다.

**In scope:**

- **C-1. 입력 문서.** 사용자가 준 원문을 `docs/samples_for_strategy_agent/07.Orange_Web3_Band_Retest.md`의
  1절부터 4절(전략 설명, 규칙, 시험 조건, 결과)과 5절 의사코드에 **그대로** 옮긴다. 출처는 "사용자
  제공 요약(원 출처: Gabriel Leyva의 Orange Web3 지표 소개)"으로 적고, 원문에 없는 것(출처 URL,
  결과 수치, 지표의 계산식)은 없다고 적는다. 이 스프린트에서 내가 쓰는 전략 관련 문서는 이것뿐이다.
- **C-2. Agent 회차.** author-strategy sub-agent가 다섯째·여섯째 회차와 같은 규칙(질문 없이
  진행, 파일 범위 고정, git·데이터베이스·서비스 조작 금지)으로 초안 생성기에서 시작해 구현, 공통 규범
  검사 두 층의 사례표 행, `author_check` 아홉 단계, 기록표(종류 여섯, 승인이 필요한 행은 "승인
  대기(지시에 따라 진행)"), 문서 5절·6절까지 맡는다. 나는 QA 재확인, dev signal_db 등록 SQL 적용,
  web-api·vite 재기동, 화면 실행, verify-strategy sub-agent(기록표 행별 확인 포함), Codex 충실도
  검토, 인수 기록 작성만 한다. **회차 중 Agent의 산출물(전략 모듈, 시험, 등록 SQL, 문서 5·6절)을
  내가 한 글자라도 고치면 목표 미달성이다.**
- **C-3. 막힘의 처리.** 이 원문은 플랫폼과 여러 곳에서 부딪힐 것이 예상된다. 정의 없는 전용 지표
  (중앙 추세선, 편차 밴드 넷, RSI 게이지: 재료 부재), 밴드 돌파 뒤 리테스트(series의 직전 값이
  오지 않음: `series.history_depth`), 분할 청산(`exit.partial`), 손절을 중앙 추세선에 두는 것(정책의
  입력이 변동성 하나뿐), 5분봉 실행. Agent는 이것을 skill 3장의 분류(빈 값, 재료 부재, 능력 부재)로
  보고하고 근사가 가능한 것은 기록표의 승인 종류로 적는다. 승인 종류의 행은 화면 단계 전에 내가
  사용자에게 모아 올리고 사용자가 정한다. 회차가 능력 목록에 없는 제약을 드러내면 항목과 시험을 더하는
  것은 내 플랫폼 작업이며 Agent의 산출물은 건드리지 않는다.
- **C-4. 기록.** 인수 기록 `docs/fullspec/stage_3_1_acceptance_three_strategies.md`에 5.9절(일곱째
  회차)을 두어 결과, 개입 여부, 도구가 잡은 것과 잡지 못한 것, 승인 행의 처리를 적는다.

**Out of scope (필요하면 에스컬레이션):**

- 재료 부재로 판정된 지표(중앙 추세선, 편차 밴드, RSI 게이지)의 구현. 정의가 원문에 없으므로
  별도 항목이며 정의를 어디서 얻을지부터 사용자가 정한다.
- 분할 청산, 이동 손절, 정책의 둘째 입력 같은 새 능력의 구현. 회차가 요구하면 ClickUp 항목으로
  올린다.
- 기존 전략 일곱을 `StrategyBase` 보조 다섯으로 다시 맞추는 changeset, 시장·종목 범위 선언 구현
  (z8nrz7e41h), Turtle 일봉 원천의 Evidence 기록(z8nrz7e4y0), Agent가 쓴 05·06 모듈의 docstring
  기록표 복사.

**Done when (transcript-verifiable, turn-capped):**

- C-1: 문서 07의 1절부터 5절이 사용자가 준 원문과 같고(diff 없음), 회차 중 내 이름의 diff가 Agent의
  산출물에 없다(회차 커밋은 sub-agent 산출물 그대로이며 커밋 메시지가 그렇게 적는다).
- C-2: 회차가 둘 중 하나로 끝난다. **(a) 구현.** 일곱째 전략이 발견되고
  `python -m backtest_service.author_check <id>`가 exit 0·판정 `passed`(단계 9 실제 실행)이며, 공통
  규범 검사 두 층의 사례표에 그 행이 있어 저장소 루트 pytest가 exit 0이고, 기록표의 승인 종류 행이
  사용자 승인 또는 "승인 대기"로 표시되고, 화면에서 실행돼 결과가 보이며, verify-strategy가 기록표
  행마다 확인을 마치고, Codex 충실도 검토가 Blocking 0이다. **(b) 보고.** 막는 것이 skill 3장의
  분류로 정확히 적히고(빈 값·재료 부재·능력 부재 각각, 능력 부재는 능력 id와 함께), 부분 구현이
  가능한 범위가 skill 4장대로 나오며, 도구가 그 판정을 어디까지 프로그램으로 잡았는지가 적힌다.
- C-3: 회차가 드러낸 능력 목록의 빈자리마다 항목과 시험이 더해져 `facts capabilities`에 보이고
  core-lib 능력 시험이 통과한다. 빈자리가 없었으면 "없음"으로 기록한다.
- C-4: 인수 기록 5.9절이 있고 위 결과를 담는다.
- 저장소 루트에서 `.venv/bin/python -m pytest services -q` exit 0, ruff·ruff format·바뀐 서비스의
  mypy exit 0. 배포된 전략 일곱의 기존 시험과 Evidence golden이 변하지 않는다.
- Turn budget: ≤ 80 orchestrator turns. 초과하면 중단하고 보고한다.

**Register with /goal:**

```
/goal Run the seventh author-strategy Agent round on the user-provided "Orange Web3" 5-minute
  band break-and-retest strategy, without intervening in the Agent's artifacts, to confirm the
  verification tooling closes a real round. C-1: copy the provided text verbatim into
  docs/samples_for_strategy_agent/07.Orange_Web3_Band_Retest.md sections 1 to 5, the only
  strategy document I write. C-2: the sub-agent starts from python -m trading_plugins.scaffold,
  implements, adds the rows to both common-check case tables, passes python -m
  backtest_service.author_check through nine stages, writes the difference table with the six
  kinds and approval status, and fills document sections 5 and 6; I only re-run QA, apply the
  registration SQL to dev signal_db, restart web-api and vite, run on the screen, run the
  verify-strategy sub-agent with its per-row check, run the Codex faithfulness review, and
  write the record. C-3: blockages are reported in the skill's three classes; platform gaps
  found get a capability entry and a test from me, never an edit to the Agent's files. C-4:
  acceptance record section 5.9.
  DONE iff (a) document 07 matches the provided text and no edit of mine touches the Agent's
  artifacts; (b) the round ends either with a deployed strategy (author_check exit 0 with
  verdict passed and stage 9 run, case-table rows present and root pytest exit 0, approval-kind
  rows approved or marked pending, a screen run, verify-strategy row-by-row check done, Codex
  faithfulness review with zero Blocking) or with a blockage report in the three classes with
  capability ids and the feasible partial scope; (c) every capability gap the round exposed has
  an entry and a passing test, or "none" is recorded; (d) section 5.9 exists; (e) repository-root
  pytest, ruff, ruff format, and per-service mypy exit 0 with existing goldens unchanged.
  Hard stop at 80 orchestrator turns; report and wait.
```
