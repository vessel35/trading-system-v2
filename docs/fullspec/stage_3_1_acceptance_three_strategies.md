# 3-1 단계 인수 시험: 온라인 전략 셋을 절차대로 옮겨 본 기록

이 문서는 2026-09-23에 3-1 단계의 목표 달성 여부를 검토하고, 그 검토를 시험하기 위해 온라인에서
수집한 암호화폐 선물 전략 셋을 전략 작성 절차(`author-strategy` skill)와 검산 절차
(`verify-strategy` skill)에 태워 본 결과를 적는다. **판단 근거와 결정 사항만 적는다.** 절차의
규칙은 `docs/strategy-authoring-contract.md`와 두 skill이 계속 소유한다.

작업은 `feat/3-1-acceptance-three-strategies` 브랜치에서 했고, 사용자 지시에 따라 질문 없이 판단해
진행했다. 절차가 원래 "묻는다"고 정한 자리마다 무엇을 어떤 근거로 정했는지를 4장에 모아 둔다.

## 1. 3-1 목표 달성 여부

`docs/roadmap-stage-3-1-plan.md` 12장의 완료 기준 열두 항목을 코드와 대조했다.

| 완료 기준 | 판정 | 근거 |
|---|---|---|
| 규범과 skill이 지표와 패턴을 포함하는 계열 정책으로 일관된다 | 달성 | 규범 1.1절과 4.4절이 지표와 패턴을 한 목록에 선언하도록 정하고, `develop-trading-strategies` skill이 규범을 표준으로 가리킨다. 이번 전략 셋은 그 선언 형식으로 등록·실행됐다 |
| 실행 능력 목록이 조회 가능하고 코드와 어긋나면 검사가 실패한다 | 달성, 갭 하나 | `core_lib.capabilities`가 있고 `trading_plugins.facts capabilities`로 조회된다. 항목마다 `verified_by`가 시험을 가리킨다. 다만 7장의 첫 발견처럼 "전략은 이번 봉의 series 값만 받는다"는 능력이 목록에 없다 |
| 신규 Adaptee가 두 실행 서비스에서 적재되고 Web API와 화면이 실행 가능 상태를 보인다 | 코드 경로는 달성, 화면 확인은 미실행 | 파일을 두는 것만으로 발견되었고(`facts deployed strategy`), Web API의 목록 응답은 시험(`test_runs_api.py`)이 새 전략 넷을 코드 레지스트리에서 내리는 것을 확인했다. 실제 화면 실행은 데이터베이스가 내려가 있어 하지 못했다(6장) |
| 일반 계열이 없는 전략과 Turtle 정책 조합이 실행된다 | 미확인 | 이번 전략 셋은 모두 series를 선언하므로 이 조합을 건드리지 않았다. 3-1 실행 계획 5장이 적은 Engine의 빈 `_indicator_specs` 문제는 이번 작업 범위 밖이다 |
| 등록 절차가 카탈로그와 `StrategyProfile`의 모든 작성 근거를 설명한다 | 달성 | `facts registration_sql`이 선언에서 등록 문장을 만들었고, 그 문장이 `init-scripts/signal-service/20260923/`에 그대로 남아 있다 |
| 읽기 전용 사전 점검이 코드·허용 목록·멱등 SQL의 불일치를 실행 전에 잡는다 | 달성 | `facts catalog_precheck`가 세 전략과 정책 하나를 모두 통과시켰고, 등록 파일과 선언의 일치는 시험 넷이 검사한다 |
| 공통 전략 규범 검사가 허용 목록 전체에 적용되고 결함 주입으로 검증된다 | 미달성 | `docs/fullspec/strategy_contract_suite_design.md` 첫 줄이 "아직 구현되지 않았다"고 적고 있고 코드에도 없다. 이번 전략 셋은 각자의 단위 시험으로 규범 9.1절의 성질을 개별 확인했다 |
| 계산 검증 방침이 독립 재계산·판단 대조·Evidence 검산·수행 시점을 포함한다 | 달성 | `verify-strategy` skill이 그 넷을 정하고, 5장의 검산이 그대로 수행됐다 |
| author와 verifier가 역할을 분리하고 구조화된 사용자 입력 종료 규약을 따른다 | 달성(형태 변경) | 두 역할은 서브에이전트가 아니라 skill 둘로 분리되어 있다(2026-08-10 하네스 결정에 따른 사용자 확정). 이번에는 사용자 지시로 질문 단계를 결정으로 대체했고 그 결정을 4장에 남겼다 |
| 두 샘플 문서의 재료·능력 판정이 사람 확인 결과와 같다 | 달성(기존) | `docs/fullspec/strategy_sample_verdicts.md`와 `test_strategy_sample_verdicts.py`가 이미 있다 |
| 기존 전략 판단, manual 호환 결과, 기본 정책과 Evidence가 달라지지 않는다 | 달성 | `vessel-reference`와 두 기존 정책 파일은 손대지 않았고, 관련 golden 시험이 그대로 통과한다 |
| pytest, mypy, ruff가 통과하고 건너뛴 검사 수를 함께 보고한다 | 달성(단서) | 5장 QA 표. 저장소 루트 전체 시험에서 web-api의 13건은 로컬 PostgreSQL이 없어 503을 받는 기존 실패이며 이번 변경과 무관하다 |

