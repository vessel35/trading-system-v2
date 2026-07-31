# Current Objective

> Edit this each sprint. `guardrails.sh` injects it at SessionStart.
> After editing, register the Done-when block as a `/goal` so each turn is auto-evaluated.
> 세 단계 전체 계획은 `docs/roadmap-stage-3.md`에 있다. 이 파일은 현재 스프린트만 담는다.

**Goal:** 로드맵 **3-0**을 완료한다. 전략이 쓸 지표를 실제로 갖춘다. 지금 등록된 지표는 여섯 종
아홉 조합뿐이라 외부에 알려진 방법 대부분이 첫 단계에서 막힌다. 계산식은 표준 문서가 소유하므로
그것을 저장소로 미러하고, 정해진 범위만큼 새로 구현하며, 기존 네 축의 검증을 그대로 통과시킨다.
새 브랜치 `feat/indicator-implementations`.

**출발점(확인된 현재 상태):**
- 등록된 지표는 ATR(14), Bollinger Bands(20, 2.0), EMA(9·21·55·200), RSI(14),
  Stochastic(14, 3), Volume SMA(20) — 여섯 종 아홉 조합.
- 계산식 표준은 `technical_indicators_calc_spec.md`(개발지침 디렉터리, 917줄, 82종)가 소유한다.
  저장소에 아직 미러되지 않았다. `50_metrics_reference.md`를 `docs/fullspec/`로 미러한 선례가 있다.
- `docs/fullspec/A1_indicator_inventory.md`가 확정한 대로 legacy signal-service 지표 코드는
  **계산식 이식 원천이 아니다.** 표준 문서대로 새로 구현한다.
- 검증 축 넷이 이미 있다: `test_indicator_registry.py`, `test_indicator_contracts.py`,
  `test_indicator_primitives.py`, `test_indicator_parity.py`(벡터 경로와 O(1) 증분 경로의 동일성).

**In scope:**
- **I-1. 표준 문서 미러.** `technical_indicators_calc_spec.md`를 `docs/fullspec/`로 미러한다. 정본은
  개발지침 디렉터리이며 저장소는 사본이다. 값이나 규약을 임의로 바꾸지 않는다.
- **I-2. 구현 범위 확정.** 82종 전량인지 우선순위 구현인지 정하고 근거를 남긴다. 개수는 계약이
  아니므로(기존 결정) 전량이 자동으로 옳지는 않다. 다만 3-1의 Agent가 미구현 지표를 만날 때마다
  멈추므로 어디까지 미리 갖출지는 정해야 한다. 범위를 정할 때 표준 문서의 분류와, 널리 쓰이는
  방법이 요구하는 지표를 근거로 삼는다. **사용자 확인을 받고 진행한다.**
- **I-3. 구현.** 정한 범위를 표준 문서대로 구현한다. 불변식을 지킨다 — 재귀형 지표는 확정 캔들로만
  갱신(진행 중 캔들 금지), 계산은 float64, 같은 지표를 두 번 구현하지 않음, 워밍업 seed와 표준편차
  분모 규약은 표준 문서를 따름.
- **I-4. 등록 조합.** 각 지표의 기본 파라미터 조합을 정해 레지스트리에 등록한다. 조합이 없으면
  전략이 선언할 수 없다. 무엇을 기본으로 두는지와 그 근거를 남긴다.
- **I-5. 검증.** 새 지표마다 네 축을 통과시킨다. 특히 벡터 경로와 증분 경로의 동일성(parity)과,
  표준 문서의 예시 값이 있으면 그 값의 재현을 확인한다.

**Out of scope (필요하면 에스컬레이션):**
- 3-1·3-2 소관 전부(전략 개발 skill·Agent·테스트 방침, `claude -p` 분석 파이프라인).
- 표준 문서의 수식·규약을 임의로 바꾸는 것. 정본은 개발지침 디렉터리이고 저장소는 미러다.
  표준이 모호하면 임의 해석 대신 사용자에게 확인한다.
- legacy signal-service 지표 코드를 계산식 원천으로 삼는 것.
- 지표를 쓰는 전략을 만드는 것. 이번 스프린트는 재료를 갖추는 것이다.

**Done when (transcript-verifiable, turn-capped):**
- I-1: 표준 문서가 저장소에 미러되고 정본과 내용이 같음이 확인된다.
- I-2: 구현 범위가 근거와 함께 정해지고 **사용자 확인**이 관찰된다. 범위 밖으로 남긴 지표가
  무엇인지도 명시된다(조용한 누락 금지).
- I-3·I-4: 정한 범위의 지표가 구현되고 기본 조합이 등록된다. 등록 목록의 전후 비교가 수치로
  제시된다(예: 여섯 종 아홉 조합 → N종 M조합).
- I-5: 새 지표 전부가 네 축의 테스트를 통과함이 관찰된다. 표준 문서에 예시 값이 있는 지표는 그
  값의 재현이 수치와 함께 보인다. 값 위조·근사로 통과시키지 않는다.
- 독립 리뷰 1회가 Blocking 0건으로 관찰된다. 특히 "표준 문서와 다른 수식을 쓰지 않았는가",
  "진행 중 캔들을 재귀 상태에 넣지 않았는가", "예시 값을 맞추려 상수를 끼워 넣지 않았는가"를
  적대적으로 확인한다.
- 저장소 루트 `pytest services` exit 0, ruff·ruff format·mypy exit 0. 기존 지표 아홉 조합의
  값이 변하지 않음이 회귀로 확인된다.
- Turn budget: ≤ 45 orchestrator turns. 초과하면 중단하고 보고한다.

**Register with /goal:**

```
/goal Complete roadmap 3-0: give the platform the indicators strategies will need. Mirror the
  calculation standard into the repository, decide and confirm with the user how much of it to
  implement, implement that scope faithfully, register a default parameter combination for each,
  and hold every new indicator to the four checks the repository already applies.
  DONE iff (a) the standard document is mirrored and matches its source, (b) the implementation
  scope is decided with rationale and confirmed by the user, with whatever is left out named
  explicitly, (c) the indicators are implemented and registered with a before/after count of the
  registry shown, (d) every new indicator passes registry, contract, primitive, and vectorized-
  versus-incremental parity checks, with any worked example in the standard reproduced by number
  and no value fabricated to force a pass, (e) one independent review returns zero Blocking after
  confirming no formula drift from the standard, no in-progress candle entering recursive state,
  and no constant inserted to match an example, and (f) repository-root `pytest services` exit 0
  with ruff+ruff-format+mypy exit 0 and the nine existing combinations unchanged.
  Hard stop at 45 orchestrator turns; report and wait.
```
