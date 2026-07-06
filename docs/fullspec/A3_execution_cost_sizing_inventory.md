# A3 — 실행·비용·사이징 인벤토리 (wallet-service, 읽기 전용 분석)

> Phase A 분석 산출물. **목적 재정의(사용자 확정):** 체결·비용·사이징 코드는 wallet-service 것을 포함해 **전부
> 새로 구현**한다. legacy에서 가져오는 것은 **기본 수치값**(수수료율·펀딩 비율·MMR·간격 등)뿐이며 코드/로직은
> 이식하지 않는다. 근거: 현행 wallet 손익 계산이 라이브에서 거래소 실측과 정확히 맞지 않아 지속 동기화가
> 필요했으므로, 신뢰할 이식 원천이 아니라 재구현 대상이다. 모든 코드 사실은 `파일:심볼`(줄) 인용.

원천 리포(읽기 전용): `/Users/vincent/workspaces/CoinTrading/trading-system`. `services/backtest/`·
`services/replay/`는 읽지 않았다(제거 대상).

---

## 1. 제약사항·방향 (스코프 결정 포함)

**체결·비용·사이징 전부 새로 구현(사용자 확정).** 체결 매처·비용·사이징을 표준(net-of-cost·이산 펀딩·청산·
1R≤1%·체결 규칙)에 따라 새로 구현한다. wallet-service 현행 구현도 **재구현 대상**이며 코드/로직을 이식하지
않는다. legacy에서 가져오는 것은 **기본 수치값**뿐이다(아래 2) — config 기본값/시작값으로 harvest한다.

**재구현 근거.** 세 가지가 재구현을 뒷받침한다. (i) 표준이 `costs`(fee·slippage·funding·liquidation)·
`execution`·`sizing`을 골든 테스트를 갖춘 신규 정본 모듈로 독립적으로 요구한다. (ii) 현행 체결 코드는 라이브
인프라(`PriceCache`·폴링·WebSocket·`filled_at=now()`)와 엉켜 있어 순수 라이브러리로 이식하면 인프라 관심사를
끌고 들어온다 — 깨끗한 분리를 위해 재구현이 낫다. (iii) 현행 wallet 손익이 라이브에서 거래소 실측과 어긋나
지속 동기화(reconciliation)가 필요했다(구체 진단된 원인: 고정 펀딩 rate 등, 실측 rate 주입·회계 정합으로 교정)
— 부정확한 손익 코드를 그대로 이식하면 그 오차가 `core_lib`을 거쳐 백테스트·프로덕션으로 되돌아 흐르므로
이식이 오히려 위험하다. 표준과 이미 동일한 수학(청산식 `Entry×(1−1/lev+mmr)`·`fee=notional×rate`)은 버리는
게 아니라 아래 2·3에 그대로 재진술된다. 신 구현은 표준 수식 + 무결성 검사(회계 항등식 `cash+position=equity`·
비용 1회 차감·net-of-cost) + 실측 rate로 이 오차 클래스를 구조적으로 막는다.

**지침 대비 조정(기록).** 이식 원천 맵은 wallet `futures_calculator`·`slippage_calculator`·페이퍼 체결·사이징을
`core_lib.execution`/`costs`/`sizing`로의 이식(port)으로 표기하지만, **코드 이식이 아니라 "기본 수치값 harvest +
표준 기준 신규 구현"** 으로 재규정한다. 지표·전략과 같은 처리다. canonical 문서 표기 정리는 사람이 반영한다.

**이미 확정한 스코프 결정.** 트레일링 유보(소비 전략 없음, 아래 6); 집행 granularity = 전략 TF 캔들 수준 보수
판정(1분 하위 집행 피드 유보, 1분은 수집·리샘플 기준 — 손절·익절 동시 도달 시 보수적 손절 우선 OHLC-locked로
캔들 수준에서 결정론화); 1R = `|체결가 − 최초 고정 SL| × 수량`.

