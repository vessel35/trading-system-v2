# T2 — 캔들스틱 패턴을 core-lib에 별도로 얹기 위한 구조 조사 (5판)

이 문서는 `feat/candlestick-patterns` 브랜치의 저장소를 읽기만 하고 작성했다. 저장소 파일은
하나도 고치지 않았고 구현 코드도 쓰지 않았다.

## 5판에서 무엇이 바뀌었는지

5판은 **마감 정리**다. 4차 적대적 교차 검토가 낸 Blocking 하나와 Non-blocking 하나를 반영하고,
남은 사용자 결정 셋을 설계가 바로 쓸 수 있는 형태로 다듬었다. 세 항목만 손댔다.

- **Rise and Fall Three Methods를 창 길이 단언에 넣었다(검토 Blocking 4).** 4판은 모든 패턴의 `k`가
  1에서 5 사이라고 단언했으나, 이 패턴의 작은 캔들 무리 개수가 아직 열려 있어 그 단언이 성급했다.
  Morris 규칙 2가 개수를 못박지 않으므로 `k = m + 2`이고, Nison 2판 7장이 이상적인 수를 셋이라
  하면서 경험상 둘에서 다섯까지 잘 작동한다고 적으므로 원전 근거가 있는 후보는 **고정 세 봉**과
  **둘에서 다섯까지의 유한 범위** 둘뿐이다. 두 후보에서 `k`와 `min_history`와 상태 보관량이 얼마가
  되는지를 4.2절에 표로 적었고, **유한 범위 후보에서는 `k`의 상한이 7이 되므로** 복잡도 표의 값을
  고쳤다. **어느 후보를 골라도 유한하므로 상한 없는 패턴이 0개라는 결론은 유지된다.**
- **검증 절의 제목을 본문에 맞췄다(검토 Non-blocking 2).** 4.3.3절의 제목이 "두 갈래"였으나 본문은
  독립 경계 검증과 두 실행 경로의 동일성 검증과 두 서비스의 동일성 검증이라는 세 갈래를 제시한다.
  본문이 맞으므로 제목을 "세 갈래"로 고쳤다.
- **남은 사용자 결정 셋을 8절로 모았다.** 각 결정마다 선택지와 **고르면 무엇을 구현해야 하는지**와
  되돌리기 난이도를 적고, 세 결정이 서로 얽혀 있는지와 정해야 할 순서를 8.4절에 적었다. 배치안
  비교표는 5.1절에 이미 있으므로 되풀이하지 않고 가리키기만 했다.

**4판에서 바뀐 것도 아래에 남겨 둔다.** 3차 교차 검토가 낸 Blocking 2번, 3번, 4번, 5번, 6번을
반영한 내역이다.

## 4판에서 무엇이 바뀌었는지

4판은 새 조사가 아니라 **정합화**다. 3차 적대적 교차 검토가 낸 Blocking 여섯 건 가운데 이 문서의
소관인 다섯(2번, 3번, 4번, 5번, 6번)을 반영했고, 그 과정에서 3판이 이미 확정된 사용자 결정을 다시
선택으로 열어 둔 자리를 닫았다.

- **Breakaway를 고정 다섯 봉으로 맞췄다(검토 Blocking 4).** 3판은 Morris의 유연성 절을 근거로
  가변 길이 줄을 복잡도 표에 두고 상한 결정을 남겨 두었으나, 원전 조사의 **결정 C**가 Morris
  내부에서는 규칙 절이 규범이라고 확정했고 규칙 절은 다섯 봉이다. 복잡도 표의 가변 길이 줄,
  6.2절의 상한 결정 항목, 부록의 관련 서술을 모두 지웠다. **이로써 상태 보관량에 상한이 없는
  패턴은 하나도 남지 않는다.**
- **추세 비교 봉을 확정하고 상태 설계를 맞췄다(검토 Blocking 2).** 3판은 추세를 패턴의 가장 이른
  봉에서 읽을지 직전 봉에서 읽을지 다시 선택으로 남겼다. Morris의 예시가 **패턴 첫날의 범위
  중간값을 그 시점의 10기간 지수이동평균과 비교**하므로 가장 이른 봉으로 확정하고
  `min_history = P + k - 1`로 못 박았다. 여기서 따라오는 것이 하나 있다. 판정 시점에 필요한 것이
  현재 이동평균이 아니라 `k - 1`봉 전의 이동평균이므로, **상태는 `EmaState(10)`에 더해 최근 `k`개의
  이동평균 값을 담은 짧은 큐를 들어야 한다.** 4.2절의 보관량을 그렇게 다시 적었고, 캔들당 작업
  수는 그대로 상수임을 확인했다.
- **`min_history` 검증을 독립적으로 만들었다(검토 Blocking 3).** 3판의 검증은 정확성 검증이 아니라
  **상호 일치 검증**이어서, 선언과 배치와 상태가 함께 한 봉 틀리면 그대로 통과했다. 4.3.3절을 세
  갈래로 다시 세우고, 첫째 갈래에 **원전 정의에서 손으로 유도한 기대 `min_history` 표**와 **경계
  봉에서 반드시 성립하는 수제 입력** 두 방식을 독립 기준으로 두었다. 첫 유효 인덱스와 **바로 앞
  봉의 NaN**을 함께 검사하므로 한 봉 빠른 구현과 한 봉 늦은 구현을 둘 다 잡는다. "기존 축에
  등록하면 자동으로 걸린다"는 서술은 사실이 아니므로 지웠다.
- **결합 실행에서 종류 신원이 사라지는 문제를 다뤘다(검토 Blocking 6).** 카탈로그 대조를
  `(kind, name, params)`로 고쳐도 실행 단계에서는 `identifier`와 `_indicator_key`가 `name`과
  `params`만으로 만들어져 종류가 사라진다. 3.6.3절을 새로 두어 종류가 기록되지 않는 자리 넷을
  코드로 짚고, 종류를 실행 신원에 넣는 갈래와 이름 비중복을 계약으로 강제하는 갈래의 비용을
  각각 적었다. 이 비용을 배치안 B와 D에 계상하고 비교표에 줄을 하나 더했다. 어느 신원 규약을
  채택할지는 사용자 결정으로 올렸다.
- **실행 불가능한 출력 후보를 정상 후보에서 뺐다(검토 Blocking 5).** "확인 전에는 값 자체를
  정의하지 않는다"는 후보는 Evidence 완결성 검사와 signal-service의 유한성 검사를 동시에 만족할 수
  없으므로 4.3.4절의 표에서 제거했다. 그 결과 **확인이 필요한 패턴의 `min_history`도 출력 표현과
  무관하게 확정된다.** 남은 결정 목록에서 결정 B의 비교 봉과 결정 C의 Breakaway 봉 수도 지웠다.

**3판에서 바뀐 것도 아래에 남겨 둔다.** 2차 교차 검토가 낸 Blocking 3번, 4번, 5번을 반영한
내역이다.

## 3판에서 무엇이 바뀌었는지

2차 적대적 교차 검토가 2판에 대해 Blocking 여섯 건을 냈고 그 가운데 **셋(3번, 4번, 5번)이 이
문서의 소관**이다. 나머지 셋은 원전 조사의 소관이므로 여기서 다루지 않는다. 여기에 사용자가
2026-08-01에 확정한 추세 판정 방식이 구조에 주는 영향과, 검토가 낸 Non-blocking 둘을 함께
반영했다.

- **`min_history` 검증이 틀렸다(검토 Blocking 3).** 2판은 배치 첫 유효 인덱스, 상태의 첫 warm
  인덱스, 백테스트 첫 평가 봉, signal-service 첫 평가 봉 **넷을 하나의 같은 인덱스로 묶어 단언**
  하라고 썼다. 앞의 둘은 `min_history - 1`이고 뒤의 둘은 `required_warmup`이므로 **한 봉 어긋나는
  것이 정상**이며, 그대로 쓰면 올바른 구현이 실패한다. 4.3.3절을 두 갈래 검증으로 다시 썼다.
  확인 지연을 `min_history`에 무조건 더한 식도 워밍업과 발표 시점을 섞은 것이어서, 4.3.4절을
  새로 두어 출력 표현별로 갈라 유도했다. Hikkake의 입력 봉 수도 5에서 3으로 고쳤다.
- **추천안 D의 공통 Protocol이 실제 소비 계약보다 작았다(검토 Blocking 4).** 두 소비자의 spec
  속성 접근을 전부 뽑아 세어 **구성원이 다섯이 아니라 일곱**임을 확인했고, 동시에
  `compute_vectorized()`와 상태의 `current()`가 **두 서비스 어디에서도 쓰이지 않는다**는 사실도
  새로 확인했다. 5절의 D-1절을 새로 두어 소비 Protocol과 검증 Protocol을 갈랐고, 그 비용을
  비교표에 계상했다.
- **판별자를 무시하는 카탈로그 대조가 계약을 보존하지 못한다(검토 Blocking 5).** 2판은 판별자
  키를 붙여도 "DDL도 대조 로직도 바꾸지 않고 통과한다"고 장점으로 적었다. 통과하는 것은 맞지만
  **그 통과가 곧 결함**이며, 3.4.1절을 새로 두어 대조 로직을 어떻게 고쳐야 하는지를 설계로 적고
  "고치지 않고 쓸 수 있다"는 서술을 지웠다.
- **배치안 A의 `all` 서술을 바로잡았다.** "표준 89종만"으로 좁힌다는 표현은 등록 상태와 맞지
  않는다. 89종 가운데 등록된 이름은 81개이고 조합은 84개이며 나머지 8종은 해석할 spec이 없다.
  기준은 **"패턴을 제외한 현재 등록 지표 전부"**로 고쳤다.
- **추세 판정이 구조에 주는 영향을 반영했다.** 사용자가 Morris의 10기간 지수이동평균을 쓰기로
  확정했으므로, 추세를 요구하는 패턴의 상태는 `EmaState(10)`을 안에 든다. 4.2절 복잡도 표에
  그 줄을 상수 시간으로 확정해 넣었고, 4.3.2절의 `min_history` 유도에 추세 항을 더했다.
  `EmaState(10)`이 인덱스 9에서 처음 warm이 된다는 것은 코드로 확인했다.
- **확인 대기 상태에 대한 과도한 결론을 거뒀다(검토 Non-blocking).** 행을 생략할 수 없다는 사실이
  강제하는 것은 매 봉 유한값 하나뿐이고, 확인 전에 불성립을 내는 계약도 그것을 만족한다. 대기
  상태를 노출할지는 출력 표현 결정의 결과라고 3.5.1절과 3.6.2절을 고쳤다.
- **복잡도 표의 고정 봉 범위도 고쳤다.** 단일 봉 패턴이 빠져 있었다. 같은 자리에서 Breakaway를
  가변 길이로 다룬 것은 4판에서 다시 고정 다섯 봉으로 바로잡았다.

**2판에서 바뀐 것도 아래에 남겨 둔다.** 1판에 대한 첫 번째 교차 검토가 낸 Blocking 여섯 건
(5번부터 10번)을 반영한 내역이다.

- 1판은 판정값을 1.0과 0.0으로 인코딩하는 것을 사실상 확정하고 전략 계약 변경이 필요 없다고
  결론지었다. 그것은 원전 조사가 **사용자 결정으로 올려 둔 항목**을 앞지른 것이었다. 2판은
  결론을 내리지 않고 가능한 표현마다 다섯 축으로 평가한 표를 3.5절에 낸다.
- 1판은 두 번째 레지스트리를 두면 소비 경로 변경이 "배선 수준"에 머문다고 했다. 그러나 지금
  계약에는 **전략이 패턴을 선언할 자리가 없고**, 선언하지 못하면 카탈로그 대조와 워밍업 계산에
  패턴이 나타나지 않는다. 2판은 배치안마다 선언·대조·합집합·워밍업·선택 모드 다섯을 5절에서
  구체적으로 답한다.
- 1판의 추천 근거 첫 문장이 사실과 달랐다. 배치안 C가 제안한 `core_lib/patterns/`는 문자 그대로
  core-lib 패키지 **안**이다. 2판은 그 오류를 바로잡고, 검토가 제시한 네 번째 안을 후보에 넣어
  네 안을 같은 기준으로 다시 평가한다.
- 1판은 상수 시간 증분이 무조건 성립한다고 썼다. 2판은 척도마다 상태·갱신식·보관량·캔들당
  작업 수를 갈라 적고, 어느 조건에서 성립하고 어느 조건에서 새 자료구조가 필요한지를 4.2절에
  적는다.
- 1판은 `min_history`를 "겹치는 방식에 맞춰 계산해야 한다"고만 했다. 2판은 TA-Lib의 `lookback`이
  우리 `min_history`와 같은 개념인지를 등록된 지표 네 종으로 검증해 **같지 않음을 반증**하고,
  패턴 형태별로 첫 유효 인덱스를 유도했다. 이 반증과 유도는 3판에서도 그대로 쓰이지만, 2판이
  함께 낸 "네 지점을 하나의 인덱스로 맞대는" 검증 절차는 위에 적은 대로 3판에서 폐기했다.
- 불변식을 열여덟에서 스물다섯으로 늘리고, Evidence의 두 문제(표준 출처가 boolean으로 눌려
  복원되지 않는 것과 완결성 검사가 행 생략을 금지하는 것)를 3.6절과 7절에서 다룬다.

패턴이 몇 종인지, 각 패턴의 판정 수식이 무엇인지는 다른 담당의 몫이므로 여기서 다루지 않는다.
여기서 답하는 것은 **그 결과물이 어느 자리에 어떤 모양으로 얹혀야 하는가**뿐이다.

조사 시점의 등록 상태는 **84 조합 / 81 이름 / 표준 89종 가운데 81종**이다. 이 숫자는
`services/core-lib`에서 `DEFAULT_REGISTRY.list()`와 `indicator_reference` 패키지를 직접 읽어
확인했다.

---

## 1. 지금의 지표 하부구조가 무엇을 계약하는가

### 1.1 `IndicatorSpec`의 각 필드가 계약하는 것

`services/core-lib/core_lib/indicators/registry.py:43-94`의 `IndicatorSpec`은 frozen dataclass
이며, 계산 하나의 **불변 신원**과 그 신원을 실행하는 **두 진입점**을 함께 담는다.

**`name`과 `params`가 신원을 만든다.** `identifier` 속성
(`services/core-lib/core_lib/indicators/registry.py:80-86`)이 파라미터를 키 이름 순으로 정렬해
`RSI(period=14)` 같은 문자열을 만들고, 이것이 등록·조회·Evidence 기록의 유일한 열쇠가 된다.
레지스트리의 내부 키는 `(name, sorted(params.items()))` 튜플이므로
(`services/core-lib/core_lib/indicators/registry.py:106-108`), 같은 이름이라도 파라미터가 다르면
별개 등록이고 파라미터까지 같으면 재등록이 거부된다
(`services/core-lib/core_lib/indicators/registry.py:117-122`). 전략은 등록된 조합만 선언할 수
있고 등록되지 않은 조합은 조회 시점에 거부된다는 것이 `docs/strategy-authoring-contract.md`
3.7절의 규칙이다.

**`pinned_impl`은 계산의 출처를 문자열로 못박는다.** 값은 자유 서술이지만 검증이 형식을
강제한다. `services/core-lib/tests/test_indicator_registry.py:85`가 등록된 **모든** spec에 대해
`"technical_indicators_calc_spec.md §"`라는 부분 문자열이 `pinned_impl` 안에 들어 있을 것을
요구한다. 즉 지금의 `DEFAULT_REGISTRY`에 들어간다는 것은 곧 "이 계산의 출처는 기술지표 계산
표준의 어느 절이다"라고 선언한다는 뜻이다. 캔들스틱 패턴은 그 표준 문서에 절이 없다.

실제로 `pinned_impl`은 절 번호에 더해 **무엇을 구현하지 않았는지**까지 적는 자리로 쓰이고 있다.
`services/core-lib/core_lib/indicators/specs/systems.py:212-218`의 TD Sequential은 setup만
구현하고 countdown은 표준이 원저서로 미뤘기 때문에 구현하지 않았다고 적어 두었고, 같은 파일
229-235줄의 Woodies CCI는 값과 구간까지만 구현했다고 적어 두었다.

**다만 이 문자열은 실행 기록에 남지 않는다.** 3.6절에서 다룬다.

**`min_history`는 그 조합이 값을 내기 위해 필요한 확정 캔들 수다.** 양수여야 하고
(`services/core-lib/core_lib/indicators/registry.py:72-73`), 배치 경로는 캔들이 이보다 적으면
계산 대신 예외를 던진다(`services/core-lib/core_lib/indicators/registry.py:209-212`). 증분 경로
쪽에서는 백테스트 Engine이 워밍업 구간 길이를 정하는 데 쓰고
(`services/backtest-service/backtest_service/engine/engine.py:383-384`), 워밍업이 끝난 뒤에도
상태가 warm이 아니면 실행을 중단한다
(`services/backtest-service/backtest_service/engine/engine.py:479-482`).

**`category`는 파일 소유권을 선언한다.** 값 자체는 계산에 쓰이지 않지만, 이 필드가 자기를 담은
등록 모듈의 이름과 다르면 import 시점에 예외가 난다. 아래 1.3절에서 다룬다.

**`required_inputs`는 캔들 밖의 입력 채널 이름을 적는 자리다.** 시장폭 지표처럼 등락종목수나
상승·하락 거래량이 있어야 계산되는 지표를 위한 것이다. 다만 **이 필드를 실제로 존중하는 것은
배치 경로 하나뿐이다.** `compute_batch`가 사용 가능한 입력의 부분집합이 아니면 그 spec을 조용히
건너뛴다(`services/core-lib/core_lib/indicators/registry.py:206-208`). 증분 경로에는 같은 여과가
없고, 백테스트 Engine의 `resolve_specs`
(`services/backtest-service/backtest_service/engine/engine.py:366-370`)와 signal-service의 상태
생성 경로 어디에도 `required_inputs`를 보는 코드가 없다. 그러므로 **이 필드는 "아직 값을 넘길 수
없는 지표를 등록해 두는 안전한 탈출구"가 아니다.** 캔들만으로 판정되는 캔들스틱 패턴에는 이
필드가 필요 없지만, 이 사실은 7절 불변식에 남긴다.

**`undefined_outputs`는 표준 자신이 정의를 포기한 출력 키의 목록이다.**
`services/core-lib/core_lib/indicators/registry.py:59-67`의 주석이 그 취지를 적고 있다. 표준
3.10절이 Bollinger %B에 대해 "분모 0 → 미정의"라고 쓴 것이 유일한 사례이고, 여기 이름이 오른
키만 워밍업 이후에도 NaN을 가질 수 있다. 이름이 없는 출력은 워밍업 이후 NaN이면 실행이 중단된다.
**이 목록은 이름 있는 키에만 걸 수 있으므로, 단일 숫자를 내는 지표는 이 면제를 쓸 수 없다.**
`services/core-lib/tests/test_indicator_volatility_flat_window.py:6-10`이 그 제약을 명시적으로
적어 두었다.

**두 실행 진입점은 배치와 증분이다.** `compute_vectorized`
(`services/core-lib/core_lib/indicators/registry.py:88-90`)는 캔들 전체를 받아 캔들 수와 같은
길이의 계열을 내고, `make_state`(`services/core-lib/core_lib/indicators/registry.py:92-94`)는
실행 데이터를 공유하지 않는 새 증분 상태를 만든다. 강제되는 것은 **둘이 같은 값을 내야 한다**는
것이며, 그 검증은 2.4절에서 다룬다. 백테스트 Engine은 look-ahead 경계가 구조적으로 유지되도록
일부러 증분 경로만 쓰고, 배치 경로는 그 증분 구현을 검증하는 독립 오라클로 남긴다는 것이
`services/core-lib/core_lib/indicators/registry.py:193-196`의 주석이다.

### 1.2 `IndicatorState` 프로토콜이 요구하는 것

`services/core-lib/core_lib/indicators/registry.py:19-40`의 `IndicatorState`는
`@runtime_checkable` Protocol이지만 저장소 어디에서도 `isinstance` 검사에 쓰이지 않는다. 실제로는
mypy가 정적으로 강제하는 구조 계약이다. 요구하는 것은 속성 하나와 메서드 셋이다.

`min_history` 속성은 spec의 같은 이름 필드와 **반드시 일치해야 한다.** 두 값이 서로 다른 파일에
쓰이므로 드리프트를 막는 것은 검증뿐이고,
`services/core-lib/tests/test_indicator_registry.py:264-279`가 등록된 모든 조합에 대해 둘을
대조한다.

`warmed_up`은 유효한 값을 낼 만큼 캔들을 보았는지를 답한다. 검증은 이것을 **정확히** 요구한다.
`services/core-lib/tests/test_indicator_registry.py:282-291`이 `min_history - 1`개를 먹인 뒤에는
warm이 아니고 한 개를 더 먹인 직후에는 warm이어야 한다고 단언한다. 하나라도 빠르거나 늦으면
실패한다.

`seed(candles)`는 상태를 **초기화한 뒤** 워밍업 캔들로 채운다. 이름이 append가 아니라 seed인
이유가 여기 있고, 실제 구현도 그렇게 되어 있다
(`services/core-lib/core_lib/indicators/systems.py:719-723`의 `FractalsState.seed`가 창과 값을
먼저 비우고 다시 채운다).

`update(candle)`은 **확정 캔들 하나만큼** 상태를 전진시키고 그 시점의 값을 돌려준다. 진행 중인
캔들이나 미래 캔들이 여기 들어오면 안 된다는 것이 확정 캔들 계약이며, 그 계약을 강제하는 함수는
`services/core-lib/core_lib/indicators/contracts.py:13-19`의 `assert_finalized`다.

`current()`는 마지막 값 또는 워밍업 모양의 NaN 값을 돌려준다. 상태를 전진시키지 않고 읽기만
한다는 점이 `update`와 다르다.

### 1.3 `specs/__init__.py`의 카테고리 소유 규칙