**요약.** 열두 항목 가운데 아홉은 달성, 하나(공통 규범 검사)는 미구현, 하나(빈 계열과 Turtle
조합)는 미확인, 하나(화면에서의 실행 확인)는 환경 때문에 미실행이다. 새 전략을 문서에서 코드·등록·
실행·검산까지 옮기는 기반은 동작한다.

## 2. 전략 수집과 선정

검색 도구(Perplexity)로 유튜브와 온라인 문서를 찾았고, 자막 발췌를 근거로 규칙을 정리했다. 원문
정리는 `docs/samples_for_strategy_agent/01.SuperTrend_EMA200_Flip.md`, `02.MACD_EMA200_ZeroLine.md`,
`03.BollingerRSI_MeanReversion.md`에 있다.

선정 기준은 셋이었다. 첫째, 규칙이 지표 값과 종가만으로 기계적으로 판정된다. 둘째, 쓰는 지표가
registry에 **같은 parameter 조합으로** 등록되어 있다. 셋째, 보호 규칙이 플랫폼의 정책 방식(변동성
입력 하나로 손절을 두는 정책)으로 표현된다.

| 전략 | 출처 | 지표 | 채택 |
|---|---|---|---|
| SuperTrend(10, 3) + EMA 200, 반대로 뒤집히면 청산 | 유튜브 aItIgJSvv-I (2026-02-28) | SuperTrend {period 10, multiplier 3.0}, EMA {200} | 채택 |
| MACD(12, 26, 9) + EMA 200 영점 교차, ATR 2.5배 손절과 1.5R 익절 | 유튜브 5CudhPUNtEk (2021-11-08) | MACD {12, 26, 9}, EMA {200}, ATR {14} | 채택 |
| Bollinger(20, 2) + RSI(14) 평균회귀, 중간 밴드 청산 | 유튜브 j2ESnjhT2no (2025-10-20) | Bollinger Bands {20, 2.0}, RSI {14} | 채택 |
| SuperTrend(8, 4.0) + EMA 200 | 유튜브 53yqW60SDPk (2026-07-03) | SuperTrend {8, 4.0} | 탈락: 그 parameter 조합이 registry에 없다(재료 부재) |
| EMA 5/20 + SuperTrend, EMA 3/20 + SuperTrend | 유튜브 c1_VEAzXlJQ, Good Crypto 블로그 | EMA {5}, {20}, {3} | 탈락: EMA는 9·21·55·200만 등록되어 있다 |
| EMA 9/21 교차 + RSI, 2% 고정 손절 | TradingView 스크립트 | EMA {9}, {21}, RSI {14} | 탈락: 고정 비율 손절은 변동성 입력이 없어 정책으로 표현되지 않는다(`money_management.volatility_inputs_per_policy`) |

탈락 셋은 절차가 "재료 부재"와 "능력 부재"를 다르게 보고하는지 확인하는 표본이 되었다.
SuperTrend(8, 4.0)은 계산이 이미 있는 지표의 새 조합이라 registry에 조합만 더하면 풀리지만, 그것은
전략 작업이 아니라 플랫폼 작업이므로 이번에는 하지 않았다.

## 3. 재료와 능력 대조에서 드러난 것