**보존 불변식.** `decision_ts < execution_ts`; net-of-cost(`x_net = x_gross − fee_entry − fee_exit −
slippage − funding − liquidation_penalty`, 비용 1회 차감); Decimal 단일 변환 관문(`Broker.submit()`에서
`Decimal(str(x))`+quantize 1회, `Decimal(float)` 금지); 사이징 1R≤1% 변동성 기반; 캔들 내 손절·익절 동시 도달
시 보수적 손절 우선(OHLC-locked); 펀딩 이산 정산(UTC 0/8/16 경계, 과거 실측 rate 주입); 청산 Isolated
`Entry×(1−1/lev+mmr)`; 회계 항등식 `cash+position=equity`.

---

## 2. legacy에서 가져올 기본 수치값 (config 기본값/시작값)

코드가 아니라 **수치값만** harvest한다. 새 구현은 이 값을 `CostModel`·실행/리스크 설정의 기본값으로 주입받는다.

| 항목 | 값 | 현행 위치 | 신 구현 처리 |
|---|---|---|---|
| 선물 수수료 maker / taker | 0.0002(0.02%) / 0.0005(0.05%) | `futures_paper_trading_service.py:69-72` | `CostModel` 주입 기본값 |
| 현물 수수료 | 0.0005(0.05%) | `paper_trading_service.py:30` | 기본값 |
| 슬리피지 호환 기본 | 선물진입 0.0005 / 현물진입 0.001 / 청산 0.0001 | `futures_paper_trading_service.py:69`·`slippage_calculator.py:16`·`sl_tp_monitor_service.py:90` | 호환 기본값 — TO-BE는 스프레드/2 + k·주문량/유동성 스트레스 모델로 대체 |
| 펀딩 정산 간격 | UTC `[0, 8, 16]` | `futures_paper_trading_service.py:41` (`FUNDING_INTERVALS_UTC`) | 간격 유지 |
| 펀딩 기본 rate | 0.0001(0.01%) | `futures_paper_trading_service.py:72` | fallback만 — 정규 경로는 과거 실측 rate 주입 |
| 청산 MMR | 0.004(0.4%, 최저 티어) | `DEFAULT_MMR` `margin_management_service.py:31` | Isolated 청산 기본값 |
| 포지션 사이즈 | `position_size_pct` 20.0% | 기본값 `core/config.py:210-221`(`futures_position_size_pct`); 사용 `wallet.py:calculate_available_for_investment:123-142` | pct 경로 기본값(호환) |
| 재량 축소 | 안티-마팅게일(`loss_position_min` 0.25 등), 변동성 고신뢰 임계 0.82 | `signal_processor_service.py:561-622` | 선택 반영 |
| 레버리지 | `wallet.default_leverage` | `futures_paper_trading_service.py:207` | 설정값 |
| 사후 슬리피지 경고 임계 | 50bp(0.5%) / 0.005 | `slippage_validator.py:39`·`slippage_calculator.py:19` | 참고(체결 차단 아님) |

---

## 3. 새 구현이 따르는 표준 (수식은 표준 기준 신규, legacy 로직 미이식)

`core_lib.execution`/`costs`/`sizing`은 아래 표준 수식·규칙을 새로 구현한다(legacy 절차 코드 이식 아님). 값은
위 2에서, 수식은 표준에서 온다.
- **수수료**: `fee = notional × rate`(maker/taker 구분, 기본 taker).
- **슬리피지**: 기본 bps + 스프레드/2 + k·(주문량/호가유동성) 스트레스(왕복 0.1~0.3%). 현행 곱셈-비율 고정값은
  호환 기본으로만.
- **펀딩**: 이산 정산 — UTC 0/8/16 경계를 보유로 지나는 포지션에 `notional × rate` 전액 부과, **과거 실측 rate를
  `DataFeed`로 주입**, 정산가 = 경계 포함 최소 가용 TF 캔들 시가.
- **청산**: `liq = Entry × (1 − 1/lev + mmr)`(Isolated 우선), last-price 캔들 극값 판정(청산 과대 = 보수 방향).
- **사이징**: 변동성 기반 `1R≤1%`(`risk_money`), pct 경로는 호환("framework 비준수" 플래그 의무),
  `turtle_unit`·`kelly.cap`. 1R = `|체결가 − 최초 고정 SL| × 수량`.
