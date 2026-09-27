# 전략 공통 계약 검사 설계

이 문서는 발견된 모든 전략에 적용할 공통 계약 검사의 최종 설계다. 2026-09-25 사용자 결정으로 검증
층별로 나눠 구현한다. **전략 단위 층은 2026-09-25에 `services/trading-plugins/tests/test_strategy_contract_suite.py`로
구현됐다**(3·4·5·7·8·9·10·12절과 6절의 방어적 검사). **Engine 조합 층(6절의 시간 무결성 주 검사,
지원하지 않는 조합의 Engine 수준 거부)은 2026-09-26에
`services/backtest-service/tests/test_strategy_contract_engine_layer.py`로 구현됐다**(16장). 두 층은
서로를 대신한다고 표시하지 않으며, 각 모듈의 docstring이 자기 층의 한계를 적는다.

## 1. 목적

`docs/strategy-authoring-contract.md`는 결정성, 정책 독립성, 시간 무결성, 금지된 의존,
선언과 실제 접근의 일치, 유효한 청산을 전략의 공통 성질로 요구한다. 현재 저장소에는
`VesselReference` 단위 검사, 기반 클래스 검사, 발견 검사와 Engine 회귀 검사가 있지만,
전략 패키지에서 발견된 클래스에 이 성질 전부가 자동으로 적용되는 공통 검사 묶음은 없다.

이 검사는 전략의 수익성을 평가하지 않는다. 신규 전략과 기존 전략이 플랫폼 정책을 계속
지키는지를 CI에서 검증한다.

## 2. 방식 상태와 적용 경계

현재 발견되는 `VesselReference`는 목표 방식인 `DecisionIntent`를 반환하고 Engine은
`MoneyManagementPolicy`를 조합한다. `StrategyAdapter.analyze()`는 이행 기간의 legacy
`TradingSignal`도 허용한다.

방식 사례표는 각 전략의 방식 종류를 명시해야 한다. 신규 전략은 `DecisionIntent`를 요구하고,
legacy 전략을 유지해야 한다면 사례표에 호환 경계임을 명시한다. 공통 검사가 legacy 반환형을
신규 전략의 정상 방식으로 넓혀서는 안 된다.

검사는 배포되는 런타임이 아니라 저장소의 테스트 계층에 둔다. 서비스 코드나 패키징 대상이
`.claude` 정의에 의존하지 않게 하고, Agent를 사용하지 않은 수동 변경에도 똑같이 적용한다.

## 3. 발견 목록과 방식 사례표

검사는 `trading_plugins.strategies`에서 발견한 클래스 전체를 매개변수화한다. 패키지에 전략을
더하면 자동으로 검사 대상이 늘어나야 한다.

발견 목록만으로는 유효한 인스턴스와 판단 시나리오를 만들 수 없다. 따라서 테스트 전용 방식
사례표를 두고 발견 목록과 전략 id 집합이 정확히 같음을 먼저 검사한다. 각 사례는 다음 정보를
명시한다.

1. 사례는 스키마 검증을 통과하는 대표 파라미터 설정을 제공해야 한다.
2. 사례는 지원 timeframe과 시장 종류를 제공해야 한다.
3. 사례는 진입 방향별로 필요한 결정적 캔들 국면과 지표 및 패턴 값을 제공해야 한다.
4. 사례는 진입 뒤 넘길 포지션 상태와 같은 방향의 청산 증거를 제공해야 한다.
5. 사례는 지원 정책, 기본 정책과 capability 기대값을 제공해야 한다.
6. 사례는 목표 방식인지 명시적인 기존 호환 방식인지 밝혀야 한다.

필수 파라미터의 중간값을 추측하거나 현재 전략의 기본값이 앞으로도 존재한다고 가정하지 않는다.
전략 파일만 추가하고 사례표를 빠뜨리면 그 자체로 검사 실패다.

## 4. 결정성 및 불변성 검사

결정성은 서로 다른 결함을 잡도록 두 갈래로 검사한다.

첫째, 같은 인스턴스에 완전히 같은 입력과 같은 포지션을 반복해서 전달하고 결과가 같은지 본다.
호출 횟수나 인스턴스 내부의 실행 상태에 의존하면 이 검사가 실패한다.

둘째, 같은 설정으로 만든 독립 인스턴스들이 같은 입력 열 전체에서 같은 결정 열을 만드는지
본다. 클래스 전역 상태나 인스턴스 사이의 숨은 공유가 있으면 이 검사가 실패한다.

각 호출 전후에는 전략 인스턴스가 허용되지 않은 실행 상태를 얻지 않았는지, 입력 캔들과 지표
사전과 포지션과 불변 설정이 변하지 않았는지를 함께 확인한다. 테스트용 결함 전략으로 호출 횟수
의존과 클래스 전역 상태가 각각 검출되는지도 입증한다.

## 5. 자금관리 정책 독립성 검사