**등록된 조합은 `facts series`로 확인했다.** 세 전략이 쓰는 여섯 series는 모두 같은 이름과
parameter로 등록되어 있고, 지표마다 채택 근거(계산 표준의 절)가 붙어 있다.

**능력 목록과 부딪힌 자리는 넷이다.**

1. **교차 판정.** 세 출처 모두 "교차하면"(MACD 선이 시그널 선을 넘을 때, SuperTrend가 뒤집힐 때,
   가격이 밴드를 넘을 때)이라고 말한다. 그런데 Engine은 전략에 **이번 봉의 series 값만** 넘기고
   (`market_data["indicators"]`는 현재 봉의 값 하나뿐이다), 전략은 stateless여야 하므로 직전 봉의
   값을 기억할 수도 없다. 그러므로 교차 자체는 표현되지 않고, **상태**(이번 봉에 두 값이 어느 쪽에
   있는가)만 표현된다. 능력 목록에는 이 사실이 없다(7장).
2. **거래당 위험 2%.** MACD 출처가 2%를 쓰는데 플랫폼 상한은 1%다(`risk.max_risk_per_trade`).
3. **ATR 기간.** MACD 출처는 차트 기본 ATR을 썼다고만 말한다. manual 정책은 ATR(14)로 고정되어
   있다.
4. **손절 값이 없는 출처.** SuperTrend 출처와 Bollinger 출처는 손절 값을 주지 않는데, 플랫폼은
   정책이 `stop_loss`를 반드시 내도록 되어 있다.

## 4. 결정 사항

절차가 "묻는다"고 정한 자리와, 출처가 비워 둔 자리에 대한 결정이다. 번호마다 근거를 붙인다.

1. **교차 규칙은 상태 규칙으로 읽는다.** 무포지션인 봉에서 상태가 성립하면 진입하고, 보유 중인
   봉에서 상태가 반대가 되면 청산한다. 청산 쪽은 뒤집히는 봉이 곧 첫 반대 상태 봉이므로 원문과
   같다. 진입 쪽은 손절 뒤나 실행 시작 시점에 상태가 이미 성립해 있으면 교차 없이 들어간다는 점이
   원문과 다르다. 근거: 1번 능력 부재를 우회하지 않고 표현 가능한 가장 가까운 규칙이며, 차이는 세
   전략의 모듈 docstring과 이 문서에 적었다.
2. **실행 시간대는 1시간봉과 4시간봉을 지원한다고 선언하고 시험은 1시간봉으로 했다.** 근거: 세
   출처 모두 시간대를 정하지 않았고, 저장소의 기준 전략(`vessel-reference`)과 기존 시험이 1시간봉을
   쓴다. 4시간봉은 Good Crypto 출처가 스윙 거래에 권한 값이다.
3. **거래당 위험은 1%로 둔다.** 근거: 플랫폼이 1%를 넘는 값을 생성 단계에서 거부한다. 원문 2%와
   다르다는 사실을 MACD 문서에 남겼다.
4. **SuperTrend 전략과 Bollinger 전략의 보호는 새 정책 `signal_exit_atr`로 둔다.** 규범 5.3.1절이
   예시로 보인 "ATR 배수 손절만 두고 목표가는 두지 않는 정책"을 파일로 배포했다
   (`services/trading-plugins/trading_plugins/money_management/signal_exit_atr.py`). 손절 배수는 예시의
   기본값 2.5를 그대로 썼다. 근거: 두 출처는 청산을 신호(뒤집힘, 중간 밴드 도달)로 정하고 손절
   값을 주지 않으므로, 목표가를 만드는 manual보다 이 정책이 원문에 가깝다. 예시에 없던
   `requires_signal_exit = True` 선언을 더했다(7장 둘째 발견).
5. **MACD 전략의 보호는 manual 정책으로 두고 실행 설정에서 `atr_stop_multiple` 2.5, `reward_risk`
   1.5, `leverage` 1을 준다.** 근거: 출처가 손절 2.5 ATR과 익절 3.75 ATR(1.5배)을 말했다.
   leverage는 출처에 없어 1로 두었다(1% 위험과 2.5 ATR 손절이면 명목 금액이 자본을 넘지 않는다).
   이 전략은 신호 청산을 내지 않으므로 `supports_signal_exit = False`로 선언하고 manual만 지원한다.
