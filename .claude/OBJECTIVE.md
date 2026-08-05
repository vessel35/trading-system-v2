# Current Objective

> Edit this each sprint. `guardrails.sh` injects it at SessionStart.
> After editing, register the Done-when block as a `/goal` so each turn is auto-evaluated.
> 세 단계 전체 계획은 `docs/roadmap-stage-3.md`에, 3-0의 실행 계획과 경과는
> `docs/roadmap-stage-3-0-plan.md`에 있다. 이 파일은 목표와 완료 조건만 담는다.

**Goal:** 3-0이 남긴 것을 닫고 **3-1로 넘어간다.** 지표 구현 본체는 끝났다. 남은 것은 증거
기록의 결함과, 이식 방법이 새로 열어 준 지표들과, 실제로 막힌 것을 사유와 함께 못박는 일이다.

**끝난 것(2026-08-05 확인).** 3-0의 지표 구현은 완료 상태다. 등록은 **84 조합 / 81 이름 /
표준 89종 중 81종**이고, 캔들스틱 패턴 **61종**이 TA-Lib v0.7.1 직접 이식으로 판
`2.0.0+talib.0.7.1`에 올라 있다. 패턴은 국면 일곱 22000봉의 427개 조합에서 TA-Lib 0.7.1
포획값과 봉 단위로 완전히 일치하며, 비영 봉 44177개의 성립·부호·크기가 모두 같다. 이 경과는
3-0 실행 계획서의 8장과 10장에 기록되어 있다.

**전제가 하나 바뀌었다.** 사용자가 TA-Lib의 계산 값을 원본으로 확정했고 소스를 가져와
비교하라고 지시했다. 패턴 61종이 그 방식으로 이식되었으므로 **같은 방식이 지표에도 쓰인다.**
"원저서 상수를 확보하지 못해 구현하지 않는다"고 적어 둔 항목 가운데 TA-Lib이 구현을 갖고
있는 것은 더 이상 막혀 있지 않다.

**In scope:**

- **R-1. 증거 기록의 결함 넷.** 첫째, `INDICATOR_DEFINITION`의 열쇠가 이름 그대로여서 판이
  다른 기록을 화면에서 구분할 수 없다. 둘째, 그 표에 종류와 채택 근거를 담을 열이 없고
  `IndicatorSpec.pinned_impl`이 담고 있는 채택 기록을 엔진이 참거짓으로 눌러 기록한다. 셋째,
  증거 차트가 값이 사전형인 행을 건너뛰어 패턴 61종이 한 봉도 그려지지 않는다. 넷째, 이식의
  근거가 된 TA-Lib 소스 파일을 저장소에 반입할지 정한다.
- **R-2. Hilbert 계열 7종 이식.** `HT_DCPERIOD`, `HT_DCPHASE`, `HT_PHASOR`, `HT_SINE`,
  `HT_TRENDLINE`, `HT_TRENDMODE`, `MAMA`를 TA-Lib v0.7.1 C 소스에서 직접 이식한다. 패턴과
  같은 순서를 따른다 — **표준 문서에 절을 먼저 쓰고 출처를 명기한 뒤 구현한다.** 코드가
  표준보다 앞서지 않는다는 규칙은 그대로다. 이것으로 표준 §12가 남겨 둔 MAMA/FAMA와
  Sinewave/Instantaneous Trendline도 함께 풀린다.
- **R-3. 두 번째 계열 입력 경로와 BETA·CORREL.** 두 지표를 막고 있는 것은 계산이 아니라
  두 번째 가격 계열을 넘길 경로가 레지스트리에 없다는 것이다. 그 경로를 설계해 구현하고 두
  지표를 등록한다. 시장폭 3종이 같은 사유로 막혀 있으므로 **같은 경로가 그것까지 덮는지**를
  함께 판단해 기록한다.
- **R-4. 실제로 막힌 것을 사유와 함께 못박는다.** 무엇이 있어야 풀리는지를 항목마다 적는다.
  막연히 "보류"라고 적지 않고, 필요한 것이 데이터인지 1차 출처인지 표준 규칙인지를 가른다.
- **R-5. 3-1로 넘어간다.** 로드맵 3-1의 네 갈래(기존 skill 보완, 단계별 산출물과 등록 절차,
  기반 방침 유지와 계산 검증 추가, 신규 전략 개발 Agent)를 실행 계획으로 옮긴다.

**Out of scope (필요하면 에스컬레이션):**

- 증거의 빈 껍데기 네 엔티티(`MISSED_OPPORTUNITY`, `CONDITION_SIGNATURE`,
  `CONDITIONAL_EXPECTANCY`, `FINDING_CLAIM`)를 채우는 것. 3-2 소관이다.
