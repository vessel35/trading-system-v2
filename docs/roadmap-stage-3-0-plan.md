# 3-0 진행 계획 — 지표 추가 개발

이 문서는 3-0 단계의 실행 계획이다. 단계 전체의 위치는 `docs/roadmap-stage-3.md`에 있고,
현재 스프린트 목표는 `.claude/OBJECTIVE.md`에 있다.

계획의 근거는 2026-07-31에 수행한 세 갈래 조사다. 표준 문서 82종과 현재 구현의 대조, 지표
하나를 추가하는 작업 단위의 실측, 그리고 그 둘을 받은 범위·순서 제안이다. 조사는 저장소를
수정하지 않았다.

## 1. 출발점 (조사로 확인한 사실)

표준 82종 가운데 **구현되어 등록까지 된 것은 6종**이다. RSI, Stochastic, ATR, Bollinger Bands,
%B, BandWidth다. EMA와 Volume SMA도 구현되어 있으나 표준이 이 둘을 §0 공유 프리미티브로 분류하므로
82종 집계에는 들어가지 않는다.

미구현 76종 가운데 **지금 구현할 수 있는 것은 64종**이다. 남는 12종은 두 갈래다. 시장폭 3종
(McClellan Oscillator, McClellan Summation, TRIN)은 등락종목수와 거래량 채널이 있어야 계산되는데
레지스트리가 그 입력을 값으로 넘기는 경로를 갖고 있지 않다. §12에 오른 9종은 상수와 초기화 규칙이
구현체마다 갈려 표준 문서 자신이 "추측하지 않고 남긴다"고 적어 둔 항목이다.

**지표 하나를 추가하는 비용**은 소스 두 파일(계열 모듈과 registry)과 테스트 두 파일에 걸치고,
새 단언 두세 건을 쓰며, **기존 단언 여섯 곳을 함께 고치는 것**이다. 마지막 항목이 규모를 정한다.
40종이면 240회의 반복 수정이 된다.

**없는 공유 프리미티브는 여섯 개**지만 실제로 지표를 막는 것은 HL2 하나이고, 그것이 일곱 종
(Awesome Oscillator, Accelerator, Fisher Transform, SuperTrend, EMV, Alligator, Gator)을 막는다.

## 2. 확정된 결정

| 결정 | 선택 |
|---|---|
| 구현 범위 | **구현 가능한 전부(74종)**. 2026-07-31 사용자 지시로 40종에서 넓혔다. 아래 7장 참고 |
| 중간 점검 | **해제**. 27종 지점에서 3-1을 시험한 뒤 정하기로 했던 조건은 범위 재지정으로 무효가 되었다 |
| 웨이브 0 | 포함한다. 지표를 늘리지 않는 계산 기반 정리를 먼저 한다 |
| 값 검증 기준 | 외부 라이브러리 대조. 표준 §13이 교차대조 대상으로 명시한 TA-Lib, pandas-ta, Tulip Indicators, TradingView |

> 2·3·4·5장은 40종 범위로 세운 원래 계획이며 웨이브 0부터 3까지의 실제 경과를 담고 있다.
> 범위를 넓힌 뒤의 계획은 7장에 있다.

값 검증 기준을 정해야 했던 이유는 **표준 문서에 수치 예시가 하나도 없기 때문**이다. "예:"로 나오는
것은 파라미터 값 제안이지 계산된 기댓값이 아니다. 기준이 없으면 벡터 경로와 증분 경로가 서로 같다는
것만 확인하게 되고, 두 경로가 같은 오해를 공유하면 검증이 그대로 통과한다.

**대조 방법(2026-07-31 확정).** 일회용 가상환경에 TA-Lib 0.7.1, Tulip Indicators 0.4.0,
ta 0.11.0을 설치해 결정적 캔들 300개에 대한 기준값을 한 번 뽑고, 그 값을
`services/core-lib/tests/test_indicator_reference_values.py`에 고정했다. 저장소와 CI는 이
라이브러리들에 의존하지 않는다. 새 지표를 더할 때만 같은 환경을 다시 만들어 값을 뽑는다.
지표마다 어느 라이브러리에서 왔는지 파일에 적는다. TA-Lib에 없는 것은 Tulip(Awesome
Oscillator)이나 ta(TSI)에서 가져왔고, 밴드 파생(%B·BandWidth)은 TA-Lib의 밴드에 표준 §3.10
수식을 적용해 만들었다.