`services/core-lib/core_lib/indicators/specs/__init__.py`는 여섯 카테고리가 각자 소유한 등록
목록을 하나로 모은다. 카테고리 이름을 적어 두는 유일한 자리이고
(`services/core-lib/core_lib/indicators/specs/__init__.py:21-32`), 모으는 방식이 디렉터리 스캔이
아니라 **손으로 적은 목록**이다. 스캔이면 모듈이 조용히 빠져도 아무것도 실패하지 않지만, 적어 둔
이름이 빠지면 레지스트리를 처음 쓰는 순간 import 오류가 난다는 것이 그 파일 9-12줄의 설명이다.

`_reject_misfiled_specs`(`services/core-lib/core_lib/indicators/specs/__init__.py:35-53`)가 막는
것은 **자기 카테고리를 소유하지 않은 모듈에서 등록된 spec**이다. 예를 들어 `category="volume"`
이라고 선언한 spec이 `specs/trend.py`에 들어 있으면 import 시점에 예외가 난다. 이 검사가 있는
이유는 파일 소유권이 분리의 전부이기 때문이다. 분류가 어긋난 spec은 한 사람의 지표를 다른 사람의
파일에 조용히 넘겨 주고, 그것은 나중에 병합 충돌로 발견되는 대신 지금 기동 실패로 드러나야 한다.

이 규칙은 **"지표 하나를 더하는 일이 딱 두 파일을 건드린다"**는 성질을 만든다. 계산 모듈 하나와
등록 모듈 하나이며, 그래서 여러 사람이 동시에 지표를 더해도 같은 파일에서 충돌하지 않는다.

### 1.4 레지스트리 조립과 `DEFAULT_REGISTRY`

`build_default_registry()`(`services/core-lib/core_lib/indicators/registry.py:251-266`)는
`specs.all_specs()`가 내놓는 모든 spec을 하나씩 등록할 뿐이고, 카테고리가 몇 개인지 그 안에 무엇이
있는지 알지 못한다. 카탈로그가 커져도 이 함수가 그대로인 이유가 그것이다. 카테고리 모듈을 함수
안에서 import하는 것은 순환 import를 피하기 위해서다(같은 파일 258-260줄의 주석).

`DEFAULT_REGISTRY`(`services/core-lib/core_lib/indicators/registry.py:269`)는 그 함수를 모듈
적재 시점에 한 번 호출해 만든 **모듈 수준 단일 인스턴스**다. 담고 있는 것은 84개의
`IndicatorSpec`이며 이름 기준으로는 81개다. 카테고리별 내역은 trend 15조합 12이름, momentum
31조합 31이름, volatility 12조합 12이름, volume 11조합 11이름, strength 5조합 5이름, systems
10조합 10이름이다.

`IndicatorRegistry`가 제공하는 조회는 네 가지다. 이름과 파라미터로 정확히 하나를 꺼내는 `get`,
이름 또는 identifier 문자열의 집합을 해석하는 `specs_for`, 외부에서 들어온
`{"name": ..., "params": ...}` 서술자를 해석하는 `specs_from_descriptors`, 그리고 `auto` ·
`explicit` · `all` 세 모드를 해석하는 `resolve_enabled`다.

**서술자 해석에 걸린 제약 하나를 미리 짚어 둔다.** `_descriptor_spec`
(`services/core-lib/core_lib/indicators/registry.py:138-159`)은 서술자의 키 집합이 정확히
`{"name", "params"}`여야 한다고 요구하고, 아니면 `"indicator descriptor must contain exactly
name and params"`로 거부한다. 곧 전략의 선언 항목에 판별자 키를 하나 더 붙이는 방식을 쓰려면
**엔진이 레지스트리에 넘기기 전에 그 키를 떼어 내야 한다.** 5절의 배치안 평가에서 이 제약이
반복해서 등장한다.

**`all` 모드는 등록된 모든 조합을 켠다**(`services/core-lib/core_lib/indicators/registry.py:227-228`).
이 모드는 백테스트 실행 설정에 그대로 노출되어 있다
(`services/backtest-service/backtest_service/config/run_config.py:71`).

`DEFAULT_REGISTRY`를 직접 참조하는 곳은 core-lib 밖에 둘뿐이다. signal-service는 생성자의 기본
인자로 받으므로 **다른 레지스트리를 주입할 수 있고**
(`services/signal-service/signal_service/application/service.py:67`), 백테스트 Engine은 모듈
전역을 직접 부르므로 **주입 지점이 없다**
(`services/backtest-service/backtest_service/engine/engine.py:366`, 374).

---

## 2. 다섯 검증 축이 각각 무엇을 강제하는가

### 2.1 `test_indicator_registry.py` — 등록 신원

이 축이 강제하는 것은 **등록된 것이 정확히 예상한 것인가**이다. 개수가 아니라 집합으로 못박는데,
개수는 숫자가 움직였다는 것만 말하지만 집합은 어느 조합이 나타났고 사라졌는지를 말하기 때문이다
(`services/core-lib/tests/test_indicator_registry.py:68-75`).

요구하는 것을 나열하면 이렇다. 등록된 identifier 집합과 이름 집합이 손으로 적어 둔 집합과
일치할 것, 모든 spec의 `version`이 `"1.0.0"`일 것(Bollinger Bands만 `"1.0.1"`), 모든 spec의
`pinned_impl`이 계산 표준 문서의 절을 인용할 것, 모든 `min_history`가 양수일 것
(`services/core-lib/tests/test_indicator_registry.py:78-86`). 이어서 카테고리별로 같은 비교를 한 번
더 해서 어긋남이 어느 소유자의 것인지를 이름과 함께 알려 주고
(같은 파일 89-108줄), 카테고리 이름 여섯 개를 튜플 그대로 못박고 잘못 분류된 spec이 없는지
확인한다(같은 파일 111-135줄). 마지막으로 spec의 `min_history`와 상태의 `min_history`가 같은지,
상태가 정확히 그 지점에서 warm이 되는지, `undefined_outputs`가 손으로 적어 둔 것과 정확히 같은지를
본다.

### 2.2 `test_indicator_contracts.py` — 확정 캔들 계약

가장 작은 축이다. `assert_finalized`가 결정 시각보다 늦게 닫히는 캔들을 거부하는지, 그리고
`drop_unfinalized`가 아직 닫히지 않은 꼬리를 잘라 내는지 두 가지만 확인한다
(`services/core-lib/tests/test_indicator_contracts.py:33-43`). 개별 지표에 대해 무엇을 요구하는
축은 아니지만, 지표 계층 전체가 서 있는 전제를 지킨다.

### 2.3 `test_indicator_primitives.py` — 공유 프리미티브

새 지표가 프리미티브를 다시 구현하지 않아도 되도록 아래층을 고정하는 축이다. 이동평균의 시드와
가중치 규약, 가격 파생 네 가지의 정의, True Range와 typical price, 모집단 표준편차, ROC와 MOM의
관계, 그리고 `safe_divide`가 **0으로 나눌 때의 대체값을 호출자가 반드시 이름 붙이도록** 강제한다는
것을 확인한다(`services/core-lib/tests/test_indicator_primitives.py:123-130`). NaN을 대체값으로
넘기는 것은 거부되는데, NaN이 워밍업 표시로 예약되어 있기 때문이다.

프리미티브 계층에서도 벡터 경로와 증분 경로의 동일성을 요구하고
(같은 파일 137-164줄), 재귀형 평균의 시드가 두 경로에서 **비트 단위로 같아야** 한다는 것까지
못박아 두었다(같은 파일 194-223줄). 이 단언은 Klinger 오실레이터에서 34기간과 55기간 두 평균의
차가 공통 크기를 상쇄하고 마지막 비트 차이만 남기면서 실제로 드러난 결함 때문에 생겼다.

### 2.4 `test_indicator_parity.py` — 두 경로 동일성과 절별 관계

가장 큰 축이며 두 종류의 단언이 섞여 있다.

첫째는 **모든 등록 조합**에 대한 두 경로 동일성이다. 네 개의 재현 가능한 난수 스트림
(`seed` 0, 7, 42, 2026)과 완전히 평평한 스트림에서, 배치 계열과 증분 갱신 결과가 값 하나하나
같아야 한다(`services/core-lib/tests/test_indicator_parity.py:205-216`). 비교는 NaN도 NaN끼리
맞아야 하는 엄격한 비교이며 허용 오차는 상대·절대 모두 1e-12다(같은 파일 175-190줄). 이 축은
`DEFAULT_REGISTRY.list()`에서 대상을 읽으므로 **등록하면 자동으로 걸린다.**

둘째는 각 지표가 자기 절에서 **계산식과 따로 적힌 성질**을 만족하는지 보는 관계 단언들이다.
같은 수식을 두 번 구현해 비교하는 것이 아니라는 점이 중요하다. 두 경로에 똑같이 잘못 옮긴
수식은 동일성 검사를 통과해 버리므로, 표준이 별도로 적어 둔 관계를 깨뜨리는 방식으로 드러나게
한다는 것이 그 취지다(같은 파일 296-303줄). MACD 히스토그램이 라인과 시그널의 차라는 것,
DEMA가 `2*EMA1 - EMA2`라는 것 같은 단언들이 여기 있다.

셋째로, **미래 봉을 읽지 않는다**는 성질이 자르기 비교로 확인된다. 캔들 300개로 계산한 결과와
앞부분만 잘라 계산한 결과가 겹치는 구간에서 같아야 한다는 형태이며, systems 계열 전체
(같은 파일 769-789줄), trend 계열 전체(360-381줄), volume과 strength의 지정 목록
(1105-1135줄), momentum의 후속 목록(642-652줄)에 걸려 있다.

### 2.5 `test_indicator_reference_values.py` — 외부 구현 대조

우리 자신이 아니라 **바깥 구현**과 값을 맞대는 축이다. 표본 지점은 300봉 계열의 인덱스 100, 200,
299 세 곳이다(`services/core-lib/tests/indicator_reference/series.py:14`).

이 파일이 요구하는 것은 셋이다. `REFERENCE`에 오른 출력은 표본 지점마다 상대·절대 1e-9 안에서
일치할 것, `CONVERGING`에 오른 출력은 각 지점의 허용치 안에 있고 **간격이 줄어들기만 할 것**,
그리고 **등록된 모든 출력이 세 표 가운데 하나에는 반드시 들어 있을 것**이다
(`services/core-lib/tests/test_indicator_reference_values.py:74-87`). 마지막 단언이 이 축의
핵심이다. 아무도 대조하지 않은 새 지표는 동일성 검사만으로 통과해 버리는데, 그 구멍을 막는 것이
이 파일의 존재 이유라고 적혀 있다.

### 2.6 `tests/indicator_reference/` 패키지의 구성과 네 이름

`services/core-lib/tests/indicator_reference/`는 카테고리마다 모듈 하나를 두고 공통 입력만
`series.py`에 모아 둔 패키지다. 두 부류의 진술이 들어 있으며 **둘 다 코드에서 읽어 오는 것이
아니라 손으로 적는다.** 자기가 검사하는 대상에서 기대치를 유도하면 어떤 레지스트리와도 일치해
버리기 때문이다(`services/core-lib/tests/indicator_reference/__init__.py:1-11`).

각 카테고리 모듈은 `CategoryModule` 프로토콜
(`services/core-lib/tests/indicator_reference/__init__.py:67-81`)이 정한 일곱 이름을 반드시
선언한다. `IDENTIFIERS`, `NAMES`, `STANDARD_SYSTEMS`, `UNDEFINED_OUTPUTS`, `REFERENCE`,
`CONVERGING`, `UNCOMPARED`이다. 하나라도 빠지면 mypy가 병합 표에서 잡는다.

병합 규칙도 느슨하지 않다. identifier와 이름은 **두 모듈이 같은 항목을 주장하면 예외**를 던지는
방식으로 합쳐지고(같은 파일 136-153줄), 세 대조 표는 서로 겹치는 출력이 있으면 import 시점에
예외가 난다(같은 파일 179-198줄).

네 이름이 뜻하는 것은 이렇다.

**`REFERENCE`는 외부 구현과 정확히 일치하는 출력**이다. 값의 출처는 TA-Lib 0.7.1이 기본이고,
TA-Lib이 구현하지 않는 것은 Tulip Indicators 0.4.0과 ta 0.11.0으로 메웠으며, TA-Lib이 아닌
항목은 그 자리에 주석으로 밝혀 두었다. 이 숫자들은 일회용 환경에서 한 번 만들어 얼려 둔 것이고
저장소는 실행 시점이나 지속적 통합에서 TA-Lib에 의존하지 않는다. 현재 95개 항목이 있다.

**`CONVERGING`은 시드 창 규약이 달라 초반에는 어긋나지만 간격이 닫히는 출력**이다. 간격이 계속
남으면 수식 자체가 다르다는 뜻이고 기하급수적으로 줄어들면 시드를 잊는 과정일 뿐이라는 것을
가르는 모양의 단언이다. 현재 17개 항목이 있다. 예를 들어 NATR은 TA-Lib이 표준 0.6절의 첫 True
Range를 건너뛰는 탓에 상대차가 8.0e-05에서 3.1e-11로 줄어들며, 구현을 TA-Lib에 맞추는 대신
같은 규약을 지키는 Tulip Indicators를 정확 대조 상대로 삼았다.

**`UNCOMPARED`는 대조 대상이 아예 없는 출력과 그 사유**다. 현재 26개 항목이 있다. 사유는 문장으로
적는다. Fractals 항목이 이번 작업과 특히 관련이 깊은데, 거기 적힌 사유가 **"TA-Lib의 패턴 계열인
CDL 함수들은 모두 캔들 자신의 시가·종가·그림자를 읽어 캔들 모양에 이름을 붙이는 것이고, 표준
6.2절은 한 캔들의 고가를 양옆 두 캔들의 고가와 비교할 뿐 캔들 안을 읽지 않는다"**는 것이다
(`services/core-lib/tests/indicator_reference/systems.py:182-190`). 저장소가 CDL 계열을
"우리 것과 종류가 다른 무엇"으로 이미 인식하고 그렇게 적어 둔 자리다.

**`STANDARD_SYSTEMS`는 그 카테고리의 등록이 표준 89종 가운데 몇 종을 차지했는가**를 세는
정수다. 손으로 적으며, 이름 개수와 일부러 다를 수 있다. 표준이 EMA와 Volume SMA를 0절 프리미티브로
분류해 89종 밖에 두고, Bollinger Bands 하나를 밴드·%B·BandWidth 세 항목으로 세기 때문이다. 현재
카테고리별 값은 trend 11, momentum 31, volatility 14, volume 10, strength 5, systems 10이고 합이
81이다.

### 2.7 89가 걸린 단언은 정확히 무엇을 세는가

문제의 단언은 `services/core-lib/tests/test_indicator_registry.py:158`의 다음 한 줄이다.

```python
assert len(follow_up) == 89 - REGISTERED_STANDARD_SYSTEMS
```

**왼쪽**은 아직 등록되지 않은 지표 이름을 모은 후속 카탈로그의 길이다. 열 개 계산 모듈이 각각
가진 `FOLLOW_UP_INDICATORS` 튜플을 이어 붙여 만든다
(`services/core-lib/tests/test_indicator_registry.py:138-150`). 지금 비어 있지 않은 것은 넷뿐이다.
`breadth.py`가 시장폭 3종, `cycle.py`가 Ehlers 3종, `momentum.py`가 Special K 한 종,
`strength.py`가 QQE 한 종을 담아 **전체 8종**이다. 나머지 여섯 모듈은 빈 튜플을 들고 있는데,
목록이 고정된 열 개 이름에서 모이므로 모듈이 사라지면 안 되기 때문이다.

**오른쪽의 89는 하드코딩된 리터럴**이며, 계산 표준 문서 11절이 "본 명세서 수록 지표 수"로 집계한
숫자를 그대로 옮겨 놓은 것이다. 표준 문서
`docs/references/technical_indicators_calc_spec.md`의 11절 표가 카테고리별로 11+31+14+10+6+4+3+4+6
을 더해 89를 낸다. 이 숫자는 2026-08-01 커밋에서 82에서 89로 올라갔다.

**오른쪽의 `REGISTERED_STANDARD_SYSTEMS`는 여섯 카테고리 모듈이 손으로 적은 `STANDARD_SYSTEMS`의
합**이며 현재 81이다. 그래서 단언은 지금 `8 == 89 - 81`로 성립한다.

이 단언이 실제로 세고 있는 것은 **"표준 문서가 수록한 지표 전부가 등록되었거나 후속 카탈로그에
남아 있거나 둘 중 하나이며, 어느 쪽에도 없는 지표는 없다"**는 성질이다. 등록도 안 되고 카탈로그에도
없는 지표가 조용히 사라지는 것을 막는 것이 목적이다.

**패턴을 어디에 등록하느냐에 따라 이 단언이 깨지는지에 대한 답은 이렇다.**

패턴을 **`DEFAULT_REGISTRY` 바깥의 별도 레지스트리**에 두면 이 단언은 전혀 움직이지 않는다.
양쪽 항 모두 손으로 적은 값과 리터럴이고, 새 레지스트리는 어느 쪽에도 기여하지 않기 때문이다.

패턴을 **`DEFAULT_REGISTRY` 안의 새 카테고리**로 두면, 그 카테고리의 `STANDARD_SYSTEMS`를 0으로
선언하는 한 **이 단언 자체는 깨지지 않는다.** 패턴은 표준 89종에 들어 있지 않으므로 0이 정직한
값이다. 다만 같은 파일의 **다른** 두 단언이 깨진다. 하나는
`services/core-lib/tests/test_indicator_registry.py:123`의
`CATEGORIES == ("trend", "momentum", "volatility", "volume", "strength", "systems")`이고, 다른
하나는 같은 파일 85줄의 `pinned_impl`이 계산 표준의 절을 인용해야 한다는 요구다. 둘 다 값이
바뀌는 것이 아니라 테스트를 고쳐야 하는 종류다. 앞의 것은 카테고리 이름 하나를 더하는 수정이고,
뒤의 것은 **패턴이 다른 표준 문서를 인용해야 하므로 단언을 조건부로 바꾸는 수정**이다. 뒤의 것이
문제의 본질에 더 가깝다.

패턴을 **기존 여섯 카테고리 중 하나에 섞어** 넣으면, `STANDARD_SYSTEMS`를 올리지 않는 한 산술은
성립하지만 그 카테고리의 `IDENTIFIERS`·`NAMES` 집합이 크게 부풀고 `pinned_impl` 요구가 그대로
걸린다. 사용자가 정한 "기존 지침과는 별도로 구성한다"는 방향과도 정면으로 어긋난다.

---

## 3. 소비 쪽이 지표 값을 어떻게 다루는가

### 3.1 signal-service의 `_assert_finite_indicator`

`services/signal-service/signal_service/application/service.py:562-571`의 이 정적 메서드는 값이
사전이면 그 값들을, 아니면 값 자신을 훑으면서 **셋 중 하나라도 해당하면 예외**를 던진다. 첫째는
`bool`인 경우, 둘째는 `float`도 `int`도 아닌 경우, 셋째는 유한하지 않은 경우다.

**면제는 없다.** `undefined_outputs`를 인자로 받지도 않고 참조하지도 않는다. 이것이 백테스트
Engine과의 실질적 차이이며, 아래 3.2절에서 대조한다.

막는 것을 정리하면, 지표는 **숫자만** 낼 수 있고, `True`/`False`는 파이썬에서 `int`의 하위형이라
그냥 통과할 수 있으므로 **명시적으로 따로 거부**되며, 워밍업이 끝난 뒤에는 NaN도 무한대도 낼 수
없다. 워밍업 구간이 이 검사에 걸리지 않는 이유는 이 서비스가 상태를 미리 seed한 뒤 확정 캔들만
`update`하기 때문이며, 그 지점은 같은 파일 277-281줄이다.

signal-service의 spec 해석에는 짚어 둘 제약이 하나 더 있다.
`services/signal-service/signal_service/application/service.py:130-134`는 `resolve_specs`를
**언제나 `"auto"` 모드로** 부른다. 곧 라이브 경로에는 `explicit`도 `all`도 없고, 전략과 자금관리
정책이 선언한 것만 계산된다. 백테스트에만 있는 세 모드가 라이브에는 없다는 이 비대칭은
5절에서 배치안마다 다시 나온다.

### 3.2 백테스트 Engine이 지표 값을 읽는 방식

Engine은 실행 시작 시점에 `DEFAULT_REGISTRY.resolve_specs`로 spec 목록을 확정하고
(`services/backtest-service/backtest_service/engine/engine.py:366-370`), 각 spec마다 상태를 하나씩
만든 뒤(같은 파일 1700-1703줄), 워밍업 캔들로 seed하고 전부 warm이 되었는지 확인한다
(같은 파일 476-483줄). 그 뒤로는 **증분 경로만** 쓴다. 캔들이 닫힐 때마다
`_update_indicators`(같은 파일 1853-1878줄)가 spec마다 `state.update(candle)`을 부르고, 값을
검사하고, `_indicator_key`로 만든 열쇠에 담고, Evidence에 스냅샷 한 행을 기록한다.

`Engine._assert_finite_indicator`(같은 파일 1880-1904줄)는 signal-service의 같은 이름 메서드와
**두 가지가 다르다.** 첫째, 사전인 경우 값뿐 아니라 **키까지** 함께 훑는다. 둘째, 유한하지 않은
값을 만나면 그 키가 `undefined_outputs`에 이름이 올라 있는지 확인하고, 올라 있으면 통과시킨다.
그래서 Bollinger %B는 밴드가 붕괴한 창에서 NaN인 채로 백테스트를 통과한다.

**여기서 기존의 결함이 하나 드러난다.** 같은 지표가 signal-service에서는 통과하지 못한다.
`Bollinger Bands(period=20,multiplier=2.0)`의 `percent_b`가 완전히 평평한 창에서 NaN이 되는 것은
`services/core-lib/tests/test_indicator_registry.py:315-345`가 명시적으로 확인하는 동작인데,
signal-service의 검사에는 그 면제가 없으므로 라이브 경로에서는 예외가 난다. 이번 작업이 만든
문제가 아니고 이번 작업의 범위도 아니지만, **패턴이 사전 형태의 출력을 내고 그 가운데 일부 키에
면제가 필요해지면 이 비대칭이 곧바로 문제가 된다.**