- `claude -p` 분석 파이프라인. 3-2 소관이다.
- 표준이 정의하지 않은 규칙을 원저서 지식으로 메우는 것. TD Sequential의 countdown, Woodies
  CCI의 패턴 판정, Market Facilitation Index의 색 분류가 여기 해당한다. **1차 출처가 오기
  전에는 구현하지 않는다.**
- 증거 열쇠의 형식을 바꾸는 것. 증거 파일은 실행 하나에 하나이므로 파일 안에서는 충돌이 없다.
- 전략을 만드는 것. 3-1은 만드는 방법을 정하는 단계이지 전략을 내놓는 단계가 아니다.

**Done when (transcript-verifiable, turn-capped):**

- R-1: 실행을 하나 돌리면 `INDICATOR_DEFINITION`의 모든 행에 종류와 갈래와 채택 근거가
  채워지고 빈 것이 없다. 엔진에 `"pinned_impl": True` 상수가 남아 있지 않다. 차트가 패턴이
  성립한 봉에 표식을 그리고 강도 0.5와 1.0이 구분된다. 차트가 열쇠와 함께 판을 보인다.
  TA-Lib 소스 반입 여부가 결정되어 근거와 함께 기록된다.
- R-2: 7종이 구현되고 등록되며, **표준 문서의 해당 절이 구현보다 먼저 들어와 있다.** 값이
  TA-Lib 0.7.1 실측과 일치함이 수치와 함께 보인다. 어긋나면 원인을 밝히고, 맞추려고 상수를
  끼워 넣지 않는다. 등록 수의 전후 비교가 제시된다.
- R-3: BETA와 CORREL이 등록되어 값이 TA-Lib과 대조된다. 두 번째 계열이 어디서 오고 누가
  넘기는지가 문서에 남는다. 시장폭 3종이 같은 경로로 풀리는지 아닌지가 판단과 근거로 남는다.
- R-4: 막힌 항목마다 무엇이 없어서 막혔고 무엇이 있으면 풀리는지가 한 줄로 읽힌다.
- R-5: 3-1의 실행 계획서가 생기고 네 갈래가 각각 무엇을 산출하는지 적힌다.
- 독립 리뷰가 Blocking 0건으로 관찰된다. 특히 "표준보다 코드가 먼저 가지 않았는가",
  "대조를 맞추려 상수를 끼워 넣지 않았는가", "포획된 표본을 계약으로 착각하지 않았는가"를
  적대적으로 확인한다.
- 저장소 루트에서 `.venv/bin/python -m pytest services -q` exit 0, ruff·ruff format·mypy
  exit 0, 웹 쪽 `npm test` exit 0. 기존 84 조합과 패턴 61종의 값이 변하지 않음이 회귀로
  확인된다.
- Turn budget: ≤ 70 orchestrator turns. 초과하면 중단하고 보고한다.

**Register with /goal:**

```
/goal Close what roadmap 3-0 left behind and move to 3-1. Fix the four Evidence-recording
  defects: surface the implementation version in the chart so runs from different registry
  editions are distinguishable, add kind and adoption-record columns to INDICATOR_DEFINITION
  and stop the engine flattening IndicatorSpec.pinned_impl to a boolean, draw dictionary-valued
  outputs so the 61 candlestick patterns render, and decide whether to vendor the TA-Lib source
  files the port derived from. Port the seven Hilbert-transform functions from TA-Lib v0.7.1 C
  source, writing the standard's sections before the code as the pattern port did. Design the
  second-price-series input channel and register BETA and CORREL on it, judging whether the same
  channel unblocks the three market-breadth indicators. Record for every still-blocked item what
  is missing and what would unblock it. Then produce the 3-1 execution plan.
  DONE iff (a) every INDICATOR_DEFINITION row carries kind, category, and adoption record with
  none blank, no "pinned_impl": True constant remains in the engine, the chart draws pattern
  marks distinguishing strength 0.5 from 1.0 and shows the version beside the key, and the
  vendoring decision is recorded with its reason, (b) the seven Hilbert functions are implemented
  and registered with their standard sections landing before the code and their values shown to
  match TA-Lib 0.7.1 by number with no constant inserted to force agreement, (c) BETA and CORREL
  are registered against a documented second-series channel and checked against TA-Lib, with a
  reasoned verdict on market breadth, (d) each blocked item states what is missing and what would
  unblock it, (e) the 3-1 execution plan exists with an output named for each of its four
  branches, (f) one independent review returns zero Blocking after adversarially checking that
  code never preceded the standard, that no constant was inserted to match a comparison, and that
  no captured sample was mistaken for a contract, and (g) repository-root
  `.venv/bin/python -m pytest services -q` exit 0 with ruff, ruff format, and mypy exit 0, web
  `npm test` exit 0, and the existing 84 indicator combinations and 61 patterns unchanged.
  Hard stop at 70 orchestrator turns; report and wait.
```