**외부 라이브러리는 계산식의 원천이 아니라 대조군이다.** A1 인벤토리가 확정한 "legacy 코드를 계산식
이식 원천으로 삼지 않는다"와 충돌하지 않는다. 계산식은 표준 문서에서 오고, 외부 라이브러리는 그렇게
구현한 값이 맞는지 비교하는 용도로만 쓴다. 값이 어긋나면 표준 문서를 다시 읽어 원인을 밝히고,
라이브러리를 따라 구현을 바꾸지 않는다. 이 구분을 지키지 않으면 표준이 소유권을 잃는다.

**대조에서 드러난 규약 차이.** 열다섯 조합 중 열하나는 상대오차 1e-9 이내로 일치했다. 나머지
넷(ATR, MACD 세 출력, TSI)은 **시드 창 규약이 달라 초반에 벌어졌다가 수렴한다.** ATR은 §0.6이
첫 True Range를 `H_0 − L_0`으로 정의하는데 TA-Lib은 첫 봉을 건너뛴다. MACD는 §2.4가 두 EMA를
각자의 기간으로 시딩하는데 TA-Lib은 둘을 느린 기간에 함께 시작한다. TSI는 ta 라이브러리가 첫
관측값으로 시딩하는데 §0.3은 단순평균으로 시딩한다. 셋 다 표준이 §0.3에서 "플랫폼 간 초반 오차의
주원인"이라 적어 둔 바로 그 차이이며, 재귀 평활이 시드를 기하급수적으로 잊으므로 간격이 닫힌다.
ATR은 4.1e-4에서 1.6e-10으로, MACD는 2.1e-5에서 0으로, TSI는 3.1e-1에서 3.5e-8로 줄었다.
테스트는 값의 일치가 아니라 **간격이 줄어드는지**를 확인한다. 줄지 않으면 수식이 실제로 다른 것이다.

## 3. 웨이브

| 웨이브 | 새 지표 | 누적 | 내용 |
|---|---|---|---|
| 0 | 0종 | 0 | 계산 기반 정리 |
| 1 | 6종 | 6 | 의존성 허브 |
| 2 | 6종 | 12 | 허브의 직계 파생 |
| 3 | 15종 | 27 | 부품이 필요 없는 나머지 별 다섯. **중간 점검 지점** |
| 4 | 9종 | 36 | 널리 쓰이는 별 넷 |
| 5 | 4종 | 40 | 시프트와 규칙형 |

**웨이브 0 — 계산 기반.** HL2 프리미티브를 더해 일곱 종의 막힘을 푼다. 증분판 프리미티브(단순
이동평균, 지수이동평균, Wilder 평활, 구간 최고·최저, 누적, 변화율)를 도입한다. 지금 증분판이 있는
프리미티브는 표준편차 하나뿐이고 나머지는 지표마다 같은 알고리즘을 다시 쓴다. 0으로 나눌 때의 공통
규약과 헬퍼를 정한다. 등록 수를 고정한 단언을 목록 대조형으로 바꾸되 지금 구조의 이점(지표를 소리
없이 늘리거나 줄일 수 없다)을 잃지 않는 형태여야 한다. 레지스트리의 최소 이력과 상태 클래스의 최소
이력을 직접 대조하는 단언을 더한다.

**웨이브 1 — 의존성 허브 6종.** MACD, DEMA, TSI, CCI, Awesome Oscillator, A/D Line. 이 여섯이
다른 지표의 입력이 된다. 먼저 오지 않으면 파생 지표가 부품을 자기 안에 다시 구현하게 되어 "같은
지표를 두 번 구현하지 않는다"는 불변식을 어긴다.

**웨이브 2 — 허브의 직계 파생 6종.** TEMA, SMI, PPO, Accelerator Oscillator, Chaikin Oscillator,
CMF. 웨이브 1의 산출물을 그대로 쓰므로 붙이는 비용이 가장 작다.

**웨이브 3 — 부품이 필요 없는 별 다섯 15종.** KAMA, Stochastic RSI, TRIX, CMO, Williams %R,
Ultimate Oscillator, Fisher Transform, KST, Coppock Curve, OBV, Force Index, DMI/ADX 시스템,
Aroon, Elder Ray, Parabolic SAR. 이 웨이브가 끝나면 별 다섯 22종 중 21종이 끝난다(남는 하나는
Ichimoku). **여기서 멈추고 3-1을 실제로 돌려 본다.** 전략 개발 Agent가 지표 부재로 멈추는 일이
얼마나 생기는지 확인한 뒤 웨이브 4와 5의 진행을 정한다.

