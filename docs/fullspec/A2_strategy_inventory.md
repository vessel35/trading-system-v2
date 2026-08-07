# A2 — 전략 인벤토리 (signal-service, 읽기 전용 분석)

> Phase A 분석 산출물. **목적 재정의(사용자 확정):** 전략 코드는 이식하지 않고, 각 전략의 진입·청산 판단은
> 전략 작성자 소유(이 설계 스코프 밖)다. 플랫폼은 전략을 끼우는 **정책**(Adaptee Protocol·Adapter Manager·
> StrategyConfig)만 설계한다. 이 노트는 그 정책 설계에 필요한 (1) `analyze` 정책 형태, (2) 호출·소비 구조
> (채택 변경 대상), (3) config 스키마 패턴, (4) 전략 유니버스를 확정하고 첫 검증 전략을 기록한다. 트레일링은
> 유보(아래 5). 모든 코드 사실은 `파일:심볼`(줄) 인용.

원천 리포(읽기 전용): `/Users/vincent/workspaces/CoinTrading/trading-system`, `services/signal-service/` 기준.
`services/backtest/`·`services/replay/`는 읽지 않았다(제거 대상).

---

## 1. 제약사항·방향 (스코프 결정 포함)

**전략 판단 로직은 이식·확정 대상이 아니다(사용자 확정).** 설계 방침상 "어떤 신호로 진입·청산할지와 그 형태
(승률·손익비)는 각 전략의 책임이며 이 설계의 스코프 밖"이다. 따라서 각 전략의 게이트·필터·confidence 계산
같은 판단 내부는 **전략 작성자 소유**이며 플랫폼이 이식하거나 표준화하지 않는다. 플랫폼이 설계하는 것은
전략을 끼우는 정책뿐이다 — `StrategyAdapter`(typing.Protocol)·Adaptee·Adapter Manager·StrategyConfig.

**첫 검증 전략(사용자 확정).** 첫 파이프라인 검증은 **VesselFluxGen2 개념의 신규 구현**으로 하되, **코드를
이식하지 않고 트레일링을 제외한 개념만** 새로 구현한다. 트레일링을 빼므로 이 전략은 부모 격 VesselFlux처럼
**ATR 기반 고정 SL/TP**를 쓴다. 개념의 형태(regime 감지 → 추세/평균회귀 라우팅 → RSI·모멘텀·ATR 필터 →
ATR 기반 고정 SL/TP)는 검증 기준으로 요약하되, 정확한 임계값·confidence 튜닝은 전략 작성자 소유로 두어
기록·이식하지 않는다.

**타임프레임은 전략이 결정.** 전략은 자기 timeframe 캔들 마감에 판단·신호 생성한다(신호·지표는 전략 TF
캔들에서만 생성). 현행 라이브의 분당 폴링(`check_interval_minutes` 게이트 등)은 판단을 1분마다 강제하던
부가장치로, 신규 모델에서는 제거하고 전략 TF 캔들 마감 판단으로 되돌린다.

**지침 대비 조정(기록).** 이식 원천 맵은 signal `AbstractStrategy·Vessel·Registry·Factory·trailing`을
`core_lib.strategy`로의 이식으로 표기하지만, 판단 로직은 작성자 소유·스코프 밖이라 **코드 이식이 아니라 정책
설계**로 재규정하고 트레일링은 유보(아래 5)한다. Adaptee가 "현행 전략 구조 미계승·신규"라는 방침과 일치하며,
"첫 검증은 Vessel로"도 VesselFluxGen2 개념을 쓰므로 유지된다. canonical 문서의 표기 정리는 사람이 반영한다.

**보존 불변식.** Adaptee stateless·판단 전용(읽기·저장·루프 없음); look-ahead는 Engine 피드 경계로 통제
(전략은 미래 데이터를 스스로 당기지 않음); 판단 입력 = Engine이 push하는 사전 계산 지표의 평평한 dict
(라이브·백테스트 동일 형태·동일 호출 정책).

---

## 2. 이식하지 않는 현행 구조 (재설계 대상, 압축)

플랫폼 정책이 계승하지 않는 현행 골격. 정책 설계 입력으로만 기록한다.
- **base `AbstractStrategy`**(ABC, `domain/strategies/base.py:113`): 추상 `get_metadata`(`:135`)/
  `get_parameter_schema`(`:141`)/`analyze`(`:172`)/`calculate_indicators`(`:236`). **stateless 아님**
  (`self._data_loader` 보유·DB IO `load_ohlcv:288`·`load_latest_ohlcv:321`·`load_ohlcv_safe:425`), 지표
  계산에 결합(`calculate_indicators`). → Adaptee statelessness로 재설계, IO는 Engine/포트 소관.
- **상속 체인**: `AbstractStrategy → AdaptiveRegime → {VesselTitan, VesselFlux → VesselFluxGen2}`;
  `AbstractStrategy → VesselAlpha`; `AbstractStrategy → VesselVanguard`. `mixins/` 비어 있음(`__all__=[]`).
  → 상속 기반 공유를 Adaptee 조합(공유는 core_lib 순수 함수 호출)으로 대체.