6. **MACD의 영점 조건은 이번 봉의 MACD 선 부호로 읽는다.** 출처 2의 조건식 `macd[1] < 0`은
   직전 봉을 보지만(1번과 같은 사유로 불가) 교차 봉 직후에는 이번 봉의 부호가 거의 같다.
   출처 2가 200 EMA 판정에 저가·고가를 쓴 것은 따르지 않고 출처 1의 "가격"을 종가로 읽었다.
7. **Bollinger 전략의 RSI 문턱은 30과 70을 기본값으로 하는 전략 parameter로 둔다.** 근거: 출처 1은
   문턱을 설정값으로만 말하고 값을 주지 않으며, 출처 2와 다른 자료가 30·70을 쓴다. 값을 코드에
   묻지 않고 parameter로 열어 두어 사용자가 화면에서 바꿀 수 있게 했다. 두 문턱의 대소 관계는
   `cross_validators`가 검사한다.
8. **Bollinger 청산에 덧붙은 RSI 문턱은 넣지 않았다.** 근거: 출처 1 발췌에 그 값이 없고, 값 없이
   넣으면 지어낸 값이 된다. 중간 밴드 교차만으로 청산한다는 사실을 문서와 docstring에 남겼다.
9. **등록 문장은 `facts registration_sql`로 만들어 `init-scripts/signal-service/20260923/`에 두고,
   `init-scripts/06-init-signal-registry.sql`에 포함시켰다.** 이때 그 파일이 빠뜨리고 있던
   `20260810/01-create-money-management-registry.sql`도 함께 포함시켰다. 근거: 정책 등록 문장은 그
   표가 있어야 적용되고, 새 프로비저닝이 표 없이 서비스가 뜨는 상태를 만들면 안 된다.
10. **운영 데이터베이스에는 적용하지 않았다.** 근거: 절차가 도구로 하지 않는 일이고, 게다가
    로컬 PostgreSQL이 내려가 있었다(6장).
11. **백테스트는 Engine을 시험용 조립으로 돌려 확인했다.** 데이터베이스가 없어 실데이터 경로를
    쓸 수 없었으므로, `services/backtest-service/tests/test_document_sourced_strategies_engine.py`가
    결정적인 합성 1시간봉 560개(200봉 이상의 warm-up과 240봉 평가 구간)로 세 전략을 실제 Engine에
    태워 Evidence를 만든다. 이 시험은 3-1 실행 계획 5장이 요구한 "신규 전략 적재 회귀 검사"로
    저장소에 남긴다.
12. **손절 뒤 즉시 재진입은 막지 않았다.** 1번 결정의 결과로 생기는 동작이며, 막으려면 직전 거래를
    아는 규칙이 필요한데 `risk.between_trade_rules`가 그것을 지원하지 않는다고 기록하고 있다.

## 5. 수행 결과

### 5.1 만든 것

| 종류 | 파일 |
|---|---|
| 전략 기술 문서 셋 | `docs/samples_for_strategy_agent/01.SuperTrend_EMA200_Flip.md`, `02.MACD_EMA200_ZeroLine.md`, `03.BollingerRSI_MeanReversion.md` |
| 전략 셋 | `services/trading-plugins/trading_plugins/strategies/supertrend_ema200_flip.py`, `macd_ema200_zero_line.py`, `bollinger_rsi_reversion.py` |
| 정책 하나 | `services/trading-plugins/trading_plugins/money_management/signal_exit_atr.py` |
| 등록 문장 넷 | `init-scripts/signal-service/20260923/01`부터 `04`까지, `init-scripts/06-init-signal-registry.sql`에 포함 |
| 단위 시험 | `services/trading-plugins/tests/test_document_sourced_strategies.py`, `test_signal_exit_atr_policy.py` |
| Engine 회귀 시험 | `services/backtest-service/tests/test_document_sourced_strategies_engine.py` |
| 재생성한 OpenAPI 문서와 프런트 형 | `apps/web/src/api/openapi.json`, `schema.d.ts` (정책 하나가 늘어 실행 설정 union이 넓어졌다) |

### 5.2 Engine 실행 결과 (합성 경로, 자본 10,000, 수수료 편도 0.04%)