**웨이브 4 — 널리 쓰이는 별 넷 9종.** Donchian Channel, SuperTrend, Chandelier Exit, Ulcer Index,
MFI, HMA, ZLEMA, Vortex Indicator, Choppiness Index. 이미 있는 ATR과 구간 최고·최저와 True Range를
소비하는 쪽이다. Donchian을 여기 둔 이유는 저장소에 Turtle 사이징이 이미 있고 진입 규칙이 쓸 지표만
비어 있기 때문이다.

**웨이브 5 — 시프트와 규칙형 4종.** Ichimoku, Alligator, Gator Oscillator, Fractals. 계산이 어려운
것이 아니라 **어느 봉에 어떤 값을 싣느냐**를 먼저 정해야 해서 마지막이다. 현재 구조는 한 봉에 값
하나를 싣고 반환 길이가 입력 캔들 수와 같아야 하는데, Ichimoku의 선행·후행 스팬과 Alligator의 세
선은 봉을 옮기고 Fractals는 중앙봉 이후 두 봉이 지나야 확정된다. 정렬 규약을 하나로 정한 뒤 네 종에
같이 적용한다.

## 4. 보류

**§12의 9종은 이번 범위 밖이다.** 넷(VIDYA, Keltner Channel, Schaff Trend Cycle, Klinger Volume
Oscillator)은 표준 본문에 한쪽 수식이 완결되어 있어 정의를 고르면 구현할 수 있고, 다섯(QQE,
MAMA/FAMA, Roofing Filter, Sinewave와 Instantaneous Trendline, Special K)은 원저서의 상수가 있어야
한다. 40종 어디에도 들어가지 않으므로 이번 스프린트에서는 결정하지 않아도 된다. 범위를 넓히는 경우에만
정의 채택과 표준 문서 갱신을 먼저 하고 구현한다. **코드가 표준보다 앞서지 않는다.**

**시장폭 3종은 미구현으로 유지한다.** 레지스트리가 입력 채널의 이름만 다루고 값을 넘기는 경로가
없다는 것이 코드로 확인됐다. 별도 입력 채널을 만드는 일은 지표 구현이 아니라 데이터 경로 설계다.

## 5. 남은 결정 (해당 웨이브 전까지)

- 0으로 나눌 때 무엇을 반환할 것인가. 웨이브 0에서 정하면 이후 지표가 그 규약을 따른다. 엔진이
  워밍업 이후 유한값을 요구하는 것과 표준 §0.11이 NaN 유지를 권하는 것이 충돌한다.
- 표준이 기본 기간을 주지 않은 14종의 조합을 어떤 규칙으로 정할 것인가. 조사는 단일 조합만 등록하고
  값을 저장소가 이미 쓰는 기간에서 고르는 규칙을 제안했다.
- 시프트를 쓰는 지표의 정렬 규약. 웨이브 5 전에 필요하다.
- TRIX의 배율과 SMI의 파라미터 등 §12 표 밖의 이설 항목. 웨이브 3에 걸린다.
- 82종 집계 밖의 변형(NATR, Cutler RSI, Stochastic Slow) 등록 여부. 지표 수를 늘리는 것이 아니라
  기존 지표에 출력을 더하는 일이라 비용이 작다.

## 6. 이 계획과 별개로 확인된 결함

이미 등록된 Bollinger Bands의 `percent_b`는 밴드 폭이 0이면 NaN을 낸다. 백테스트 엔진은 워밍업
이후 지표 값이 유한하지 않으면 실행을 중단시킨다. 가격이 완전히 평탄해 표준편차가 0이 되는 구간을
만나면 볼린저를 쓰는 실행이 그 자리에서 실패한다. 3-0과 무관하게 이미 존재하는 문제이므로 별도
changeset으로 다룬다. 웨이브 0의 "0으로 나눌 때의 공통 규약"이 이 문제의 해법을 포함하게 된다.

## 7. 범위 재지정 — 구현 가능한 전부 (2026-07-31)