- **Registry**(`registry.py:11`, 수동 등록 `main.py:84-99`)·**Factory**(`factory.py:12`, `create_from_db:79`)
  → Adapter Manager(생성·lifecycle·signal_db 레지스트리, 주입 포트 경유)로 재설계.
- **`indicator_mapper`** DB컬럼→입력 매핑 경로 → 지표 인소싱·Engine push로 대체(지표 인벤토리와 연동).

---

## 3. Adaptee 판단 정책 형태 (정책 설계 입력)

플랫폼이 Adaptee Protocol을 설계하려면 판단 **내부 로직**이 아니라 판단의 **정책 형태**를 알아야 한다.
- **시그니처**: `async analyze(market_data: Dict[str, Any], current_position: Optional[Dict]=None) ->
  TradingSignal`(Vessel 5종 공통). 입력은 `MarketData` 모델이 아니라 평평한 `Dict`(모델은 정의됐으나 미사용,
  `base.py:65`; 통일 TODO `base.py:188-195`).
- **입력 내용**: 사전 계산 지표의 평평한 dict(`ema_fast`·`ema_mid`·`rsi`·`atr`·`bb_*`·`close_lookback`·
  `current_price/close` + 매크로 `funding_rate`/`fgi`). look-ahead는 Engine이 통제.
- **출력**: `TradingSignal`(`base.py:35`) — `signal_type`(BUY=LONG/SELL=SHORT/HOLD)·`symbol`·`price`·
  `confidence`(0~1)·`timestamp`·`metadata`·`reason`, 선물 필드 `market_type`·`leverage`·`stop_loss`·
  `take_profit`. **판단만**(수량·방향 결정은 sizing/execution 소관).
- **순수성·예외 접점**: precomputed 분기는 판단 전용(DB·루프·저장 없음). 예외 접점 = 시계 읽기
  (`time_provider.now()`)와 OHLCV 분기의 `calculate_indicators`(라이브 비활성). 이식 시 시각은 시계 포트,
  지표는 Engine push로 외부화되고 판단 정책 형태만 남는다.
- **포지션 입력**: 현행 드라이버는 `analyze(market_data=...)`만 호출하고 `current_position`을 넘기지 않는다
  (`strategy_executor.py:1040`). 포지션 입력 정책은 플랫폼 설계에서 확정.

---

## 4. 호출·소비 구조 (채택 변경 대상)

실행 드라이버 `strategy_executor.py`가 전략을 구동하는 흐름 — 채택 시 core_lib import로 치환될 구조.
- **인스턴스**: `StrategyFactory.create_from_db`(`:464`).
- **판단 주기**: 전략 TF 캔들 기준. 현행엔 분당 폴링 게이트 `check_interval_minutes`(`:477`)가 있으나 신규
  모델에서 제거 — 판단은 전략 TF 캔들 마감에 이뤄진다.
- **지표 피드**: `IndicatorLoader.load_latest`(`:953`) → `indicator_mapper.build_market_data_from_db`(`:974`)
  → 매크로 병합(`:985`) → `analyze(market_data=...)`(`:1040`). 신규: 지표는 core_lib 증분 계산으로 push.
- **신호 흐름**: `signal_id` 생성 → metadata Decimal→float(`:595`) → signal_db `SignalRepository.create`
  (`:629`, `session.begin_nested()` savepoint) → HTTP 전송 `send_signal_to_service`(`:1104`).

---

## 5. 트레일링 — 유보 (사용자 확정)

트레일링은 현재 스코프의 어떤 전략도 쓰지 않아(첫 검증 전략이 트레일링 제외) **유보**한다. 트레일링 계산기·
파리티 기준은 트레일링을 쓰는 전략이 도입될 때 확정한다.
- **현행 사실(유보 대상, 재도입 시 참조)**: 트레일링 수식은 signal-service 순수 함수
  `trailing_stop_calculator.py:TrailingStopCalculator`(`:30`)에 있고, `analyze`에서 이를 호출하는 것은
  VesselFluxGen2뿐(`vessel_flux_gen2_strategy.py:216-264`)이며 결정을 signal metadata로 방출한다. wallet이
  상태 지속(`TrailingState`) + stage 수식 재구현을 갖는 3곳 중복(실행·비용 인벤토리에서 상세).
- **유보 근거**: 소비자가 없는 트레일링 기계장치(계산기·1분 워터마크 파리티)를 지금 설계하면 자기완결성만
  떨어진다. 재도입 시 단일 표준 `core_lib.strategy.trailing`로 3곳 중복을 통합하고 파리티 기준을 확정한다.
- **지침 대비 조정(기록)**: 트레일링을 core_lib 공유 함수로 두는 방침과 트레일링 평가 주기(1분 워터마크) 확정을
  **유보**로 재규정한다. 트레일링은 하드 불변식 목록에 없으므로 유보가 어떤 불변식도 약화하지 않는다.

---