Evidence 기록에도 계약이 있다.
`services/backtest-service/backtest_service/adapters/evidence_schema.py:269-281`의
`INDICATOR_SNAPSHOT` 테이블은 `value`(실수 하나)와 `value_json`(사전 직렬화) 가운데 **정확히
하나만** 채워져 있을 것을 제약 조건으로 요구한다(같은 파일 279줄). 사전 값을 기록할 때는 NaN을 JSON null로 바꾸는데
(`services/backtest-service/backtest_service/engine/engine.py:1906-1924`), 전략에 넘어가는 메모리
상의 값은 NaN 그대로 유지된다.

행 수는 **등록된 spec 수 곱하기 캔들 수**로 정확히 선형이다. spec마다 캔들마다 한 행이다.

### 3.3 전략이 지표를 읽는 계약

`docs/strategy-authoring-contract.md`의 3.1절이 정한 것은 전략이 **확정된 캔들과 Engine이 전달한
사전 계산 지표만** 쓴다는 것이다. 전략은 stateless이고 같은 입력에서 같은 판단을 낸다. 아직 닫히지
않은 캔들이나 미래 캔들의 참조는 금지되어 있다.

Engine과 signal-service는 둘 다 전략에게 `market_data` 사전을 넘기고, 그 안의 `"indicators"`
키에 지표 값 사전을 담는다
(`services/backtest-service/backtest_service/engine/engine.py:552-560`,
`services/signal-service/signal_service/application/service.py:284-292`). 열쇠는
`IndicatorSpec.identifier`가 아니라 `_indicator_key`가 만든 소문자·밑줄 형태다. 예를 들어
`EMA(period=9)`는 `ema:period=9`가 된다
(`services/backtest-service/backtest_service/engine/engine.py:1926-1932`).

전략이 그 값을 읽는 모습은
`services/core-lib/core_lib/strategy/adaptees/vessel_reference.py:136-141`에 있다. 사전에서 열쇠로
꺼낸 뒤 **`bool`이면 거부하고 `float`이나 `int`가 아니면 거부한 다음 `float`으로 변환**한다.
소비 쪽 세 계층이 모두 같은 형태로 `bool`을 거부하고 있다는 뜻이다.

3.4절은 전략이 요구하는 지표와 자금관리 정책이 요구하는 지표를 합집합으로 합치고 가장 긴
워밍업을 적용한다고 정하고, 3.7절은 등록된 조합만 선언할 수 있다고 정한다.

### 3.4 전략 선언과 카탈로그 대조의 현재 계약

이번 보강에서 가장 중요한 사실이 여기 있다. **지금 계약에는 전략이 패턴을 선언할 자리가 없다.**

`services/core-lib/core_lib/strategy/base.py:31-47`의 `StrategyMetadata`가 가진 필드는
`required_indicators`, `min_history`, `supported_timeframes`, `profile`, `money_management`
다섯이다. `required_indicators`의 타입은 `list[dict[str, object]]`이고 `__post_init__`은
`[dict(item) for item in ...]`로 얕게 복사할 뿐이므로 **항목의 키 구성을 제약하지 않는다.**

그 선언은 두 곳에서 소비된다.

첫째는 `AdapterManager._validate_declared_history`
(`services/core-lib/core_lib/strategy/manager.py:116-154`)의 카탈로그 대조다. 외부 카탈로그의
`min_history`, `supported_timeframes`, `required_indicators_json`을 코드의 선언과 맞대고 어긋나면
실행을 거부한다. 어느 쪽이 낡았는지 구현이 판단할 수 없으므로 조용히 한쪽을 택하지 않는다는 것이
그 함수 docstring의 설명이다. 지표 목록의 비교는 `_indicator_identities`
(같은 파일 15-27줄)가 맡는데, **`name`과 `params`만 읽고 나머지 키는 무시하며 순서와 키 순서도
무시한다.** 카탈로그 항목이 `None`이면 비교 자체를 건너뛴다(같은 파일 146-147줄).

카탈로그 쪽 스키마는 `init-scripts/signal-service/20260724/01-redefine-strategy-registry.sql:150`의
`required_indicators_json JSONB NOT NULL DEFAULT '[]'::jsonb`이고, 제약은 같은 파일 164-166줄의
`jsonb_typeof(required_indicators_json) = 'array'` 하나뿐이다. **배열 안 객체의 키 구성은 데이터베이스가
제약하지 않는다.**

이 두 사실을 합치면 좁은 결론이 하나 나온다. **선언 항목에 판별자 키를 하나 더 붙여도 데이터베이스
제약과 현재 대조 로직은 변경 없이 통과한다.** 다만 1.4절이 적은 대로 `_descriptor_spec`이 키
집합을 정확히 `{"name", "params"}`로 요구하므로, 엔진이 레지스트리에 넘기기 전에 목록을 갈라
판별자를 떼어 내야 한다.

#### 3.4.1 그러나 그 통과는 장점이 아니라 계약 결함이다

2판은 위 문장을 "고치지 않고 쓸 수 있다"는 장점으로 적었다. **그것은 틀렸고, 2차 검토의 지적이
옳다.** 지금 대조가 판별자를 무시한다는 사실은 통과를 뜻하는 동시에 **대조가 해야 할 일을 하지
않는다**는 뜻이다.

구체적으로 이렇다. 전략 코드가 `{"name": "Engulfing", "params": {}, "kind": "pattern"}`을
선언하고 카탈로그가 `{"name": "Engulfing", "params": {}, "kind": "indicator"}`를 담고 있다고
하자. `_indicator_identities`(`services/core-lib/core_lib/strategy/manager.py:15-27`)는 `name`과
`params`만 읽어 신원 튜플을 만들므로 **두 항목을 같다고 판정하고 실행이 통과한다.** 그런데 그
판별자는 어느 레지스트리에서 그 요구를 해석할지를 결정한다. 곧 **판별자가 다르면 실행 의미가
다르다.** 실행 의미를 바꾸는 값이 신원 비교에서 빠져 있으므로, 지금 대조는
`docs/strategy-authoring-contract.md` 3.6절이 정한 계약, 곧 **전략 선언이 원본이고 등록은 그
사본이며 어긋나면 실행을 거부한다**는 계약을 보존하지 못한다.

**따라서 판별자 방식을 쓰는 배치안은 대조 로직을 함께 고쳐야 하고, 그 비용을 자기 몫으로
계상해야 한다.** 고치는 방법은 하나다. **`_indicator_identities`가 만드는 신원 튜플에 판별자를
포함시킨다.** 지금 튜플은 `(name, sorted(params.items()))`이므로 여기에 종류를 더해
`(kind, name, sorted(params.items()))`로 만들고, 판별자가 없는 항목은 기존 뜻이 유지되도록
`"indicator"`로 읽는다. 판별자 없는 기존 선언과 기존 카탈로그 행은 양쪽 모두 `"indicator"`로
읽히므로 **비교 결과가 지금과 같고 기존 전략은 영향을 받지 않는다.**

이 수정에는 짚어 둘 점이 둘 있다. 첫째, `_indicator_identities`는 core-lib 안의 모듈 수준 함수이고
`_validate_declared_history`에서만 쓰이므로 **변경 범위가 좁다.** 둘째, 그럼에도 이것은 **기존 전략
등록 경로의 동작을 바꾸는 변경**이므로 7절 불변식 22번이 걸리고, 판별자 없는 기존 데이터가 계속
통과한다는 것을 회귀로 확인해야 한다.

**정리하면, 판별자 방식의 실제 비용은 "카탈로그 DDL 변경 없음, 대조 로직 변경 있음"이다.** 2판이
"둘 다 변경 없음"이라고 적은 것을 이렇게 고친다.

둘째 소비처는 실행 시점의 spec 해석과 워밍업 계산이다. 백테스트 Engine은
`services/backtest-service/backtest_service/engine/engine.py:362-384`에서 전략 선언과 자금관리
정책의 지표 요구를 이어 붙인 뒤 **오직 `DEFAULT_REGISTRY`로** 해석하고,
`longest_indicator_history = max(spec.min_history for spec in self._indicator_specs)`도 그
레지스트리에서만 나온다. signal-service는
`services/signal-service/signal_service/application/service.py:118-138`에서 같은 일을 주입된 단일
레지스트리로 한다.

곧 **두 번째 레지스트리를 그냥 만들어 두기만 하면, 전략이 패턴을 선언할 경로도 패턴이 워밍업에
반영될 경로도 없다.** 이것이 1판 추천안이 답하지 못한 지점이고, 5절이 배치안마다 답해야 하는
다섯 질문의 출발점이다.

세 번째 소비처도 있다. 웹 API가 전략 목록을 낼 때 `required_indicators`를 그대로 실어 보낸다
(`services/web-api/web_api/repository.py:529-538`, `services/web-api/web_api/models.py:894`).
따라서 선언의 모양을 바꾸면 API 응답 모양과 생성된 프런트 타입이 함께 움직인다.

### 3.5 판정 결과를 나르는 값이 이 경로에 들어오면 무엇이 깨지는가

**먼저 확정된 제약 다섯을 적는다.** 이것들은 표현 선택과 무관하게 어떤 표현이든 만족해야 한다.

첫째, **`bool`로는 나를 수 없다.** 세 계층
(`services/backtest-service/backtest_service/engine/engine.py:1898`,
`services/signal-service/signal_service/application/service.py:566`,
`services/core-lib/core_lib/strategy/adaptees/vessel_reference.py:139`)이 모두 `bool`을 명시적으로
거부한다. 값은 `float`이나 `int`여야 한다.

둘째, **`IndicatorValue`가 나를 수 있는 모양은 `float` 하나 또는 `dict[str, float]` 하나뿐이다**
(`services/core-lib/core_lib/indicators/registry.py:15`). 중첩 사전도, 문자열도, 튜플도 안 된다.

셋째, **워밍업의 NaN 처리는 패턴에도 그대로 적용되고, 그래야 한다.** `Fractals`가 그 본보기다.
창이 다 차기 전에는 `{"up": NaN, "down": NaN}`을 내고, `warmed_up`은 값에 NaN이 없는지로 정의된다
(`services/core-lib/core_lib/indicators/systems.py:715-717`). 창이 차면 값은 반드시 확정되므로
정확히 `min_history` 지점에서 warm이 된다. **0.0("판정했고 불성립")과 NaN("아직 판정할 수 없음")은
서로 다른 뜻이고, 이 구분을 흐리면 워밍업 단언이 곧바로 깨진다.**

넷째, **워밍업 이후의 NaN은 사실상 금지다.** 단일 숫자를 내는 출력은 `undefined_outputs` 면제를
쓸 수 없고, 사전을 내더라도 signal-service 쪽에는 면제 자체가 없다.

다섯째, **모든 등록 spec은 평가 봉마다 반드시 값을 낸다.** Evidence 완결성 검사
(`services/backtest-service/backtest_service/adapters/evidence_sink.py:719-745`)가 등록된 모든
`indicator_key`에 대해 `is_warmup = 0`인 스냅샷의 `feature_ts` 목록이 포트폴리오 봉 격자와
**정확히 같을 것**을 요구한다. 그러므로 "패턴이 성립한 봉에만 값을 낸다"는 희소 이벤트 표현은
구조적으로 불가능하다. 3.6절에서 다시 다룬다.

#### 3.5.1 출력 표현 후보를 다섯 축으로 평가한다

**여기서 어느 표현을 쓸지 결론짓지 않는다.** 출력 표현은 원전 조사가 결정 9(반환 값의 표현)와
결정 10(확인 시점 정렬)으로 사용자에게 올려 둔 항목이다. 1판이 그것을 앞질러 1.0과 0.0으로
확정한 것이 교차 검토가 지적한 Blocking 5이고, 2판은 표현마다 제약을 재는 데서 멈춘다.

보존해야 할 정보가 무엇인지부터 적는다. 원전 조사가 TA-Lib 관찰에서 확인한 값의 합집합은
`-200, -100, -80, 0, 80, 100, 200` 일곱이고, 뜻은 이렇게 갈린다. 0은 불성립, ±100은 통상 성립이며
부호가 강세와 약세를 가르고, ±80은 Engulfing·Harami·Harami Cross 세 함수에서만 나오는 **경계에
걸친 약한 성립**이며, ±200은 Hikkake 두 함수에서만 나오는 **확인까지 끝난 성립**이다. 그리고
`CDLDOJI`처럼 0과 +100만 내는 함수에서 +100의 부호는 방향이 아니라 그저 성립을 뜻한다. 곧
보존 대상은 **성립 여부, 방향, 경계 강도, 확인 단계** 넷이고 그중 방향은 패턴에 따라 뜻이 없다.

| 표현 후보 | `IndicatorValue` 손실 여부 | Evidence | 워밍업 NaN 규약 | 웹 화면 | TA-Lib 대조 변환 |
|---|---|---|---|---|---|
| 가. TA-Lib 표기 그대로 실수 하나 (−200…200) | 손실 없음. `float` 하나에 일곱 값이 그대로 들어간다 | `value` 한 칸. 완결성 검사도 만족 | 충돌하지 않는다. 워밍업만 NaN, 그 뒤로는 언제나 일곱 값 중 하나 | 가격 축 `LineSeries`에 그려져 사실상 못 읽는다. 별도 축이나 마커가 필요 | 0회. 단 TA-Lib 래퍼는 워밍업도 0으로 채우므로 대조 시 앞 구간을 잘라야 한다 |
| 나. 성립과 방향 두 키 (`present`, `direction`) | **손실 있음.** ±80과 ±200을 담을 자리가 없다 | `value_json` | 두 키 모두 NaN으로 통일 가능 | `value`가 비므로 **아예 그려지지 않는다** | 1회. 다만 되돌릴 수 없어 왕복 대조가 안 된다 |
| 다. 성립·방향·강도·확인 네 키 | 손실 없음. 네 축이 각각 자기 키를 갖는다 | `value_json` | 네 키 모두 NaN | 그려지지 않는다 | 1회이고 가역이다. 등록 출력 키가 패턴당 4개라 `REFERENCE` 표 항목이 네 배가 된다 |
| 라. 패턴마다 필요한 키만 (방향 없는 패턴은 방향 키를 내지 않음) | 손실 없음이고 뜻이 가장 정확하다 | `value_json` | 키 집합이 패턴마다 달라 워밍업 모양도 패턴마다 다르다 | 그려지지 않는다 | 1회. 소비자와 대조 코드가 키 유무를 분기해야 한다 |
| 마. 방향별로 등록을 쪼갠다 (강세형과 약세형을 별도 identifier, 각 실수 하나) | 손실 있음. 강도와 확인 단계가 남는다 | `value` 한 칸 | 문제 없다 | 여전히 선으로 그려진다 | 1회. 등록 조합 수가 늘어 61종이 최대 88 조합쯤 된다 |

**표에서 읽어야 할 것은 셋이다.** 첫째, 정보를 온전히 보존하는 후보는 가, 다, 라 셋이다. 둘째,
**웹 화면이 그릴 수 있는 후보는 지금 코드로는 하나도 없다.** 실수 하나를 내면 가격 축에 붙은
평평한 선이 되고, 사전을 내면 `value`가 비어 건너뛰어진다
(`apps/web/src/components/evidence/chart-tab.tsx:157-170`). 어느 표현을 고르든 화면 쪽 작업이
따로 필요하다는 뜻이며, 이는 표현 선택의 판단 근거가 되지 못한다. 셋째, **`CONVERGING` 대조는
어느 후보에도 쓸 수 없다.** 그 표의 단언은 "간격이 줄어들기만 해야 한다"인데
(`services/core-lib/tests/test_indicator_reference_values.py:54-71`), 이산값 계열에서는 간격이
줄어드는 과정이라는 것이 없다. 패턴은 `REFERENCE`(정확히 일치)나 `UNCOMPARED`(대조 대상 없음)
둘 중 하나로만 다뤄야 한다.

**확인 시점(원전 조사 결정 10)과의 상호작용도 표현 선택에 걸린다.** 3.5절 다섯째 제약 때문에
확인 대기 중인 봉에도 값을 내야 하고, 넷째 제약 때문에 그 값이 NaN일 수 없다.

**다만 여기서 2판이 한 걸음 더 나간 것은 잘못이었다.** 2판은 그로부터 "확인 대기를 뜻하는 별도
숫자가 반드시 있어야 한다"고 결론지었으나, **그 결론은 나오지 않는다.** 확인되기 전에는 불성립을
뜻하는 값을 계속 내고 확인된 봉에서만 성립값을 내는 계약도 매 봉 유한값과 Evidence 완결성을 똑같이
만족한다. 그 계약에서 확인 대기는 소비자에게 보이지 않을 뿐이고, 행이 빠지지도 NaN이 나오지도
않는다.

**정확히 말하면 이렇다.** 행을 생략할 수 없다는 사실이 강제하는 것은 **매 평가 봉에 유한한 값이
있어야 한다**는 것 하나뿐이다. 대기 상태를 소비자에게 **노출할지 말지**는 그와 별개이며, 원전 조사
결정 9(반환 값의 표현)와 결정 10(확인 시점 정렬)의 결과다. 후보 가와 다는 대기를 노출할 자리를
이미 갖고 있고(가는 ±100과 ±200의 구별, 다는 `confirmed` 키), 후보 나와 마는 갖고 있지 않지만
**갖고 있지 않다는 것이 그 후보를 탈락시키지는 않는다.** 노출하지 않는 쪽을 고르면 확인 전 봉은
불성립으로 기록될 뿐이다.

이 구별은 4.3.4절에서 다시 쓰인다. 대기를 노출하는 표현과 노출하지 않는 표현은 `min_history`를
**같은 값으로 둔다.** 값을 다르게 만드는 표현은 확인된 사건만 출력하고 그 전에는 값 자체를 정의하지
않는 것뿐인데, 그것은 매 봉 유한값 요구를 만족하지 못해 4판에서 후보에서 제거했다. **곧 실행
가능한 표현들 사이에서는 `min_history`가 표현 선택과 무관하다.**

### 3.6 Evidence 쪽 두 문제

#### 3.6.1 표준 출처가 boolean으로 눌려 복원되지 않는다

`IndicatorSpec.pinned_impl`은 계산 표준의 절을 적은 문자열이지만, Engine은 Evidence에 그 문자열을
쓰지 않고 `"pinned_impl": True`라는 boolean만 기록한다
(`services/backtest-service/backtest_service/engine/engine.py:1845`). 스키마도 그것만 허용한다
(`services/backtest-service/backtest_service/adapters/evidence_schema.py:262`의
`pinned_impl INTEGER NOT NULL CHECK (pinned_impl IN (0, 1))`).

**따라서 패턴 spec이 패턴 표준의 절을 인용하더라도, 실행 기록만 보고는 그것이 어느 표준의 어느
절이었는지 복원되지 않는다.** 이 문제는 어느 배치안을 고르든 남는다. 지표와 패턴이 서로 다른
표준을 인용하게 되는 순간, 실행 기록에서 둘을 가를 수 없다는 것이 더 아프게 드러날 뿐이다.

처리할 수 있는 방법이 넷 있고 각각 값이 다르다.

**첫째, `INDICATOR_DEFINITION`에 출처 문자열 칸을 하나 더한다.** 예를 들어 `pinned_impl_ref TEXT`를
두고 spec의 문자열을 그대로 쓴다. 가장 정직하고, 기존 boolean 칸은 "고정 여부"라는 원래 뜻으로
남는다. 대가는 스키마 변경이며, 이미 만들어진 실행 Evidence 파일과의 호환을 함께 봐야 한다.

**둘째, `impl_version`에 표준 식별자를 얹는다.** 예를 들어 `"1.0.0+cdl-spec§2.3"`처럼 쓴다. 칸을
더하지 않고도 복원할 수 있다. 대가는 버전 문자열의 뜻이 흐려지는 것이고, 그 칸을 읽는 쪽이 파싱을
하게 된다.

**셋째, 실행 시작 시점에 별도 Evidence 레코드 타입을 하나 더 기록한다.** `INDICATOR_DEFINITION`을
건드리지 않고 출처만 따로 남기는 방식이다. 대가는 테이블이 하나 늘고 완결성 검사에 그 테이블을
어떻게 걸지 정해야 한다는 것이다.

**넷째, 아무것도 하지 않고 출처는 코드와 표준 문서에만 남긴다.** 지금 상태다. 대가는 실행 기록의
자기완결성을 포기하는 것이며, 재현성을 근거로 삼는 이 저장소의 성격과 어긋난다.

**판단.** 첫째가 가장 정직하다. 다만 이 개선은 **지표에도 똑같이 적용되는 것**이므로 패턴 작업에
끼워 넣지 말고 별도의 bounded changeset으로 다루는 편이 맞다. 패턴 작업 안에서는 "출처가 기록되지
않는다"는 사실을 알고 설계하되 고치지 않는 쪽이 변경 경계를 지킨다.

#### 3.6.2 완결성 검사가 행 생략을 금지한다

`services/backtest-service/backtest_service/adapters/evidence_sink.py:719-745`의 `_indicator_failures`
는 `INDICATOR_DEFINITION`의 모든 `indicator_key`에 대해, `is_warmup = 0`인 스냅샷의 `feature_ts`
목록이 포트폴리오 봉 격자와 **리스트 그대로 같을 것**을 요구한다. 하나라도 빠지면
`indicator_grid_mismatch`로 실행이 불완전으로 판정된다. 그리고 Engine은 스냅샷을 언제나
`"is_warmup": False`로 기록하므로
(`services/backtest-service/backtest_service/engine/engine.py:1874`) 이 검사를 피해 갈 여지도 없다.

**이것이 강제하는 것은 셋이다.**

첫째, **패턴은 평가 봉마다 반드시 한 행을 낸다.** 성립한 봉에만 값을 내는 희소 표현은 불가능하고,
3.5.1절의 다섯 후보가 모두 "매 봉 값을 내는" 모양인 것은 우연이 아니라 이 제약의 결과다.

둘째, **확인이 끝나야 값이 정해지는 패턴도 확인 전 봉에 유한한 숫자를 내야 한다.** 그 값은 NaN일
수 없다(3.5절 넷째 제약). **다만 그 숫자가 "확인 대기"라는 별도 상태여야 하는 것은 아니다.**
확인 전에는 불성립 값을 계속 내다가 확인된 봉에서만 성립값을 내는 계약도 이 요구를 그대로
만족한다. 대기 상태를 노출할지는 출력 표현 결정의 결과이지 이 제약의 결과가 아니다. 2판이 이
자리에서 별도 대기 숫자가 필수라고 쓴 것은 출력 선택을 다시 앞지른 것이었다.