사용자가 3-0의 목표를 "구현 가능한 모든 지표를 구현하는 것"으로 다시 정했다. 40종이라는
숫자와 웨이브 3의 중간 점검은 이 지시로 폐기됐다.

### 7.1 남은 것과 빠지는 것

웨이브 3까지 끝난 시점의 등록 상태는 **36 조합 / 33 이름 / 표준 82종 기준 33종**이다.
이름 33개 가운데 EMA와 Volume SMA는 §0 프리미티브라 82종 집계 밖이고, Bollinger Bands
하나가 82종 집계에서는 밴드·%B·BandWidth 셋으로 세어진다. 그래서 남은 것은 49종이다.

그 49종 가운데 **41종을 구현하고 8종을 남긴다.** 목표 등록 상태는 **82종 중 74종**이다.

빠지는 여덟 종은 이유가 둘로 갈린다. **시장폭 3종**(McClellan Oscillator, McClellan
Summation Index, TRIN/Arms)은 등락종목수와 상승·하락 거래량이 있어야 계산되는데 레지스트리에
그 입력을 값으로 넘기는 경로가 없다. 만드는 일은 지표 구현이 아니라 데이터 경로 설계다.
**원저서 상수가 없는 5종**(QQE, MAMA/FAMA, Roofing Filter, Sinewave/Instantaneous Trendline,
Special K)은 §12가 "추측하지 않고 남긴다"고 적어 둔 항목이다. QQE의 트레일링 밴드 락 규칙,
MAMA/FAMA의 Hilbert 6-tap 계수, Roofing Filter의 컷오프와 SuperSmoother 계수, Special K의
항별 기간과 가중치표는 표준 본문에 아예 없고, Sinewave는 그 계수를 쓰는 §8.1에 종속된다.
상수를 지어 넣으면 표준이 계산의 소유권을 잃으므로 구현하지 않는다.

**§12의 나머지 4종은 구현한다.** VIDYA, Schaff Trend Cycle, Klinger Volume Oscillator,
Keltner Channel은 §12 표에 올라 있지만 **표준 본문에 한쪽 수식이 완결되어 있다.** 본문에
적힌 수식을 채택하고, 고른 갈래와 버린 갈래를 `pinned_impl`과 아래 7.4에 남긴다. 표준
문서 자체는 고치지 않으므로 "코드가 표준보다 앞서지 않는다"는 원칙과 충돌하지 않는다.

### 7.2 병렬 작업을 막고 있던 구조 (웨이브 0-B)

지표를 계열별로 나눠 동시에 구현하려면 한 파일을 두 작업자가 건드리지 않아야 한다. 지금
구조는 그 조건을 어긴다. `build_default_registry()` 하나가 818줄에 모든 등록을 담고,
외부 대조 기준값도 `test_indicator_reference_values.py` 한 파일에 모여 있다. 계열이 달라도
같은 파일의 같은 영역을 고치게 되므로 충돌이 확정적이다.

그래서 지표를 늘리기 전에 등록과 기준값을 계열별 모듈로 나눈다. 지표 수도, 등록 목록도,
계산 결과도 달라지지 않는 순수한 구조 변경이며, 달라지지 않았다는 것을 테스트로 확인한다.
41종이 더해지면 등록 파일이 2000줄을 넘게 되므로 이 분리는 병렬화와 무관하게도 필요하다.

**분리 결과.** 등록은 `core_lib/indicators/specs/` 아래 계열별 모듈로 옮겼고, 각 모듈이
자기 계열의 `SPECS` 튜플 하나를 소유한다. `registry.py`는 여섯 계열을 고정된 목록으로
모아 등록만 하므로 지표가 늘어도 바뀌지 않는다. 테스트가 계열에 대해 기대하는 것도 모두
`tests/indicator_reference/` 아래 계열별 모듈로 옮겼다. 한 모듈이 자기 계열에 대해 일곱
가지를 손으로 적는다. 등록 조합 목록(`IDENTIFIERS`), 지표 이름 목록(`NAMES`), 그 등록이
표준 82종 가운데 몇 종을 차지하는지(`STANDARD_SYSTEMS`), 표준이 미정의로 남긴 출력
(`UNDEFINED_OUTPUTS`), 그리고 외부 대조의 세 표(`REFERENCE`·`CONVERGING`·`UNCOMPARED`)다.
패키지의 `__init__.py`가 여섯 모듈을 합쳐 지금까지와 같은 합본을 만들고, 테스트는 합본과
살아 있는 레지스트리를 비교만 한다.

