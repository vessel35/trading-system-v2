# Current Objective

> Edit this each sprint. `guardrails.sh` injects it at SessionStart.
> After editing, register the Done-when block as a `/goal` so each turn is auto-evaluated.
> 세 단계 전체 계획은 `docs/roadmap-stage-3.md`에, 이 스프린트의 실행 계획은
> `docs/roadmap-stage-3-0-plan.md`에 있다. 이 파일은 목표와 완료 조건만 담는다.

**Goal:** 로드맵 **3-0**을 완료한다. 전략이 쓸 지표를 실제로 갖춘다. 표준 82종 중 구현되어
등록된 것은 여섯 종뿐이라 외부에 알려진 방법 대부분이 첫 단계에서 막힌다. 계산 기반을 먼저
정리하고, 확정된 40종을 표준 문서대로 구현하며, 값이 맞는지 외부 라이브러리로 대조한다.
새 브랜치 `feat/indicator-implementations`.

**확정된 결정(2026-07-31 사용자 선택):** 구현 범위는 40종이며 웨이브 3이 끝나는 누적 27종
지점에서 멈춰 3-1을 시험한 뒤 계속할지 정한다. 지표를 늘리지 않는 웨이브 0(계산 기반 정리)을
포함한다. 값 검증은 외부 라이브러리 대조로 한다. 근거와 웨이브 구성은 실행 계획 문서에 있다.

**출발점(확인된 현재 상태):**
- 표준 82종 기준으로 구현·등록된 것은 6종(RSI, Stochastic, ATR, Bollinger Bands, %B, BandWidth).
  EMA와 Volume SMA도 있으나 표준이 §0 프리미티브로 분류해 82종 집계 밖이다. 등록 조합은 아홉 개.
- 미구현 76종 중 지금 구현할 수 있는 것은 64종. 남는 12종은 시장폭 3종(입력 채널 없음)과
  §12 미확정 9종이며, 둘 다 이번 40종 범위 밖이라 이번 스프린트에서 결정하지 않아도 된다.
- 지표 하나 추가는 소스 2파일·테스트 2파일에 걸치고 기존 단언 6곳을 함께 고쳐야 한다.
  없는 프리미티브는 6개지만 실제로 막는 것은 HL2 하나이며 그것이 7종을 막는다.
- 계산식 표준은 `technical_indicators_calc_spec.md`(917줄, 82종)가 소유한다. 작업 트리의
  `docs/references/`에 미러가 놓였으나 **아직 커밋되지 않았다.** 이력에 넣는 것이 첫 작업이다.
- 표준 문서에는 **수치 예시가 없다.** "예:"로 나오는 것은 파라미터 값 제안이며 계산된 기댓값이
  아니다. 그래서 값의 정확성은 외부 라이브러리 대조로 확인한다.
- `docs/fullspec/A1_indicator_inventory.md`가 확정한 대로 legacy signal-service 지표 코드는
  **계산식 이식 원천이 아니다.** 표준 문서대로 새로 구현한다.
- 검증 축 넷이 이미 있다: `test_indicator_registry.py`, `test_indicator_contracts.py`,
  `test_indicator_primitives.py`, `test_indicator_parity.py`(벡터 경로와 O(1) 증분 경로의 동일성).

**In scope:**
- **I-1. 표준 문서를 이력에 넣는다.** `docs/references/technical_indicators_calc_spec.md`를
  커밋한다. 정본은 개발지침 디렉터리이며 저장소는 사본이다. 값이나 규약을 임의로 바꾸지 않는다.
- **I-2. 웨이브 0 — 계산 기반.** HL2 프리미티브 추가, 증분판 프리미티브 도입, 0으로 나눌 때의
  공통 규약, 등록 수 고정 단언을 목록 대조형으로 전환, 최소 이력 두 선언의 직접 대조 단언 추가.
  지표를 늘리지 않지만 이후 모든 웨이브의 지표당 비용을 정한다.
- **I-3. 구현.** 정한 범위를 표준 문서대로 구현한다. 불변식을 지킨다 — 재귀형 지표는 확정 캔들로만
  갱신(진행 중 캔들 금지), 계산은 float64, 같은 지표를 두 번 구현하지 않음, 워밍업 seed와 표준편차
  분모 규약은 표준 문서를 따름.
- **I-4. 등록 조합.** 각 지표의 기본 파라미터 조합을 정해 레지스트리에 등록한다. 조합이 없으면
  전략이 선언할 수 없다. 무엇을 기본으로 두는지와 그 근거를 남긴다.
