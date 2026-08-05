# 캔들스틱 패턴 모듈 — 분석과 이력

이 디렉터리는 TA-Lib 기반 캔들스틱 패턴 포트의 분석 기록과 폐기된 전제의
이력을 담는다. 활성 계산 표준은 `docs/references/candlestick_pattern_calc_spec.md`가
소유한다.

## 현재 전제

캔들스틱 패턴 61종의 계산 원본은 TA-Lib v0.7.1 C 소스다. TA-Lib은 더 이상
외부 대조군만이 아니다. 포트와 표준 문서가 TA-Lib v0.7.1과 어긋나면 우리 쪽이
틀린 것이다.

다만 런타임과 CI는 TA-Lib 라이브러리에 의존하지 않는다. TA-Lib은 고정 포획값을
새로 만들 때만 쓰며, 저장소의 테스트는 이미 포획된 raw integer fixture와 Python
포트를 비교한다.

기존 지표 표준과의 경계는 그대로 유지한다.

- 패턴은 **89종 지표 집계에 합류하지 않는다.**
- 패턴은 **자체 표준 문서**를 갖는다.
- 패턴은 **자체 레지스트리**를 갖고 `DEFAULT_REGISTRY`에 등록되지 않는다.

## 파일

| 파일 | 현재 의미 |
|---|---|
| `analysis-1-original-sources.md` | Nison, Morris, Chesler 원전 조사 기록. 현재 계산 기준이 아니라 TA-Lib 전환 전 조사 이력이다 |
| `analysis-2-corelib-structure.md` | core-lib 하부구조 조사와 배치안 검토 기록. 일부 전제는 TA-Lib 전환 전 상태다 |
| `review-1.md` ~ `review-4.md` | 분석 문서에 대한 교차 검토 기록 |
| `deprecated-candlestick-pattern-calc-spec-pre-talib.md` | TA-Lib 기준으로 대체된 수작업 판정 명세의 폐기 이력 |

## 원전 조사 기록의 위치

원전은 세 편이다.

- Steve Nison, *Japanese Candlestick Charting Techniques*, 2판(2001)
- Gregory L. Morris, *Candlestick Charting Explained*, 3판(2006)
- Daniel L. Chesler, "Trading False Moves with the Hikkake Pattern", *Active Trader*,
  2004년 4월호

이 원전 조사는 `analysis-1-original-sources.md`에 보존되어 있다. 현재 표준 문서는
그 내용을 다시 복사하지 않고 필요한 경우 이 파일을 가리킨다.

## 사용자가 확정한 결정의 현재 상태

**결정 A — 수치 척도의 출처.** 현재는 원전 기반 수치와 자체 규약이 아니라
TA-Lib v0.7.1 소스로 대체됐다. 출처는 저장소, 태그, 커밋 SHA, C 파일 경로로
활성 표준 문서에 고정한다.

**결정 B — 직전 추세.** 무효다. 10기간 EMA로 직전 추세를 패턴 내부에서 판정한다는
전제는 수작업 판정 규칙의 일부였고, 현재 TA-Lib 포트의 계약이 아니다.

**결정 C — 조건 충돌 처리.** 무효다. 원전 문장 사이에서 좁고 엄격한 쪽을 고르는
방식은 폐기됐다. 현재 판정 기준은 TA-Lib `src/ta_func/ta_CDL*.c` 소스다.

**결정 D — 갭.** 무효다. 실체 갭과 고저 갭을 원전 해석으로 고정하던 전제는
폐기됐다. 현재는 각 TA-Lib C 함수가 쓰는 비교를 그대로 따른다.

**결정 E — 배치.** 유효하다. 패턴은 `core_lib/patterns/`에 자체 `PatternSpec`과
`PatternRegistry`를 두며, 실행기가 읽는 공통 `SeriesSpec` 형태를 만족한다.

**결정 F — 출력 표현.** 원시 정수 계층과 네 키 어댑터 계층으로 재정의됐다.
TA-Lib raw integer `0`, `±80`, `±100`, `±200`이 동등성 기준이고, 기존 소비자는
패턴 이름, `_dir`, `_strength`, `_confirm` 네 키를 읽는다.

**결정 G — 신원 규약.** 유효하다. 지표와 패턴의 이름 집합은 서로소여야 하며,
패턴 레지스트리는 지표 `DEFAULT_REGISTRY`와 별도로 유지된다.

## 검증

현재 검증은 TA-Lib v0.7.1로 포획한 국면 일곱 22000봉 raw integer fixture를
기준으로 한다. 포획값은 `services/core-lib/tests/pattern_reference/talib_signals.py`에
고정되어 있고, 포획이 덮지 못한 rare branch는 수제 OHLC 입력 테스트로 보완한다.

활성 표준 문서의 캔들 설정 표와 61종 대응표는 테스트가 파싱해 코드 레지스트리와
비교한다. 표준 문서의 표가 `DEFAULT_CANDLE_SETTINGS`, `TALIB_FUNCTIONS`, 포트의
워밍업·사용 설정, 포획 관측값과 갈라지면 테스트가 실패한다.

## 남은 위험

TA-Lib 원본 C 소스 스냅샷은 저장소에 없다. 외부 소스를 들이는 것은 별도 결정이
필요하므로 현재 표준은 출처 커밋을 고정하고, 원본 접근이 사라질 위험만 기록한다.