셋째, **패턴이 별도 테이블을 쓰기로 하면 이 검사를 그 테이블까지 넓혀야 한다.** 넓히지 않으면
패턴 값이 통째로 빠져도 실행이 완전으로 판정된다. 5절의 배치안 C와 D에서 이 항목이 비용으로
계상된다.

#### 3.6.3 결합 실행에서 종류 신원이 사라진다

3판은 이 자리에 "이름 충돌을 막아야 한다"는 한 문단만 두었다. **그것으로는 부족하다.** 3차 검토가
지적한 대로, 카탈로그 대조를 `(kind, name, params)`로 고쳐도 **실행 단계에서 종류가 다시 사라진다.**
문제를 코드로 정확히 적는다.

**종류가 기록되지 않는 자리가 넷이다.** 첫째, Engine은 상태를 `spec.identifier`를 열쇠로 삼는
사전에 담는데(`services/backtest-service/backtest_service/engine/engine.py:1700-1703`),
`identifier`는 `name`과 `params`만으로 만들어진다
(`services/core-lib/core_lib/indicators/registry.py:80-86`). 둘째, `_indicator_key`도 `name`과
`params`만 읽는다(`services/backtest-service/backtest_service/engine/engine.py:1926-1932`). 셋째,
`resolved_indicators_json`은 `name`과 `params`와 `version` 셋만 담는다(같은 파일 416-423줄).
넷째, `INDICATOR_DEFINITION`에 기록되는 것도 같은 셋이고 종류 칸이 없다(같은 파일 1835-1849줄).
signal-service의 열쇠 생성도 같은 방식이다
(`services/signal-service/signal_service/application/service.py:573-580`).

**따라서 이름과 파라미터가 같은 지표와 패턴이 생기면 이렇게 된다.** 카탈로그 대조는 종류가 다르다고
보아 통과시키지만, 실행 단계에서는 `identifier`가 같아 **상태 사전에서 하나가 다른 하나를 덮어쓰고**,
`INDICATOR_DEFINITION.indicator_key`가 기본 키이므로
(`services/backtest-service/backtest_service/adapters/evidence_schema.py:257`) **두 번째 삽입이
실패한다.** 곧 대조 단계와 실행 단계가 서로 다른 신원 개념을 쓴다.

이것은 지금 당장의 결함이 아니라 **결합 실행을 도입하는 순간 생기는 결함**이다. 지금은 레지스트리가
하나뿐이라 같은 `identifier`가 두 번 등록되는 것을 `IndicatorRegistry.register`가 막는다
(`services/core-lib/core_lib/indicators/registry.py:117-122`). 레지스트리를 둘로 나누면 그 방어가
사라진다. **배치안 B와 D처럼 두 레지스트리의 결과를 한 목록으로 합치는 안은 모두 이 문제를 안는다.**

**해결 갈래가 둘 있고 비용이 다르다. 어느 신원 규약을 채택할지는 사용자 결정이다.**

**갈래 하나. 종류를 실행 신원에 포함한다.** `identifier`와 `_indicator_key`와 실행 메타데이터와
Evidence에 종류를 넣는다. 구체적으로는 `PatternSpec.identifier`가 접두사를 갖도록 만들고
(예를 들어 `cdl:Engulfing()` 형태), `_indicator_key`가 그 접두사를 반영하며,
`resolved_indicators_json`과 `INDICATOR_DEFINITION`에 종류 칸을 더한다.

- **얻는 것.** 대조 신원과 실행 신원이 같아지고, 이름이 겹쳐도 충돌하지 않으며, 실행 기록만 보고
  어느 종류였는지 복원된다. **3.6.1절의 출처 기록 문제와도 같은 방향이다.**
- **비용.** `resolved_indicators_json`의 모양이 바뀌므로 **`config_hash`가 달라진다.**
  `config_hash`는 `resolved_indicators_json`을 포함한 `_run_meta` 전체에서 계산되므로
  (`services/backtest-service/backtest_service/engine/engine.py:454`), 종류 칸을 무조건 더하면
  **패턴을 켜지 않은 기존 실행의 해시까지 달라져 7절 불변식 19번을 깬다.** 그러므로 기존 지표
  항목에는 칸을 더하지 않고 패턴 항목에만 더하거나, 종류가 `indicator`인 경우를 직렬화에서
  생략하는 형태여야 한다. 여기에 `INDICATOR_DEFINITION` 스키마 변경과 기존 Evidence 파일과의
  호환 확인이 따라온다.

**갈래 둘. 이름 공간의 비중복을 계약으로 강제한다.** 종류를 신원에 넣지 않는 대신, **패턴 이름이
지표 이름과 절대 겹치지 않는다**는 것을 검증으로 못 박는다. 두 레지스트리의 이름 집합이 서로소인지
확인하는 단언 하나를 두면 되고, 정규화 후의 열쇠까지 비교해야 한다. `_indicator_key`가 소문자와
밑줄로 정규화하므로 `Three Outside`와 `three-outside`가 같은 열쇠로 접히기 때문이다.

- **얻는 것.** 실행 경로와 Evidence 스키마와 `config_hash`를 **한 글자도 건드리지 않는다.**
  불변식 19번이 저절로 지켜진다.
- **비용.** 신원이 이름에 실리므로 **패턴과 지표가 같은 개념 이름을 쓸 수 없다.** 실제로 걸릴
  자리가 있다. TA-Lib의 CDL 계열에 `Doji`가 있고 우리 지표 쪽에는 아직 없지만, 표준 6.2절의
  `Fractals`처럼 패턴 성격의 것이 이미 지표 레지스트리에 등록되어 있으므로 앞으로 겹칠 여지가
  남는다. 또한 실행 기록에서 종류가 여전히 복원되지 않으므로 3.6.1절의 문제가 그대로 남는다.

**판단.** 갈래 둘이 이번 작업의 변경 경계를 훨씬 잘 지킨다. 실행 경로와 해시를 건드리지 않으므로
"패턴을 켜지 않은 기존 실행이 그대로"라는 불변식을 증명할 필요조차 없다. 갈래 하나는 더 정직하지만
`config_hash`를 건드릴 위험이 있어 별도의 bounded changeset이 되어야 하고, 그렇다면 3.6.1절의 출처
기록 개선과 묶어서 한 번에 다루는 편이 낫다. **다만 고르는 것은 사용자의 몫이므로 여기서 정하지
않는다.**

### 3.7 그 밖에 연속량을 가정한 자리와, 깨지지 않는 것

**연속량을 가정한 자리가 셋 있다.** 웹 차트가 지표를 가격 축의 선으로 그리고 `value`가 `null`인
행을 건너뛴다는 것(3.5.1절), `CONVERGING` 대조가 "간격이 줄어든다"는 형태라는 것(같은 절), 그리고
자금관리 경로가 `atr:period=14`를 이름으로 꺼내 변동성 척도로 쓴다는 것
(`services/backtest-service/backtest_service/engine/engine.py:1074-1078`)이다. 마지막 것은 특정
지표를 이름으로 지목하므로 패턴이 끼어들 여지가 없지만, 지표 사전이 "숫자를 재는 것들의 모음"이라는
전제로 쓰이는 자리라는 점은 기록해 둔다.

**Evidence 부피가 spec 수에 정비례한다.** 패턴을 같은 실행에 켜면 캔들마다 패턴 수만큼 스냅샷
행이 더 쌓이고, 화면은 그 행들을 200행 커서로 읽어 들인다
(`apps/web/src/hooks/use-evidence.ts:332-344`). 정확성이 깨지는 문제는 아니지만 `all` 모드의 뜻이
조용히 달라지는 자리다.

**깨지지 않는 것도 분명히 해 둔다.** Evidence 스키마의 값 칸은 그대로 쓸 수 있다. `_indicator_key`의
이름 정규화도 패턴 이름에 그대로 작동한다. 전략이 값을 읽는 방식도 바뀌지 않는다. 판정값이 결국
`float`이면 3.1절의 "확정 캔들과 사전 계산 지표만 쓴다"는 규칙 안에 그대로 들어온다. 바뀌어야
하는 것은 값의 모양이 아니라 **선언과 워밍업의 경로**이고, 그것이 5절의 주제다.

---

## 4. 두 경로 요구가 패턴에도 성립하는가

### 4.1 성립한다. 다만 "같은 함수를 쓰니 어긋날 데가 없다"는 것은 과장이다

캔들스틱 패턴은 최근 몇 봉의 시가·고가·저가·종가를 읽어 모양을 판정하는 것이고, 창의 길이는
패턴마다 고정된 상수다. 배치 함수는 인덱스마다 그 창을 잘라 판정하면 되고, 증분 상태는 같은
길이의 `deque`를 들고 캔들이 올 때마다 밀어 넣은 뒤 같은 판정 함수를 부르면 된다. `Fractals`가
정확히 그 구조로 되어 있다. 판정 자체는 `_fractal_flags`
(`services/core-lib/core_lib/indicators/systems.py:672-679`) 하나이고, 배치 함수(같은 파일
682-697줄)는 인덱스마다 창을 잘라 그것을 부르며, 상태(같은 파일 700-734줄)는
`deque(maxlen=period)`에 밀어 넣고 같은 함수를 부른다.

**그러나 1판이 "값이 어긋날 자리가 없다"고 쓴 것은 과장이었다.** 순수 판정 함수를 공유하면 판정
규칙 자체의 불일치는 사라지지만, 두 경로는 여전히 네 곳에서 어긋날 수 있다. 창을 자르는 인덱스가
한 칸 다를 수 있고, `seed`가 상태를 비우고 다시 채우는 순서가 배치의 누적 순서와 다를 수 있으며,
참조하는 평균의 갱신 시점이 판정 시점과 어긋날 수 있고, 확인 지연 패턴에서 발표를 늦추는 봉 수가
두 경로에서 다를 수 있다.

**게다가 공유를 지나치게 넓히면 안 된다.** `compute_batch`는
`services/core-lib/core_lib/indicators/registry.py:193-196`에서 증분 구현의 **독립 parity oracle**로
명시되어 있다. 두 경로가 같은 코드를 너무 많이 공유하면 같은 수식 오류가 두 경로를 나란히 통과해
동일성 검사가 아무것도 잡지 못한다. 그래서 공유는 **순수 predicate까지로 한정**하고, 값의 정확성은
원전이 적은 예제와 절이 따로 적은 관계 단언으로 따로 확인해야 한다. 이는 기존 지표가 2.4절의
"절별 관계 단언"으로 이미 하고 있는 일과 같은 구조다.

### 4.2 상수 시간은 조건부다 — 척도마다 상태·갱신식·보관량·작업 수

1판은 `FractalsState`를 근거로 상수 시간이 성립한다고 썼으나, 그 클래스는 스스로
`"O(period)-per-candle fractal state"`라고 적고 창 전체를 리스트로 만들어 순회한다
(`services/core-lib/core_lib/indicators/systems.py:700-730`). **계열 길이에 대해 선형인 것과
기간에 대해 상수인 것은 다른 진술이다.** 갈라서 다시 적는다.

먼저 두 진술을 이름 붙여 구별한다. **계열 선형**은 전체 실행 시간이 캔들 수에 비례한다는 뜻이고,
**기간 상수**는 캔들 하나를 처리하는 비용이 등록 파라미터인 기간에 의존하지 않는다는 뜻이다.
`FractalsState`는 앞은 만족하고 뒤는 만족하지 않는다.

캔들스틱 패턴에서는 이 구별이 한 겹 더 갈린다. **패턴이 걸치는 봉 수는 등록 파라미터가 아니라
패턴 정의가 고정한 상수**다. Doji는 언제나 1봉이고 Engulfing은 언제나 2봉이며 Morning Star는
언제나 3봉이다. 반면 "길다·짧다"를 재는 평균 창의 길이는 파라미터가 될 수 있다. 그래서 아래
표에서 첫 줄만 성격이 다르다.

2차 검토가 지적한 대로 2판이 이 봉 수를 "2봉에서 5봉"이라고 적은 것은 **단일 봉 패턴을
빠뜨렸다.** 그래서 아래 표는 `k`의 하한을 1봉으로 잡는다.

**`k`의 상한은 패턴 하나에 달려 있고, 그 패턴에도 유한한 후보만 남았다.** 두 걸음으로 적는다.

**첫째, Breakaway는 고정 다섯 봉이다.** 3판은 Morris가 Breakaway의 갭 뒤 봉 수를 둘 이상으로
열어 둔 유연성 절(`morris_cce.txt` 5065-5070줄)을 근거로 가변 길이 줄을 따로 두었으나, **그것은
원전 조사의 결정 C와 어긋난다.** 결정 C는 Morris 내부에서 규칙 절이 규범이고 유연성 절은 주석이라고
확정했고, Breakaway의 규칙 절(`morris_cce.txt` 5044줄)은 **고정 다섯 봉**이다. 그러므로 Breakaway는
다섯 봉짜리 고정 길이 패턴이며, 3판의 가변 길이 줄과 상한 결정 항목은 4판에서 지웠다.

**둘째, Rise and Fall Three Methods만 봉 수가 아직 확정되지 않았고 그 후보가 둘이다.** 4판은 이
패턴을 빠뜨린 채 `k`의 상한을 5로 단언했으나, 4차 검토가 지적한 대로 그것은 성급했다. Morris의
규칙 2는 긴 캔들 뒤에 오는 것을 "작은 실체 캔들 **무리**"라고만 적고 개수를 못박지 않는다
(`morris_cce.txt` 7055줄). 곧 이 패턴의 봉 수는 **긴 캔들 하나와 작은 캔들 `m`개와 마지막 강한
날 하나를 더한 `k = m + 2`**이고, `m`이 확정되지 않았다.

**다만 `m`의 후보는 둘 다 유한하다.** Nison 2판 7장이 이상적인 개수를 셋이라고 하면서 둘이나 셋보다
많은 경우도 허용하고 경험상 **둘에서 다섯까지** 잘 작동한다고 적기 때문이다. 그러므로 원전 근거가
있는 후보는 **고정 세 봉**과 **둘에서 다섯까지의 유한 범위** 둘뿐이고, 상한 없는 선택지는 원전에
근거가 없다. 두 후보에서 값이 이렇게 갈린다.

| 후보 | `m` | `k` | `min_history` | 모양 상태 보관량 | 추세 큐 길이 |
|---|---|---|---|---|---|
| 고정 세 봉 | 3 | 5 | `max(5, N + 5, P + 4) = 15` | `5 × 4 = 20` 실수 | 5 |
| 유한 범위 | 2에서 5 | 4에서 7 | `max(7, N + 7, P + 6) = 17` | `7 × 4 = 28` 실수 | 7 |

`N = P = 10`으로 계산했고, 식은 4.3.2절의 `min_history = max(k, N + k, P + k - 1)`을 그대로 썼다.
이 패턴은 긴실체와 짧은실체 척도를 모두 쓰고 추세도 요구하므로 세 항이 다 걸린다.

**유한 범위 후보에서는 `k`의 상한이 5가 아니라 7이 되므로 그 값을 아래 표에 반영했다.** 곧 표의
`k` 범위는 고정 세 봉을 고르면 1에서 5, 유한 범위를 고르면 1에서 7이다.

**범위 후보에서 `min_history`를 가장 긴 형태로 잡는 이유를 적어 둔다.** `m`이 2에서 5 사이면 짧은
형태는 더 이른 봉에서 판정할 수 있지만, 그 봉에서 낸 값은 "검사할 수 있었던 형태 가운데 성립하는
것이 없다"는 뜻이고 그보다 뒤의 봉에서 낸 값은 "모든 허용 형태 가운데 성립하는 것이 없다"는 뜻이라
**두 값의 의미가 달라진다.** 값의 뜻이 봉마다 달라지면 소비하는 쪽이 그 차이를 알 수 없으므로,
가장 긴 형태를 기준으로 삼아 모든 발표 값이 같은 뜻을 갖게 한다. 짧은 형태부터 발표하는 반대
규약도 가능하지만, 그것을 고르면 표준이 "인덱스 몇까지는 어떤 형태만 검사했다"를 문장으로 적어야
하고 소비자가 그 구간을 다르게 읽어야 한다.

**두 후보 가운데 무엇을 채택할지는 표준 문서를 쓰면서 사용자가 정한다.** 이 문서가 확인한 것은
**어느 쪽을 골라도 값이 유한하다**는 것이고, 그것이 아래 표의 결론을 지탱한다.

**이 두 걸음으로 상태 보관량에 상한이 없는 패턴은 하나도 남지 않는다.** Breakaway는 다섯으로
확정되었고, Rise and Fall Three Methods는 후보가 둘 다 유한하다.

**사용자가 2026-08-01에 확정한 추세 판정 방식이 이 표를 바꾼다.** 직전 추세를 패턴이 직접
판정하고, 그 판정은 Morris의 10기간 지수이동평균을 쓴다. 곧 추세를 요구하는 패턴의 상태는
`EmaState(10)`을 **안에 들고 있어야 한다.** 이는 프리미티브를 다시 구현하지 않는다는 저장소
규칙에 그대로 맞고, 갱신 비용도 상수다.

**여기에 3판이 빠뜨린 것이 하나 있다.** Morris의 예시는 **패턴 첫날의 범위 중간값을 그 시점의
10기간 지수이동평균과 비교**한다. 패턴 첫날은 판정 시점보다 `k - 1`봉 앞이므로, 상태가 **현재
지수이동평균 값 하나만 들고 있으면 그 비교를 할 수 없다.** 판정 시점의 이동평균이 아니라 `k - 1`봉
전의 이동평균이 필요하기 때문이다. 그러므로 패턴 상태는 `EmaState(10)`에 더해 **최근 `k`개의
이동평균 값을 담은 짧은 큐**를 함께 들어야 한다. `k`가 최대 5이므로 이것도 상수 보관이고 캔들당
작업 수도 상수다. 3판의 복잡도 표는 최근 시가·고가·저가·종가와 현재 지수이동평균 상태만 적어
이 큐가 빠져 있었다.

| 척도 | 상태 | 갱신식 | 보관량 | 캔들당 작업 수 |
|---|---|---|---|---|
| 고정 길이 모양 비교 (1봉에서 5봉, Rise and Fall Three Methods가 유한 범위로 정해지면 7봉까지) | 최근 `k`봉의 시가·고가·저가·종가만 담은 `deque` | 새 캔들을 밀어 넣고 가장 오래된 것을 버린 뒤 판정 함수를 한 번 부른다 | `k × 4` 실수. `k`는 1에서 5, 유한 범위 후보를 고르면 1에서 7 | `O(k)`이고 `k`가 패턴 정의가 고정한 상수이므로 **실질 상수**. 파라미터가 아니라는 점이 `Fractals`와 다르다 |
| 직전 추세 판정 (**확정: 10기간 지수이동평균**) | 기존 `EmaState(10)` (`services/core-lib/core_lib/indicators/primitives.py`)**에 더해, 최근 `k`개의 이동평균 값을 담은 `deque(maxlen=k)`** | 이동평균을 한 번 갱신하고 그 값을 큐에 밀어 넣는다. 판정은 큐의 가장 오래된 항목, 곧 패턴 첫날의 이동평균을 읽는다 | 이동평균 상태의 실수 한둘에 더해 **`k` 실수**. `k`가 최대 5이므로 최대 일곱 실수이고, Rise and Fall Three Methods가 유한 범위로 정해지면 최대 아홉 실수 | **`O(1)`.** 이동평균 갱신이 재귀형이고 큐 연산이 양쪽 끝에서 일어나므로 기간에도 `k`에도 의존하지 않는다 |
| 최근 `N`봉 실체·범위 평균 | 기존 `SmaState` (`services/core-lib/core_lib/indicators/primitives.py:326-356`) | 합에 더하고 빠지는 값을 뺀다 | `N` 실수와 합 하나 | `O(1)` |
| 최근 `N`봉 최고·최저 | 기존 `RollingExtremeState` (같은 파일 447-492줄) | 단조 감소·증가 후보 `deque`에서 뒤에서 밀어내고 앞에서 만료시킨다 | 최대 `N` 쌍 | **상환 `O(1)`.** 클래스 docstring이 스스로 그렇게 적는다 |
| 최근 `N`봉 표준편차 | 기존 `StdevState`, 곧 `_RollingPopulationStdev` | Welford 방식으로 평균과 2차 모멘트를 더하고 뺀다 | `N` 실수와 모멘트 둘 | `O(1)` |
| 최근 `N`봉 중앙값·분위수 | **없다. 새로 만들어야 한다** | 최대힙과 최소힙 두 개에 지연 삭제를 걸거나 정렬 자료구조를 쓴다 | `N` 실수와 힙 두 개 | `O(log N)`. 상수가 아니며, 새 프리미티브와 두 경로 동일성 증명이 따로 필요하다 |
| 가변 확인 창 (Hikkake는 3봉 이내) | 확인 대기 중인 설정을 담은 대기열 | 새 설정을 넣고, 확인되거나 창을 넘긴 설정을 뺀다 | 동시에 열려 있는 설정 수. 상한이 확인 창 길이이므로 상수 | 상한이 확인 창 길이이므로 **실질 상수**. 다만 이 분석은 **확인 기한이 원문에 적힌 Hikkake에만 그대로 적용된다.** Morris가 확인을 요구하는 다른 패턴들은 기한과 확인 조건이 아직 정해지지 않았으므로 같은 상한 논증을 쓸 수 없다 |

**표에서 읽어야 할 것은 셋이다.**

첫째, 추세 판정이 지수이동평균으로 확정되면서 2판이 미확정으로 남겼던 줄이 **상수 시간으로
닫혔다.** 회귀 추세를 골랐다면 `LinregState`가 없어 새로 만들어야 했는데, 그 위험이 사라졌다.
패턴 첫날의 이동평균을 보존하려고 큐를 하나 더 들어도 보관량이 최대 아홉 실수이므로 결론은
바뀌지 않는다.