- **I-5. 검증.** 새 지표마다 네 축을 통과시킨다. 벡터 경로와 증분 경로의 동일성에 더해, **값의
  정확성을 외부 라이브러리와 대조**한다(표준 §13이 교차대조 대상으로 적은 TA-Lib, pandas-ta,
  Tulip Indicators, TradingView). 외부 라이브러리는 계산식의 원천이 아니라 대조군이다. 값이
  어긋나면 표준 문서를 다시 읽어 원인을 밝히고, 라이브러리를 따라 구현을 바꾸지 않는다.

**Out of scope (필요하면 에스컬레이션):**
- 3-1·3-2 소관 전부(전략 개발 skill·Agent·테스트 방침, `claude -p` 분석 파이프라인).
- 표준 문서의 수식·규약을 임의로 바꾸는 것. 정본은 개발지침 디렉터리이고 저장소는 미러다.
  표준이 모호하면 임의 해석 대신 사용자에게 확인한다.
- legacy signal-service 지표 코드를 계산식 원천으로 삼는 것.
- 지표를 쓰는 전략을 만드는 것. 이번 스프린트는 재료를 갖추는 것이다.
- §12 미확정 9종과 시장폭 3종. 40종 범위 밖이라 정의 채택과 입력 채널 설계를 이번에 하지 않는다.
- 이미 등록된 Bollinger `percent_b`의 NaN 결함 수정. 웨이브 0의 0-나눗셈 규약이 해법을 포함하되,
  기존 지표의 동작을 바꾸는 일은 별도 changeset으로 분리한다.

**Done when (transcript-verifiable, turn-capped):**
- I-1: 표준 문서가 저장소에 미러되고 정본과 내용이 같음이 확인된다.
- I-2: 웨이브 0의 다섯 항목이 완료되고, 등록 수를 고정한 단언이 목록 대조형으로 바뀌었음에도
  지표를 소리 없이 늘리거나 줄일 수 없다는 성질이 유지됨이 테스트로 확인된다.
- I-3·I-4: 정한 범위의 지표가 구현되고 기본 조합이 등록된다. 등록 목록의 전후 비교가 수치로
  제시된다(예: 여섯 종 아홉 조합 → N종 M조합).
- I-5: 새 지표 전부가 네 축의 테스트를 통과하고, **값이 외부 라이브러리와 일치함이 수치와 함께**
  보인다. 값 위조·근사로 통과시키지 않는다. 대조에서 어긋난 지표가 있으면 원인과 처리를 남긴다.
- **중간 점검**: 누적 27종(웨이브 3 종료) 시점에서 멈추고, 3-1을 시험해 지표 부재로 막히는 일이
  얼마나 생기는지 확인한 결과가 이 transcript에 남는다. 웨이브 4·5의 진행 여부는 그 결과로 정한다.
- 독립 리뷰 1회가 Blocking 0건으로 관찰된다. 특히 "표준 문서와 다른 수식을 쓰지 않았는가",
  "진행 중 캔들을 재귀 상태에 넣지 않았는가", "외부 라이브러리를 계산식의 원천으로 삼지 않았는가",
  "대조를 맞추려 상수를 끼워 넣지 않았는가"를 적대적으로 확인한다.
- 저장소 루트 `pytest services` exit 0, ruff·ruff format·mypy exit 0. 기존 지표 아홉 조합의
  값이 변하지 않음이 회귀로 확인된다.
- Turn budget: ≤ 45 orchestrator turns. 초과하면 중단하고 보고한다.

**Register with /goal:**

```
/goal Complete roadmap 3-0: give the platform the indicators strategies will need. Commit the
  calculation standard into the repository, lay the calculation groundwork in wave 0, implement the decided
  40 indicators across waves 1-5, register a default parameter combination for each, and check every
  value against an outside library because the standard carries no worked examples.
  DONE iff (a) the standard is committed and matches its source, (b) wave 0 is complete and the
  registry-size assertions became list comparisons without losing the property that indicators
  cannot be added or dropped silently, (c) the indicators are implemented and registered with a
  before/after count shown, (d) every new indicator passes registry, contract, primitive, and
  vectorized-versus-incremental parity checks and its values match an outside library by number,
  with nothing fabricated to force a pass and any mismatch explained, (e) the run pauses at the
  27-indicator mark to try 3-1 and that result is recorded before waves 4-5 proceed, (f) one
  independent review returns zero Blocking after confirming no formula drift from the standard, no
  in-progress candle entering recursive state, no outside library treated as the source of a
  formula, and no constant inserted to match a comparison, and (g) repository-root `pytest services`
  exit 0 with ruff+ruff-format+mypy exit 0 and the nine existing combinations unchanged.
  Hard stop at 45 orchestrator turns; report and wait.
```