전략 판단은 자금관리 정책이 달라져도 같아야 한다. 이 검사는 생산 입력의 모양을 그대로
재현한다.

manual 정책을 조합한 입력에는 전략 선언과 함께 strategy timeframe의 ATR이 들어간다. Turtle
정책을 조합한 일반 전략 입력에는 전략이 선언한 계열만 들어간다. Turtle의 일봉 `N`은 별도
일봉 조회로 계산되어 정책에 전달되므로 전략의 `market_data["indicators"]`에 넣지 않는다.

두 입력은 같은 시각, 같은 전략 설정, 같은 캔들과 같은 전략 소유 계열 값을 가져야 한다. 서로
다른 것은 정책 때문에 추가되는 strategy timeframe 계열뿐이다. 전략이 자기 선언 밖의 ATR을
읽으면 결정 열이 달라져 검사가 실패한다.

지원하지 않는 정책은 성공 경로로 꾸미지 않는다. 사례표에 선언된 지원 정책과 capability를
검사하고, 지원하지 않는 조합은 `AdapterManager`가 명시적으로 거부하는지를 조합 검사에서
확인한다.

## 6. 시간 무결성 검사

전략 단위 검사만으로 미래 참조가 없음을 완전히 증명할 수 없다. 생산 Engine은 각 판단 시점에
확정 접두와 현재 지표 값만 전달하므로, 같은 생산 입력을 두 번 재생하는 접두 비교에는 애초에
미래 값이 없다.

시간 무결성의 주 검사는 Engine 조합 계층에 둔다. 각 판단에서 캔들 마감 시각과 사용한 지표 및
패턴의 시각이 판단 시각보다 늦지 않고, 판단 시각이 실제 체결 시각보다 빠른지를 확인한다.
Turtle 일봉은 판단 시각 전에 완전히 닫힌 가장 최근 일봉만 사용해야 한다.

전략 단위 계층에는 방어적 검사를 둔다. 현재 시점 뒤의 데이터만 독립적으로 바꾸고 그 이전
결정이 같은지 본다. 이 검사는 입력에 노출된 미래 부분을 읽는 결함을 잡지만, Engine 조합의
시간 보증을 대체하지 않는다는 한계를 검사 설명에 적는다.

## 7. 금지된 의존 검사

금지된 의존은 정적 검사와 실행 중 감시를 함께 사용한다.

정적 검사는 전략 구현체와 전략 전용 도우미의 import를 재귀로 따라간다. 공용 `core_lib`
경계에서는 멈추고, 서비스 패키지, 데이터베이스 드라이버, 네트워크 모듈, 파일 입출력 모듈과
하위 프로세스 모듈을 거부한다. 타입 검사 전용 import는 실행 의존과 구분한다.

실행 중 감시는 파일 열기, 소켓과 HTTP 연결, 데이터베이스 연결, 하위 프로세스 생성과 벽시계
호출을 실패시킨다. 동적 import와 주입된 호출자와 저장소 도우미 뒤에 숨은 입출력을 정적 검사
하나에 맡기지 않는다.

## 8. 선언과 실제 접근의 일치 검사

전략에 전달하는 계열 사전을 추적 가능한 Mapping으로 감싸 실제 읽기를 기록한다. 추적기는
`__getitem__`뿐 아니라 `get`, 포함 여부, 순회, `keys`, `values`, `items`와 복사 경로를 다뤄야
한다. 전략 설정 접근도 같은 방식으로 기록한다.

선언하지 않은 계열이나 파라미터를 읽으면 실패한다. 선언했지만 관찰된 사례에서 한 번도 읽지
않은 항목은 낭비 또는 실행되지 않은 분기일 수 있으므로 보고하되, 한 시나리오의 관찰만으로
곧바로 정책 위반으로 단정하지 않는다. 필수 사례 전체에서도 관찰되지 않았다면 사례가 부족한지
선언이 과한지를 사람이 구분할 수 있게 진단을 남긴다.

동적 접근 기록은 실행된 경로의 증거일 뿐이다. 사례표가 모든 가능한 분기를 증명한다고 주장하지
않는다.

## 9. 진입과 청산의 대응 검사

각 방식 사례는 의도적으로 진입 증거를 만들어야 한다. 진입이 우연히 나오지 않았다는 이유로
검사를 건너뛰지 않는다.

긴 방향 진입 사례는 긴 포지션을 전략에 넘긴 뒤 그 포지션을 닫는 청산 결정을 요구하고, 짧은
방향 진입 사례는 짧은 포지션을 넘긴 뒤 그 포지션을 닫는 청산 결정을 요구한다. 한 방향에서만
나온 청산을 다른 방향의 증거로 인정하지 않는다.

`supports_signal_exit` 선언과 실제 청산 증거도 맞아야 한다. Turtle 정책을 지원하는 전략은
신호 청산 capability와 실제 청산 사례를 모두 제공해야 한다.

## 10. 시그니처와 추가 공통 성질