- **체결**: 결정 후 **next-bar-open**(현행 immediate는 gap), 캔들 수준 보수 최악 경로(동시터치 손절 우선),
  자기 체결 캔들 소급 검사 skip, 리버설 순서·갭 처리·체결가 기준 재산정.
- **회계**: `cash + position = equity`, 비용 1회 차감, reduce_only 마진 정확 반환.

---

## 4. `fill_timing` 확인

현행 동작은 전 경로에서 **IMMEDIATE(같은-틱)**, next-bar-open이 아니며 명명 설정도 아니다(`services/`에서
`fill_timing` grep 0건). 진입 즉시 체결 `_execute_order_in_session`(`futures_paper_trading_service.py:156-232`,
`filled_at=now()` `:170`), SL/TP 즉시 트리거 체결(`sl_tp_monitor_service.py:349-383`). → 신 구현의
`fill_timing`(`immediate`/`next_bar`) 주입형 + next-bar-open 모델은 gap(신규).

---

## 5. wallet 회귀·동기화 이력 (재구현 근거)

- **라이브 손익 부정확 → 지속 동기화(사용자 확인).** 현행 wallet 손익이 거래소 실측과 어긋나 계속
  reconciliation을 수행해야 했다(구체 원인: 고정 펀딩 rate 등 — 실측 rate 주입·회계 정합으로 교정). 이것이
  회계·손익 코드 재구현의 근거다.
- **회귀 blast radius.** wallet 테스트 `test_*.py` 71파일에 **1279개**(grep `def test_|async def test_`;
  개발 계획의 "1175"는 과소). 실행·비용·사이징·트레일링 커버 약 262개(이 중 트레일링·15분 폴링 45개는 유보
  스코프). `FuturesPaperTradingService`(선물 진입 체결+펀딩+청산 시뮬)에 전용 단위 테스트 없음(grep 0건) —
  선물 체결 경로 미검증.
- **채택 시 동작이 표면별로 갈린다.** 채택(기존 서비스가 core_lib 사용)의 효과는 표면마다 다르다. 지표·
  `analyze` 인소싱은 **동작 보존**(같은 계산값)이지만, **회계·손익·체결 표면은 동작 변경**(정확도 교정)이다.
  즉 "wallet 회귀 그대로 통과 = 동작 불변" 게이트는 회계 표면에서 성립하지 않으므로 골든 기준선을 재수립한다.
- **수용 기준(하방 인계).** 재구현본(회계·손익·체결)의 수용 기준은 **거래소 실측 대비 정확성**(정의된 허용
  오차 내에서 실측과 대사되는 골든)으로 명명하고, 채택·검증 단계의 필수 게이트로 인계한다. 이 정확성 검증은
  구↔신 backtest 대사(제거 대상이라 waive)와 **별개**다 — 대사 waive가 회계 정확성 검증까지 면제하지 않는다.

---

## 6. 트레일링 — 유보 (사용자 확정)

트레일링은 현재 스코프의 어떤 전략도 쓰지 않아 **유보**한다(위 1). 재도입 시 참조용으로 현행 사실만 압축 기록.
- 수식 위치: signal-service 순수 함수 `trailing_stop_calculator.py:TrailingStopCalculator`(`:30`, 상수
  `INITIAL_ATR_MULT=1.5`·`INITIAL_MIN/MAX_PCT=0.0045/0.0065`·`STAGE3_TRIGGER_R=3.0` 등). wallet 3곳 중복
  (`trailing_stop_update_service.py`의 `update_sub_candle`·`update_trailing_stop` + signal 원본), 현행 라이브
  주기 15분 폴링(`trailing_stop_background_service.py:27`, `INTERVAL_SECONDS=900`).
- 재도입 시: 단일 표준 `core_lib.strategy.trailing`로 새로 구현(값만 참조), 트레일링 평가 주기 파리티 기준 확정.
- **하방 전달**: 이후 Engine·포트 설계 단계는 이 유보를 입력으로 받아, DataFeed 포트 표면을 전략 TF 캔들로
  좁히고 1분 트리거-walk 시퀀스·트레일링 파리티 확정을 재유보로 처리한다(현 스코프에 소비 전략 없음).

---