기대 목록은 어느 것도 레지스트리에서 유도하지 않는다. 자기가 검사할 대상에서 값을 읽어
오는 목록은 어떤 레지스트리와도 일치하므로 아무것도 잡아내지 못한다. 손으로 적혀 있기
때문에 지표를 소리 없이 늘리거나 줄이면 합본과 레지스트리가 어긋나 실패한다.

**담당별 소유 파일.** 아래 표의 세 열이 한 담당이 지표를 더할 때 고치는 파일 전부다.
계산 모듈에 함수와 증분 상태 클래스를 쓰고, 등록 모듈에 `IndicatorSpec`을 더하고, 기대
모듈에 위의 일곱 가지 가운데 해당하는 것을 적는다. 담당끼리 파일이 겹치지 않는다.

| 담당 | 계산 모듈 | 등록 모듈 | 기대·기준값 모듈 |
|---|---|---|---|
| 추세 | `core_lib/indicators/trend.py` | `core_lib/indicators/specs/trend.py` | `tests/indicator_reference/trend.py` |
| 모멘텀 | `core_lib/indicators/momentum.py` | `core_lib/indicators/specs/momentum.py` | `tests/indicator_reference/momentum.py` |
| 변동성 | `core_lib/indicators/volatility.py` | `core_lib/indicators/specs/volatility.py` | `tests/indicator_reference/volatility.py` |
| 거래량·방향성 | `core_lib/indicators/volume.py`, `core_lib/indicators/strength.py` | `core_lib/indicators/specs/volume.py`, `core_lib/indicators/specs/strength.py` | `tests/indicator_reference/volume.py`, `tests/indicator_reference/strength.py` |
| 시스템 | `core_lib/indicators/systems.py` | `core_lib/indicators/specs/systems.py` | `tests/indicator_reference/systems.py` |

경로는 모두 `services/core-lib/` 기준이다. 거래량·방향성 담당만 두 계열을 함께 맡으므로
파일이 두 벌이다. **지표를 등록하는 경로에는 이제 여러 담당이 함께 고치는 파일이 없다.**

**아무도 고치지 않는 파일.** `core_lib/indicators/registry.py`(`IndicatorSpec`과
`IndicatorRegistry` 정의, 그리고 여섯 계열을 모으는 `build_default_registry()`),
`core_lib/indicators/specs/__init__.py`(계열 이름 여섯 개를 적은 곳),
`core_lib/indicators/primitives.py`, `tests/indicator_reference/__init__.py`(합치는 곳이며,
계열 모듈이 무엇을 선언해야 하는지를 `CategoryModule` 프로토콜로 적어 둔 곳),
`tests/indicator_reference/series.py`(대조용 300봉 생성기와 표본 지점 100·200·299,
수렴 판정의 잡음 바닥값), `tests/test_indicator_registry.py`(합본과 레지스트리를 비교하는
곳), `tests/conftest.py`가 여기에 해당한다. 특히 `series.py`를 고치면 여섯 모듈의 기준값이
한꺼번에 무효가 되므로 손대지 않는다.

**계열을 빠뜨리거나 목록을 어긋나게 두면 조용히 통과하지 않는다.** 네 가지 경우를 실제로
만들어 확인했다.

첫째, 담당이 지표를 등록하고 자기 기대 목록을 고치지 않으면
`test_registry_contains_required_coverage_and_pinned_authority`와
`test_each_category_registers_exactly_what_its_own_module_expects`를 포함해 여섯 개가
실패한다. 둘째, 반대로 기대 목록에서 한 줄을 지우면 같은 방식으로 다섯 개가 실패한다.
셋째, 기대값 패키지의 합치기에서 계열 하나를 빠뜨리면 그 계열의 등록이 기대 목록에서
사라지고, 표준 82종 집계도 어긋나며, 그 계열의 출력이 외부 대조에서 미대조로 남아 여덟
개가 실패한다. 넷째, 등록 패키지의 모으기에서 계열 하나를 빠뜨리면 레지스트리 자체가
작아져 일곱 개가 실패한다.