`runtime_checkable` Protocol의 `isinstance` 검사는 메서드 이름의 존재를 확인하지만 정확한
시그니처를 보장하지 않는다. 공통 검사는 `get_metadata()`, `get_parameter_schema()`와
`analyze()`의 시그니처를 규범 정책과 대조한다. `StrategyBase`를 상속하는 구현은 추상 메서드를
빠뜨렸을 때 인스턴스화가 거부되는지도 별도로 확인한다.

정책의 기본 여섯 성질과 함께 다음 사항을 확인한다.

1. 신규 전략은 목표 반환형인 `DecisionIntent`를 사용해야 한다.
2. 호출 뒤 전략과 입력과 resolved 설정이 변하지 않아야 한다.
3. 지원하는 모든 timeframe과 대표 설정에서 같은 성질이 유지되어야 한다.
4. 선언한 지표와 패턴 조합은 각각의 레지스트리에 있어야 하고 warm-up은 충분해야 한다.
5. 지원 정책, 기본 정책과 capability 선언이 실제 조합 가능 상태와 같아야 한다.
6. 신규 전략 파라미터 스키마에는 자금관리 정책이 소유하는 필드가 없어야 한다.

현재 `VesselReference`의 평면 `leverage`, `reward_risk`, `atr_stop_multiple`은 manual 호환
경계이므로 명시적인 예외로 보존한다. 이 예외를 신규 전략에 일반화하거나 기존 기본값을
바꾸지 않는다.

## 11. 전략용 재료와 실행 비용

공통 검사의 영구 재료는 전략용으로 따로 만든다. 지표 대조용 300봉과 패턴 대조용 장기 계열은
각자의 검증 목적에 맞춰졌으며, 모든 전략의 진입과 청산 국면을 싸게 만드는 재료가 아니다.

전략용 생성기는 짧고 결정적이어야 하며, 사례가 필요한 국면과 timeframe을 선택할 수 있어야
한다. Turtle 조합 검사가 필요하면 확정 일봉 곁입력을 제공하되 전략 입력에는 일봉 `N`을 넣지
않는다.

캔들 재료와 불변 계열 값은 timeframe과 계열 집합별로 공유하고 캐시한다. 전략 수, 정책 수,
시나리오 수와 봉 수의 곱으로 같은 계열을 반복 계산하지 않는다. 접두를 매번 처음부터 다시
계산하는 제곱 비용도 피한다.

## 12. 결함 주입 검증

검사 자체가 실제 결함을 잡는지 테스트용 전략으로 증명한다. 최소한 다음 결함은 각자 대응하는
검사를 실패시켜야 한다.

- 클래스 전역 상태에 따라 판단이 달라지는 전략을 검출해야 한다.
- 호출 횟수에 따라 판단이 달라지는 전략을 검출해야 한다.
- 입력 객체나 resolved 설정을 변경하는 전략을 검출해야 한다.
- 선언하지 않은 계열을 읽거나 `get`과 순회로 접근을 숨기는 전략을 검출해야 한다.
- 동적 import, 파일, 네트워크, 데이터베이스, 하위 프로세스와 벽시계를 쓰는 전략을 검출해야
  한다.
- 긴 진입을 짧은 청산 증거로 통과시키려는 전략을 검출해야 한다.
- 지원하지 않는 정책이나 자금관리 소유 필드를 선언하는 신규 전략을 검출해야 한다.

## 13. 완료 기준

- 허용 목록의 모든 전략에 공통 성질이 자동으로 적용되어야 한다.
- 발견 목록과 방식 사례표의 전략 id 집합이 정확히 같아야 한다.
- 결정성의 두 경로와 입력 및 설정 불변성 검사가 있어야 한다.
- 정책별 생산 입력 모양을 재현한 정책 독립성 검사가 있어야 한다.
- 시간 무결성의 Engine 조합 검사와 한계가 명시된 전략 방어 검사가 모두 있어야 한다.
- 정적 의존 검사와 실행 중 입출력 감시가 모두 있어야 한다.
- 계열과 설정 접근 기록이 `get`, 포함 여부와 순회 경로까지 다뤄야 한다.
- 각 진입 방향에 대응하는 청산 증거를 요구해야 한다.
- 결함 주입 전략으로 각 검사 장치가 실제로 실패하는지 입증해야 한다.
- 재료와 계산을 캐시해 전략이 늘어도 불필요한 곱 비용이 생기지 않아야 한다.
- 현재 발견 목록의 전략이 전부 통과해야 하며, 실패하면 전략을 조용히 고치지 않고 발견 사실을
  먼저 보고해야 한다.
- 관련 pytest, mypy와 ruff가 통과하고 건너뛴 검사 수를 함께 보고해야 한다.

## 14. 열려 있는 결정

