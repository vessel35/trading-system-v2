# A1 — 지표 인벤토리 (signal-service, 읽기 전용 분석)

> Phase A 분석 산출물. **목적 재정의(사용자 확정):** 82종 지표는 지표 계산 표준 문서를 기준으로 전부 새로
> 구현하므로, legacy signal-service 지표 코드는 **계산식 이식 원천이 아니다.** 이 노트는 (1) 현행 지표
> **호출·소비 구조**(채택 시 변경 대상)와 (2) 첫 검증 전략의 **지표 커버리지**를 확정한다. 지표 자체는 표준
> 문서 기준으로 전부 새로 구현하며 기존 코드를 참조하지 않는다. 모든 코드 사실은 `파일:심볼`(줄) 인용.

원천 리포(읽기 전용): `/Users/vincent/workspaces/CoinTrading/trading-system`, `services/signal-service/`만.
`services/backtest/`·`services/replay/`는 읽지 않았다(제거 대상).

---

## 1. 제약사항·방향 (스코프 결정 포함)

**지표는 표준 문서 기준 신규 구현(사용자 확정).** 82종 지표의 수식·분류·구현 이견 고정 규약은 지표 계산
표준 문서 `technical_indicators_calc_spec.md`가 소유한다. 새 `core_lib.indicators`는 이 표준 문서대로 82종을
한 번만 구현하며(DRY), **legacy `domain/indicators/` 코드를 계산식 이식 원천으로 삼지 않는다.** legacy 지표
코드의 역할은 둘로 한정된다.
- (a) 현행 지표 **호출·소비 구조**를 파악해 채택(라이브 인소싱)의 변경 지점을 확정하는 것(아래 2).
- (b) 첫 검증 전략이 실제로 필요로 하는 지표·파라미터 **커버리지**를 확정해, 신규 구현이 이를 빠짐없이 덮게
  하는 것(아래 3).

**근거.** (i) 표준 문서가 수식을 소유하므로 계산식은 legacy가 아니라 표준 문서에서 온다. (ii) 현행 **라이브가
실제로 쓰는 지표 값은 외부 collector가 만든 것**이라(아래 2) in-code 계산식이 애초에 라이브의 표준이 아니다.
(iii) in-code 구현은 대부분 얇은 pandas 래퍼라 새 registry·증분 경로로 어차피 재작성되므로 이식 가치가 낮다.

**지침 대비 조정(기록).** 이식 원천 맵은 signal `domain/indicators/`를 `core_lib.indicators`로의 이식(port)
원천으로 표기하지만, **결과(82종을 표준 문서대로 한 번만 구현)는 유지**하되 legacy를 계산식 이식 원천이
아니라 호출 구조·커버리지 **참조**로 재규정한다. 최종 상태가 표준 문서와 동일하므로 지표 관련 불변식·산출물
요구는 그대로 충족된다. canonical 설계 문서의 해당 표기 정리는 사람이 반영한다.

**타임프레임은 전략이 결정.** 어떤 timeframe을 쓰는지는 전략이 정하며, 지표는 **전략 TF 캔들 마감**마다
계산한다. 1분은 **수집·리샘플 기준**(1분에서 상위 TF를 파생)일 뿐 지표 판단 주기가 아니다 — 1분 수집 범위·
사전계산 폐지 경계는 collector 내부화 인벤토리에서 다룬다.

**보존 불변식(신규 구현이 지킬 것).** 재귀형 지표(EMA·RMA·SAR·cumsum 등 상태 보유)는 확정 캔들로만 갱신
(`close_time ≤ 판단 시각`, 진행 중 캔들 금지); 계산은 float64(Decimal 변환은 지표 밖 체결 관문); DRY(82종 한
번); run이 실제 계산하는 지표는 설정이 결정(전략 선언 필요분 / 명시 리스트 / 82종 전량); 워밍업 seed·표준편차
분모 규약은 표준 문서가 통일(현행 in-code 규약 계승 아님).

---

## 2. 현행 지표 호출·소비 구조 (채택 변경 대상)

signal-service의 지표 계산·소비는 두 경로로 갈린다.

**활성 라이브 경로 = 외부 사전계산 + DB 읽기.** 외부 collector가 지표를 미리 계산해 `technical_indicators`
테이블에 넣고, 실행 드라이버가 `IndicatorLoader.load_latest`(`infrastructure/data/indicator_loader.py:56`)로
읽어 `indicator_mapper.build_market_data_from_db`(`application/services/indicator_mapper.py:13`)가 전략 입력
평평한 dict로 재구성해 `analyze`에 밀어 넣는다. 신선도 게이트 `check_freshness`(`indicator_loader.py:112`).
`{지표}_{기간}` 키 규약(`ema_9`·`rsi_14` 등)은 이 collector/mapper 계층에만 존재한다.

