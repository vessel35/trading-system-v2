# Current Objective

> Edit this each sprint. `guardrails.sh` injects it at SessionStart.
> After editing, register the Done-when block as a `/goal` so each turn is auto-evaluated.
> 세 단계 전체 계획은 `docs/roadmap-stage-3.md`에, 이 스프린트의 실행 계획은
> `docs/roadmap-stage-3-0-plan.md`에 있다. 이 파일은 목표와 완료 조건만 담는다.

**Goal:** 로드맵 **3-0**을 완료한다. **계산 표준 82종 가운데 구현 가능한 것을 남김없이 구현한다.**
40종으로 잡았던 이전 범위는 2026-07-31 사용자 지시로 폐기하고, 표준 문서가 계산을 확정해 둔
지표 전부를 대상으로 삼는다. 브랜치 `feat/indicator-wave0`에서 이어서 진행한다.

**범위 재지정(2026-07-31 사용자 확정).** 82종 중 **74종을 등록 완료 상태로 만든다.**
현재 33종이 등록되어 있으므로 이번에 **41종을 새로 구현한다.**

구현 대상에서 빠지는 것은 여덟 종뿐이며, 빠지는 이유가 서로 다르다.

- **시장폭 3종**(McClellan Oscillator, McClellan Summation Index, TRIN/Arms)은 등락종목수와
  상승·하락 거래량이라는 입력이 있어야 계산된다. 레지스트리는 그 입력의 이름만 알고 값을
  넘기는 경로가 없다. 이것은 지표 구현이 아니라 데이터 경로 설계이므로 이번 범위 밖이다.
- **원저서 상수가 없는 5종**(QQE, MAMA/FAMA, Roofing Filter, Sinewave/Instantaneous Trendline,
  Special K)은 표준 문서 §12가 "추측하지 않고 남긴다"고 적어 둔 항목이다. QQE는 트레일링 밴드
  락 규칙, MAMA/FAMA는 Hilbert 6-tap 계수, Roofing Filter는 컷오프와 SuperSmoother 계수,
  Sinewave는 §8.1에 종속된 위상 파이프라인 상수, Special K는 항별 기간과 가중치표가 표준
  본문에 아예 없다. 상수를 지어내면 표준이 소유권을 잃으므로 구현하지 않는다.

**§12의 나머지 4종은 구현한다.** VIDYA, Schaff Trend Cycle, Klinger Volume Oscillator,
Keltner Channel은 §12에 올라 있으나 **표준 본문에 한쪽 수식이 완결되어 있다.** 본문에 적힌
수식을 채택하고, 어느 갈래를 골랐는지와 버린 갈래가 무엇인지를 `pinned_impl`과 실행 계획
문서에 남긴다. 표준 문서 자체는 고치지 않는다.

**확정된 결정(2026-07-31 사용자 선택).** 웨이브 3 종료 시점의 중간 점검은 **해제한다.**
3-1을 시험한 뒤 계속 여부를 정하기로 했던 조건은 범위 재지정으로 무효가 되었다. 값 검증은
외부 라이브러리 대조로 계속한다.

**출발점(확인된 현재 상태):**
- 등록 상태는 **36 조합 / 33 이름 / 표준 82종 기준 33종**이다. 이름 33개 가운데 EMA와
  Volume SMA는 표준이 §0 프리미티브로 분류해 82종 집계 밖이고, Bollinger Bands 하나가
  82종 집계에서는 밴드·%B·BandWidth 세 항목으로 세어진다.
- 웨이브 0부터 3까지가 끝나 프리미티브 계층이 갖춰져 있다. `safe_divide`, `hl2`, `hlcc4`,
  `ohlc4`, `sma`, `ema`, `wma`, `rma`, `tr`, `tp`, `stdev`, `hh`, `ll`, `cumulative`, `mom`,
  `roc`, `linreg`와 그 증분 상태 클래스가 이미 있다. 새 지표가 프리미티브를 다시 구현하지
  않는다.
- 계산식 표준은 `docs/references/technical_indicators_calc_spec.md`(917줄, 82종)가 소유하며
  저장소 이력에 들어와 있다. 이 파일은 정본의 사본이고 값이나 규약을 임의로 바꾸지 않는다.
- 표준 문서에는 **수치 예시가 없다.** 값의 정확성은 외부 라이브러리 대조로 확인한다.
  TA-Lib 0.7.1, Tulip Indicators 0.4.0, ta 0.11.0을 담은 일회용 환경이 이미 만들어져 있어
  같은 환경을 다시 만들 필요가 없다.
- 검증 축 다섯이 있다: `test_indicator_registry.py`, `test_indicator_contracts.py`,
  `test_indicator_primitives.py`, `test_indicator_parity.py`(벡터 경로와 O(1) 증분 경로의
  동일성), `test_indicator_reference_values.py`(외부 구현 대조).

**In scope:**
- **I-0. 병렬 작업이 가능한 구조로 먼저 바꾼다.** 지금은 `build_default_registry()` 하나가
  모든 등록을 담고 기준값도 파일 하나에 모여 있어, 두 사람이 동시에 지표를 더할 수 없다.
  등록과 기준값을 계열별 모듈로 나눠 **한 파일을 두 작업자가 건드리지 않게** 만든다. 지표
  수는 늘지 않고 등록 목록과 계산 결과도 그대로여야 한다.