공통 계약 검사 전체를 한 changeset에서 구현할지, 검증 층별로 나눠 구현할지는 2026-09-25에
사용자가 "층별"로 정했다. 첫 층(전략 단위)은 2026-09-25에, 둘째 층(Engine 조합)은 2026-09-26에
구현됐다. 구현을 나누더라도 중간 단계가 전체 정책을 제공하는 것처럼 표시해서는 안 되며, 두 층의 모듈
docstring이 각자의 한계를 적는다.

전략 단위 층에서 정한 것 둘을 적어 둔다. 첫째, 방식 사례표는 시험 모듈 안의 표(`_CASES`)이며 별도
파일이 아니다. 시험 모듈끼리 import할 수 없는 pytest 설정(`--import-mode=importlib`) 때문이고, 발견
목록과 id 집합이 같은지는 첫 시험이 검사한다. 둘째, 실행 중 감시는 `sys.addaudithook`으로 파일·소켓·
하위 프로세스·데이터베이스·동적 import 사건을 잡고 벽시계는 `time` 함수를 바꿔 잡는다. `datetime.now`
같은 C 구현 호출은 실행 중 잡지 못하므로 정적 검사가 그 호출 이름을 거부한다.

Engine 조합 층에서 정한 것 셋도 적어 둔다. 첫째, 조합 표 `_ENGINE_CASES`는 backtest-service 시험 모듈
안에 따로 있다. trading-plugins는 backtest-service에 의존하지 않고 시험 모듈끼리 import할 수 없기
때문이며, 발견 목록과 id 집합이 같은지는 그 모듈의 첫 시험이 검사한다. 둘째, 실행 조합은 선언한
timeframe마다 기본 정책 하나와 Turtle을 선언한 전략의 Turtle 하나로, 정책과 timeframe의 전체 곱이
아니다(16.2절). 셋째, Turtle 일봉 원천은 Evidence에 없으므로 검사 4의 재계산은 feed 입력에 대한 것이고,
일봉 원천의 Evidence 기록은 별도 항목이다(16.4절).

## 15. 검토에서 바로잡힌 사실

- `VesselReference`가 생성자에서 보관하는 값은 동결된 `ResolvedConfig`이며 호출에 따라 변하는
  실행 상태가 아니다. 현재 클래스는 `StrategyBase`를 상속하지 않지만 구조적으로
  `StrategyAdapter`를 만족한다.
- Engine은 자금관리 정책 지표 가운데 `timeframe`이 `strategy`인 항목만 일반 계열 목록에
  합친다. manual의 ATR은 합쳐지지만 Turtle의 일봉 `N`은 별도 일봉 조회로 계산되어 정책에만
  전달된다.
- 같은 새 인스턴스 둘의 재생 결과만 비교하면 두 인스턴스가 같은 방식으로 변하는 호출 횟수
  결함을 놓칠 수 있다.
- 생산 Engine이 확정 접두만 전달하는 상황에서 접두 재생끼리 비교하는 것만으로는 미래 참조를
  증명할 수 없다.
- 현재 전략은 계열 Mapping의 `get`을 사용한다. `__getitem__`만 기록하는 접근 추적기는 실제
  읽기를 놓친다.
- `StrategyAdapter`의 Protocol 검사는 정확한 메서드 시그니처를 강제하지 않는다.
- 현재 저장소에는 허용 목록 전체를 대상으로 이 설계의 성질을 적용하는 공통 계약 검사 묶음이
  없다.

## 16. Engine 조합 층의 구현 설계(2026-09-26)

전략 단위 층이 병합된 뒤 남은 둘째 층이다. 6절의 시간 무결성 주 검사와 5절 끝의 "지원하지 않는
조합의 거부"를 발견된 전략 전체에 Engine 실행으로 적용한다. 이 장은 그 층의 자리, 검사, 결함 주입,
비용, 하지 않는 것과 완료 기준을 정한다.

### 16.1 코드에서 확인한 사실

- `Engine.step_close`(`services/backtest-service/backtest_service/engine/engine.py`)는 확정 접두
  `list(self._confirmed)`, 현재 봉, 현재 봉까지 갱신된 `dict(self._indicator_values)`만 전략에
  넘기고, 결정의 `timestamp`가 현재 봉 마감보다 늦으면 HOLD를 포함해 `ValueError`로 거부한다.
- `Engine.step_open`은 이월 주문마다 `feature_ts <= decision_ts < execution_ts`를 확인하고 어긋나면
  `ValueError`를 낸다. next_bar 체결 시각은 `core_lib/execution/matcher.py`의 `_execution_candle`이
  정하는 `max(next_candle.open_time, close_time + 1ms)`이고, 보호 청산(손절·목표·강제청산)은
  `resolve_triggers`가 봉 open을 결정 시각으로, 그 봉의 close를 체결 시각으로 쓴다. 따라서 결정
  시각은 언제나 체결 시각보다 앞선다.