**비활성 in-code 경로.** 각 전략의 `calculate_indicators`가 `TechnicalIndicators`+`extended`를 직접 호출하는
경로는 라이브에서 **비활성**이다 — 실행 드라이버의 OHLCV 분기가 예외를 던진다(`strategy_executor.py:1053`,
"iloc ordering bug"). 즉 라이브가 실제로 돌리는 지표 값은 in-code 계산식이 아니라 collector 산출물이다.

**채택(라이브 인소싱) 변경 지점.** 외부 collector 사전계산 + `technical_indicators` 읽기 경로를 폐지하고,
**캔들 마감마다 `core_lib.indicators`로 증분(O(1)) 직접 계산**해 같은 dict 계약으로 `analyze`에 push하도록
바꾼다. 코드뿐 아니라 호출 계약(확정 캔들 트리거·매 캔들·OHLCV 순수 함수)까지 같아야 백테스트와 라이브 값이
갈리지 않는다. collector의 사전계산 로직 자체(폐지 대상)와 폐지 경계는 collector 내부화 인벤토리 소관.

---

## 3. 첫 검증 전략 지표 커버리지

첫 파이프라인 검증 전략은 VesselFluxGen2 개념(트레일링 제외)의 신규 구현이며, 그 판단은 공유 엔진
`AdaptiveRegimeStrategy` 계열의 지표에 의존한다. 새 82종 구현이 아래를 반드시 덮어야 한다(파라미터 포함).

| 지표 계열 | 파라미터 | 인용 |
|---|---|---|
| EMA | 9 / 21 / 55 / 200 | `adaptive_regime_strategy.py:161-170`, `indicator_mapper.py:247-278` |
| RSI | 14 | 동상 |
| Bollinger Bands | period 20, std 2.0 | 동상 |
| Stochastic | k 14, d 3 | 동상 |
| ATR | 14 | 동상 |
| 거래량 이동평균 | 20 | 동상 |

트레일링을 뺀 VesselFluxGen2 개념은 부모 격 VesselFlux처럼 ATR 기반 고정 SL/TP를 쓰며, 그 계산도 위 지표
(특히 ATR14) 위에서 이뤄진다 — 추가 지표 계열을 요구하지 않는다.

(참고: 다른 Vessel·비-Vessel 전략은 MACD·fractal·VWAP·volume_profile·delta·opening_range·parabolic_sar 등
추가 계열을 쓰나 첫 검증 경로가 아니다. 82종 표준이 이 나머지를 포함하므로 커버리지 필수 집합은 위 표다.)

---

## 4. 지표 구현 방침 — 전량 신규 (기존 코드 미참조)

82종 지표는 지표 계산 표준 문서 기준으로 **전부 새로 구현**하며 기존 signal-service 지표 코드
(`technical.py`·`extended.py`)를 참조하지 않는다. 계산식은 표준 문서에서 오므로 개별 legacy 구현을 이 노트에
기술하지 않는다. 첫 검증 전략 커버리지(위 3)는 82종 표준에 대해 확인됐으며, 82종 밖의 legacy 지표를 이후
이식 전략이 요구하면 그 전략 온보딩 시 `required_indicators` 선언으로 포착한다(별도 지표 인벤토리 불요).

---

## 5. 82종 구성 참고

82종 목록·수식·분류·구현 이견 고정(EMA seed·`adjust`·표준편차 분모 등)은 지표 계산 표준 문서가 소유하며 전량
신규 구현한다. 설계상 유의점 하나: 시장폭(breadth) 계열(McClellan Oscillator/Summation, TRIN)은 등락종목수·
거래량 같은 별도 입력 채널이 있어야 계산되며, 단일 심볼 OHLCV만으로는 입력이 없어 비활성 처리된다.

---

## 6. 분류 (신규 구현 / 참조 전용 / 폐지)

**신규 구현 → `core_lib.indicators`:** 82종 전량을 표준 문서 기준으로 한 번만. registry·`IndicatorSpec`·
`IndicatorState`(증분)·`contracts`·공용 프리미티브 독립화, vectorized·incremental 두 경로 포함.

**참조 전용(이식 아님):** 첫 검증 커버리지(3)·현행 호출 소비 구조(2). 커버리지 확인과 라이브 인소싱 변경 지점
파악용일 뿐 계산식을 이식하지 않는다.