| 전략 | 정책 | 거래 수 | 청산 사유 | 최종 자본 | 무결성 검사 |
|---|---|---|---|---|---|
| supertrend-ema200-flip | signal_exit_atr | 9 | SIGNAL_EXIT 5, STOP_LOSS 3, END_OF_DATA 1 | 9,953.71 | 여섯 항목 모두 통과 |
| macd-ema200-zero-line | manual | 2 | STOP_LOSS 2 | 9,794.48 | 여섯 항목 모두 통과 |
| bollinger-rsi-reversion | signal_exit_atr | 5 | SIGNAL_EXIT 5 | 10,377.91 | 여섯 항목 모두 통과 |

성적은 합성 경로의 결과이므로 전략의 좋고 나쁨을 말하지 않는다. 같은 설정을 두 번 돌려 Evidence
hash가 같음을 시험이 확인한다.

### 5.3 검산 결과 (`verify-strategy` 절차, 독립 재계산)

검산 스크립트는 전략과 지표 구현을 import하지 않고, 계산 표준(`docs/references/technical_indicators_calc_spec.md`)의
정의로 값을 다시 계산해 Evidence와 견주었다. 48개 항목이 모두 통과했다.

- **series 재계산.** 평가 구간 240봉 전부에서 ATR(14), EMA(200), SuperTrend(10, 3), MACD(12, 26, 9),
  Bollinger(20, 2), RSI(14)의 재계산 값이 `INDICATOR_SNAPSHOT`과 상대 오차 1e-13 이내로 같다.
  SuperTrend는 표준이 첫 상태를 정하지 않아 첫 봉만 구현의 갈래를 따랐고, 평가 구간에서는 차이가
  없었다.
- **판단 손 계산.** 전략마다 첫 진입 봉에서 원문 규칙이 성립하고, 걸러진 봉(예: SuperTrend가
  상승인데 종가가 EMA 200 아래)에서 규칙이 막았음을 확인했다. 첫 청산 봉은 SuperTrend는 방향이
  뒤집힌 봉, Bollinger는 종가가 중간 밴드에 닿은 첫 봉이었다.
- **Evidence 산술.** 거래마다 총손익, 수수료(진입·청산 명목 금액의 0.04%), 순손익이 1e-8 이내로
  맞고, 손절 청산의 체결가는 진입 결정의 손절가와 같으며, 최종 자본은 초기 자본에 순손익 합을
  더한 값과 같다. 첫 진입의 손절 거리는 판단 봉 ATR(14)의 2.5배, 위험 금액은 100이다.
- **시각 무결성.** 판단 시각은 봉 마감 시각과 같고, 체결은 그 뒤 봉에서 일어나며, 진입 체결가는
  다음 봉 시가와 같다(합성 경로는 시가가 직전 종가와 같아 결정 봉 종가와도 같다).
- **선언 대조.** 실행에 쓰인 series 목록이 전략 선언에 정책의 ATR을 더한 것과 같고, 정책 id와
  판, 전략 판이 Evidence에 남아 있다.

한 세션이 구현과 검산을 모두 했으므로 같은 오독이 양쪽에 들어갈 위험은 남는다. skill이 말하는
독립 관문(다른 모델 계열의 코드 리뷰)은 6장에 적은 대로 이번에 닫지 못했다.

### 5.4 QA

| 검사 | 결과 |
|---|---|
| `services/trading-plugins` pytest | 121 통과, 2 deselected(통합 표시) |
| `services/backtest-service` 새 Engine 시험 | 4 통과 |
| `services/web-api` pytest | 120 통과, 13 실패(모두 로컬 PostgreSQL 부재로 503, 변경 전과 같음), 11 skipped |
| 저장소 루트 `pytest services` | 2100 통과, 13 실패(위와 같은 데이터베이스 부재 건), 65 skipped, 17 deselected |
| ruff check, ruff format --check | 통과 |
| mypy (`trading-plugins`, `backtest-service` 새 시험, `web-api`) | 통과 |
| `apps/web` `npm run typecheck`, `npm test` | 통과(139건) |