- `Engine._money_management_volatility`는 Turtle 일봉 N을 `_turtle_n_values` 가운데 마감 시각이
  판단 봉 마감 시각 이하인 마지막 항목으로 고른다. 마감 시각이 판단 시각과 같은 일봉은 그 순간 확정된
  것이므로 쓴다. 고른 시각과 값은 SIGNAL의 `metadata_json.money_management.volatility_timestamp`와
  `volatility`에 남는다. 일봉 N은 전략 입력 `indicators`에 들어가지 않는다(15절).
- `INDICATOR_SNAPSHOT`은 봉마다 해석된 계열 수만큼의 행을 `snapshot_seq` 순으로 남기고,
  `feature_ts`는 그 계열의 source candle 마감 시각이다. 판단 봉 자체는 행에 없으므로 봉과 행의
  대응은 순서로 복원한다.
- Evidence audit(`adapters/evidence_schema.py`의 `TIMESTAMP_ORDER_AUDIT_SQL`과
  `adapters/evidence_sink.py`의 `audit`)은 snapshot의 `candle_close_time > feature_ts`, SIGNAL의
  `feature_ts > decision_ts` 또는 `candle_close_time <> decision_ts`, EXECUTION의
  `decision_ts >= execution_ts`, 한 timeframe을 넘는 실행 지연, 결정 없는 체결을 실패로 잡고,
  `_indicator_failures`가 계열별 `feature_ts` 열을 봉 grid와 대조한다. 이 audit은 한 실행의 기록
  안에서 관계를 보며, 전략이 실제로 받은 입력은 보지 않는다.