둘째, **상태 보관량에 상한이 없는 패턴은 하나도 없다.** 4판에서 Breakaway가 고정 다섯 봉으로
확정되었고, 5판에서 마지막으로 열려 있던 Rise and Fall Three Methods도 원전 근거가 있는 후보가
**둘 다 유한**임을 확인했다. 표의 여섯 줄을 다시 훑으면, 모양 비교는 `k ≤ 5`(유한 범위 후보를
고르면 `k ≤ 7`), 추세는 이동평균 상태와 `k` 이하의 큐, 평균과 최고최저와 표준편차는 등록 파라미터
`N`, 확인 대기열은 확인 창 길이가 각각 상한이다. **`N`은 등록 시점에 고정되는 파라미터이므로
실행 중에 자라지 않는다.** 곧 어떤 패턴도 캔들이 쌓인다고 상태가 커지지 않으며, **아직 정해지지
않은 선택이 어느 쪽으로 결정되어도 이 성질은 유지된다.**

셋째, **남은 조건부 항목은 이제 하나뿐이다.** 사용자가 중앙값이나 분위수를 척도로 고르는 경우이며,
그때는 `O(log N)`이 되고 새 프리미티브와 두 경로 동일성 증명이 따로 필요하다. 원전 조사가 확인한
TA-Lib의 척도(실체와 범위의 최근 평균)와 패턴의 고정 봉 수와 지수이동평균 추세만 쓰는 한
**모든 척도가 상수 또는 상환 상수이고 새 자료구조가 필요 없으며**, 기존 프리미티브 넷이 그대로
쓰인다.

**확인 대기열 줄에는 단서가 하나 남는다.** 상한 논증은 확인 기한이 원문에 적힌 Hikkake에만 그대로
적용된다. Morris가 확인을 요구하는 다른 패턴들은 확인 조건과 기한이 아직 정해지지 않았으므로,
그 값들이 정해지기 전에는 같은 상한 논증을 쓸 수 없다. **다만 이것은 상태 크기에 상한이 없다는
뜻이 아니라 상한의 값을 아직 모른다는 뜻이며**, 표준이 기한을 적으면 그 값이 곧 상한이 된다.
누락된 확인 조건과 기한은 6.2절의 결정 목록에 올려 두었다.

### 4.3 `min_history`를 실제 워밍업 길이로 유도한다

#### 4.3.1 TA-Lib의 `lookback`은 우리 `min_history`와 같은 개념이 아니다

먼저 두 정의를 나란히 적는다. TA-Lib의 `lookback`은 **출력을 내지 못하는 앞쪽 봉의 수**이고, 첫
유효 출력이 놓이는 인덱스가 곧 그 값이다. 우리 `min_history`는 **상태가 warm이 되기까지 필요한
확정 캔들의 수**이고, 배치 경로의 첫 유효값이 놓이는 인덱스는 `min_history - 1`이다. 두 정의가
가리키는 창이 같다면 관계는 `min_history = lookback + 1`이 된다.

**등록된 지표 넷으로 검증했다.** 우리 쪽 값은 레지스트리에서 직접 읽었고, TA-Lib 쪽 값은 그
라이브러리가 문서화한 `lookback` 산출식(단순이동평균 계열은 기간에서 1을 뺀 값, Wilder 평활
계열은 기간 그대로)을 적용한 것이다. **이 자리에서 재측정하지는 않았고, 그 이유는 아래에 적는다.**

| 지표 | 우리 `min_history` | TA-Lib `lookback` | `lookback + 1` | 일치 |
|---|---|---|---|---|
| `EMA(period=9)` | 9 | 8 | 9 | 일치 |
| `RSI(period=14)` | 15 | 14 | 15 | 일치 |
| `Bollinger Bands(period=20)` | 20 | 19 | 20 | 일치 |
| `ATR(period=14)` | 14 | 14 | 15 | **어긋남** |

**따라서 `min_history = lookback + 1`은 두 구현이 같은 창을 쓸 때만 성립하고, 창이 다르면 어긋난다.**
ATR의 어긋남은 우연이 아니라 이미 문서화된 것이다. TA-Lib은 표준 0.6절이 정의한 첫 True Range를
건너뛰므로 그 아래 깔린 시드 창이 한 봉 늦게 시작하고, 그 사실은
`docs/roadmap-stage-3-0-plan.md` 8.5절에 NATR의 수렴 간격으로 기록되어 있다. 곧 **어긋남은 흡수할
것이 아니라 원인을 밝힐 신호다.**

**캔들스틱 패턴에서는 이 관계가 더 위험하다.** 원전 조사가 남긴 `lookback` 표와 봉 수 실험이 서로
맞지 않는 자리가 있기 때문이다. 원전 조사 111-141줄에 따르면 `CDLENGULFING`의 `lookback`은 2인데
같은 문서의 교란 실험은 그 패턴이 2봉짜리라고 말한다. 2봉이면 인덱스 1에서 이미 판정되므로
`min_history`는 2여야 하는데, `lookback + 1`을 그대로 쓰면 3이 된다. 반대로
`CDLXSIDEGAP3METHODS`는 `lookback`이 2인데 교란 실험은 3봉짜리라고 말하므로, `lookback`을 그대로
쓰면 판정에 필요한 봉 수보다 **작다.**

결론은 이렇다. **`lookback` 표를 그대로 `min_history`로 옮기면 안 된다.** 그 표는 상한과 하한을
가늠하는 참고이고, 값은 우리 표준 문서가 적을 판정 규칙에서 유도해야 한다. 그리고 유도한 값이
`lookback`과 어긋나면 그 차이의 원인을 밝혀 기록해야 한다. 이는 기존 지표에서 ATR과 NATR에 대해
이미 하고 있는 처리와 같다.

한 가지 덧붙인다. **TA-Lib은 이 저장소 어디에도 설치되어 있지 않다.** `python3.11`, `python3.12`,
기본 `python3` 어디서도 `import talib`이 실패한다. 그러므로 위 `lookback` 값은 원전 조사가 일회용
환경에서 관찰해 남긴 기록이고, 재측정하려면 그 환경을 다시 만들어야 한다. 이것은 불편이 아니라
지켜야 할 성질이며 7절 불변식에 넣는다.

#### 4.3.2 패턴 형태별 첫 유효 인덱스 유도

기호를 정한다. `k`는 패턴이 걸치는 봉 수, `N`은 "길다·짧다"를 재는 평균 창의 길이, `P`는 추세
판정에 쓰는 지수이동평균의 기간이다. 사용자 확정에 따라 `P = 10`이다. 인덱스는 0부터 센다.

**`min_history`의 뜻을 먼저 못박는다. 그것은 "유효한 값을 낼 수 있는 첫 시점"이다.** 특정 사건이
언제 확정되어 발표되는가와는 다른 것이며, 2판이 이 둘을 섞은 것이 2차 검토가 지적한 오류다.
확인 지연 문제는 아래 4.3.4절에서 따로 다룬다.

**형태 1. 평균도 추세도 없는 `k`봉 모양.** `k`봉이 모두 존재하는 첫 인덱스는 `k - 1`이므로
`min_history = k`다. Engulfing의 모양만 보면 2, Morning Star의 모양만 보면 3이다.

**형태 2. `N`봉 평균을 참조하는 `k`봉 모양.** 평균이 그 봉 자신을 뺀 직전 `N`봉을 본다면, 패턴의
**가장 이른 봉**도 자기 앞에 `N`봉을 갖고 있어야 한다. 가장 이른 봉의 인덱스가 `i - (k-1)`이므로
`i - (k-1) ≥ N`, 곧 첫 유효 인덱스는 `N + k - 1`이고 `min_history = N + k`다. 평균이 그 봉을
포함해 `N`봉을 본다면 각각 1씩 줄어든다. **어느 쪽인지는 우리 표준 문서가 정해야 하고, 정하지
않으면 모든 패턴이 한 봉씩 어긋난다.**

**형태 3. 추세를 요구하는 패턴.** 사용자가 확정한 대로 패턴이 10기간 지수이동평균으로 직전 추세를
직접 판정하므로, 그 지수이동평균이 유효해야 패턴도 유효하다. `EmaState(P)`가 언제 warm이 되는지는
코드로 확인했다. `EmaState(10)`에 값을 하나씩 먹이면 인덱스 0부터 8까지는 warm이 아니고 NaN을
내며, **인덱스 9에서 처음 warm이 되어 값을 낸다.** 이는 표준 0.3절이 첫 `P`개의 단순평균으로
재귀를 시드하기 때문이고, 등록된 `EMA(period=9)`의 `min_history`가 9인 것과 같은 규약이다.

**비교 봉은 확정되어 있다.** 3판은 이것을 다시 두 갈래로 열었으나 그럴 이유가 없었다. Morris의
예시는 **패턴 첫날의 범위 중간값을 그 시점의 10기간 지수이동평균과 비교**하며, 원전 조사도 그
문장을 근거로 삼는다. 곧 읽는 봉은 **패턴의 가장 이른 봉**이고, 패턴 직전 봉이 아니다. 이 판에서
그 갈래를 지운다.

그 확정에서 값이 따라 나온다. 패턴의 가장 이른 봉의 인덱스가 `i - (k - 1)`이고 그 봉에서
이동평균이 유효하려면 `i - (k - 1) ≥ P - 1`이어야 하므로, 첫 유효 인덱스는 `P + k - 2`이고
**`min_history = P + k - 1`**이다.

**이 확정이 상태 설계에 주는 요구를 4.2절에서 이미 적었지만 여기서 다시 짚는다.** 판정 시점 `i`에서
필요한 이동평균은 `i`의 값이 아니라 `i - (k - 1)`의 값이다. 그러므로 상태는 `EmaState(10)` 하나로는
부족하고 **최근 `k`개의 이동평균 값을 담은 `deque(maxlen=k)`**를 함께 들어야 한다. 판정할 때는 그
큐의 가장 오래된 항목을 읽으면 된다. `k`가 최대 5이므로 보관량은 상수이고 캔들당 작업 수도 상수다.

**단일 봉 패턴에서는 큐가 필요 없다.** `k = 1`이면 패턴 첫날이 곧 판정 봉이므로 현재 이동평균
값이 그대로 쓰이고, `min_history = P + 1 - 1 = P = 10`이 된다.

**형태 4. 셋을 다 갖춘 패턴.** 세 요구는 서로 독립이므로 각각이 요구하는 최소 이력의 **최댓값**이
답이다. 곧 **`min_history = max(k, N + k, P + k - 1)`**이다. 셋째 항은 위에서 확정되었고, 둘째 항만
평균 창이 그 봉을 포함하는지에 따라 한 봉 움직인다. `P = 10`이고 `N = 10`이면 `N + k`가
`P + k - 1`보다 늘 하나 크므로 평균 항이 지배하지만, `N`을 더 작게 정하면 추세 항이 지배할 수
있다.

**값으로 적으면 이렇다.** 표준이 "직전 `N`봉" 규약을 고르고 `N = P = 10`이라고 하자. 추세 항은
확정된 `P + k - 1`을 쓴다.

| 패턴 | `k` | 평균 필요 | 추세 필요 | `min_history` |
|---|---|---|---|---|
| Doji | 1 | 있음 | 없음 | `N + k = 11` |
| Hammer | 1 | 있음 | 있음 | `max(11, 10) = 11` |
| Engulfing | 2 | 없음 | 있음 | `max(2, 11) = 11` |
| Morning Star | 3 | 있음 | 있음 | `max(13, 12) = 13` |
| Hikkake 설정 | 3 | 없음 | 없음 | `k = 3` |

**여기서 세 가지를 짚는다.** 첫째, **추세를 요구하는 패턴과 요구하지 않는 패턴의 `min_history`가
실제로 갈린다.** Engulfing은 모양만 보면 2봉이지만 추세를 요구하므로 11이 된다. Nison이
Engulfing의 첫 기준으로 뚜렷한 직전 추세를 든다는 사실이 그대로 워밍업 길이에 나타난다. 둘째,
평균을 참조하는 패턴에서는 `N = 10`인 한 평균 항이 추세 항보다 크므로 **추세 판정이 워밍업을
늘리지 않는다.** 늘어나는 것은 Engulfing처럼 평균을 안 쓰면서 추세만 쓰는 패턴이다. 셋째,
**Hikkake의 입력 봉 수는 3이다.** 2판이 5라고 적은 것은 확인 창을 모양에 합산한 결과였고, 게다가
Chesler가 설정을 두 가격 봉이라고 부르더라도 첫 봉이 인사이드 바인지 판정하려면 그 **앞 봉**이
필요하므로 설정 판정에 실제로 드는 입력은 세 봉이다.

#### 4.3.3 검증은 세 갈래로 나눠야 한다

2판은 네 지점을 하나의 같은 인덱스로 묶어 단언하라고 썼다. **그것은 틀렸고, 그대로 쓰면 올바른
구현이 실패한다.** 네 지점의 정의를 코드에서 다시 확인해 적으면 이렇다.

**첫째, 배치 경로의 첫 유효값은 인덱스 `min_history - 1`이다.** `spec.compute_vectorized(candles)`의
그 인덱스가 유효한 값이고 `min_history - 2`가 NaN이어야 한다.

**둘째, 상태가 처음 warm이 되는 것도 인덱스 `min_history - 1`이다.**
`services/core-lib/tests/test_indicator_registry.py:282-291`이 `min_history - 1`개를 seed한 뒤에는
warm이 아니고 한 개를 더 먹인 직후에 warm이어야 한다고 요구한다. 캔들 `min_history`개를 먹였다는
것은 마지막 캔들의 인덱스가 `min_history - 1`이라는 뜻이다.

**셋째, 백테스트 Engine의 첫 평가 봉은 인덱스 `required_warmup`이다.** Engine은
`required_warmup = max(metadata.min_history, longest_indicator_history)`를 계산하고
(`services/backtest-service/backtest_service/engine/engine.py:383-384`), `available_preload`의
마지막 `required_warmup`개를 `self._preload`로 삼아(같은 파일 392줄) 그것으로 모든 상태를 seed한 뒤
warm을 확인하고(같은 파일 476-483줄), **그 다음** 캔들부터 평가한다. preload가 인덱스 0부터
`required_warmup - 1`까지를 먹었으므로 첫 평가 봉은 인덱스 `required_warmup`이다.

**넷째, signal-service의 첫 평가 봉도 인덱스 `required_warmup`이다.** 이 서비스는
`required_warmup + 1`개를 읽어(`services/signal-service/signal_service/application/service.py:146-151`)
마지막 하나를 뺀 `required_warmup`개로 seed하고 warm을 확인한 뒤(같은 파일 159-165줄) 마지막 봉을
평가한다(같은 파일 166줄).

**따라서 앞의 둘은 `min_history - 1`이고 뒤의 둘은 `required_warmup`이다. 이 둘이 한 봉 이상
어긋나는 것이 정상이다.** 패턴 spec 하나가 전체 워밍업을 결정하는 가장 단순한 경우, 곧
`required_warmup = min_history`인 경우에도 앞의 둘은 `min_history - 1`이고 뒤의 둘은
`min_history`이므로 **정확히 한 봉 차이가 난다.** 두 서비스가 워밍업 구간을 평가에서 구조적으로
제외하기 때문이며, 이는 결함이 아니라 look-ahead 경계를 유지하는 설계다. 네 값을 같다고 단언하면
올바른 구현이 실패한다.

그래서 검증은 **세 갈래로 나눠** 세운다. 3판은 둘로 나누었으나, 3차 검토가 지적한 대로 그 둘은
모두 **상호 일치 검증**이어서 정확성을 확인하지 못한다. 독립적인 기준을 세우는 검증 하나를 먼저
둔다.

##### 검증 하나. 독립 기준에 대고 경계를 확인한다

**3판의 검증이 왜 부족했는지 먼저 적는다.** 3판은 "배치 첫 유효 인덱스와 상태의 첫 warm 인덱스가
둘 다 `min_history - 1`인지" 보라고 했고, 기존 축에 등록하면 자동으로 걸린다고 덧붙였다. **그
단언은 셋이 함께 틀리면 통과한다.** 두 봉 패턴의 올바른 `min_history`가 2인데 `spec`과 상태와 배치가
모두 3으로 구현되어 앞 두 값을 NaN으로 두고 셋째부터 숫자를 내면, 세 값이 서로 일치하므로 그대로
통과한다. 반대로 셋이 다 1로 구현되어 첫 봉부터 숫자를 내도 마찬가지다. 실제로 기존
`test_min_history_and_seed_warmup`
(`services/core-lib/tests/test_indicator_parity.py:276-293`)은 **선언된 시점의 배치값과 상태값만**
비교하고 바로 앞 봉이 어때야 하는지를 독립적으로 확인하지 않는다. **"기존 축에 등록하면 자동으로
걸린다"는 서술은 사실이 아니므로 지운다.**

독립 기준은 두 가지 방식으로 세울 수 있고, 둘 다 쓰는 것을 권한다.

**방식 하나. 원전 정의에서 손으로 유도한 기대 `min_history` 표를 둔다.** 패턴마다 4.3.2절의 식으로
값을 손으로 유도해 표로 적어 두고, 검증은 레지스트리에서 읽은 `spec.min_history`가 아니라 **그 표의
값**을 기준으로 삼는다. 표는 `tests/pattern_reference/` 안의 카테고리 모듈에 손으로 적으며, 기존
`indicator_reference` 패키지가 등록 identifier와 외부 대조값을 손으로 적어 두는 것과 같은 방식이다
(`services/core-lib/tests/indicator_reference/__init__.py:1-11`이 그 취지를 적는다). 자기가 검사하는
대상에서 기대치를 유도하면 어떤 구현과도 일치해 버린다는 그 파일의 경고가 여기에 그대로 적용된다.

검증은 그 표의 값 `m`에 대해 **세 가지를 함께** 본다. 첫째, `spec.min_history == m`이다. 이것이
선언 자체를 표에 대고 확인한다. 둘째, 배치 계열의 인덱스 `m - 1`이 NaN이 아니다. 셋째, **배치
계열의 인덱스 `m - 2`가 NaN이다.** 세 번째가 3판에 없던 것이며, 이것이 한 봉 늦은 구현과 한 봉
빠른 구현을 갈라 잡는다. 구현이 한 봉 늦으면 둘째가 실패하고, 한 봉 빠르면 셋째가 실패한다.
상태 쪽도 같은 형태로 본다. `m - 1`개를 seed한 뒤 warm이 아니고, 한 개를 더 먹인 직후 warm이며,
그 값이 배치의 인덱스 `m - 1` 값과 같은지를 본다.

**방식 둘. 경계 봉에서 반드시 성립하는 수제 입력을 만든다.** 패턴마다 캔들을 손으로 지어, **정확히
어느 인덱스에서 처음 성립값이 나와야 하는지**를 계열 자체가 못 박게 한다. 예를 들어 Engulfing이면
앞의 `m - 2`봉을 추세가 성립하도록 만들고 마지막 두 봉을 감싸는 모양으로 지은 뒤, 인덱스 `m - 1`에
성립값이 나오고 그 앞은 NaN이거나 불성립인지를 본다. 이 방식의 값은 **어느 구현에서 읽어 온 것이
아니라 사람이 캔들을 짓고 답을 함께 적은 것**이므로 방식 하나와 독립이고, 두 방식이 어긋나면 유도가
틀렸거나 캔들이 잘못 지어진 것이므로 어느 쪽이든 드러난다.

이 방식은 저장소에 전례가 있다. `services/core-lib/tests/test_indicator_parity.py:869-895`의 Fractals
검증이 정확히 그 모양이다. 고가와 저가를 손으로 지어 어느 봉이 프랙탈인지 사람이 읽을 수 있게 만든
뒤, 앞의 네 봉이 NaN이고 인덱스 4에 `{"up": 1.0, "down": 0.0}`이 나오며 인덱스 6에 하락 프랙탈이
나온다고 **인덱스를 못 박아** 단언한다. 패턴도 같은 방식으로 쓸 수 있다.

**두 방식이 함께 막는 것을 정리하면 이렇다.** 방식 하나는 선언과 두 실행 경로를 **바깥 표**에 대고
확인하므로 셋이 함께 틀리는 경우를 잡고, 방식 둘은 그 표의 값 자체가 유도 과정에서 틀린 경우를
잡는다. 어느 쪽도 검사 대상에서 기대치를 읽어 오지 않는다.

##### 검증 둘. 두 실행 경로가 서로 일치하는지 본다

배치 계열과 증분 상태가 값 하나하나 같은지 보는 기존 동일성 검사다
(`services/core-lib/tests/test_indicator_parity.py:205-216`). 이것은 정확성 검증이 아니라 **일치
검증**이며, 그 사실을 이제 명시한다. 검증 하나가 경계의 정확성을 잡고, 이 검증이 두 경로가 같은
값을 낸다는 것을 잡는다. 둘은 서로를 대신하지 못한다.

##### 검증 셋. 두 서비스가 같은 봉에서 같은 값을 내는지 본다

두 서비스가 **정확히 `required_warmup`개를 preload한 뒤 그 다음 봉부터 같은 값을 내는지** 본다.
같은 캔들 계열과 같은 전략 선언으로 백테스트 Engine을 한 번 돌리고 signal-service를 한 주기 돌린 뒤,
두 쪽이 첫 평가 봉에 대해 기록한 패턴 값이 같은지, 그리고 그 봉이 양쪽 모두 워밍업 시작점에서 센
인덱스 `required_warmup`인지를 확인한다. 이 단언이 지키는 것은 7절 불변식 23번이다.

**이것도 상호 일치 검증이라는 한계가 있다.** 두 서비스가 같은 잘못된 `required_warmup`을 공유하면
그대로 통과한다. 그 구멍은 검증 하나가 막는다. `required_warmup`은
`max(metadata.min_history, 각 spec의 min_history)`로 계산되므로, 검증 하나가 각 패턴의
`min_history`를 독립 기준에 대고 확인하면 그것을 입력으로 삼는 `required_warmup`도 따라서 옳아진다.

##### 세 검증이 각각 잡는 실패