기존 시험 가운데 배포 목록을 고정해 둔 것들(`test_discovery.py`, `test_strategy_registry.py`,
`test_runs_api.py`, `test_policy_default_freeze.py`, `test_money_management_registry_availability.py`)은
새 배포 목록에 맞게 고쳤다. 고친 방식은 "첫 항목"이 아니라 `vessel-reference`를 이름으로 골라 보는
것으로, 배포가 늘어도 다시 깨지지 않게 했다.

## 6. 하지 못한 것과 그 이유

- **로컬 PostgreSQL이 내려가 있었다.** `localhost:5432` 연결이 거부됐고, Docker 데몬도 떠 있지
  않았으며, 프로젝트 설정이 Docker 명령을 거부한다(`permissions.deny`의 `Bash(docker:*)`). 서비스를
  띄우는 일은 절차가 권한을 묻도록 정한 자리이므로 하지 않았다. 그 결과 셋이 남았다. 등록 문장을
  데이터베이스에 적용하는 일, 실데이터로 백테스트를 돌리는 일, 화면에서 실행해 결과를 보는 일이다.
  **이어서 할 절차:** Docker Desktop을 띄운 뒤 `init-scripts/README.md`대로 데이터베이스를 올리고,
  `init-scripts/signal-service/20260810/01-create-money-management-registry.sql`과
  `20260923/01`부터 `04`까지를 `psql -d signal_db -v ON_ERROR_STOP=1 -f`로 적용하고, web-api와
  vite를 다시 띄워 화면에서 세 전략을 고른다.
- **다른 모델 계열의 코드 리뷰를 받지 못했다.** `mcp__codex-cli__review`를 한 번 불렀으나
  "The 'gpt-5.3-codex' model is not supported when using Codex with a ChatGPT account"로
  거부됐다(하네스 문서가 적어 둔 것과 같은 상태). Orca 워커 경로는 열지 않았다. 그러므로 push
  관문은 지나지 않았고 커밋은 브랜치에만 있다.
- **ClickUp 항목은 갱신하지 않았다.** 지시 범위 밖이다.

## 7. 플랫폼에 대한 발견

1. **능력 목록에 "전략은 이번 봉의 series 값만 받는다"가 없다.** 교차 규칙은 온라인 전략의
   대다수가 쓰는 표현인데, 지금은 `capabilities.py`를 읽어도 이것이 안 된다는 사실을 알 수 없다.
   `run.strategy_inputs`에 한 문장을 더하거나 별도 항목(예: `series.history_depth = 1`)을 두는 것이
   맞다. 이 갭 때문에 이번 전략 셋이 4장 1번의 결정을 필요로 했다.
2. **규범 5.3.1절의 예시 정책은 `requires_signal_exit`를 선언하지 않는다.** 규범 5.3.2절은
   목표가를 두지 않는 정책이 그것을 참으로 선언하라고 하는데, 예시 코드에는 없다. 발견 검사는
   base class의 기본값(거짓)도 bool이라 통과시키므로 예시를 그대로 배포하면 청산을 못 내는 전략과
   조합될 수 있다. 예시에 한 줄을 더해야 한다.
3. **`init-scripts/06-init-signal-registry.sql`이 자금관리 등록 표를 만들지 않았다.** 새
   프로비저닝에서는 표가 없어 발견된 정책 전부가 허용되는 상태로 떴다. 이번에 포함시켰다.
4. **`services/trading-plugins/pyproject.toml`에 `integration` 마커 등록이 빠져 있었다.** 패키지
   단독 실행이 수집 오류로 멈췄다. 이 브랜치의 첫 커밋으로 고쳤다.
5. **배포 목록을 고정한 시험이 다섯 파일에 있었다.** 전략이나 정책을 하나 더할 때마다 깨진다.
   이번에 고친 방식(이름으로 고르기)이 앞으로도 유지되어야 한다.
6. **정책을 배포하면 `apps/web/src/api/openapi.json`을 다시 생성해야 한다.** `test_openapi.py`가
   이것을 막아 주며, `npm run generate:api`가 그 일을 한다. 등록 절차 문서에 이 한 줄이 있어야 한다.
7. **Evidence 검산에 쓸 값의 단위.** 가격·수량·손익 열은 10^8 배 정수이고 `PORTFOLIO_PNL`의
   `total_equity`도 같다. 검산 절차 문서에는 이 사실이 없어 처음 한 번 헤맸다.