- **I-1. 구현 41종.** 계열별로 나눠 표준 문서대로 구현한다. 불변식을 지킨다 — 재귀형 지표는
  확정 캔들로만 갱신, 계산은 float64, 같은 지표를 두 번 구현하지 않음, 워밍업 seed와 표준편차
  분모 규약은 표준 문서를 따름.
- **I-2. 미래 참조 금지.** 시프트를 쓰는 지표(Ichimoku의 선행·후행 스팬, Alligator의 세 선,
  Fractals의 확정 지연)에서 **t 시점 출력이 t 이후 데이터에 의존해서는 안 된다.** 정렬 규약을
  하나로 정해 네 종에 같이 적용하고 규약을 문서에 남긴다.
- **I-3. 등록 조합.** 각 지표의 기본 파라미터 조합을 정해 등록한다. 표준이 기본 기간을 주지
  않은 지표는 단일 조합만 등록하고 근거를 남긴다.
- **I-4. 검증.** 새 지표마다 다섯 축을 통과시킨다. 벡터 경로와 증분 경로의 동일성에 더해
  **값의 정확성을 외부 라이브러리와 대조**한다. 외부 라이브러리는 계산식의 원천이 아니라
  대조군이다. 값이 어긋나면 표준 문서를 다시 읽어 원인을 밝히고, 라이브러리를 따라 구현을
  바꾸지 않는다. 대조 대상이 없는 지표는 이유를 적어 미대조로 남긴다.
- **I-5. 채택 기록.** §12의 네 종은 채택한 갈래와 버린 갈래를 남긴다.

**Out of scope (필요하면 에스컬레이션):**
- 3-1·3-2 소관 전부(전략 개발 skill·Agent·테스트 방침, `claude -p` 분석 파이프라인).
- 표준 문서의 수식·규약을 바꾸는 것. 정본은 개발지침 디렉터리이고 저장소는 사본이다.
  표준이 모호하면 임의 해석 대신 사용자에게 확인한다.
- legacy signal-service 지표 코드를 계산식 원천으로 삼는 것.
- 지표를 쓰는 전략을 만드는 것. 이번 스프린트는 재료를 갖추는 것이다.
- 제외 8종(시장폭 3종, 원저서 상수 5종). 입력 채널 설계와 원저서 대조는 별도 작업이다.

**Done when (transcript-verifiable, turn-capped):**
- I-0: 계열별 분리가 끝난 뒤 등록 목록과 기존 지표 값이 분리 전과 같음이 테스트로 확인된다.
- I-1·I-3: 41종이 구현되고 기본 조합이 등록된다. 등록 목록의 전후 비교가 수치로 제시된다
  (36 조합 / 33 이름 / 82종 중 33종 → N 조합 / M 이름 / 82종 중 74종).
- I-2: 시프트 지표의 정렬 규약이 문서에 남고, t 시점 출력이 t 이후 데이터를 쓰지 않음이
  테스트로 확인된다.
- I-4: 새 지표 전부가 다섯 축을 통과하고, **값이 외부 라이브러리와 일치함이 수치와 함께**
  보인다. 값 위조·근사로 통과시키지 않는다. 어긋난 지표는 원인과 처리를 남긴다.
- I-5: §12 네 종의 채택 기록이 남는다.
- 독립 리뷰 1회가 Blocking 0건으로 관찰된다. 특히 "표준 문서와 다른 수식을 쓰지 않았는가",
  "진행 중 캔들이나 미래 봉을 재귀 상태에 넣지 않았는가", "외부 라이브러리를 계산식의 원천으로
  삼지 않았는가", "대조를 맞추려 상수를 끼워 넣지 않았는가"를 적대적으로 확인한다.
- 저장소 루트 `pytest services` exit 0, ruff·ruff format·mypy exit 0. 기존 36 조합의 값이
  변하지 않음이 회귀로 확인된다.
- Turn budget: ≤ 60 orchestrator turns. 초과하면 중단하고 보고한다.

**Register with /goal:**

```
/goal Complete roadmap 3-0 under its widened scope: implement every indicator the calculation
  standard actually specifies. Split the registry and the reference values into per-category
  modules so waves can run in parallel, implement the 41 remaining implementable indicators
  across trend, momentum, volatility, volume, strength, and system categories, register a
  default parameter combination for each, and check every value against an outside library
  because the standard carries no worked examples. Eight indicators stay out: three market
  breadth ones need an input channel that does not exist, and five need original-source
  constants the standard deliberately left blank.
  DONE iff (a) the per-category split leaves the registered list and every existing value
  unchanged, (b) 41 indicators are implemented and registered with a before/after count shown
  (36 combinations / 33 names / 33 of 82 systems -> N / M / 74 of 82), (c) the shift-alignment
  convention is written down and no output at bar t depends on data after t, (d) every new
  indicator passes registry, contract, primitive, parity, and outside-library checks with
  values shown by number, nothing fabricated to force a pass, and every mismatch explained,
  (e) the four §12 indicators record which branch of the formula was adopted and which was
  rejected, (f) one independent review returns zero Blocking after confirming no formula drift
  from the standard, no future bar entering a value, no outside library treated as the source
  of a formula, and no constant inserted to match a comparison, and (g) repository-root
  `pytest services` exit 0 with ruff+ruff-format+mypy exit 0 and the existing 36 combinations
  unchanged.
  Hard stop at 60 orchestrator turns; report and wait.
```