## 7. 분류 (신규 구현 / 값 harvest / 유보 / 폐지)

**신규 구현 → `core_lib.execution`/`costs`/`sizing`:** 체결 매처·비용·사이징·회계 전부를 표준 수식·규칙(위 3)
기준으로 새로 구현. wallet 현행 코드는 이식하지 않는다.

**값 harvest(코드 아님):** 위 2의 기본 수치값을 config 기본값/시작값으로.

**유보:** 트레일링 기계장치(6)·1분 하위 집행 피드(집행은 캔들 수준 보수 판정). 재도입 시 계약·파리티 확정.

**폐지(재구현으로 대체):** wallet 현행 체결·비용·사이징·트레일링 코드 전부(`futures_paper_trading_service`·
`paper_trading_service`·`sl_tp_monitor_service`·`futures_calculator`·`slippage_calculator`·
`trailing_stop_update_service` 등); 라이브 인프라(`PriceCache`·폴링 루프·WebSocket·Binance 이벤트 핸들러·
`filled_at=now()` wall-clock); slippage_validator 사후 경고 게이트.

---

## 8. 블로커·확인 사항

- **`fill_timing` 설정 부재** — immediate 하드코딩(전 경로). 동작으로 immediate 확정, 설정 항목으로는 미존재.
- **라이브 손익 불일치·지속 동기화** — 현행 코드 재구현의 근거(사용자 확인). 신 구현은 무결성 검사(회계 항등식·
  비용 1회 차감)로 재발 방지.
- **선물 체결 경로 미검증** — `FuturesPaperTradingService` 전용 단위 테스트 부재.
- **비용 rate 불일치** — 진입 선물 0.05% / 현물 0.1% / 청산 0.01% 슬리피지 등. 새 구현은 `CostModel` 주입으로
  일원화(현행 값은 기본값 후보).
- **회귀 수치 1175 → 실제 1279** — 채택 시 회계·손익 표면은 동작 변경(정확도 교정)이라 골든 재수립 필요
  (지표·analyze 표면은 동작 보존).

---

## 9. Traceability (설계 표준 요구 ↔ 이 노트 절)

| 이 노트의 절 | 충족하는 표준 요구(이름) |
|---|---|
| 1, 3 | 체결은 결정 후행(`decision_ts < execution_ts`), next-bar-open은 신규 |
| 1, 3 | 모든 손익 net-of-cost, 비용 1회 차감, 회계 항등식 `cash+position=equity` |
| 2, 3 | 펀딩 이산 정산·과거 실측 rate 주입, 청산 Isolated `Entry×(1−1/lev+mmr)` |
| 1, 3 | 사이징 1R≤1% 변동성 기반, pct 경로는 framework 비준수 플래그, 1R=고정 SL 거리 |
| 1, 3 | 집행은 캔들 수준 보수 판정(동시터치 손절 우선 OHLC-locked) — 1분 집행 피드 유보 |
| 1, 6 | 트레일링 유보(소비자 없음), 재도입 시 단일 표준 신규 구현·파리티 확정 |
| 1, 3 | Decimal 단일 변환 관문(`Broker.submit`), `Decimal(float)` 금지 |
| 3, 7 | 환경별 관심사(체결·시계·비용·데이터피드)를 포트로 분리, 값 주입 |
| 5 | 라이브 손익 정확성 결함이 재구현 근거, 채택 시 동작 변경·골든 재수립 |

**정합성 확인 대상:** 체결·비용·사이징을 전부 새로 구현하되 legacy에서 기본 수치값만 harvest하는 경계가
표준(net-of-cost·이산 펀딩·청산·1R≤1%·체결 규칙)과 맞물리는지, 라이브 손익 불일치·동기화 이력이 재구현
근거로 명시됐는지, 유보(트레일링·1분 집행 피드)·캔들 수준 집행이 하드 불변식(동시터치 손절 우선·
decision<execution·net·회계 항등식·Decimal 관문)을 보존하는지. 이 노트는 이후 실행·Engine 설계 단계가
재인벤토리 없이 매처·비용·사이징을 표준 기준으로 새로 설계하고 harvest 값을 기본값으로 쓰도록 한다.