여섯 계열 이름은 `test_the_registry_is_exactly_the_six_category_modules_gathered`가
문자열 그대로 못 박아 두고, 등록 패키지와 기대값 패키지가 정확히 그 여섯을 덮는지 확인한다.
`specs/__init__.py`는 그와 별개로 import 시점에 각 spec의 `category`가 그 spec을 담은
모듈과 일치하는지 확인하고 어긋나면 예외를 낸다.

**등록 경로 밖에 남은 것 하나.** 지표마다 표준이 따로 진술하는 성질을 확인하는 관계
테스트는 아직 `tests/test_indicator_parity.py`에 함수 단위로 들어간다. 다섯 담당이 각자
함수를 덧붙이게 되므로 파일은 겹치지만, 서로 다른 함수를 파일 끝에 더하는 형태라 충돌은
함수 단위로 정리된다. 등록 목록처럼 한 집합을 여럿이 나눠 고치는 것과는 성질이 다르다.

### 7.3 계열별 분담 (동시 진행)

| 담당 | 모듈 | 지표 | 수 |
|---|---|---|---|
| 추세 | `trend.py` | T3, HMA, ZLEMA, ALMA, VIDYA, McGinley Dynamic, Guppy GMMA | 7 |
| 모멘텀 | `momentum.py` | Connors RSI, QStick, Chande Forecast Oscillator, DeMarker, DPO, Schaff Trend Cycle, Relative Vigor Index(Ehlers), Laguerre RSI, Pretty Good Oscillator, Center of Gravity Oscillator | 10 |
| 변동성 | `volatility.py` | Keltner Channel, Donchian Channel, SuperTrend, Chandelier Exit, Ulcer Index, Relative Volatility Index(Dorsey), Chaikin Volatility, Mass Index | 8 |
| 거래량·방향성 | `volume.py`, `strength.py` | MFI, EMV, Klinger Volume Oscillator, NVI, PVI, Vortex, Choppiness Index, Random Walk Index | 8 |
| 시스템 | `systems.py` | Ichimoku Kinko Hyo, Alligator, Fractals, Gator Oscillator, Market Facilitation Index, Elder Impulse System, TD Sequential, Woodies CCI | 8 |

Center of Gravity Oscillator는 표준에서 §8 Ehlers 계열에 있으나 계산이 순수한 오실레이터라
모멘텀 담당이 가져간다. 다섯 담당은 서로 다른 모듈만 고치므로 동시에 진행할 수 있다.

### 7.4 담당 사이에 공통으로 지켜야 하는 것

**미래 봉을 쓰지 않는다.** 시프트를 쓰는 지표에서 t 시점 출력이 t 이후 데이터에 의존하면
안 된다. Ichimoku의 선행 스팬은 t 시점에 t−26에서 계산한 값을 싣는 형태여야 하고, 후행
스팬은 t 시점에 미래 종가를 알 수 없으므로 같은 방식으로 지연시켜 싣는다. Fractals는 중앙봉
이후 두 봉이 지나야 확정되므로 t 시점에 t−2가 프랙탈이었는지를 낸다. 정렬 규약은 시스템
담당이 하나로 정해 네 종에 같이 적용하고, 규약과 그 이유를 이 문서에 남긴다.

**규칙형 지표의 출력 형태.** TD Sequential, Elder Impulse System, Fractals, Market
Facilitation Index는 수치가 아니라 상태를 낸다. 상태를 숫자로 인코딩하고 그 대응을
`pinned_impl`에 적는다. 인코딩을 지어내는 것이 아니라 표준이 정의한 상태 집합을 그대로
숫자에 대응시키는 것이다.

**정의가 갈리는 네 종의 채택 기록.** VIDYA는 CMO 기반과 표준편차 비율 기반이 갈리고,
Keltner는 원형(단순이동평균과 고저범위)과 현대형(지수이동평균과 ATR)이 갈리며, Schaff Trend
Cycle은 내부 평활 상수가, Klinger Volume Oscillator는 cm 초기화와 절댓값 처리가 갈린다.
넷 다 표준 본문에 적힌 갈래를 채택하고, 버린 갈래가 무엇인지를 함께 적는다.

**대조군은 계산식의 원천이 아니다.** 값이 외부 라이브러리와 어긋나면 표준 문서를 다시 읽어
원인을 밝힌다. 라이브러리를 따라 구현을 바꾸거나 대조를 맞추려 상수를 끼워 넣지 않는다.
대조 대상이 아예 없는 지표는 이유를 적어 미대조로 남긴다.