## 6. 분류 (신규 정책 / 참조 전용 / 유보 / 폐지)

**신규 → `core_lib.strategy`:** `StrategyAdapter`(Protocol)·Adaptee·Adapter Manager·StrategyConfig(해석·검증·
직렬화·JSON Schema)·ResolvedConfig(불변). `required_indicators`의 `{name, params}` 파라미터화 선언(현행 비정형
라벨 대체). 전략 프로파일 선언(family·기대 승률/손익비 범위·tail_shape·holding_horizon·primary_metric 등)과
소비 규칙. **첫 검증 Adaptee = VesselFluxGen2 개념(트레일링 제외)의 신규 구현.**

**참조 전용(이식 아님):** 판단 정책 형태(3)·호출 소비 구조(4)·config 스키마 패턴(아래 7)·전략 유니버스(7).
각 전략의 판단 내부와 파라미터 값은 전략 작성자 소유.

**유보:** 트레일링 기계장치(5).

**폐지:** `AbstractStrategy` 상속 골격·상태 보유 base(데이터 로드·DB IO·지표 파사드·`calculate_indicators`
결합)·`StrategyRegistry`/`StrategyFactory` 현행 구현·`MarketData` 미사용 모델·`indicator_mapper` DB 경로.

---

## 7. 전략 유니버스·config 패턴·확인 사항

- **유니버스**: Vessel 5종(Alpha·Titan·Flux·FluxGen2·Vanguard) 외에도 `AbstractStrategy` concrete가 다수
  존재한다(`fractal_breakout`·`alex_sr`·`heikin_ashi_trend`·`fabio_scalper`·`parabolic_rsi` 등; `trend_estimation/a1`은 미독). 읽은 전략은 동일
  Adaptee 판단 전용 패턴(순수 `analyze`)을 따르며, 미독 디렉터리도 같은 정책 형태를 노출하는지 확인 대상이다.
  Adapter Manager·레지스트리는 소수가 아니라 **다수 concrete를 수용**하도록 크기를 잡는다.
- **config 스키마 패턴**: 각 `*Parameters`가 `StrategyParameters`(`base.py:103`, `extra="forbid"`)를 상속하고,
  전략이 스키마를 선언하며 값은 호출자가 소유한다(예: `ema_fast: int = Field(9, ge=3, le=30)`,
  `adaptive_regime_strategy.py:35`). StrategyConfig는 이 패턴(선언=Adaptee, 해석·검증·기본값 병합·`extra=forbid`
  =Config)으로 설계한다. 전략별 파라미터 값 전량은 작성자 소유라 나열하지 않고 패턴만 이식 근거로 둔다.
- **선언 메타**: `required_indicators`·`supported_timeframes`·`min_history_periods`가 `get_metadata()`로
  선언된다(예: VesselFluxGen2 계열 `required_indicators=["ema","rsi","bb","atr","stochastic","volume"]`,
  `min_history=210`, `supported_timeframes=["1h","4h"]`; base 기본값 `["1h"]`을 concrete가 override).
- **미정리 항목(플랫폼 정책에서 확정)**: `current_position` 미전달, `MarketData` 미사용, base 비-stateless —
  현행 사실로만 기록하며 Adaptee 정책 설계에서 정리한다.
- **`trend_estimation/a1` 하위 디렉터리 미독** — 이 전략 인벤토리의 판단 범위 밖으로 판단해 읽지 않았다.

---

## 8. Traceability (설계 표준 요구 ↔ 이 노트 절)

| 이 노트의 절 | 충족하는 표준 요구(이름) |
|---|---|
| 1, 3, 6 | Adaptee=판단 전용(읽기·저장·루프 없음), 진입·청산 엣지는 각 전략(작성자) 소유·스코프 밖 |
| 1, 3 | look-ahead는 Engine 피드 경계로 통제, 입력=Engine push 평평한 dict, Adaptee stateless |
| 1, 4 | 타임프레임은 전략이 결정, 전략 TF 캔들 마감 판단(분당 강제 판단 제거) |
| 2, 6, 7 | 현행 전략 구조(상속·registry·factory) 미계승·재설계, Adapter Manager·StrategyConfig 분리 |
| 6, 7 | 파라미터 스키마 선언=Adaptee·해석=Config, 전략 프로파일 신설, `{name,params}` 지표 선언 |
| 5 | 트레일링은 core_lib 공유 순수 함수를 호출(상속 아님) — 소비자 없어 유보, 재도입 시 단일 표준 통합 |
| 3 | 판단 출력 정책=TradingSignal(수량·방향 없음, 판단만) |

**정합성 확인 대상:** 정책 설계 입력이 "Adaptee=판단 전용" 원칙에 부합하는지 — 판단 정책 형태·호출 구조·config
패턴은 참조로, 판단 내부·파라미터 값은 작성자 소유로, Protocol·Manager·Config·프로파일은 신규로, 트레일링은
유보로 갈랐다. 이 노트는 이후 전략 설계 단계가 재인벤토리 없이 Adaptee 정책·Manager·Config를 설계하도록 한다.