- `Engine.run`은 `AdapterManager.create_runtime`(`services/core-lib/core_lib/strategy/manager.py`)과
  `config.timeframe not in metadata.supported_timeframes`("strategy does not support the configured
  timeframe") 검사를 `catalog.register` 이전에 둔다. `create_runtime`은 배포된 정책을 먼저 만든 뒤
  전략이 선언하지 않은 mode를 "strategy '…' does not support money-management mode '…'" 문구로
  거부한다. "unsupported money-management mode"는 이 경로의 문구가 아니라 정책 registry와
  `default_settings` 검증의 문구다. 배포되지 않은 mode는 `RunConfig.model_validate`의 discriminated
  union이 그보다 먼저 거부하므로 Engine 수준 거부 검사는 배포된 mode만 쓴다. 거부된 조합은 run_id도
  Evidence 파일도 남기지 않는다.
- Turtle의 일봉 계열은 `_indicator_specs`에 들어가지 않는다. 따라서 `INDICATOR_DEFINITION` 행도
  `INDICATOR_SNAPSHOT` 행도 없고, `_record_source_snapshots`가 기록하는 `SOURCE_DATA_SNAPSHOT`에도
  없다(실행 timeframe과 `_indicator_specs`의 timeframe만 기록한다). 일봉 요구는
  `resolved_indicators_json`에 정책 version과 함께 적힐 뿐이다. 그러므로 Evidence audit이 통과해도
  일봉 원천 자체의 출처는 Evidence에 없다.
- EXECUTION 행이 생기는 경로는 다섯이다. 신호 주문(진입·청산·반전의 두 다리)은 봉 마감의 결정에서
  `max(next open, close + 1ms)`에 체결된다. 보호 청산(손절·목표·가격 강제청산)은 봉 open의 결정에서 그
  봉의 마감에 체결된다. 데이터 공백 앞의 강제 청산(`_close_at_data_gap`)은 봉 마감의 결정에서
  `close + 1ms`에 체결된다. funding 소진 강제청산(`_settle_at_boundary`)은 funding 경계에서
  `boundary + 1ms`에 체결된다. 데이터 끝의 청산은 결정 없이(`decision_id` NULL, exit_reason
  END_OF_DATA) 마지막 마감 `+1ms`에 체결되며 audit이 이를 허용한다.
- 기존 Engine 시험은 fixture 전략에 대한 것이다.
  `test_vessel_turtle_uses_only_prior_finalized_daily_n_and_records_plan`,
  `test_multi_timeframe_series_aligns_without_future_values_and_records_its_source`,
  `test_execution_lag_over_one_timeframe_fails_timestamp_integrity`(모두
  `services/backtest-service/tests/test_engine_and_harness.py`). 문서 출처 전략 시험 셋
  (`test_document_sourced_strategies_engine.py`, `test_three_bar_reversion_engine.py`,
  `test_bollinger_band_bounce_engine.py`)은 각 전략을 1h와 기본 정책 한 조합으로만 돌리고 시간
  관계를 검사하지 않는다. 발견된 전략 전체에 자동으로 적용되는 Engine 조합 검사는 없다.
- `trading-plugins`는 `backtest-service`에 의존하지 않고 그 반대는 의존한다. 따라서 이 층은
  `services/backtest-service/tests`에 둔다. 두 서비스의 시험 모듈은 서로 import할 수 없으므로
  (`--import-mode=importlib`) 전략 단위 층의 사례표 `_CASES`를 재사용할 수 없다.
- 저장소 전체 pytest는 2026-09-26 기준 2분 4초(2,359 통과)다. 합성 경로 위의 Engine 실행 하나는
  1h 평가 240봉 기준 약 2.6초이며 sqlite commit과 봉 루프가 대부분이다.

### 16.2 자리와 조합 표

새 모듈 `services/backtest-service/tests/test_strategy_contract_engine_layer.py` 하나를 둔다.
서비스 코드와 `Engine`은 바꾸지 않는다.

조합 표 `_ENGINE_CASES`는 전략 id마다 스키마를 통과하는 대표 파라미터와 시장 종류를 적는다(3절의
규칙대로 기본값이 앞으로도 있다고 가정하지 않는다). 첫 시험은 `discover_strategies()`의 id 집합과
표의 id 집합이 같고 발견 fault가 없음을 확인한다. timeframe과 정책은 표에 적지 않고 전략의
`get_metadata()` 선언에서 읽는다. 선언을 다시 적으면 어긋났을 때 무엇이 옳은지 시험이 정하게 되기
때문이고, 선언과 사례표의 일치는 이미 전략 단위 층이 검사한다.

실행 조합은 다음 둘의 합이다.

1. 전략마다 선언한 timeframe 각각을 기본 정책으로 실행한다(정책 설정은 mode만 제출해 선언된
   `default_settings`가 실리게 한다).
2. Turtle을 선언한 전략은 첫 timeframe을 `turtle`로 한 번 더 실행한다.

정책과 timeframe의 전체 곱은 돌리지 않는다. 정책이 시간 관계에 영향을 주는 경로는 Turtle의 일봉
N 하나뿐이고(다른 정책의 ATR은 전략 timeframe 계열이라 다른 계열과 같은 경로를 탄다), 정책이 판단을
바꾸지 않는 것은 전략 단위 층이 검사한다. 현재 발견 목록에서 조합은 열셋이다(1h 일곱, 4h 셋,
turtle 셋).

### 16.3 재료

합성 재료는 고정 seed의 국면 전환 random walk 하나를 1m로 만들고, 실행 timeframe의 봉과 Turtle의
일봉을 모두 그 1m 경로에서 합쳐 만든다. 그래서 실행 경로, Engine이 검증하는 1m 원천, Turtle이 읽는
일봉이 하나의 가격 이력이다. 재료 길이는 발견된 전략이 선언한 timeframe 전부에 대해 warm-up 예산
320봉과 평가 구간을 덮도록 선언에서 계산하고 하루 단위로 올림한다(일봉이 UTC 일 경계에 맞게). 평가
구간은 한 시간 이하의 timeframe에서 240봉, 그보다 길면 480시간어치(최소 20봉)다. 선언에 없는
timeframe을 새 전략이 더해도 재료가 없어 KeyError로 멈추지 않고 그 timeframe의 경로가 만들어진다.

이 재료는 9절의 방향별 의도적 사례가 아니다. 그 사례는 전략 단위 층의 사례표에 있고, 이 층의 재료는
모든 조합이 실제로 진입하는 하나의 고정 경로다. seed는 재료의 일부이지 조정 손잡이가 아니다. 어떤
조합이 이 경로에서 진입하지 않게 되면(전략이 바뀌었을 때) 그 사실을 먼저 보고하고 재료를 다시 정하며,
seed를 바꿔 가며 통과를 찾지 않는다. 재료를 만들 때(2026-09-26) 1m 기준 경로의 seed 후보 넷을
견주어, 열세 조합 전부가 셋 이상 진입하고 turtle 조합 셋이 서로 다른 날 넷·셋·여섯 번 진입하는 하나를
골라 고정했다. 시험 모듈의 `_MATERIAL_SEED`가 그 값이며 주석이 이 선택을 적는다.

Turtle용 일봉은 같은 재료를 UTC 일 경계로 합친 것이며 시작 전 60일을 덮는다. Engine은 일봉을 실행의
`end`까지 읽어 두므로 평가 구간 안에서 닫히는 일봉은 처음부터 feed에 있고, 검사는 그 일봉이 닫힌 뒤에만
쓰였는지를 본다(N의 시각이 판단 시각을 따라 전진한다). `end` 뒤에 닫히는 일봉은 feed가 `up_to`로
걸러 Engine에 닿지 않으므로 그런 봉을 두는 것은 검사가 아니다. 일봉 N은 전략 입력에 넣지 않는다(Engine이
그렇게 한다).

### 16.4 검사

각 조합에서 Engine을 한 번 돌리고 다음을 확인한다. 모든 조합에서 진입 체결이 하나 이상 있어야 한다.
없으면 시간 검사가 공허하므로 실패로 보고하며, 그때는 전략이 아니라 경로 seed를 바꾼다.

1. **전략이 받은 입력의 시간.** 발견된 클래스의 `analyze`를 monkeypatch로 감싸 호출마다 판단 봉의
   마감 시각, `candles`의 마지막 봉과 최대 마감 시각, `candles`의 timeframe 집합, `indicators`의
   키 집합을 기록한다. 모든 호출에서 `candles`의 마지막이 판단 봉이고 모든 봉의 마감이 판단 봉
   마감 이하이며 timeframe은 실행 timeframe이고, 키 집합은 `INDICATOR_DEFINITION`의 키 집합과 같다.
   그 집합은 `resolved_indicators_json`에서 정책 소유 항목(정책의 `required_indicators()` 가운데
   timeframe이 `strategy`가 아닌 것, 곧 Turtle의 일봉 N)을 뺀 것과 같아야 한다. 전략 자신이 선언한
   일봉 계열은 정의에도 전략 입력에도 있으므로 빼지 않는다.
2. **계열의 시각.** INDICATOR_SNAPSHOT을 `snapshot_seq` 순으로 `INDICATOR_DEFINITION`의 키 수만큼
   묶어 k번째 묶음을 k번째 `analyze` 호출과 짝짓는다. 묶음마다 키 집합이 정의 집합과 정확히 같고,
   모든 `feature_ts`가 판단 봉 마감 이하이며, 실행 timeframe 계열은 판단 봉 마감과 같다. 행 수는
   키 수 곱하기 호출 수와 같아야 한다.
3. **판단과 체결.** 결정을 가진 EXECUTION마다 DECISION을 결정 id로 이어 `decision_ts <
   execution_ts`, `execution_ts == planned_execution_ts`를 확인하고, 체결을 두 종류 가운데 하나로
   분류한다. 봉 마감의 결정은 `planned_execution_ts`가 `decision_ts + 1ms`이고(신호 주문과 공백 앞
   청산), 봉 open의 보호 청산은 `planned_execution_ts`가 `decision_ts`에 한 봉을 더한 값이다. 어느
   쪽도 아니면 실패한다. 결정 없는 EXECUTION은 exit_reason이 END_OF_DATA뿐이어야 한다. SIGNAL은
   `decision_ts`, `feature_ts`, `candle_close_time`이 모두 같고 관찰된 판단 봉 마감 가운데 하나다.
   조합 전체를 합쳐 두 종류가 모두 관찰되어야 한다. 데이터 공백과 funding 소진 경로는 이 재료에서
   일어나지 않으며, 그 시각 규칙은 Engine 시험
   `test_open_position_is_closed_before_unobservable_gap_boundaries`와
   `test_funding_margin_exhaustion_liquidates_without_negative_cash`가 지킨다.
4. **Turtle 일봉.** turtle 조합의 enter·reverse SIGNAL마다 `volatility_timestamp`가 feed가 제공한
   일봉 가운데 마감이 `decision_ts` 이하인 가장 최근 일봉의 마감과 같고, `volatility`가 그 시각까지의
   일봉 접두로 독립 재계산한 `turtle_n_series(prefix, period)`의 마지막 값과 같다. 평가 구간에서
   `volatility_timestamp`가 서로 다른 값을 둘 이상 가진다(일봉이 닫히면 전진한다). 이 재계산의
   원천은 feed의 일봉 입력이지 Evidence가 아니다. Engine이 일봉 원천을 Evidence에 남기지 않는 것은
   이 층이 고치지 않는 별도 항목이다.
5. **Engine 수준 거부.** 전략마다 선언하지 않은 timeframe 하나(후보 `1d`, `4h`, `1h`, `15m`
   가운데 첫 미선언)와 배포됐지만 선언하지 않은 정책 mode 각각으로 `Engine.run`을 부르면
   "strategy does not support the configured timeframe" 또는 "does not support money-management
   mode" 문구의 `ValueError`가 나고 `catalog.register`가 불리지 않으며 Evidence 파일이 bind되지
   않는다. 다른 문구의 `ValueError`는 "다른 이유로 거부됨"으로 실패다. 배포된 mode 전부를 선언한
   전략은 정책 거부 검사를 건너뛰고 pytest skip 사유로 그 사실을 남긴다.
6. **audit.** 각 실행의 `integrity_status`가 `passed`다. 기존 audit과 겹치는 관계는 그대로 두고,
   이 층은 전략이 받은 입력과 독립 재계산을 더한다.

### 16.5 결함 주입

결함은 전략이 아니라 조합에 주입한다. 발견된 전략은 그대로 둔다.

- 다음 평가 봉을 `_confirmed`에 미리 넣는 `step_close` 감싸기는 검사 1에서 실패해야 한다.
- 실행 timeframe 계열의 source candle을 다음 봉으로 바꾸는 `_update_indicators` 감싸기는 검사
  2에서 실패해야 한다.
- 체결 시각을 판단 봉 마감으로 되돌리는 broker `submit` 감싸기는 Engine의 실행 중 검사가
  `ValueError`("feature_ts <= decision_ts < execution_ts was violated")로 멈춰야 한다. 이 결함은
  Evidence까지 가지 못하므로 검사 3의 Evidence 대조가 아니라 Engine의 거부를 증명한다.
- 시각을 무시하고 마지막 일봉 N을 돌려주는 `_money_management_volatility` 감싸기는 검사 4에서
  실패해야 한다.
- 발견된 전략의 `supported_timeframes`를 넓힌 metadata 감싸기는 검사 5가 "거부되지 않음"으로
  실패해야 한다. 거부가 사라진 뒤 실행이 다른 이유로 멈추면 결함이 잘못된 이유로 잡히므로, 이 결함은
  일봉 feed가 warm-up을 댈 수 있는 조합(three-bar-reversion을 1d에서 짧은 평가 구간으로)에서 실행이
  끝까지 가게 하고, 실패 문구가 "was not refused"인지까지 본다.

### 16.6 비용

조합 열셋에 결함 다섯을 더해 Engine 실행은 약 열여덟 번이다. 재료 캐시로 경로와 1m 원천은 timeframe별로
한 번만 만든다. 추가 시간은 1분 안쪽을 목표로 하고 실제 값은 구현 뒤 보고한다.

### 16.7 하지 않는 것

- 전략 판단 값의 재계산. 그것은 `verify-strategy`의 일이다.
- 정책과 timeframe의 전체 곱, 시장 종류와 종목 범위(별도 항목).
- `Engine`이나 서비스 코드의 변경, 능력 목록 항목 추가.
- 실제 데이터베이스 접근.

### 16.8 완료 기준

- 발견 목록과 조합 표의 id 집합이 같다.
- 조합 열셋이 전부 통과하고 각 조합에 진입 체결이 하나 이상 있다.
- 결함 다섯이 각각 대응하는 검사(또는 Engine의 거부)에서 실패한다.
- 거부 검사가 전략 일곱 전부에 대해 통과하고 건너뛴 수가 보고된다.
- 기존 전략 시험과 Evidence golden이 변하지 않는다.
- 저장소 루트 pytest, ruff, ruff format, backtest-service mypy가 초록이고 Codex 리뷰가 Blocking 0이다.
- 이 문서의 첫 문단과 14절, 인수 기록 1장의 공통 규범 검사 행, 규범 `docs/strategy-authoring-contract.md`
  2.1절(여섯 성질을 잡는 자동 검사의 자리)을 갱신한다.

### 16.9 검토에서 바로잡힌 사실(Codex, 2026-09-26)

- 선언하지 않은 정책 mode의 거부 문구를 "unsupported money-management mode"라고 적은 것은 내 오류였다.
  `create_runtime`의 문구는 "strategy '…' does not support money-management mode '…'"이고, 내가 적은
  문구는 registry와 `default_settings` 검증의 것이다. 16.1과 검사 5를 고쳤다.
- 검사 2의 묶음 폭을 "해석된 계열 수"라고만 적으면 Turtle 조합에서 `resolved_indicators_json`의 일봉
  항목을 세게 된다. 폭은 `INDICATOR_DEFINITION`의 키 수이고 묶음마다 키 집합이 정확히 같아야 한다.
- Turtle 일봉 원천은 Evidence에 없다. 검사 4의 재계산은 feed 입력에 대한 것이며 Evidence 출처가
  아니라고 적었고, 일봉 원천 기록은 별도 항목으로 뺐다.
- EXECUTION이 생기는 경로 다섯을 16.1에 적고, 검사 3이 두 종류로 분류해 나머지를 실패로 만들며
  공백·funding 경로는 기존 Engine 시험이 지킨다고 적었다.
- 재료가 9절의 의도적 사례가 아님을 16.3에 적었다. seed는 재료의 일부이고, 진입이 사라지면 보고 뒤
  재료를 다시 정한다.
- timeframe을 넓힌 결함이 "다른 이유로 거부됨"으로 잡히면 검사의 유효성 증명이 아니다. 실행이 끝까지
  가는 조합을 쓰고 실패 문구를 본다.

코드 리뷰(Codex, 2026-09-26, Blocking 0)에서 바로잡은 것 둘. 첫째, 검사 1의 대조가 `1d` 항목을 모두
빼고 있어 전략 자신이 일봉 계열을 선언하면 통과할 수 없었다. 정책 소유 항목만 뺀다. 둘째, 재료가
1h와 4h에만 있어 규범이 허용하는 다른 실행 timeframe(`5m`, `15m`, `1d`)을 선언한 전략이 들어오면
검사 전에 KeyError로 멈췄다. 재료를 1m 기준 경로에서 선언된 timeframe으로 합쳐 만든다. 이 둘은 현재
전략 일곱에는 드러나지 않았고 앞으로 들어올 전략에 대한 것이다. `end` 뒤에 닫히는 일봉이 검사라고
적은 것은 내 오류였다. feed가 걸러 Engine에 닿지 않으므로 16.3에서 뺐다.