**검증 하나**는 선언과 두 실행 경로가 **함께** 한 봉 빠르거나 늦은 경우를 잡는다. 이것이 3판에
없던 유일한 종류이며, 나머지 둘로는 절대 잡히지 않는다. **검증 둘**은 두 실행 경로가 서로 다른
값을 내는 경우를 잡는다. **검증 셋**은 `min_history`가 옳더라도 두 서비스가 서로 다른 봉을 첫
평가로 삼거나 서로 다른 값을 내는 경우를 잡는다. 두 서비스가 같은 식을 쓰되 그 식이 두 파일에 따로
쓰여 있으므로 드리프트를 막는 것은 이 단언뿐이다.

#### 4.3.4 확인 지연은 `min_history`에 더하는 것이 아니다

2판은 확인 지연 `d`를 형태 1이나 2의 값에 무조건 더했다. **그것은 워밍업과 발표 시점을 섞은
것이다.** `min_history`는 "유효한 값을 낼 수 있는 첫 시점"이고, 확인 지연은 "특정 사건이 언제
확정되는가"이다. 상태가 유효한 숫자를 내기 시작하는 시점은 확인을 기다리는 사건이 있든 없든
바뀌지 않는다.

**Hikkake로 보면 분명해진다.** Chesler의 확인은 설정 뒤 **세 봉 가운데 어느 봉에서든** 일어날 수
있으므로 지연은 고정값이 아니라 1에서 3 사이다. 고정값이 아닌 것을 `min_history`에 더할 수는
없다.

**그러면 지연이 `min_history`에 어떻게 관여하는가는 출력 표현에 따라 달라진다.** 3.5.1절의 표현
후보마다 갈라 적으면 이렇다.

| 출력 표현 | 상태가 유효한 숫자를 내기 시작하는 시점 | 확인 지연이 `min_history`에 주는 영향 |
|---|---|---|
| 확인 전에는 불성립을 내고 확인된 봉에서만 성립값을 낸다 | 설정을 판정할 수 있는 첫 봉. Hikkake면 인덱스 2 | **없다.** `min_history = 3`이고 확인은 그 뒤의 값이 무엇이 되는가의 문제일 뿐이다 |
| 확인 전 성립과 확인 후 성립을 다른 값으로 낸다(TA-Lib의 100과 200에 해당) | 같다. 설정을 판정할 수 있는 첫 봉 | **없다.** 대기 상태를 숫자로 낼 수 있으므로 첫 유효 시점이 앞당겨지지도 미뤄지지도 않는다 |

**3판에 있던 셋째 줄은 이 판에서 제거했다.** "확인된 사건만 출력하고 그 전에는 값 자체를 정의하지
않는다"는 표현은 **실행 가능한 소비 시계열이 아니기 때문이다.** 워밍업이 끝난 뒤 모든 평가 봉에
유한값을 요구하는 Evidence 완결성 검사
(`services/backtest-service/backtest_service/adapters/evidence_sink.py:719-745`)와 면제가 아예 없는
signal-service의 유한성 검사
(`services/signal-service/signal_service/application/service.py:562-571`)를 동시에 만족할 수 없다.
3판은 "잘 맞지 않는다"고 적는 데서 멈췄으나, 만족할 수 없는 것은 정상 후보가 아니므로 지운다.
3.5.1절의 표현 후보 다섯은 모두 매 봉 값을 내는 모양이므로 그 표에는 영향이 없다.

**남은 두 표현에서는 지연이 `min_history`를 전혀 움직이지 않는다.** 곧 **확인이 필요한 패턴의
`min_history`도 확인 지연과 무관하게 4.3.2절의 형태별 식으로 확정된다.** 3판이 "출력 표현이
정해지기 전에는 확정할 수 없다"고 적은 것은 실행 불가능한 셋째 표현을 후보에 두었기 때문이며, 그것을
빼면 남은 두 표현이 같은 값을 주므로 확정할 수 있다.

다만 확인 지연이 `min_history`에 들어가지 않더라도 **어느 봉에 무엇이 실리는가**는 여전히 정렬
규약의 문제로 남으며, 그것은 7절 불변식 11번의 미래 봉 금지가 지키는 자리다. 그리고 각 패턴의
확인 조건과 기한이 무엇인지는 표준이 정해야 하며, 6.2절의 결정 목록에 올려 두었다.

---

## 5. "지침과 별도로 구성"을 코드로 옮기는 방법 — 배치안 넷

1판은 셋을 냈고 그 비교가 공정하지 않았다. 배치안 C가 제안한 `services/core-lib/core_lib/patterns/`는
문자 그대로 core-lib 패키지 **안**이므로 "core-lib 옆"이라고 쓴 것은 사실이 아니었고, 그 문장이
비교를 B에 유리하게 기울였다. 2판은 그 오류를 바로잡고, 교차 검토가 제시한 네 번째 안을 후보에
넣어 넷을 같은 기준으로 평가한다.

**배치안마다 다섯 질문에 답한다.** 답하지 못하는 안은 추천할 수 없다는 것이 이번 보강의 규칙이다.
다섯 질문은 전략의 선언 자리, 카탈로그 대조 통과 방법, 두 종류 요구의 합집합, 워밍업 계산, 그리고
`indicator_mode` 세 값의 뜻이다.

### 배치안 A — `DEFAULT_REGISTRY`의 일곱 번째 카테고리

**패키지와 파일 배치.** 계산은 `services/core-lib/core_lib/indicators/patterns.py`(또는 같은 이름의
서브패키지)에 두고, 등록은 `services/core-lib/core_lib/indicators/specs/patterns.py`에 둔다.
`services/core-lib/core_lib/indicators/specs/__init__.py`의 `CATEGORY_SPECS`에 `"patterns"` 항목을
더한다. 기존 여섯 카테고리와 완전히 같은 모양이다.

**레지스트리.** 기존 `DEFAULT_REGISTRY`를 그대로 쓴다.

**1. 전략의 선언 자리.** 기존 `required_indicators`에 `{"name": "Bullish Engulfing", "params": {}}`를
그대로 넣는다. `StrategyMetadata`를 고치지 않는다.

**2. 카탈로그 대조.** `required_indicators_json` 배열에 같은 항목이 들어가고 `_indicator_identities`가
그대로 대조한다. **DDL 변경도 API 모델 변경도 없다.** 네 안 가운데 가장 싸다.

**3. 두 종류 요구의 합집합.** 합칠 것이 없다. 목록이 애초에 하나이고 `resolve_specs`가 그대로
해석한다.

**4. 워밍업.** `longest_indicator_history = max(spec.min_history for spec in self._indicator_specs)`에
패턴 spec이 자동으로 포함된다. 계산식을 고치지 않는다. signal-service도 같다.

**5. `indicator_mode`.** `auto`는 전략과 정책이 선언한 것(지표와 패턴이 섞여 있다), `explicit`은
사용자가 지정한 목록, `all`은 **패턴을 포함한 등록 전부**가 된다. 여기가 문제다. `all`의 뜻이 조용히
넓어지는 것은 7절 불변식 21번이 금지하는 일이므로 `resolve_enabled`를 고쳐야 한다.

**고칠 때의 기준을 정확히 적는다.** 2판은 `all`을 "표준 89종만"으로 좁힌다고 썼는데 그것은 현재
등록 상태와 맞지 않는다. 표준 89종 가운데 **등록된 이름은 81개이고 레지스트리 조합은 84개**이며,
나머지 8종은 후속 카탈로그에 이름만 있고 해석할 spec이 없다. 그러므로 89를 기준으로 삼으면 존재하지
않는 spec을 가리키게 된다. 실제로 필요한 기준은 **"패턴 카테고리를 제외한 현재 등록 지표 전부"**,
곧 지금의 84 조합이고, 앞으로 지표가 늘면 그만큼 함께 늘어나는 집합이다. 구현으로는
`resolve_enabled`의 `all` 갈래가 `spec.category != "patterns"`인 spec만 모으는 형태가 된다. 이렇게
쓰면 패턴을 켜지 않은 기존 실행의 resolved 목록이 글자 그대로 보존되므로 불변식 19번도 함께 지켜진다.

**곧 "기존 코드를 한 줄도 고치지 않는다"는 A의 최대 장점이 바로 이 지점에서 깨진다.**

**89 집계와 기존 식별자.** 기존 84개 조합의 identifier와 값은 움직이지 않는다. 89가 걸린 단언도
`STANDARD_SYSTEMS = 0`이면 성립한다. 대신 카테고리 튜플 단언과 `pinned_impl` 인용 요구 두 단언을
고쳐야 한다. 뒤의 것이 실질적 대가이며, **"이 레지스트리에 있는 것의 출처는 계산 표준"이라는 지금의
단순한 진술이 조건부 진술로 바뀐다.**

**테스트 소유권.** `services/core-lib/tests/indicator_reference/patterns.py`를 새로 만들어 일곱 이름을
선언하면 나머지는 자동으로 걸린다. 다섯 축 파일은 위 두 단언 말고는 그대로다. **복제가 가장 적다.**

**소비 경로.** 기존 지표와 완전히 같다. Evidence도 같은 테이블을 쓰므로 `indicator_key` 이름 충돌만
막으면 된다.

**나중에 후회할 만한 것.** 사용자가 정한 "별도로 구성한다"는 방향이 필드 수준에서 흐려진다. 패턴과
지표가 같은 spec 타입, 같은 `pinned_impl` 필드, 같은 선택 모드를 공유하고, 되돌리려 할 때는 등록
식별자가 이미 Evidence에 남은 뒤일 것이다.

### 배치안 B — 같은 `IndicatorSpec` 타입, 두 번째 `IndicatorRegistry` 인스턴스

**패키지와 파일 배치.** `services/core-lib/core_lib/indicators/patterns/` 서브패키지에 계산 모듈,
등록 모듈, 조립 함수 `build_pattern_registry()`와 모듈 수준 `PATTERN_REGISTRY`를 둔다. 타입은 기존
`IndicatorSpec`과 `IndicatorRegistry`를 그대로 재사용한다.

**레지스트리.** 새 인스턴스를 만든다. `IndicatorRegistry`는 인스턴스마다 독립된 `_specs` 사전을 갖는
평범한 클래스이므로(`services/core-lib/core_lib/indicators/registry.py:100-104`) 두 번째 인스턴스를
만드는 데 클래스 변경이 필요 없다.

**1. 전략의 선언 자리.** 두 갈래가 있고 대가가 다르다.

갈래 하나는 **같은 목록에 판별자 키를 붙이는 것**이다. `{"name": ..., "params": ..., "kind": "pattern"}`
형태이며, `StrategyMetadata.required_indicators`가 자유형 사전 목록이므로 dataclass를 고치지 않는다.
갈래 둘은 **`StrategyMetadata`에 `required_patterns` 필드를 새로 두는 것**이다. 기본값을 빈 목록으로
두면 기존 전략은 영향이 없다.

**2. 카탈로그 대조.** 갈래 하나는 **데이터베이스 제약은 그대로 통과하지만 대조 로직을 반드시
고쳐야 한다.** 3.4.1절이 보인 대로 `_indicator_identities`가 판별자를 무시하므로, 고치지 않으면
코드가 `kind="pattern"`이고 카탈로그가 `kind="indicator"`여도 같다고 판정되어 전략 선언이 원본이라는
계약이 깨진다. 고치는 방법은 신원 튜플에 판별자를 넣고 없는 항목을 `"indicator"`로 읽는 것이며,
그러면 기존 선언과 기존 카탈로그 행의 비교 결과는 지금과 같다. **곧 갈래 하나의 실제 비용은
"DDL 변경 없음, 대조 로직 변경 있음, 응용 프로그래밍 인터페이스 변경 없음"이다.** 2판이 "둘 다
변경 없음"이라고 적은 것을 이렇게 고친다.

갈래 둘이면 `required_patterns_json` 컬럼 신설, `_validate_declared_history`에 비교 한 벌 추가,
web-api의 `StrategyOption` 모델 필드 추가, 생성된 프런트 타입 갱신이 필요하다. 다만
`_validate_declared_history`가 카탈로그 키가 없으면 비교를 건너뛰므로
(`services/core-lib/core_lib/strategy/manager.py:146-147`) 마이그레이션 중에도 실행이 깨지지는 않는다.
**갈래 둘에는 판별자 드리프트 문제가 아예 없다.** 두 목록이 물리적으로 갈려 있어 종류가 곧 자리이기
때문이다. 이것이 갈래 둘이 비용이 크면서도 계약 면에서 더 안전한 이유다.

**3. 두 종류 요구의 합집합.** 엔진이 목록을 판별자나 필드로 갈라 각 레지스트리에 넘기고, 나온
`list[IndicatorSpec]` 둘을 이어 붙인다. 갈래 하나를 쓰면 **레지스트리에 넘기기 전에 판별자 키를 떼야
한다.** `_descriptor_spec`이 키 집합을 정확히 `{"name", "params"}`로 요구하기 때문이다
(`services/core-lib/core_lib/indicators/registry.py:139-141`). 타입이 같으므로 그 뒤의
`_indicator_states`, `_update_indicators`, `_assert_finite_indicator`, Evidence 기록은 **한 벌로
유지된다.** 이것이 B의 실질적 장점이다.

**4. 워밍업.** `max(spec.min_history for spec in 지표_spec + 패턴_spec)` 한 줄 확장이다.
signal-service도 같은 방식이다.

**5. `indicator_mode`.** `auto`는 두 목록을 각자의 레지스트리에서 해석한다. `explicit`은 두 종류를
따로 받아야 하므로 `explicit_indicators` 옆에 패턴용 목록이 필요하고, 이는 `RunConfig`와 API 변경이다.
`all`은 **레지스트리마다 따로 뜻을 가질 수 있다.** 지표 `all`의 뜻을 그대로 두고 패턴은 별도 스위치로
두면 되므로, A와 달리 `all`의 뜻을 넓히지 않고도 표현할 수 있다.

**89 집계와 기존 식별자.** 영향이 없다. `DEFAULT_REGISTRY`가 그대로이므로
`services/core-lib/tests/test_indicator_registry.py`의 모든 단언이 손대지 않은 채 통과한다.

**테스트 소유권.** 완전히 갈린다. 패턴용 등록 테스트와 참조값 패키지를 새로 만들고, 다섯 축에
해당하는 검사를 패턴 레지스트리를 대상으로 다시 쓴다. 형태는 그대로 가져올 수 있지만 **코드는
복제된다.**

**소비 경로.** 배선이 필요하다. signal-service는 이미 레지스트리를 생성자에서 받으므로 주입 지점이
있지만 인자를 하나에서 둘로 바꿔야 하고, 백테스트 Engine은 `DEFAULT_REGISTRY`를 모듈 전역으로 직접
부르므로 주입 지점을 새로 만들어야 한다. Evidence는 같은 테이블을 쓰므로 **3.6.3절의 결합 실행
신원 문제를 그대로 안는다.** 두 갈래 가운데 하나를 골라야 하고, 그 비용이 B의 몫으로 계상된다.

**나중에 후회할 만한 것.** 검증 코드가 복제되어 두 벌이 서서히 갈라질 수 있다. 기존 다섯 축에 고칠
결함이 생기면 두 곳을 고쳐야 하고 한 곳만 고치면 아무것도 실패하지 않는다. 그리고 spec 타입이 같아서
`pinned_impl`이 두 표준을 가리키게 되는데, 3.6.1절대로 Evidence는 그 차이를 기록하지 않는다.

### 배치안 C — `core_lib/patterns/` 독립 패키지, 자체 spec 타입, 별도 소비 경로

**패키지와 파일 배치.** `services/core-lib/core_lib/patterns/`를 `indicators/`와 나란한 패키지로
만든다. **이것은 core-lib 패키지 안이다.** 그 안에 자체 `PatternSpec`과 `PatternRegistry`, 계열별
등록 모듈, 계산 모듈을 둔다. `core_lib.indicators.primitives`와 `core_lib.indicators.contracts`,
`core_lib.types.Candle`은 가져다 쓴다.

**레지스트리.** 자체 타입으로 새로 만든다. 실익은 **필드를 패턴에 맞게 다시 정할 수 있다**는 것이다.
`pinned_impl` 대신 패턴 표준의 절을 가리키는 필드를 두고, 증분 경로에서 존중되지 않는
`required_inputs` 같은 필드를 아예 만들지 않으며, 확인 지연 봉 수를 1급 필드로 둘 수 있다.

**1. 전략의 선언 자리.** 타입이 다르므로 같은 목록에 섞을 수 없다. `StrategyMetadata.required_patterns`
신설이 사실상 강제된다.

**2. 카탈로그 대조.** `required_patterns_json` 컬럼 신설, 대조 로직 추가, API 모델 추가, 프런트 타입
갱신이 필요하다. B의 갈래 둘과 같다.

**3. 두 종류 요구의 합집합.** **합치지 않는다.** Engine이 `_pattern_specs`, `_pattern_states`,
`_update_patterns`, 패턴용 유한성 검사를 따로 갖는다. 소비 코드가 한 벌 더 생긴다.

**4. 워밍업.** `required_warmup = max(전략 min_history, 지표 최대, 패턴 최대)`로 항이 셋이 된다.
두 서비스 모두에서 같은 확장이 필요하다.

**5. `indicator_mode`.** 패턴용 모드를 따로 둔다. 뜻이 완전히 분리되어 가장 명확하지만 설정 축이 하나
늘고 API에도 드러난다.

**89 집계와 기존 식별자.** 영향이 없다.

**테스트 소유권.** 완전히 갈리고 복제가 가장 많다. 타입이 다르므로 값 비교 헬퍼부터 다시 써야 한다.

**소비 경로.** 가장 많이 건드린다. 상태 생성, 워밍업 검증, 유한성 검사, Evidence 기록이 각각 한 벌씩
더 필요하고, Evidence를 별도 테이블로 두면 완결성 검사도 그 테이블까지 넓혀야 한다(3.6.2절).

**나중에 후회할 만한 것.** 소비 경로의 이중화가 core-lib 밖의 두 서비스와 Evidence 스키마와 웹
화면까지 번진다. 지금 지표 계층이 가진 성질, 곧 하나의 진입점과 하나의 유한성 규칙과 하나의 스냅샷
테이블이 둘로 갈라지면 되돌리기가 가장 어렵다.

### 배치안 D — `core_lib/patterns/` 독립 패키지에 공통 시계열 Protocol을 더한다

**패키지와 파일 배치.** C와 같이 `services/core-lib/core_lib/patterns/`에 자체 `PatternSpec`과
`PatternRegistry`를 둔다. **거기에 더해, 지표와 패턴이 공통으로 만족할 시계열 계산 Protocol을
core-lib에 뽑아 둔다.**

#### D-1. Protocol의 구성원을 소비 경로에서 다시 뽑는다

2판은 그 Protocol이 `identifier`, `min_history`, `undefined_outputs`, `make_state()`,
`compute_vectorized()` 다섯이면 된다고 썼다. **그것은 틀렸다.** 2차 검토의 지적대로 두 소비자는 더
많은 것을 읽는다. 짐작하지 않고 두 파일에서 spec 속성 접근을 전부 뽑아 세었다.

**백테스트 Engine이 읽는 것은 일곱이다.** `spec.identifier`(373, 376, 1702, 1856, 1858줄),
`spec.min_history`(383, 1846줄), `spec.name`(418, 1842, 1928줄), `spec.params`(419, 1843, 1930줄),
`spec.version`(420, 1844줄), `spec.undefined_outputs`(1858줄), `spec.make_state()`(1702줄)이다.
줄 번호는 모두 `services/backtest-service/backtest_service/engine/engine.py`의 것이다.

**signal-service가 읽는 것은 다섯이다.** `spec.identifier`(157, 279줄), `spec.min_history`(137줄),
`spec.name`(575줄), `spec.params`(578줄), `spec.make_state()`(157줄)이며 줄 번호는
`services/signal-service/signal_service/application/service.py`의 것이다.

**두 소비자가 읽는 것의 합집합은 일곱이다.** 곧 소비 Protocol은 `identifier`, `name`, `params`,
`version`, `min_history`, `undefined_outputs`, `make_state()`다. 2판이 빠뜨린 것은 `name`, `params`,
`version` 셋이며, 빠진 채로 `PatternSpec`을 만들면 실행 메타데이터
(`engine.py:416-423`의 `resolved_indicators_json`), Evidence 정의(같은 파일 1835-1849줄), 그리고
정규화 열쇠 생성(같은 파일 1926-1932줄과 signal-service의 573-580줄)에서 실패한다.

**대신 조사에서 새로 확인한 사실 둘이 이 비용을 낮춘다.**

첫째, **`compute_vectorized()`는 두 소비자 어디에서도 불리지 않는다.** 저장소 전체에서
`compute_vectorized`를 부르는 곳은 `IndicatorRegistry.compute_batch`와 core-lib 테스트뿐이다. 곧
**소비 Protocol과 검증 Protocol은 서로 다르다.** 소비 쪽에는 배치 경로가 필요 없고, 배치 경로는
두 경로 동일성을 검사하는 오라클로서만 필요하다. 2판이 이 둘을 하나로 묶은 것도 잘못이었다.

둘째, **상태 쪽 계약은 오히려 `IndicatorState`보다 작다.** 두 소비자가 상태에서 쓰는 것은
`seed()`, `warmed_up`, `update()` 셋뿐이고 **`current()`는 어느 서비스에서도 불리지 않는다.**
`current()`는 core-lib 테스트가 쓰는 검증용 구성원이다.

정리하면 Protocol은 두 벌로 나뉜다.

| Protocol | 구성원 | 만족해야 하는 쪽 |
|---|---|---|
| 소비 Protocol (`SeriesSpec`) | `identifier`, `name`, `params`, `version`, `min_history`, `undefined_outputs`, `make_state()` | 엔진과 signal-service가 spec에서 읽는 전부 |
| 소비 상태 Protocol | `seed()`, `warmed_up`, `update()` | 두 서비스가 상태에서 쓰는 전부 |
| 검증 Protocol | 위에 더해 `compute_vectorized()`와 상태의 `current()` | core-lib 테스트와 `compute_batch`만 |

**`IndicatorSpec`이 이 Protocol을 이미 만족하는가.** 만족한다. 일곱 구성원이 모두 공개 필드이거나
공개 메서드이고, `_vectorized`와 `_state_factory`라는 private 필드는 Protocol에 들어가지 않는다
(소비자가 그 필드가 아니라 `make_state()` 메서드를 부르기 때문이다). **따라서 기존 dataclass를
고치지 않아도 된다는 2판의 결론 자체는 유지된다.** 바뀐 것은 Protocol의 크기이지 그 성질이 아니다.