**폐지:** 외부 collector 사전계산 + `technical_indicators` 읽기 경로(`indicator_loader`·`indicator_mapper`의
DB컬럼 매핑)·정적 메서드 네임스페이스 구조·전략에 얹힌 지표 파사드. backtest 지표 복제본은 미참조(제거 대상,
드리프트 대조 waive — 폐기 대상 코드와의 비교는 이식·커버리지 판단에 기여하지 않음).

---

## 7. 블로커·확인 사항

- **collector "~60 지표" 사전계산 집합**(주간 ATR 포함, `indicator_loader.py:37`)의 계산 원천은
  crypto-data-hub(collector)라 이 노트 범위 밖 — collector 내부화 인벤토리 소관. signal-service에서
  보이는 것은 소비 키 이름뿐.

---

## 8. Traceability (설계 표준 요구 ↔ 이 노트 절)

| 이 노트의 절 | 충족하는 표준 요구(이름) |
|---|---|
| 1, 4, 6 | 지표는 공통 라이브러리·DRY(82종 한 번만 구현), 구현은 전부·계산은 설정 |
| 1 | 재귀형 지표는 확정 캔들로만 갱신, 워밍업 seed·표준편차 분모 규약 통일, 계산은 float64·Decimal은 체결 관문 |
| 1, 2, 6 | 라이브 지표 인소싱(외부 collector 사전계산·`technical_indicators` 읽기 폐지, 증분 직접 계산) |
| 1 | 타임프레임은 전략이 결정, 지표는 전략 TF 캔들 마감 계산(1분은 수집·리샘플 기준) |
| 3 | 첫 검증 전략 지표 커버리지(신규 구현이 덮어야 할 집합) |
| 4, 5 | 지표는 전량 표준 문서 기준 신규 구현(기존 코드 미참조), 시장폭은 별도 입력 채널 필요 시 활성 |
| 6 | 폐기 대상 backtest 복제본 비참조 |

**정합성 확인 대상:** 신규 구현 커버리지 집합(3)이 "구현은 전부·계산은 설정" 전제와 맞물리는지, 그리고 호출
소비 구조(2)가 라이브 인소싱 채택 지점을 자기완결적으로 짚는지. 이 노트는 이후 지표 설계 단계가 표준 문서 +
이 커버리지·호출 구조만으로 82종 registry·증분 경로·인소싱을 설계하도록 한다.

## 9. 표준 지표 수 변경 기록 (2026-08-01)

위 본문이 적은 "82종"은 이 노트를 쓰던 시점의 표준 지표 수이며 그때의 결정을 그대로
남긴다. 그 뒤 표준이 늘었으므로 현재 수치를 여기에 따로 적어 둔다. 본문의 결정 서술을
사후에 고치면 무엇을 근거로 무엇을 정했는지가 사라지기 때문에 본문은 손대지 않는다.

TA-Lib 0.7.1이 제공하는 함수와 표준을 대조해 표준에 없던 7종을 더했다. TRIMA는 §1.11,
APO는 §2.28, BOP는 §2.29, IMI는 §2.30, NATR은 §3.11, ACCBANDS는 §3.12이고, Stochastic
Slow는 절을 새로 만들지 않고 §2.2가 Fast와 Slow를 별개로 세고 별개로 등록한다는 규약을
더하는 방식으로 처리했다. 그 결과 표준의 커버리지 집계가 **82종에서 89종**이 되었다.

따라서 본문에서 "82종"이라고 읽히는 자리는 모두 **현재 89종**으로 이해해야 한다. "지표는
표준 문서 기준 전량 신규 구현", "DRY(한 번만 구현)", "run이 계산하는 지표는 설정이 결정"
같은 방침 자체는 지표 수와 무관하게 그대로 유효하다.

구현 상태는 등록 84조합 / 81이름 / 표준 89종 중 81종이다. 남은 8종은 시장폭 3종(McClellan
Oscillator, McClellan Summation Index, TRIN/Arms)과 원저서 상수를 확보하지 못한 5종(QQE,
MAMA/FAMA, Roofing Filter, Sinewave/Instantaneous Trendline, Special K)이다. 시장폭 3종이
본문 1절과 7절이 짚은 "별도 입력 채널이 있어야 계산되는" 항목에 해당하며, 그 상태가
이번에도 바뀌지 않았다.

표준 문서의 정본 위치도 이때 바뀌었다. 지금은 저장소의
`docs/references/technical_indicators_calc_spec.md`가 정본이고, 개발지침 디렉터리의 같은
이름 파일은 그 저장소 파일을 가리키는 심볼릭 링크다. 개발지침 디렉터리에서 열어 고치면
실제로 저장소 파일이 바뀐다.