**`PatternSpec`이 부담해야 하는 것.** 일곱 구성원을 모두 갖되, `version`과 `undefined_outputs`는
패턴에서 뜻이 다를 수 있다. `version`은 패턴 표준의 판을 가리키면 되고, `undefined_outputs`는
패턴이 워밍업 이후 NaN을 낼 일이 없다면 빈 튜플로 두면 된다. **곧 일곱을 만족시키는 비용은
"필드 셋을 더 선언한다"이지 "지표 개념을 그대로 물려받는다"가 아니다.** 이것이 D가 B와 다른
점이며, `pinned_impl`이나 `required_inputs` 같은 지표 전용 필드는 여전히 물려받지 않는다.

**대안도 적어 둔다.** Protocol을 일곱으로 넓히는 대신, Evidence 기록과 열쇠 생성을 **어댑터로
분리**할 수도 있다. 소비 Protocol은 다섯으로 유지하고, `name`·`params`·`version`을 읽어 열쇠와
Evidence 레코드를 만드는 부분만 spec 종류별 어댑터에 맡기는 방식이다. 이쪽은 Protocol이 작아지는
대신 어댑터 배선이 엔진 안에 하나 더 생기고, `_indicator_key`와 `_record_indicator_definitions`를
어댑터 호출로 바꾸는 리팩터링이 따라온다. **일곱으로 넓히는 쪽이 변경 범위가 더 작다**고 판단하며,
근거는 세 필드를 선언하는 것이 두 메서드를 어댑터로 옮기는 것보다 건드리는 곳이 적다는 것이다.

**레지스트리.** 패턴용을 새로 만들되, 엔진과 signal-service는 두 레지스트리에서 나온 spec을 **하나의
`list[SeriesSpec]`**으로 합쳐 지금의 실행기를 그대로 쓴다. 다만 두 서비스는 레지스트리에서
`resolve_specs()`를 부르고 엔진은 `specs_from_descriptors()`도 부르므로
(`services/backtest-service/backtest_service/engine/engine.py:366`, 374줄,
`services/signal-service/signal_service/application/service.py:130`), **패턴 레지스트리도 같은 두
메서드를 제공해야 한다.** 이는 Protocol이 아니라 레지스트리 쪽 계약이며 D의 비용에 함께 계상한다.

**1. 전략의 선언 자리.** 두 갈래가 B와 같되, 공통 Protocol이 있으므로 **공통 요구 타입을 core-lib에
두는 세 번째 갈래**가 열린다. 예를 들어 종류와 이름과 파라미터를 담은 요구 항목 하나를 정의하고
전략이 그 목록 하나만 선언하게 하는 방식이다. 이 경우 판별자가 임시 키가 아니라 1급 필드가 되고,
`StrategyMetadata`는 필드 하나만 바뀐다.

**2. 카탈로그 대조.** 한 배열에 판별자를 담는 갈래를 고르면 **DDL 변경은 없지만 3.4.1절의 대조
로직 수정이 필요하다.** 신원 튜플에 종류를 넣고 없는 항목을 `"indicator"`로 읽는 그 수정이며,
B의 갈래 하나와 같은 비용이다. 두 배열로 나누는 갈래를 고르면 C와 같은 비용이 든다. **다만 D에는
세 번째 갈래가 있고 그것이 이 문제를 가장 깨끗하게 푼다.** 공통 요구 타입을 core-lib에 두어 종류를
1급 필드로 만들면, 대조 함수가 그 필드를 읽는 것이 자연스러워지고 "판별자를 무시한다"는 상태가
애초에 생기지 않는다. 이 갈래에서도 대조 함수는 고쳐야 하지만, 임시 키를 특별 취급하는 것이
아니라 타입이 가진 필드를 읽는 형태가 된다.

**3. 두 종류 요구의 합집합.** **공통 Protocol이 정확히 이 문제를 푼다.** 두 레지스트리가 각자 해석한
결과를 이어 붙이면 그 뒤의 `_prepare_indicator_states`, `_update_indicators`, 유한성 검사, Evidence
기록이 **손대지 않고 그대로 돈다.** 다만 이것이 성립하는 것은 위 D-1절의 일곱 구성원을 모두
갖췄을 때이며, 2판이 적은 다섯만으로는 성립하지 않는다. 소비 코드가 복제되지 않는다는 결론은
유지되지만 **그 대가로 `PatternSpec`이 `name`·`params`·`version`을 선언해야 한다.**

**그리고 여기서 3.6.3절의 문제가 D에 그대로 걸린다.** 두 레지스트리의 결과를 한 목록으로 합치는
것이 D의 핵심인데, 합친 뒤의 실행 경로는 `identifier`와 `_indicator_key`로 신원을 만들고 그 둘
어디에도 종류가 없다. 곧 **카탈로그에서 다른 신원으로 통과한 지표와 패턴이 상태 사전과 Evidence
기본 키에서 충돌할 수 있다.** 3.6.3절의 두 갈래 가운데 하나를 골라야 하며, 그 비용이 D의 몫으로
계상된다. **이름 비중복을 계약으로 강제하는 갈래를 고르면 실행 경로와 `config_hash`를 건드리지
않으므로 "소비 코드를 손대지 않는다"는 D의 근거가 그대로 유지되고, 종류를 실행 신원에 넣는 갈래를
고르면 그 근거가 약해진다.** 어느 쪽인지가 D의 실제 비용을 가른다.

**4. 워밍업.** 합친 목록 하나에 대해 `max(spec.min_history for spec in specs)`이므로 지금 식이 그대로
쓰인다. C보다 단순하고 B와 같다.

**5. `indicator_mode`.** 종류별로 해석한다. 지표 `all`의 뜻을 그대로 두고 패턴은 별도 스위치로 둘 수
있으므로 B와 같은 자유도를 갖되, 타입이 갈려 있어 실수로 섞을 수 없다.

**89 집계와 기존 식별자.** 영향이 없다.

**테스트 소유권.** **복제를 피할 수 있다.** 두 경로 동일성, 워밍업 시점, 미래 봉 금지는 spec 타입과
무관하게 Protocol 위에서 진술되는 성질이므로, 공통 계약 테스트 묶음을 만들고 레지스트리를
매개변수로 넘기면 된다. 반면 등록 신원 비교와 외부 대조 값은 패턴이 자기 파일에서 소유한다. 곧
**형태가 같은 것은 공유하고 내용이 다른 것은 나누는 분할**이 가능하다.

**소비 경로.** Protocol을 뽑는 한 번의 리팩터링이 필요하고 그 뒤로는 한 벌이다. Evidence를 같은
테이블에 둘지 나눌지는 여전히 결정 사항이며, 나누면 완결성 검사 확장이 따라온다.

**나중에 후회할 만한 것.** **가장 큰 위험은 Protocol 추출 자체다.** 이미 돌아가고 테스트가 덮고 있는
코드를 건드리는 일이므로, 패턴을 더하는 작업과 **반드시 분리된 bounded changeset**이어야 한다.
한 커밋에 섞으면 회귀가 났을 때 원인이 리팩터링인지 새 패턴인지 가릴 수 없다. 그리고 Protocol이
너무 넓게 정의되면 지표 전용 개념이 패턴 쪽으로 새어 들어와 B와 같은 의미 혼합이 다시 생긴다.

### 5.1 네 안을 같은 기준으로 비교한다

**3판에서 이 표가 바뀐 곳을 먼저 밝힌다.** 2차 검토가 지적한 대로 2판의 표는 **추천안 D의 비용을
누락한 채로** 비교하고 있었다. 아래 표는 D-1절이 다시 뽑은 Protocol 구성원 일곱, 패턴 레지스트리가
제공해야 하는 두 메서드, 그리고 판별자 방식이 요구하는 대조 로직 수정을 모두 해당 열에 계상했다.

| 기준 | 안 A (일곱째 카테고리) | 안 B (둘째 레지스트리, 같은 타입) | 안 C (독립 패키지, 별도 소비 경로) | 안 D (독립 패키지, 공통 Protocol) |
|---|---|---|---|---|
| "core-lib 안에 두되 별도 구성" | core-lib 안이지만 별도가 아니다. 같은 spec 타입, 같은 표준 인용 필드, 같은 선택 모드를 공유한다 | core-lib 안이고 레지스트리가 갈린다. 다만 spec 타입과 `IndicatorValue`를 공유하므로 별도 계약은 약하게만 만족한다 | core-lib 안이고 타입까지 갈린다. 가장 강하게 만족한다 | core-lib 안이고 타입이 갈린다. 일곱 구성원을 공유하지만 그것은 실행 계약이고 `pinned_impl`·`required_inputs` 같은 지표 전용 필드는 물려받지 않는다 |
| 89 집계와 기존 식별자 | 값은 무영향. 테스트 단언 둘을 고쳐야 하고 그중 하나는 출처 요구를 약화시킨다 | 무영향 | 무영향 | 무영향 |
| 다섯 질문에 답할 수 있는가 | 다섯 다 답한다. 다만 다섯째에서 `all`의 기준을 "패턴을 뺀 현재 등록 지표 전부"로 좁히는 코드 변경이 필요해 "무변경"이라는 장점이 깨진다 | 다섯 다 답한다. 첫째와 둘째에 갈래가 둘이고 대가가 다르다 | 다섯 다 답하지만 첫째부터 다섯째까지 모두 새 코드가 필요하다 | 다섯 다 답한다. 셋째와 넷째가 Protocol 덕에 기존 코드 그대로이되, **그것은 일곱 구성원을 모두 갖췄을 때만 성립한다** |
| 카탈로그 신원 대조 | 고칠 것 없다. 종류가 곧 카테고리이고 목록이 하나다 | 판별자 갈래는 **대조 로직을 고쳐야 한다.** 별도 필드 갈래는 고칠 것 없이 새 비교를 더한다 | 고칠 것 없이 새 비교를 더한다. 목록이 물리적으로 갈려 있다 | 판별자 갈래는 B와 같은 수정이 필요하고, 공통 요구 타입 갈래는 종류가 1급 필드라 수정이 자연스럽다 |
| 결합 실행 신원(3.6.3절) | **문제가 생기지 않는다.** 레지스트리가 하나뿐이라 `register`가 identifier 충돌을 이미 막는다 | **문제가 생긴다.** 두 레지스트리를 합치므로 3.6.3절의 두 갈래 가운데 하나를 골라야 한다 | **문제가 생기지 않는다.** 목록과 상태 사전과 Evidence 경로가 물리적으로 갈려 있다. 대신 Evidence를 나누면 완결성 검사를 그 테이블까지 넓혀야 한다 | **문제가 생긴다.** B와 같다. 비중복 이름을 계약으로 강제하는 갈래를 고르면 실행 경로와 `config_hash`를 건드리지 않아 D의 근거가 유지되고, 종류를 실행 신원에 넣는 갈래를 고르면 근거가 약해진다 |
| 검증 코드 복제량 | 가장 적다. 참조값 모듈 하나만 늘어난다 | 다섯 축 형태가 복제된다 | 가장 많다. 값 비교 헬퍼까지 다시 쓴다 | 형태는 매개변수화로 공유하고 내용만 나눈다. B보다 적다 |
| 소비 경로 변경량 | 사실상 없다(다섯째 제외) | 배선 수준. 주입 지점 신설과 목록 합치기 | 가장 크다. 상태·검사·기록이 한 벌 더 생긴다 | **2판이 적은 것보다 크다.** Protocol 추출 한 번에 더해, `PatternSpec`이 `name`·`params`·`version`을 선언해야 하고 `PatternRegistry`가 `resolve_specs()`와 `specs_from_descriptors()`를 제공해야 한다. 그 뒤로는 한 벌이다 |
| 되돌리기 난이도 | 어렵다. 등록 식별자가 기존 목록과 섞인 채 Evidence에 남는다 | 보통. 레지스트리를 떼면 되지만 배선이 두 서비스에 남는다 | 어렵다. 이중화가 두 서비스와 스키마와 화면까지 번진다 | 보통. 패턴 레지스트리를 떼면 원상복구되고 Protocol만 남는데, 그것은 그 자체로 해로운 것이 아니다 |

### 5.2 추천

**비용을 다시 계상한 뒤에도 배치안 D를 추천한다. 고르는 것은 사용자의 몫이므로 근거만 적는다.**

**추천이 바뀌지 않은 이유를 먼저 밝힌다.** 2차 검토는 D의 Protocol이 실제 소비 계약보다 작아서
"소비 코드를 손대지 않고 재사용한다"는 근거가 입증되지 않았다고 지적했고, 그 지적은 옳았다.
그러나 D-1절에서 소비 경로를 다시 뽑아 본 결과, **빠진 것은 필드 셋(`name`, `params`, `version`)
이고 그것은 `PatternSpec`이 선언하면 끝나는 종류였다.** 구조적 장애가 아니라 선언 비용이다.
그리고 같은 조사에서 **`compute_vectorized()`와 `current()`가 두 서비스 어디에서도 쓰이지 않는다**는
사실이 새로 확인되어, 소비 Protocol이 검증 Protocol보다 오히려 **작다**는 것이 드러났다. 비용이
늘어난 만큼 다른 자리에서 줄어든 셈이며, D가 다른 셋보다 나은 이유 자체는 그대로 남는다.

첫째, **다섯 질문 가운데 가장 어려운 셋째와 넷째를 소비 코드 변경 없이 답한다.** 두 레지스트리의
결과를 하나의 `list[SeriesSpec]`으로 이어 붙이면 `_prepare_indicator_states`, `_update_indicators`,
유한성 검사, Evidence 기록, 워밍업 계산이 모두 지금 모습 그대로 돈다. 이 성질은 D만 갖는다. C는
같은 일을 하려면 그 다섯을 한 벌 더 만들어야 한다.

둘째, **89 집계와 카테고리 소유 규칙과 `pinned_impl` 인용 요구를 한 글자도 건드리지 않으면서
타입 수준의 분리를 얻는다.** A는 분리를 얻지 못하고, B는 분리를 얻되 spec 타입 전체를 공유해
`pinned_impl`과 `required_inputs` 같은 지표 전용 필드까지 물려받는다. D가 공유하는 일곱 구성원에는
그 둘이 들어 있지 않다.

셋째, **검증 코드의 복제를 구조적으로 피한다.** 두 경로 동일성과 워밍업 시점과 미래 봉 금지는
Protocol 위에서 진술되는 성질이므로 매개변수화가 자연스럽다. B의 가장 큰 대가가 여기서 사라진다.

넷째, **되돌리기가 쉽다.** 패턴 레지스트리를 통째로 떼면 남는 것은 Protocol 하나이고, 그것은
지표 계층만 있어도 해롭지 않다.

**D의 대가를 빠짐없이 적는다.** 다섯 가지다. 첫째, Protocol 추출은 이미 돌아가는 코드를 건드리는
리팩터링이므로 패턴을 더하는 작업과 반드시 분리해야 하고, 그 리팩터링이 기존 실행의 결과를 바꾸지
않았음을 회귀로 확인해야 한다. 둘째, `PatternSpec`이 `name`·`params`·`version` 셋을 더 선언해야
한다. 셋째, `PatternRegistry`가 `resolve_specs()`와 `specs_from_descriptors()` 두 메서드를 제공해야
한다. 넷째, 선언 갈래로 판별자를 고르면 3.4.1절의 대조 로직 수정이 따라온다. **다섯째, 3.6.3절의
결합 실행 신원 규약을 골라야 한다.** 이것이 이번 판에서 새로 계상한 항목이며, 어느 갈래를 고르느냐가
D의 소비 경로 변경량을 실제로 가른다.

**A와 C는 다섯째 항목을 갖지 않는다.** A는 레지스트리가 하나라 `register`가 충돌을 이미 막고, C는
목록과 상태 사전과 Evidence 경로가 물리적으로 갈려 있다. **곧 결합 실행 신원 문제는 "두 레지스트리를
한 목록으로 합친다"는 선택의 대가이고, 그 선택을 하는 B와 D만 부담한다.** 이것을 D의 비용으로
정직하게 계상하고도 추천이 유지되는 이유는, 비중복 이름을 계약으로 강제하는 갈래를 고르면 그 비용이
**검증 단언 하나**로 끝나기 때문이다.

**그리고 어느 안을 골라도 남는 것이 둘 있다.** 3.6.1절의 출처 기록 문제와 3.6.2절의 완결성 검사
확장이다. **네 안 가운데 어느 것도 그 둘을 자동으로 풀지 못한다.**

마지막으로 한 가지를 다시 강조한다. **어느 안을 골라도 3.5.1절의 출력 표현이 정해지지 않으면
설계를 닫을 수 없다.** 표현이 사전이면 웹 화면 작업이 따라오고, 확인 단계를 별도 값으로 두면
완결성 검사가 그 값을 요구하며, 방향별로 등록을 쪼개면 등록 조합 수가 61에서 최대 88쯤으로 늘어
카탈로그와 워밍업 계산에 그대로 반영된다. 배치와 표현은 서로 독립이 아니다.

---

## 6. 표준 문서를 어디에 둘 것인가

### 6.1 지금의 배치

`docs/references/technical_indicators_calc_spec.md`가 저장소 안에 실체로 있고(1022줄), 개발지침
디렉터리 `/Users/vincent/Documents/X2.Mine/01.Trading/트레이딩시스템_개발지침/`가 그 사본을 갖는
쪽이다.

1판을 쓸 때는 그 디렉터리의 링크가 동기화 충돌로 깨져 있었다. 지금은 정리되어, 심볼릭 링크 대신
저장소와 같은 크기의 일반 파일이 놓여 있다. 곧 **저장소가 원본이고 개발지침 쪽은 수동 사본**이다.
이 사실이 6.3절 판단의 근거가 된다.

### 6.2 패턴 표준 문서를 어디에 둘 것인가

**새 파일 하나를 `docs/references/` 아래에 나란히 두는 것을 권한다.** 이름은
`candlestick_pattern_calc_spec.md` 같은 형태가 자연스럽다.

**기존 표준 문서에 절을 덧붙이지 않아야 하는 이유가 구조적으로 있다.** 그 문서의 11절 집계인 89는
장식이 아니라 **테스트에 걸린 리터럴**이다(2.7절). 패턴을 그 문서에 절로 넣으면 11절의 카테고리
표와 합계를 고쳐야 하고, 그러면 `services/core-lib/tests/test_indicator_registry.py:158`의 `89`를
함께 옮겨야 하며, 후속 카탈로그 8종의 의미도 흔들린다.

**같은 규율은 그대로 유지된다.** 곧 표준 문서를 먼저 쓰고 그것을 보고 구현한다는 순서다. 이 저장소가
바로 앞 작업에서 그 순서를 지킨 기록이 `docs/roadmap-stage-3-0-plan.md` 8장에 있다. TA-Lib 대비
공백 7종을 더할 때, TA-Lib은 "무엇이 빠져 있는지 알려 준 목록"일 뿐이고 **수식은 표준 문서에 먼저
적고 그 표준을 보고 구현했다**고 명시되어 있다. 패턴도 똑같이 해야 한다.

**새 문서가 스스로 갖춰야 할 것을 기존 문서를 본떠 정해 두는 편이 좋다.** 목록으로 적으면 이렇다.
캔들 파생량의 정의(몸통, 위꼬리, 아래꼬리, 전체 폭)를 담은 공유 프리미티브 절, 0으로 나누는 자리의
대체값 규약, 판정 결과를 숫자로 옮기는 인코딩 규약, 확인이 필요한 패턴의 정렬 규약, 커버리지 집계,
1차 출처 목록이다.

**여기에 조사에서 드러난 항목 셋을 더한다. 모두 표준이 문장으로 정하지 않으면 구현이 어긋나는
것들이다.**

첫째, **평균 창이 그 봉을 포함하는지 여부.** 4.3.2절이 보인 대로 이 한 줄이 평균을 참조하는 모든
패턴의 `min_history`를 한 봉씩 움직인다.

둘째, **확인이 필요한 패턴에서 각 패턴의 확인 조건과 기한.** Chesler의 Hikkake는 세 봉이라는 기한이
원문에 있지만 Morris가 확인을 요구하는 다른 패턴들은 기한과 확인 조건이 원문에 없다. 4.2절의 확인
대기열이 상수 크기라는 논증은 기한이 있을 때만 성립한다. 다만 **확인 지연을 `min_history`에 더하는
것이 아니라는 점은 4.3.4절이 유도했으므로, 표준이 적어야 하는 것은 지연 봉 수가 아니라 확인 조건과
기한이다.**

셋째, **워밍업 이후 언제나 값을 낸다는 계약과 그 값들의 뜻.** 3.6.2절의 완결성 검사가 행 생략을
금지하기 때문이다.

**3판이 이 목록에 두었던 두 항목은 이 판에서 지웠다. 둘 다 이미 확정되었기 때문이다.**

- **추세 판정을 어느 봉에서 읽는가.** Morris의 예시가 패턴 첫날의 범위 중간값을 그 시점의 10기간
  지수이동평균과 비교하므로 **패턴의 가장 이른 봉**으로 확정되어 있다. 3판이 이것을 다시 선택으로
  남긴 것은 잘못이었고, 4.3.2절에서 `min_history = P + k - 1`로 못 박았다.
- **가변 길이 패턴의 상한.** 원전 조사가 결정 C에 따라 Breakaway를 **고정 다섯 봉**으로 확정했다.
  Morris 내부에서는 규칙 절이 규범이고 유연성 절은 주석이라는 것이 결정 C의 내용이며, 규칙 절
  (`morris_cce.txt` 5044줄)이 다섯 봉이다. 4.2절에서 가변 길이 줄을 지웠고, 이로써 **상태 보관량에
  상한이 없는 패턴은 하나도 남지 않는다.**

인코딩과 정렬 두 규약에 대해서는 **이미 `docs/roadmap-stage-3-0-plan.md`의 7.4.1절과 7.4.2절이
지표 쪽에서 문장으로 확정해 둔 것이 있다.** 다만 그 규약은 지표의 상태 집합을 위해 쓰인 것이므로
패턴에 그대로 옮겨 쓸 수 있는지는 3.5.1절의 표현 결정이 난 뒤에 판단해야 한다. **1판이 그 규약을
패턴에 그대로 적용된다고 쓴 것이 앞질러 나간 부분이다.**

### 6.3 개발지침 디렉터리에 링크를 걸 것인가

**걸지 않는 쪽을 권한다.** 근거는 셋이다.

첫째, **같은 디렉터리에서 심볼릭 링크가 이미 한 번 실패했다.** 그 실패가 조용했다는 점이 특히
나쁘다. 낡은 일반 파일이 원래 이름을 차지하고 있었으므로 그 디렉터리를 읽는 쪽은 자기가 낡은 것을
읽고 있다는 사실을 알 수 없었다.

둘째, 링크가 필요했던 이유가 이 문서에는 약하다. 기존 지표 표준은 개발지침 디렉터리가 원래
소유하던 문서가 저장소로 옮겨 온 것이라 양쪽에서 같은 이름으로 읽히던 이력이 있다. 패턴 표준은
**처음부터 저장소에서 태어나는 문서**이므로 그런 이력이 없다.

셋째, 개발지침 쪽이 필요로 하는 것은 파일 자체가 아니라 **그런 문서가 있고 어디에 있는지**다.
그 디렉터리의 `00_INDEX.md`는 이미 표를 두어 각 참조 문서가 무엇이고 언제 쓰는지를 한 줄로 적고
있다. 거기에 패턴 표준 한 줄을 더하고 저장소 경로를 그 줄에 적는 것이 링크보다 안전하고 같은
목적을 이룬다.

---

## 7. 바뀌면 안 되는 것

불변식을 스물다섯으로 적는다. 1판의 열여덟에 교차 검토가 요구한 일곱을 더했고, 더한 것은 19번부터
25번이다.

1. **기존 84개 조합의 identifier 문자열.** `services/core-lib/tests/indicator_reference/`의 여섯
   모듈에 손으로 적힌 `IDENTIFIERS` 집합이 그대로여야 한다. identifier는 Evidence의 열쇠이자
   전략 등록의 대조 대상이므로 한 글자만 달라져도 과거 실행과의 연결이 끊긴다.

2. **기존 81개 이름.** 같은 모듈들의 `NAMES` 집합이 그대로여야 한다.

3. **기존 지표의 값.** `REFERENCE`와 `CONVERGING`에 얼려 둔 수치가 그대로 통과해야 한다. 새 코드가
   프리미티브나 공유 헬퍼를 건드려 기존 값을 움직이면 이 표들이 즉시 실패한다.

4. **89라는 집계와 그것이 걸린 단언.** `services/core-lib/tests/test_indicator_registry.py:158`의
   `len(follow_up) == 89 - REGISTERED_STANDARD_SYSTEMS`가 성립해야 한다. 패턴은 표준 89종에 속하지
   않으므로 어느 카테고리의 `STANDARD_SYSTEMS`도 패턴 때문에 올라가면 안 된다.

5. **후속 카탈로그 8종.** 시장폭 3종과 원저서 상수가 없는 5종은 그대로 남아 있어야 한다.

6. **카테고리 소유 규칙.** `_reject_misfiled_specs`
   (`services/core-lib/core_lib/indicators/specs/__init__.py:35-53`)가 유지되어야 하고, spec의
   `category`는 그것을 담은 모듈이 소유한 이름과 같아야 한다.

7. **`DEFAULT_REGISTRY`에 든 모든 spec의 `pinned_impl`이 계산 표준의 절을 인용한다는 규칙.**
   패턴이 다른 문서를 인용해야 한다면, 그 규칙을 약하게 만드는 대신 패턴을 그 레지스트리 밖에
   두거나 단언을 카테고리별로 명시적으로 갈라야 한다. "인용을 요구하지 않는다"로 물러서면 안 된다.

8. **버전 규약.** 등록된 spec의 `version`은 `"1.0.0"`이고 Bollinger Bands만 `"1.0.1"`이다
   (`services/core-lib/tests/test_indicator_registry.py:83-84`).

9. **워밍업 계약.** `IndicatorSpec.min_history`와 상태의 `min_history`가 같아야 하고, 상태는
   정확히 그 지점에서 warm이 되어야 하며, 그때의 `current()`가 배치 경로의 같은 인덱스 값과
   같아야 한다.

10. **두 경로 동일성.** 등록된 모든 조합이 네 개의 난수 스트림과 평평한 스트림에서 값 하나하나
    같아야 한다. 허용 오차는 상대·절대 1e-12이고 NaN은 NaN끼리 맞아야 한다. 다만 4.1절대로,
    공유는 순수 판정 함수까지로 한정하고 값의 정확성은 별도 관계 단언으로 확인한다.

11. **확정 캔들 계약과 미래 봉 금지.** 진행 중이거나 미래의 캔들이 재귀 상태에 들어가면 안 되고,
    인덱스 t의 값이 t 이후 캔들을 읽으면 안 된다.

12. **외부 라이브러리는 대조군이지 계산식의 원천이 아니다.** 값이 어긋나면 표준 문서를 다시 읽어
    원인을 밝히고, 라이브러리를 따라 구현을 바꾸거나 대조를 맞추려 상수를 끼워 넣지 않는다.
    4.3.1절의 `lookback` 어긋남도 흡수하지 말고 원인을 기록해야 하는 종류다.

13. **표준 문서의 소유권.** `docs/references/technical_indicators_calc_spec.md`가 원본이고 수식과
    규약을 임의로 바꾸지 않는다. 패턴 때문에 11절의 집계를 움직이지 않는다.

14. **값은 `float`이고 `bool`은 거부된다.** 세 계층
    (`services/backtest-service/backtest_service/engine/engine.py:1898`,
    `services/signal-service/signal_service/application/service.py:566`,
    `services/core-lib/core_lib/strategy/adaptees/vessel_reference.py:139`)이 모두 `bool`을 명시적으로
    거부한다.

15. **워밍업 이후의 NaN은 이름 있는 키에만 허용되고, signal-service에는 그 면제조차 없다.**
    단일 숫자를 내는 출력은 어떤 경우에도 워밍업 이후 NaN을 낼 수 없다.

16. **0.0과 NaN을 섞지 않는다.** 워밍업 구간은 NaN이고, 판정을 마친 불성립은 숫자다. 이 구분이
    흐려지면 `warmed_up` 단언이 곧바로 깨진다.

17. **`required_inputs`는 증분 경로에서 여과되지 않는다**
    (`services/core-lib/core_lib/indicators/registry.py:206-208`). 값을 넘길 경로가 없는 지표를
    이 필드로 안전하게 등록해 둘 수 있다고 가정하면 안 된다.

18. **Evidence의 기록 형태.** `INDICATOR_SNAPSHOT`은 `value`와 `value_json` 가운데 정확히 하나만
    채워져야 하고(`services/backtest-service/backtest_service/adapters/evidence_schema.py:279`),
    등록된 모든 키가 평가 봉마다 한 행씩을 가져야 한다
    (`services/backtest-service/backtest_service/adapters/evidence_sink.py:719-745`).

19. **패턴을 켜지 않은 기존 실행이 글자 그대로 그대로여야 한다.** 구체적으로 네 가지다.
    `resolved_indicators_json`(`services/backtest-service/backtest_service/engine/engine.py:416-424`),
    그것을 입력으로 삼는 `config_hash`(같은 파일 454줄), 논리 Evidence 해시, 그리고 전략의 결정
    자체다. `config_hash`가 resolved indicator 목록에서 나오므로 **패턴이 목록에 조용히 들어가면
    과거 실행과 해시가 갈린다.**

20. **manual 자금관리 호환이 그대로여야 한다.** 보호가격, 수량, leverage가 같은 입력에서 같은 값을
    내야 한다. 이번 작업은 전략 edge도 자금관리 수식도 건드리지 않는다.

21. **`indicator_mode="all"`의 뜻을 패턴까지 조용히 넓히지 않는다.** 좁힐 때의 기준은 "표준 89종"이
    아니라 **"패턴을 제외한 현재 등록 지표 전부"**다. 표준 89종 가운데 등록된 이름은 81개이고
    조합은 84개이며 나머지 8종은 해석할 spec이 없기 때문이다. 배치안 A를 고르면 이 불변식을
    지키기 위해 `resolve_enabled`를 명시적으로 고쳐야 한다.

22. **전략 코드의 메타데이터와 `signal_db.strategy_registry.required_indicators_json`의 대조가
    유지되어야 한다**(`services/core-lib/core_lib/strategy/manager.py:116-154`). 선언이 원본이고
    등록이 사본이라는 관계를 패턴이 깨뜨리면 안 된다.

23. **백테스트와 signal-service가 같은 구현과 같은 출력 시점과 같은 워밍업을 써야 한다.**
    4.3.3절이 보인 대로 두 서비스의 첫 평가 인덱스는 지금 같은 값이며, 그 성질은 두 곳에 따로
    쓰여 있으므로 검증으로 지켜야 한다.

24. **TA-Lib은 테스트 대조군일 뿐 런타임 의존성이 되어서는 안 된다.** 지금 이 저장소의 어느
    파이썬 환경에도 설치되어 있지 않다는 사실을 4.3.1절에서 확인했고, 그 상태가 유지되어야 한다.
    대조값은 일회용 환경에서 만들어 얼려 두는 방식을 그대로 쓴다.

25. **API와 생성된 프런트 타입을 바꾸면 명시적 버전과 회귀 검증이 필요하다.** 전략 선언의 모양이
    바뀌면 `services/web-api/web_api/models.py`의 `StrategyOption`과
    `apps/web/src/api/openapi.json`이 함께 움직인다.

---

## 8. 사용자가 확정할 세 결정

이 문서가 결론을 내리지 않고 남긴 것은 셋이다. 앞의 절들이 각각을 다루었으나 흩어져 있으므로,
조율자가 사용자에게 그대로 올릴 수 있도록 한자리에 모은다. 배치안 넷의 비교표는 5.1절에 있으므로
여기서 되풀이하지 않고 그 표를 가리킨다.

### 8.1 결정 하나 — 출력 값의 표현

**무엇을 정하는가.** 패턴 판정을 어떤 숫자 모양으로 나를지다. 보존 대상은 성립 여부와 방향과 경계
강도와 확인 단계 넷이고, 그중 방향은 도지처럼 방향이 없는 패턴에서는 뜻이 없다. 후보와 평가는
3.5.1절의 표에 있고, 여기서는 **고르면 무엇을 구현해야 하는가**를 적는다.

| 후보 | 고르면 구현해야 하는 것 | 되돌리기 |
|---|---|---|
| 가. TA-Lib 표기 그대로 실수 하나 | 판정 결과를 일곱 값 가운데 하나로 접는 매핑 하나. 등록 조합은 패턴 수와 같다. 화면 쪽에 별도 축이나 마커 표시가 필요하다 | 어렵다. 기록된 값의 뜻이 바뀌므로 과거 Evidence를 새 뜻으로 읽을 수 없다 |
| 나. 성립과 방향 두 키 | 두 키를 내는 사전 출력과 그 키들의 워밍업 NaN 처리. 강도와 확인 단계를 버리므로 그 정보가 필요 없다는 판단이 함께 필요하다 | 어렵다. 위와 같고, 버린 정보는 되돌려도 복원되지 않는다 |
| 다. 성립·방향·강도·확인 네 키 | 네 키를 내는 사전 출력. `REFERENCE` 대조 표의 항목이 패턴당 네 배가 되므로 대조값 생성 분량이 그만큼 늘어난다 | 어렵다. 다만 정보를 다 보존하므로 다른 표현으로 접는 것은 가능하다 |
| 라. 패턴마다 필요한 키만 | 패턴별로 키 집합이 달라지므로 소비자와 대조 코드가 키 유무를 분기해야 한다. 등록 시점에 키 집합을 선언하는 자리도 필요하다 | 어렵다. 키 집합 자체가 신원의 일부가 되므로 바꾸면 과거 기록과 모양이 어긋난다 |
| 마. 방향별로 등록을 쪼갠다 | 강세형과 약세형을 별도 identifier로 등록한다. 등록 조합이 61에서 최대 88쯤으로 늘어 카탈로그와 워밍업 계산과 검증 행 수에 그대로 반영된다 | **가장 어렵다.** 등록 식별자 자체가 달라지므로 불변식 1번과 같은 종류의 고정이 걸린다 |

**공통으로 딸려 오는 것 둘.** 첫째, **어느 후보를 골라도 화면 쪽 작업이 따로 필요하다.** 실수
하나를 내면 가격 축에 붙은 평평한 선이 되고, 사전을 내면 `value`가 비어 그려지지 않는다
(3.5.1절). 둘째, **`CONVERGING` 대조는 어느 후보에도 쓸 수 없으므로** 패턴은 `REFERENCE`나
`UNCOMPARED` 둘 중 하나로만 다뤄야 한다.

**이 결정이 더는 좌우하지 않는 것 하나를 밝혀 둔다.** 확인이 필요한 패턴의 `min_history`는 실행
불가능한 후보를 4판에서 뺀 뒤로 **표현 선택과 무관하게 확정된다**(4.3.4절).

### 8.2 결정 둘 — 배치안 선택

**무엇을 정하는가.** 패턴을 core-lib 안 어디에 어떤 레지스트리로 얹을지다. 네 안의 정의와 다섯
질문에 대한 답은 5절에, 여섯 기준 비교는 5.1절에, 추천과 근거는 5.2절에 있다. **되돌리기 난이도도
5.1절 표의 마지막 줄에 이미 있으므로 여기서 되풀이하지 않는다.**

고르면 무엇을 구현해야 하는지만 한 줄씩 다시 적는다. **안 A**는 계산 모듈과 등록 모듈을 기존
`specs/` 옆에 더하고 `resolve_enabled`의 `all` 갈래를 좁힌다. **안 B**는 두 번째
`IndicatorRegistry` 인스턴스와 두 서비스의 주입 지점을 만들고 목록을 합친다. **안 C**는 자체 spec
타입과 레지스트리에 더해 상태 생성과 유한성 검사와 Evidence 기록을 한 벌 더 만든다. **안 D**는
자체 spec 타입과 레지스트리를 두되 일곱 구성원짜리 소비 Protocol을 뽑아 기존 실행기를 그대로 쓴다.

### 8.3 결정 셋 — 결합 실행의 신원 규약

**무엇을 정하는가.** 이름과 파라미터가 같은 지표와 패턴이 생겼을 때 실행 단계에서 둘을 어떻게
가를지다. 문제의 소재와 두 갈래의 비용은 3.6.3절에 있다.

| 갈래 | 고르면 구현해야 하는 것 | 되돌리기 |
|---|---|---|
| 종류를 실행 신원에 포함한다 | `PatternSpec.identifier`에 접두사를 넣고, `_indicator_key`가 그것을 반영하며, `resolved_indicators_json`과 `INDICATOR_DEFINITION`에 종류 칸을 더한다. **종류가 `indicator`인 경우를 직렬화에서 생략하는 처리가 반드시 함께 필요하다.** 그러지 않으면 패턴을 켜지 않은 기존 실행의 `config_hash`까지 달라져 불변식 19번을 깬다 | 어렵다. identifier와 Evidence 열쇠가 바뀌므로 그 규약으로 남긴 실행 기록과의 연결이 끊긴다 |
| 이름 공간의 비중복을 계약으로 강제한다 | 두 레지스트리의 이름 집합이 서로소인지 보는 검증 단언 하나. **정규화 후의 열쇠까지 비교해야 한다**(`_indicator_key`가 소문자와 밑줄로 접으므로 `Three Outside`와 `three-outside`가 같은 열쇠가 된다) | 쉽다. 단언 하나를 더하고 빼는 일이며 실행 경로와 Evidence를 건드리지 않는다 |

### 8.4 세 결정이 서로 얽혀 있는가, 그리고 어떤 순서로 정해야 하는가

**결정 둘이 결정 셋을 지배한다. 이것이 유일한 강한 의존이다.** 결정 셋은 두 레지스트리의 결과를
하나의 목록으로 합칠 때에만 생기는 문제이므로, **안 A나 안 C를 고르면 결정 셋은 아예 사라진다.**
안 A는 레지스트리가 하나뿐이라 `IndicatorRegistry.register`가 identifier 충돌을 이미 막고
(`services/core-lib/core_lib/indicators/registry.py:117-122`), 안 C는 목록과 상태 사전과 Evidence
경로가 물리적으로 갈려 있다. 안 B나 안 D를 고를 때에만 결정 셋을 물어야 한다.

**결정 하나는 나머지 둘과 독립이다. 다만 비용의 크기에만 영향을 준다.** 어떤 출력 표현도 배치안을
탈락시키지 않고, 어떤 배치안도 출력 표현을 탈락시키지 않는다. 값의 모양이 `float`이든
`dict[str, float]`이든 네 안 모두 그대로 나를 수 있고, Evidence의 `value`와 `value_json`도 네 안에서
같다. 영향은 두 군데에 크기로만 나타난다. 첫째, 후보 마를 고르면 등록 조합이 61에서 88쯤으로
늘어 **어느 안을 골랐든** 카탈로그와 워밍업 계산과 검증 행 수가 그만큼 커진다. 둘째, 같은 이유로
패턴 이름이 늘어나므로 **결정 셋에서 비중복 갈래를 골랐을 때 지켜야 할 이름이 많아진다.**

**따라서 정하는 순서는 이렇다.**

1. **결정 둘(배치안)을 먼저 정한다.** 이것이 결정 셋을 물어야 하는지 아닌지를 결정하기 때문이다.
2. **안 B나 안 D를 골랐다면 결정 셋(신원 규약)을 정한다.** 안 A나 안 C를 골랐다면 이 결정은
   건너뛴다.
3. **결정 하나(출력 표현)는 앞의 둘과 나란히 정해도 된다.** 다만 **표준 문서를 쓰기 전에는 반드시
   닫혀야 한다.** 값들의 뜻을 적는 절이 표준 문서에 들어가야 하고, 6.2절이 요구하는 "매 봉 값을
   낸다는 계약과 그 값들의 뜻"이 곧 이 결정의 결과이기 때문이다.

**되돌리기가 가장 어려운 것은 결정 하나다.** 나머지 둘은 코드 구조와 검증에 걸리지만, 결정 하나는
**기록된 값의 뜻**에 걸린다. 배치를 바꾸면 코드를 옮기면 되고 신원 규약의 비중복 갈래는 단언
하나지만, 표현을 바꾸면 그 표현으로 남긴 실행 Evidence를 새 뜻으로 읽을 수 없다. 그러므로 셋
가운데 **가장 신중하게 물어야 하는 것은 순서상 마지막이어도 되는 결정 하나**다.

---

## 부록 — 이 조사의 한계와 남긴 것

**조사하다 막힌 것은 없다.** 저장소는 모두 읽혔고 숫자는 실행으로 확인했다.

**확인하지 못한 것이 하나 있다.** TA-Lib이 설치되어 있지 않으므로 4.3.1절의 `lookback` 값은 원전
조사가 남긴 기록을 그대로 인용했고 재측정하지 않았다. 등록된 지표 넷과의 대조는 우리 쪽 값을
레지스트리에서 직접 읽고 TA-Lib의 잘 알려진 `lookback` 정의를 적용한 것이며, 어긋남이 확인된
ATR의 경우는 저장소 문서(`docs/roadmap-stage-3-0-plan.md` 8.5절)가 이미 그 원인을 적어 두었다는
사실로 뒷받침된다. **`lookback` 값 자체를 다시 재는 일은 대조값 생성 환경을 다시 만들 때 함께
하는 편이 맞다.**

**결론을 내리지 않고 사용자에게 남긴 것이 셋 있다.** 3.5.1절의 출력 표현, 5절의 배치안, 그리고
3.6.3절의 결합 실행 신원 규약이다. 셋 다 사용자가 확정할 항목이고, 이 문서의 몫은 각 선택이 어떤
제약을 짊어지는지를 재는 데까지다. **선택지와 구현 결과와 되돌리기 난이도와 정해야 할 순서는
8절에 한자리로 모아 두었다.** 결정 셋은 배치안 B나 D를 고르는 경우에만 답이 필요하다.

**여기에 표준 문서를 쓰면서 닫힐 결정이 하나 더 붙는다.** Rise and Fall Three Methods의 작은 캔들
무리 개수이며, 고정 세 봉과 둘에서 다섯까지의 유한 범위 둘 가운데 하나다. 이 문서가 확인한 것은
어느 쪽을 골라도 창 길이와 상태 보관량이 유한하다는 것이고, 두 후보의 값은 4.2절에 적었다.

**확인이 필요한 패턴의 `min_history`는 이제 출력 표현과 무관하게 확정된다.** 3판은 표현이 정해져야
확정할 수 있다고 적었으나, 실행 불가능한 표현 하나를 후보에서 빼고 나면 남은 두 표현이 같은 값을
주기 때문이다. 4.3.4절에 그 유도를 적었다.

**표준이 문장으로 정해 주어야 구현이 어긋나지 않는 것이 셋 있다.** 6.2절에 목록으로 적었다.
평균 창이 그 봉을 포함하는지, 각 패턴의 확인 조건과 기한이 무엇인지, 그리고 매 봉 값을 낸다는
계약과 그 값들의 뜻이 무엇인지다. 첫째를 정하지 않으면 평균을 참조하는 패턴의 `min_history`가 한
봉씩 어긋난다. **3판이 이 목록에 두었던 추세 비교 봉과 가변 길이 상한 둘은 각각 결정 B와 결정 C로
이미 확정되어 있으므로 이번 판에서 지웠다.**

**이 문서의 범위 밖이지만 기록해 두는 것이 셋 있다.** 첫째, signal-service와 백테스트 Engine의
유한성 검사가 서로 달라 Bollinger %B가 두 경로에서 다르게 취급된다(3.2절). 둘째, 실행 Evidence에
표준 출처가 boolean으로만 남아 어느 절이었는지 복원되지 않는다(3.6.1절). 셋째, 웹 화면이 지표를
가격 축의 선으로만 그리고 사전형 지표는 아예 건너뛴다(3.5.1절). 셋 다 이번 작업이 만든 문제가
아니지만, 셋 다 패턴이 들어오는 순간 더 아프게 드러난다.
