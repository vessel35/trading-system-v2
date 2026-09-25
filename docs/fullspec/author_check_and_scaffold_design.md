# 전략 작성의 배포 전 검사를 명령 하나로 판정하고 반복 공통 코드를 플랫폼이 소유한다

이 문서는 전략 작성 절차(`.claude/skills/author-strategy/SKILL.md`)가 지는 두 책임, 곧
**주어진 전략을 정확히 옮기는 것**과 **플랫폼의 방식을 따르며 오류 없이 도는 코드를 내는 것**을
사람이나 agent의 성실함이 아니라 **프로그램이 판정하게** 만드는 설계다. 3-1 인수 시험
(`docs/fullspec/stage_3_1_acceptance_three_strategies.md`)에서 드러난 실패를 출발점으로 삼는다.

이 문서는 두 단계 가운데 첫째다. 둘째 단계(전략을 중간 언어로 적고 변환기가 파이썬을 만드는
것)는 여기서 다루지 않고 7장에 경계만 적는다.

**이 문서는 검토를 두 번 받아 고쳐진 판이다.** 내부 검토(같은 모델 계열의 독립 문맥)와 외부
검토(Codex, `gpt-5.6-terra`)가 찾은 사실 오류와 그 정정은 9장에 모아 두었다. 외부 검토가
가장 크게 바로잡은 것은 이 검사의 이름이다. 공통 규범 검사 묶음이 없는 동안 이 명령은
**배포 전 검사**(파일을 두고 등록해도 되는가를 판정한다)이지 **완료 판정**(전략이 문서대로 다
됐는가)이 아니며, 완료는 이 검사에 검산과 사람의 확인을 더한 것이다.

## 1. 지금 무엇이 아쉬운가

인수 시험에서 전략 셋을 절차대로 옮겼을 때 난 실패는 넷이었고, 원인은 서로 다르다.

1. **플랫폼이 자기 제약을 다 말하지 않는다.** 전략은 등록된 series의 판단 봉 값만 받으므로
   지표끼리의 교차는 상태 규칙으로만 표현되는데, 능력 목록
   (`services/core-lib/core_lib/capabilities.py`)에 그 사실이 없어 Engine 코드를 읽고서야
   알았다(인수 기록 7장 첫째 발견).
2. **규칙이 한 곳에만 있고 검사가 없다.** 정책 id는 등록 표의 `mode` 검사 제약 때문에
   kebab-case여야 하는데, 그 규칙은 DDL에만 있었다. 규범(`docs/strategy-authoring-contract.md`)
   5.3.1절의 예시 정책이 그 규칙을 어기고 있었고, 발견 검사도 사전 점검(`catalog_precheck`)도
   잡지 못했으며, 데이터베이스에 적용하는 순간에야 드러났다(인수 기록 7장 여덟째 발견).
3. **플랫폼이 가져야 할 반복 공통 코드를 작성자가 쓴다.** `market_data`에서 캔들·시간대·지표를 꺼내
   형을 확인하는 코드, `DecisionIntent`를 만드는 코드, 시험에서 실행 key를 적는 코드를
   전략마다 다시 썼다. 인수 작업의 QA 단계에서 그 반복 코드에서 mypy 오류 셋과 시험의 key 오기가
   났고 커밋 전에 고쳤다. 인수 기록은 결과만 적고 이 과정을 적지 않았으므로 여기 남긴다.
4. **원문과의 차이가 산문에만 남는다.** 빈 값을 정한 것과 규칙을 근사한 것이 인수 기록 4장의
   문단으로만 있어서, 무엇이 승인된 차이이고 무엇이 검산 대상인지 프로그램이 알 수 없다.

넷의 공통점은 **완료를 사람이 읽는 체크리스트(규범 10장)로만 정의해 두었다**는 것이다. 목록은
읽는 사람마다 다르게 적용되고, 빠뜨려도 아무것도 멈추지 않는다.

## 2. 코드에서 확인한 사실

- **사실 모듈은 여섯 명령을 가진다.** `services/trading-plugins/trading_plugins/facts.py`는
  `capabilities`, `series`, `deployed`, `declaration`, `registration_sql`, `catalog_precheck`를
  명령줄(`_USAGE`와 `_arguments`의 닫힌 이름 집합)과 MCP 서버(`mcp_server.py`, 명령마다
  명시적인 wrapper 함수를 `@mcp.tool`로 등록한다) 양쪽에 낸다. 어떤 명령도 데이터베이스에
  닿지 않고, 임의 DSN을 받는 명령도 없다(등록 MCP 설계
  `docs/fullspec/strategy_registration_mcp_design.md` 6장의 결정). `main`은 플러그인 예외를
  `"fact lookup failed"` 하나로 뭉개며, `tests/test_facts.py`는 `facts.py` 소스에 배포 재고
  이름(mode, 지표, 패턴)이 낱말로 나오면 실패한다(다른 파일은 보지 않는다).
- **사실 함수는 고정 패키지만 본다.** `_strategy_class`와 `_policy_class`는 인자 없는
  `discover_strategies()`와 `discover_money_management()`를 부르고,
  `_validate_module_path`는 모듈 경로가 `trading_plugins.strategies.` 또는
  `trading_plugins.money_management.`로 시작하지 않으면 거부한다. 그러므로 임시 패키지의
  클래스에는 사전 점검도 등록 문장 생성도 닿지 않는다.
- **정책 설정에는 기본값이 없는 항목이 있을 수 있다.** `_policy_settings`는 그런 항목을
  `has_default: False`로 적고 생성자 값을 내지 않으며, `MoneyManagementFactory.create`
  (`core_lib/money_management/registry.py`)는 받은 설정만 넘겨 dataclass 기본값에 기댄다.
  기본값이 없는 정책은 설정 없이 만들 수 없다.
- **사전 점검이 보는 것은 셋뿐이다.** `_precheck_strategy`는 등록 신원과 선언 대조
  (`reconcile_strategy_registries`), 수명주기, 어댑터 생성(`AdapterManager.create`, 그 안에서
  `StrategyConfig.resolve`가 기본값으로 돈다)만 본다. 정책 쪽은 신원과 수명주기다.
  `checks_performed`가 그 목록이고 `_NOT_CHECKED`가 보지 않는 것의 목록이며,
  `tests/test_facts.py`가 두 목록을 고정하고 있다. 식별자 형식은 어느 목록에도 없다.
- **발견 검사는 이름의 존재만 본다.** `discovery.py`의 `discover_strategies`는
  `STRATEGY_ID`가 클래스 자신에 선언된 비어 있지 않은 문자열인지(`vars(candidate)`로 읽는다),
  중복인지만 보고, `discover_money_management`는 `id`와 설정 표면(`policy_settings`)과
  `requires_signal_exit`의 선언 여부를 본다. 형식은 어느 쪽도 보지 않는다.
- **식별자 형식 규칙은 세 곳에 따로 있고 표기가 다르다.** 등록 표 DDL
  (`init-scripts/signal-service/20260724/01-redefine-strategy-registry.sql`의
  `ck_strategy_registry_strategy_id`,
  `init-scripts/signal-service/20260810/01-create-money-management-registry.sql`의
  `ck_money_management_registry_mode`)은 둘 다 `^[a-z0-9]+(-[a-z0-9]+)*$`이고, 실행 설정
  (`services/backtest-service/backtest_service/config/run_config.py`의
  `_STRATEGY_ID_PATTERN`)은 `^[a-z0-9]+(?:-[a-z0-9]+)*$`로 `strategy_id`에만 걸린다. 두
  정규식은 같은 문자열을 받지만 글자가 다르다. 정책 mode는 코드 어디에서도 검사되지 않는다.
- **런타임은 정책 정합을 스스로 검사한다.** `core_lib/strategy/manager.py`의
  `create_runtime`은 먼저 `create`를 불러 전략을 만들고(그래서 사전 점검의 어댑터 생성과
  겹친다), 전략이 `TradingSignal` 방식이면 정책을 붙일 수 없다고 거부하며, mode가
  `supported` 안에 있는지, 정책이 `requires_signal_exit`를 선언했는지, 선언했다면 전략이
  `supports_signal_exit`인지를 거부로 검사한다. `StrategyMetadata.decision_contract`의
  기본값은 `TradingSignal`이다. 그리고 `MoneyManagementSupport.__post_init__`
  (`core_lib/strategy/base.py`)은 `default`가 `supported` 밖이면 생성 자체를 거부하므로,
  그런 전략은 `get_metadata()`를 부르는 첫 자리에서 터진다.
- **능력 목록에는 series 값을 몇 봉까지 받는지가 없다.** `run.strategy_inputs`는 전략이 받는 여섯 key를
  적지만 `indicators`가 **판단 봉의 값 하나**라는 것은 적지 않는다. Engine은
  `market_data["candles"]`에 확정 캔들 전부를, `market_data["indicators"]`에
  `dict(self._indicator_values)`를 넣고, 그 사전은 key마다 그 봉의 값 하나로 새로 만들어진다
  (`engine.py`). 그러므로 캔들 값끼리의 교차는 전략이 `candles`로 판정할 수 있지만, 등록된
  series의 직전 값은 오지 않아 지표끼리의 교차나 가격과 지표의 교차는 직접 판정할 수 없다.
  `series.value_shapes`는 값의 모양(스칼라 또는 출력 사전)만 말한다.
  `Capability.__post_init__`은 `verified_by`가 `경로.py::함수` 형식이기를 요구하고,
  `services/core-lib/tests/test_core_lib_capabilities.py`는 그 파일과 함수가 실제로 있어야
  통과한다. `services/trading-plugins/tests/test_trading_plugins_capabilities.py`는 `value`
  안의 문자열을 배포 mode·지표·패턴 이름과만 대조하므로 정규식 문자열과 정수 1은 값으로
  허용된다. `capabilities.py`는 지금 `core_lib`의 어떤 모듈도 import하지 않는다.
- **warm-up을 계산하는 곳은 Engine뿐이다.** `engine.py`의 `_warmups_by_stream`이 유일한
  정의이고 `core_lib`에는 확보 구간을 계산하는 함수가 없다.
- **기반 클래스에 보조 메서드가 하나 있는데 아무도 쓰지 않는다.** `StrategyBase.series_value`는
  `SeriesSpec`을 받아 실행 key를 만들고 없으면 `KeyError`를 올린다. 배포된 전략 넷은 모두
  `series_key_of`와 `indicators.get`으로 값을 읽으며, 캔들·시간대·시장 종류를 꺼내 형을
  확인하는 일과 `DecisionIntent`를 만드는 일은 `vessel_reference.py`가 inline
  `isinstance`와 `_indicator`·`_decision`으로, 새 전략 셋이 모듈 함수 `_inputs`·`_number`·
  `_decision`으로 각자 한다.
- **공통 규범 검사는 설계만 있다.** `docs/fullspec/strategy_contract_suite_design.md`가
  결정성·정책 독립성·시간 무결성·금지 의존·선언과 접근 일치·유효한 청산의 여섯 성질을 발견된
  전략 전부에 자동 적용하는 검사를 정했고, 첫 줄이 "아직 구현되지 않았다"고 적는다. 그 설계는
  전략마다 **방식 사례표**(대표 설정, 지원 정책별 설정, 방향별 진입·청산 증거)를 시험이
  소유하도록 정했고(3절), 10절에 "선언한 지표와 패턴 조합이 registry에 있고 warm-up이 충분할
  것", "지원 정책과 기본 정책과 capability 선언이 실제 조합 가능 상태와 같을 것", "parameter
  스키마에 자금관리 소유 필드가 없을 것"도 공통 성질로 적었다.
- **Engine을 데이터베이스 없이 돌리는 조립은 시험 파일 안에만 있고, 전략 셋을 고정한다.**
  `services/backtest-service/tests/test_document_sourced_strategies_engine.py`가 인공
  1시간봉 공급 어댑터(320봉 warm-up과 240봉 평가 구간, 고정 seed), 메모리 카탈로그(결정성 참조를
  "이전 실행 없음"으로 꾸며 냄), 등록 행 fixture, 전략마다 명시한 자금관리 설정으로 **새 전략
  셋만**(`vessel-reference`는 빠져 있다) 실제 Engine에 태우고 Evidence 완전성과 결정성을
  본다. `backtest_service` 패키지에는 `synthetic`·`dry_run`·`fixture`라는 이름의 모듈도
  `__main__`도 없고, `tests/conftest.py`와 다른 시험 파일에 `DataFeed`의 시험용 대체 구현이 여럿 있다.
  `web_api`는 `backtest_service`의 실행 설정(`config.run_config`), 카탈로그 어댑터
  (`adapters.catalog_store`)와 runner 같은 운영 모듈을 import하며, 진단 목적의 모듈은
  import하지 않는다.
- **규범의 코드 예시는 시험되지 않고, 하나는 두 가지로 규범을 어긴다.** 규범을 읽는 시험이
  없다. 4.1절의 `EmaEngulfingExample`은 첫째로 `STRATEGY_ID`를 모듈 상수로만 두고 클래스에
  선언하지 않아 발견 검사가 "must declare its own non-empty STRATEGY_ID"로 거부하고(6.5절
  위반), 둘째로 `supported=("manual",)`을 선언하면서 `decision_contract`를 선언하지 않아 기본값
  `TradingSignal`이 되므로 `create_runtime`이 "cannot attach money management"로 거부한다.
  5.3.1절의 정책 예시는 인수 시험에서 id와 `requires_signal_exit`를 고친 뒤로는 발견된다.
- **통합 시험의 이름에는 전략 id가 없다.** `tests/test_facts_integration_postgres.py`의
  시험 둘은 `test_strategy_registration_round_trips_and_preserves_lifecycle`과
  `test_policy_registration_round_trips_canonical_settings_and_is_idempotent`이며 매개변수화가
  없다. `pytest -k <전략 id>`는 아무것도 고르지 못한다.
- **의존 방향이 정해져 있다.** `services/backtest-service/pyproject.toml`이
  `trading-plugins`를 의존하고 `run_config.py`가 이미 `trading_plugins`를 import한다. 반대
  방향은 없다. 그러므로 Engine을 부르는 검사는 `trading_plugins` 안에 둘 수 없다.
- **저장소 뿌리는 QA 밖이다.** 뿌리에 `pyproject.toml`·`ruff.toml`·`mypy.ini`가 없고 각
  서비스의 `[tool.ruff] src`와 `[tool.mypy] files`는 자기 패키지와 `tests`만 가리키므로,
  `scripts/` 아래 파일은 ruff·mypy·pytest 어느 검사도 거치지 않는다.

## 3. 무엇을 만드는가

여섯 가지 변경이다. 처음 넷이 둘째 책임(오류 없는 코드)을, 다섯째가 반복 공통 코드를, 여섯째가
첫째 책임(정확한 이식)을 맡는다.

### 3.1 식별자 규칙을 독립 모듈 한 곳에 두고 네 자리에서 쓴다

`core_lib/identifiers.py`(다른 모듈을 import하지 않는 독립 모듈)에
`PLUGIN_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")`과
`is_plugin_identifier(text)`를 둔다. 정규식은 **DDL과 글자까지 같은 형태**로 적는다. 쓰는
자리는 넷이다.

1. `run_config.py`의 `strategy_id` 검사가 이 상수를 쓴다. 받는 문자열 집합은 같고 정규식
   글자만 `(?:...)`에서 `(...)`로 바뀐다.
2. `capabilities.py`가 이 모듈을 import해 `plugin.identifier_format`의 값으로 싣는다(3.2).
   그래서 정규식은 코드에 한 번만 있고 DDL 둘과 대조된다.
3. `discovery.py`가 형식에 어긋나는 `STRATEGY_ID`와 정책 `id`를 **발견 단계의 fault**로
   낸다. 잘못된 id는 배포되지 않고 사유가 남는다. 규범 6.5절의 "잘못된 파일 하나가 나머지를 막지
   않는다"는 그대로다.
4. `catalog_precheck`가 후보 행의 `strategy_id`와 `mode`를 같은 상수로 검사해 finding으로
   낸다. `checks_performed`에 "identifier format"이 더해지고, `tests/test_facts.py`의 고정
   목록을 그에 맞춘다.

DDL과 코드가 어긋나지 않도록 `services/core-lib/tests/test_identifiers.py`가 두 DDL 파일에서
`~ '...'` 정규식 문자열을 읽어 `PLUGIN_IDENTIFIER_PATTERN.pattern`과 같은지 본다. 규칙을
바꾸려면 세 곳을 함께 바꿔야 하고, 하나만 바꾸면 그 시험이 막는다.

규범 두 문장을 함께 고친다. 6.4절의 "밑줄이 든 id는 등록 문장 적용 단계에서 거부된다"는
"발견 단계에서 fault가 되어 배포되지 않는다"로, 6.5절의 "정책은 배포 시점에 선언 둘을
확인한다"는 "선언 둘과 id 형식을 확인한다"로 바뀐다.

### 3.2 능력 목록에 빠진 제약 둘을 넣고, 부딪힌 제약은 반드시 넣는다는 규칙을 세운다

항목 둘을 더한다.

- `series.history_depth`, 값 `1`. 문장은 "전략은 등록된 series의 판단 봉 값 하나만 받는다.
  series의 직전 값은 오지 않고 전략은 상태를 기억할 수 없으므로, 지표끼리의 교차나 가격과
  지표의 교차는 직접 판정되지 않고 판단 봉의 상태 관계로만 표현된다. 확정 캔들은 전부
  오므로 캔들 값끼리의 교차는 전략이 판정할 수 있다. 값의 모양은 `series.value_shapes`가
  말한다"이다. 검증 시험은 `services/backtest-service/tests/test_engine_and_harness.py`에
  두고, Engine이 전략에 넘긴 `indicators`의 **key 집합이 그 실행의 해석된 series 집합과 같고 각
  값이 그 봉의 `INDICATOR_SNAPSHOT` 값과 같음**을 단언한다. 값의 모양만 보는 시험은
  `series.value_shapes`가 이미 갖고 있으므로 되풀이하지 않는다.
- `plugin.identifier_format`, 값은 `PLUGIN_IDENTIFIER_PATTERN.pattern`. 문장은 "전략 id와
  정책 mode는 kebab-case이며, 발견 검사와 등록 표가 같은 규칙으로 거부한다"이다. 검증 시험은
  changeset 1에서는 3.1의 DDL 대조 시험 하나이고, changeset 2에서 발견 fault 시험이 더해진다.
  `verified_by`가 아직 없는 시험을 가리키면 능력 목록 시험이 실패하므로 순서를 이렇게 둔다.

그리고 절차 규칙 하나를 `author-strategy` skill에 적는다. **문서를 옮기다가 능력 목록에 없는
제약에 부딪히면, 그 전략 작업과 같은 changeset에서 항목과 시험을 더한다.** 이번처럼 설계
문서에만 적고 넘어가면 다음 작성자가 같은 벽에 다시 부딪힌다.

### 3.3 규범의 코드 예시를 시험되는 코드로 만든다

`services/trading-plugins/tests/test_contract_examples.py`가
`docs/strategy-authoring-contract.md`에서 언어가 `python`인 코드 블록 가운데 첫 줄이
`# contract-example: strategy` 또는 `# contract-example: policy`인 블록을 뽑아 임시 패키지에
파일로 쓰고 다음을 본다. `discover_strategies(package)`와 `discover_money_management(package)`가
fault 없이 찾는가, 3.1의 형식 검사를 통과하는가, `AdapterManager.create`로 인스턴스가
만들어지는가, 지원한다고 선언한 mode마다 `create_runtime`이 거부하지 않는가, 전략 예시는
규범 4.1절의 최소 시나리오(EMA 둘과 장악형 값)에서 `analyze`가 `DecisionIntent`를
돌려주는가. **등록 문장 생성과 사전 점검은 시험하지 않는다.** 둘은 모듈 경로가 실제 배포
패키지 안이어야 하므로 임시 패키지에서는 성립하지 않고, 배포된 플러그인에 대해서는 이미 시험돼
있다. 사실 함수에 시험용 우회 인자를 두지 않는다.

3.4의 결함 주입 시험은 같은 임시 패키지 방식으로 결함 전략을 만들어 `trading_plugins.author_check`의
단계 함수에 **발견 결과 mapping을 주입**해 검사한다. 그 주입 인자는 단계 함수의 파이썬
인자이고 명령줄과 MCP 표면에는 없다.

규범을 세 군데 고친다. 4.1절 예시 클래스에 `STRATEGY_ID = STRATEGY_ID`(클래스 속성)와
`decision_contract=StrategyDecisionContract.DECISION_INTENT`(import 포함)를 더해 6.5절과
5.2절에 맞추고, 두 예시 블록 첫 줄에 표시 주석을 더한다. 표시가 없는 블록은 시험 대상이
아니다(부분 발췌를 실행하지 않기 위해서다). 이 시험이 있었다면 4.1절 예시의 빠진 선언 둘과
5.3.1절 예시의 밑줄 id는 문서를 고칠 때 바로 드러났다.

### 3.4 `author_check`: 배포 전 검사를 명령 하나로 판정한다

`python -m backtest_service.author_check <전략 id> [--mode-settings <json 파일>]`이 아래
단계를 차례로 돌려 단계별 통과·실패·건너뜀과 사유를 JSON 하나로 내고, 실패가 하나라도 있으면
exit 1이다. 건너뜀은 통과가 아니며 사유가 붙고, **건너뛸 수 있는 단계는 9 하나뿐**이다. 각
단계는 스스로 `(Exception, SystemExit)`를 잡아 그 단계의 실패로 적는다. 실패마다 `rule`
필드에 고정 어휘의 규칙 이름이 들어가고(예: `identifier-format`, `series-unregistered`,
`policy-mode-not-deployed`, `policy-settings-required`, `runtime-refused`), 그 어휘는 시험이
고정한다. 문구는 받은 값을 그대로 되돌려 줄 뿐 mode나 series 이름을 적지 않는다(배포 재고
이름을 소스에 쓰지 않는다는 사실 모듈의 시험을 새 모듈에도 같은 방식으로 건다).

**mode별 대표 설정.** 단계 3과 6은 지원하는 mode마다 정책 설정 하나가 필요하다. 전략이
`MoneyManagementSupport.default_settings`로 그 mode의 값을 선언했으면 그것을 대표 설정으로 쓰고,
그 위에 `--mode-settings` 파일의 값이 덮는다. 선언도 파일도 없고 정책의 설정에 모두 기본값이
있으면 기본값을 쓰며, 기본값 없는 설정이 하나라도 남으면 단계 3이 `policy-settings-required`로
실패한다. 이것은 공통 규범 검사 설계 3절의 방식 사례표가
지원 정책별 설정을 시험이 소유하도록 정한 것과 같은 요구를 명령 인자로 받는 것이다.

| 단계 | 무엇을 보는가 | 어디서 |
|---|---|---|
| 1. 발견 | 그 id가 fault 없이 발견되는가(형식 fault 포함) | `trading_plugins.author_check` (새 모듈, 3.4.2) |
| 2. 선언 | 선언한 series 각각이 registry에 같은 이름·parameter로 있는가, `supported_timeframes`가 형식에 맞는가 | 같은 모듈 |
| 3. 자금관리 정합 | `supported`의 mode마다 대표 설정으로 `AdapterManager.create_runtime`을 실제로 불러 거부되지 않는가. 런타임의 규칙을 복제하지 않고 런타임을 부른다. `create_runtime`이 안에서 `create`를 다시 부르는 것은 단계 5와 겹치지만 의도된 중복이며 독립 검증으로 세지 않는다 | 같은 모듈 |
| 4. parameter | 스키마에 자금관리 소유 이름(규범 4.2절)이 없는가 | 같은 모듈 |
| 5. 등록 대조 | `registration_sql`로 만든 행이 `catalog_precheck`를 통과하는가(어댑터 생성과 기본값 `resolve`는 이 안에서 돈다) | 같은 모듈 |
| 6. 인공 캔들 경로 실행 | **지원하는 mode마다** 대표 설정으로, 고정된 인공 캔들 경로 위에서 실제 Engine을 끝까지 돌려 예외가 없고 Evidence 무결성이 통과하며 두 번 돌린 hash가 같은가. Engine이 보고한 `warmup_candles`를 함께 낸다. 거래가 0건인 mode는 "경고"로 보고한다(규칙이 그 경로에서 서지 않았다는 뜻이며 오류는 아니다) | `backtest_service.diagnostics.synthetic_dry_run` (3.4.1) |
| 7. 정적 QA | `ruff check`, `ruff format --check`, `mypy`를 `services/trading-plugins`에서 | 하위 프로세스 |
| 8. 단위 시험 | `services/trading-plugins`의 pytest에서 그 전략 클래스를 import하는 시험 모듈이 하나 이상 수집되고 통과하는가 | 하위 프로세스 |
| 9. 일회용 데이터베이스 적용 | `pytest -m integration -k <id>`로 통합 시험을 부른다. 그 시험(`test_facts_integration_postgres.py`)은 배포된 전략과 정책 전부로 **매개변수화**해 node id에 전략 id와 mode가 들어가게 하고, 명령은 **하나 이상 수집됐는지**를 확인한 뒤에야 종료 코드를 판정으로 삼는다. 데이터베이스에 닿지 않으면 "건너뜀(데이터베이스 없음)" | 하위 프로세스 |

**이 명령이 증명하는 것과 증명하지 않는 것.** 이 명령은 전략이 발견·등록·조합·실행되는지를 보는
**배포 전 검사**다. 문서의 규칙대로 진입하고 청산하는지(방향별 진입·청산 증거)와 결정성·정책
독립성·시간 무결성·금지 의존·선언과 접근 일치·유효한 청산은 증명하지 않는다. 그것은 공통
규범 검사 설계가 방식 사례표로 정한 일이며, 그 묶음이 구현되면 단계 6과 7 사이에 "10. 공통
규범 검사(그 전략 하나에 대해)"로 들어가고 그때 이 명령이 완료 판정의 도구가 된다.

**앞선 두 설계와의 관계.** 단계 2·3·4는 공통 규범 검사 설계 10절의 4·5·6번 성질을 전략
하나에 대해 구현한 것이고, 그 묶음은 이 세 단계를 재사용한다. 등록 MCP 설계 7장의 "런타임의
실행 검사를 도구 안에 복제하지 않는다"는 단계 3이 런타임을 직접 부르는 것으로 지킨다. 단계
9는 등록 MCP 설계 6장의 "일회용 데이터베이스 검사는 도구가 아니라 시험으로 둔다"를 그대로
따르고, 명령은 그 시험을 부를 뿐이다.

**skill의 완료 정의를 바꾼다.** `author-strategy` skill 6장의 "규범 10장의 체크리스트가
완료의 기준이다"를 다음으로 바꾼다. "구현이 끝났다고 말하려면 셋이 필요하다. 첫째,
`python -m backtest_service.author_check <id>`가 exit 0이고 단계 9가 건너뜀이 아니다. 둘째,
`verify-strategy` 절차가 원문 대비 차이 기록표(3.6)의 행마다 확인을 마쳤다. 셋째, 프로그램이 못 보는
체크리스트 항목(판단 edge만 소유하는가, look-ahead가 없는가, 방향별 진입·청산 증거)은 사람이
본다. 공통 규범 검사가 생기면 셋째의 앞 둘은 첫째로 옮겨 간다."

#### 3.4.1 인공 캔들 경로 실행 모듈

`services/backtest-service/backtest_service/diagnostics/synthetic_dry_run.py`에
`test_document_sourced_strategies_engine.py`의 인공 캔들 공급 어댑터, 메모리 카탈로그, 등록 행 fixture,
실행 설정 생성을 옮기고 시험은 그 모듈을 import한다. **등록 행 fixture는 세 전략의 고정 표가
아니라 발견 결과에서 id로 만든다.** 그래야 `vessel-reference`를 포함한 배포 전략 전부와 앞으로
더해질 전략에 같은 명령이 닿는다.

**배포 패키지에 시험용 대체 구현이 들어간다.** 메모리 카탈로그는 결정성 참조를 "이전 실행 없음"으로
꾸며 내고 등록 행 fixture는 배포된 클래스에서 행을 지어낸다. 받아들이는 이유는 이 대체 구현들이
진단 전용이며 `diagnostics` 하위 패키지에 격리되고, 운영 어댑터(`adapters/`의 PostgreSQL
구현)와 이름도 자리도 겹치지 않으며, `backtest_service/__init__.py`와 일반 소비 모듈이 그것을
import하지 않아 `web_api`에 import 비용이 생기지 않기 때문이다. `tests/conftest.py`와 다른
시험의 `DataFeed` 대체 구현은 그대로 두고, 이 인수 시험 하나만 진단 모듈을 쓰도록 옮긴다.

캔들 경로는 **현재 시험의 320봉 warm-up과 240봉 평가 구간, 고정 seed**를 그대로 둔다.
전략마다 길이를 바꾸면 난수 열이 달라져 시험의 판정(청산 사유, 전략 셋의 거래 수 차이)이
흔들리기 때문이다. 명령은 전략 id와 mode와 그 mode의 설정을 받는다. 시험은 자기 설정을
명시적으로 넘긴다(지금도 그렇다). 출력은 거래 수, 청산 사유 분포, 무결성 결과,
`warmup_candles`, hash 둘의 일치 여부다. Evidence 파일은 임시 디렉터리에 쓰고 지운다.

#### 3.4.2 단계 1부터 5의 자리

단계 1부터 5는 `services/trading-plugins/trading_plugins/author_check.py`에 둔다. 사실 모듈
`facts.py`를 import해 쓰되 그 파일을 고치지 않는다. `facts.py`의 닫힌 명령 집합(`_USAGE`,
`_arguments`, `__all__`)과 `test_facts.py`의 고정 시험을 건드리지 않기 위해서다. 새 모듈은
자기 명령줄(`python -m trading_plugins.author_check <id>`)을 갖는다.

MCP 서버에는 **명시적인 wrapper 함수 하나를 더해** `author_check` 도구로 싣고, 그 wrapper의
오류 경계(플러그인 예외를 도구 오류로 바꾸는 것)와 도구 목록을 `test_mcp_server.py`가
확인한다. 이것은 등록 MCP 설계 3장이 정한 "MCP 껍데기는 사실 모듈 위에 얹는다"를 한 모듈
더로 넓히는 것이며, 그 설계 문서에 한 줄로 적어 둔다. 새 모듈은 데이터베이스에 닿지 않고
JSON만 내며 플러그인 예외를 단계의 실패로 바꾼다는 사실 모듈의 규칙을 그대로 따르고, 배포
재고 이름을 소스에 쓰지 않는다는 시험을 `author_check.py`에 대해 따로 건다(`test_facts.py`의
시험은 `facts.py`만 본다).

`backtest_service.author_check`는 이 모듈을 import해 단계 1부터 5를 돌리고 6부터 9를 더한다.
저장소 뿌리에 `scripts/author_check.py`를 둔다면 이 명령을 부르는 얇은 호출자일 뿐이며, 판정
코드는 서비스 안에 있어 그 서비스의 ruff·mypy·pytest를 지난다.

### 3.5 전략마다 반복되는 공통 코드를 플랫폼이 소유한다

**기반 클래스에 보조 다섯을 더한다.** `core_lib.strategy.StrategyBase`에 정적 메서드
다섯을 둔다. `read_inputs(market_data)`는 규범 4.1절의 여섯 입력(`candles`, `candle`,
`symbol`, `timeframe`, `market_type`, `indicators`)을 형 확인과 함께 꺼내 불변
`DecisionInputs`로 돌려준다. `series(inputs, name, params)`는 `series_key_of`로 key를 만들어
`inputs.indicators`에서 읽고 없으면 선언 누락을 말하는 `KeyError`를 올린다.
`number(value, name)`은 `bool`을 제외한 `int`·`float`만 받아 `float`로 돌려주고,
`outputs(value, name)`은 사전 출력만 받아 `Mapping[str, float]`로 돌려주며,
`decide(candle, action, reason, *, adaptee, confidence=1.0, metadata=None)`은 규범 4.1절이
정한 필드 규칙대로 `DecisionIntent`를 만든다. 다섯 다 상태가 없다. 기존 `series_value`는
`SeriesSpec`을 받고 없으면 `KeyError`를 올리는데 전략 넷이 모두 `series_key_of`와 `get`을 쓴
것은 그 모양이 판단 코드와 맞지 않았기 때문이다. `series_value`는 그대로 둔다.

규범 4.1절의 예시와 `vessel_reference.py`, 새 전략 셋을 이 보조로 다시 맞추는 것은 별도
changeset이며, 판단이 바뀌지 않음을 기존 시험과 인공 캔들 경로의 Evidence hash로 확인한다.

**전략 초안 생성기를 둔다.** 선언은 채우고 판단 로직만 비운 전략 파일을 만드는 도구다. `python -m trading_plugins.scaffold <입력 JSON>`이 JSON 하나(전략
id, 클래스 이름, series 목록, 지원 시간대, `min_history`, 지원 정책과 기본 정책, capability
넷, parameter 목록, `StrategyProfile` 열두 값)를 받아 넷을 만든다. 전략 모듈(선언은 입력
그대로이고 **`decision_contract=StrategyDecisionContract.DECISION_INTENT`를 언제나 낸다**,
`analyze`는 보조로 값을 읽은 뒤 `# 여기부터 판단`이라는 자리만 비운 채 `HOLD("scaffold")`를
돌려줌), 시험 모듈(선언 대조, 등록 파일 대조, `series_key_of`로 만든 key를 쓰는 판단 시험의
빈 자리), 등록 SQL(`registration_sql`로 생성해 `init-scripts/signal-service/<날짜>/`에 씀),
그리고 `init-scripts/06-init-signal-registry.sql`에 그 파일을 포함하는 `\ir` 줄이다. legacy
`TradingSignal` 방식의 초안은 만들지 않는다. 정책 초안도 이 단계에서 만들지 않으므로 OpenAPI
재생성은 생성기의 범위 밖이며, 정책을 배포할 때 `npm run generate:api`가 필요하다는 사실은
규범 6.4절에 적는다. 생성 직후의 초안은 판단 없이도 `author_check` 단계 1부터 5와 7을 통과해야
한다. 그래야 작성자가 채우는 것이 판단 로직뿐이다.

생성기는 파일을 만드는 도구이므로 사실 모듈에 두지 않고 별도 모듈로 둔다. 존재하는 파일은
덮어쓰지 않고 거부한다.

### 3.6 원문 대비 차이 기록표: 원문과 구현의 차이를 구조로 남긴다

첫째 책임은 "원문 그대로"가 아니라 **"원문과 다른 곳을 하나도 숨기지 않고, 측정하는 질문이
바뀌는 차이는 사람이 승인한다"**로 정의해야 프로그램과 사람이 지킬 수 있다.

전략 기술 문서(`docs/samples_for_strategy_agent/`의 형식)에 절 하나를 필수로 둔다. 제목은
"원문 대비 차이 기록표"이고 열은 넷이다. 원문 규칙, 플랫폼 표현, 차이의 종류, 근거. 차이의
종류는 셋 중 하나다.

| 종류 | 뜻 | 절차 |
|---|---|---|
| 능력 부재로 강제됨 | 능력 목록의 항목 때문에 원문대로 표현할 수 없어 다른 규칙을 씀(지표 교차를 상태로 읽는 것) | 구현 전에 사람이 승인한다 |
| 빈 값을 정함 | 원문에 없는 수치를 골랐음(시간대, 손절 배수, 문턱) | 지시가 있으면 진행하되 장부에 근거를 적는다 |
| 근사함 | 원문 규칙을 조금 다른 규칙으로 대신함(영점 조건을 판단 봉 부호로 읽는 것) | 구현 전에 사람이 승인한다 |

`author-strategy` skill 4장과 5장의 "차이를 모아 한 번 묻는다"를 이 표로 바꾼다. 기록표의
각 행은 전략 모듈 docstring에 같은 표로 옮겨 적고, `verify-strategy` 절차는 기록표의 행마다
그 차이가 실제로 그렇게 구현됐는지를 확인 항목으로 삼는다(예: 상태 규칙으로 읽었다면 손절 뒤
재진입이 몇 번 있었는지 세어 보인다).

"질문하지 말고 진행하라"는 지시가 있을 때 첫째와 셋째 종류에서도 멈출지는 설계가 정할 일이
아니라 사용자가 정할 일이므로 8장에 둔다.

이 단계에서는 기록표를 프로그램이 검사하지 않는다. 기록표를 구조화된 파일로 두고 검사하는 것은
둘째 단계(중간 언어)의 일이다.

## 4. 하지 않는 것

- 중간 언어와 변환기. 7장에 경계만 적는다.
- 공통 규범 검사 묶음의 나머지 구현. 별도 설계가 있고 `author_check`는 그 자리를 비워 둔다.
- 운영 데이터베이스에 쓰는 도구. 단계 9는 표시가 붙은 시험을 부를 뿐이고, 등록 적용은 사람의
  절차로 남는다.
- 화면과 Web API의 변경.
- 기존 전략 넷의 판단 로직 변경. 보조 메서드로 다시 맞추는 changeset은 판단을 바꾸지 않는다.
- 정책 초안 생성과 legacy 방식의 전략 초안.
- 사실 함수에 시험용 우회 인자를 두는 것.

## 5. changeset 분리와 순서

1. **식별자 규칙과 능력 항목 둘.** `core_lib/identifiers.py`, `run_config`의 교체,
   `capabilities.py`의 두 항목, `services/core-lib/tests/test_identifiers.py`(DDL 대조),
   `test_engine_and_harness.py`의 series 값 범위 시험. 이 changeset만으로 능력 목록 시험이 초록이다.
2. **발견 fault와 사전 점검 확장, 규범 예시 시험, 규범 편집.** `discovery.py`의 형식 fault,
   `facts.py`의 형식 finding과 `checks_performed`, `test_contract_examples.py`, 규범 4.1절
   예시의 클래스 선언과 `decision_contract` 선언, 표시 주석 둘, 6.4절과 6.5절의 문장.
   `plugin.identifier_format`의 `verified_by`에 발견 fault 시험을 더한다.
3. **`synthetic_dry_run` 진단 모듈.** 등록 행 fixture를 발견 결과 기반으로 바꾸고 기존 인수
   시험이 그 모듈을 쓰도록 옮긴다. 시험의 판정은 바뀌지 않는다.
4. **`trading_plugins.author_check`(단계 1부터 5)와 `backtest_service.author_check`(6부터
   9), MCP wrapper, 통합 시험의 매개변수화, skill 문구.** 결함 주입 시험 셋을 함께 둔다. 밑줄 id
   정책은 발견 fault로, 미등록 조합을 선언한 전략은 단계 2의 `series-unregistered`로,
   `supported`에 배포되지 않은 mode를 적은 전략은 단계 3의 `policy-mode-not-deployed`로
   실패해야 한다. 배포된 전략 넷 전부에 대해 exit 0을 확인한다.
5. **`core_lib` 보조 다섯과 전략 초안 생성기.** 그 뒤 기존 전략 넷을 보조로 다시 맞추는 changeset을
   따로 둔다.
6. **원문 대비 차이 기록표.** 전략 기술 문서 형식, 두 skill의 문구, 새 전략 셋의 문서에
   기록표를 소급해 적는다.

1과 2가 인수 시험에서 난 실패 둘을 직접 막고, 4가 배포 전 검사를 세운다. 5와 6은 그 뒤에
얹는다. 이 문서의 구현은 하네스가 정한 대로 turn 상한을 두며, 60 turn을 넘기면 멈추고
보고한다.

## 6. 무엇을 만족하면 닫힌 것인가

- `python -m backtest_service.author_check`가 배포된 전략 넷(`vessel-reference`,
  `supertrend-ema200-flip`, `macd-ema200-zero-line`, `bollinger-rsi-reversion`)에 대해
  exit 0이고, 단계마다 통과·실패·건너뜀이 사유와 함께 JSON에 있으며, 단계 6이 지원 mode
  전부에 대해 돌았고, **단계 9가 실제로 하나 이상의 시험을 수집해 돈 실행이 이 transcript에
  하나 이상 있다.**
- 결함 주입 셋이 각각 지정한 단계에서 실패하고, 실패의 `rule` 값이 시험이 고정한 어휘 안에
  있다. 밑줄 id 정책은 발견 fault, 미등록 조합은 `series-unregistered`, 배포되지 않은 mode는
  `policy-mode-not-deployed`. 기본값 없는 설정을 가진 정책을 지원하는 전략에 설정 파일 없이
  명령을 돌리면 `policy-settings-required`로 실패한다.
- `test_contract_examples.py`가 규범의 두 예시 블록을 임시 패키지에 배포하고, 지원 mode마다
  `create_runtime`을 통과시키며, 전략 예시가 최소 시나리오에서 `DecisionIntent`를 낸다. 예시의
  id에 밑줄을 넣거나 클래스 선언 또는 `decision_contract` 선언을 지우면 그 시험이 실패한다.
- `test_identifiers.py`가 통과하고, `PLUGIN_IDENTIFIER_PATTERN`의 글자를 바꾸면 실패한다.
- 능력 목록 두 항목이 `facts capabilities`로 조회되고 `verified_by`의 시험이 존재해 통과한다.
- 규범의 편집 다섯(4.1절 예시의 클래스 선언과 `decision_contract` 선언, 두 표시 주석, 6.4절
  문장, 6.5절 문장)과 skill의 편집 셋(3.2의 절차 규칙, 3.4의 완료 정의, 3.6의 차이 기록표),
  등록 MCP 설계의 한 줄이 grep으로 확인된다.
- `synthetic_dry_run`을 같은 id와 mode로 두 번 돌린 hash가 같고, `vessel-reference`에도 돌며,
  기존 인수 시험이 옮긴 모듈로 그대로 통과한다.
- `test_mcp_server.py`가 `author_check` 도구와 그 오류 경계를 확인한다.
- 전략 초안 생성기가 만든 전략이 손대지 않은 채 `author_check` 단계 1부터 5와 7을 통과하고, 만든
  모듈에 `DECISION_INTENT` 선언이 있으며, 만든 `\ir` 줄이 06 스크립트에 있다.
- 저장소 뿌리 `.venv/bin/python -m pytest services -q`가 exit 0, `ruff check`와
  `ruff format --check`가 exit 0, 바뀐 서비스 디렉터리 안의 mypy가 exit 0이다.

## 7. 둘째 단계와의 경계

둘째 단계는 전략을 파이썬이 아니라 중간 언어로 적고 변환기가 파이썬을 만드는 것이다. 이
문서의 산출물은 그때 그대로 쓰인다. `author_check`는 변환기가 만든 코드에도 같은 판정을
내리고, 초안 생성기의 출력 형식이 변환기의 출력 형식이 되며, 차이 기록표는 중간 언어의 한 절이
된다. 언어의 범위는 이 단계에서 쌓인 전략들이 실제로 쓴 규칙 모양(series 값 비교, 상태
정렬, 밴드 돌파, 문턱 교차)에서 정한다.

## 8. 열려 있는 결정

- "질문하지 말고 진행하라"는 지시가 있을 때, 차이 기록표의 첫째와 셋째 종류(능력 부재로 강제됨,
  근사함)에서도 멈춰 승인을 받을지. 3-1 인수에서는 사용자 지시로 결정으로 대체한 전례가 있다.
- `author_check` 단계 9(일회용 데이터베이스 적용)를 CI에서 필수로 할지. 지금 CI에는 로컬
  PostgreSQL이 없어 건너뜀으로 남는다.
- 전략 초안 생성기가 `StrategyProfile` 열두 값을 입력으로 요구할지, 표시 자리만 두고 `provisional`
  기본값을 채울지. 규범 4.1절이 일곱 값의 기준을 아직 정하지 않았다.
- 기존 전략 넷을 보조 메서드로 다시 맞추는 일을 5번 changeset에 붙일지 따로 둘지.
- 인공 캔들 경로에서 거래가 0건인 mode를 경고로 둘지 실패로 둘지. 그 경로는 전략마다 다르게
  설계되지 않았으므로 정당한 전략도 0건일 수 있다.

## 9. 검토에서 바로잡힌 사실

모두 코드로 확인한 뒤 받아들였다.

### 9.1 내부 검토(같은 모델 계열, 독립 문맥)

- **규범 4.1절의 예시 전략은 발견 검사에 걸린다.** `STRATEGY_ID`가 모듈 상수뿐이고 클래스에
  없어 발견이 fault를 낸다. 규범 6.5절이 요구하는 것을 규범의 예시가 어기고 있었다. 3.3에 예시
  수정을 넣었다.
- **사실 함수는 고정 패키지만 본다.** 임시 패키지의 예시나 결함 전략에 `catalog_precheck`와
  `registration_sql`이 닿지 않는다. 처음에는 주입 인자로 풀려 했으나 외부 검토가 모듈 경로
  검사까지 지적해 3.3을 다시 고쳤다(9.2).
- **"`supported` 밖의 `default`"는 단계 3에 이르지 못한다.** `MoneyManagementSupport`가
  생성 시점에 거부하므로 선언 읽기 실패로 나타난다. 결함 주입 셋째를 "배포되지 않은 mode를
  `supported`에 적음"으로 바꿨다.
- **단계 2·3·4는 공통 규범 검사 설계 10절의 4·5·6번과 같았고, 단계 3의 정합 대조는 런타임
  규칙의 복제였다.** 관계를 명시하고 단계 3이 `create_runtime`을 직접 부르게 했으며, 기본값
  `resolve`는 단계 5에 흡수했다.
- **warm-up 계산은 Engine에만 있다.** 단계 2에서 warm-up 계산을 빼고 단계 6이 Engine의
  `warmup_candles`를 보고하게 했다.
- **인공 캔들 경로의 길이를 전략마다 바꾸면 기존 시험의 판정이 흔들린다.** 320봉과 240봉 고정 경로로
  못박고 시험이 자기 설정을 명시적으로 넘긴다고 적었다.
- **`synthetic_dry_run`은 시험용 대체 구현을 배포 패키지에 들이는 일이다.** 순환은 없지만 그 사실과
  받아들이는 근거, `conftest.py`의 대체 구현과의 관계를 3.4.1에 적었다.
- **changeset 1이 홀로 실패 상태로 끝날 순서였고 정규식이 네 번째로 복사될 참이었다.**
  `verified_by`를 changeset별로 나누고, 상수를 독립 모듈에 두어 `capabilities.py`가 import하게
  했다.
- **저장소 뿌리의 `scripts/`는 어떤 QA 검사도 거치지 않는다.** 판정 코드를 서비스 모듈로 옮기고
  뿌리 스크립트는 얇은 호출자로만 남겼다.
- **단계 8의 기준은 fixture 문자열로도 만족됐고, 단계 9는 등록 MCP 설계 6장의 결정을 도구로
  되돌리는 것이었다.** 단계 8을 "전략 클래스를 import하는 시험 모듈"로, 단계 9를 "표시가 붙은
  통합 시험을 부른다"로 바꿨다.
- **완료 기준에 규칙 이름 어휘, 규범과 skill의 편집, turn 상한, 초안 생성기의 06 포함, 건너뜀
  허용 범위가 없었다.** 6장과 5장에 더했다.
- **사실 모듈의 소스에는 배포 재고 이름을 쓸 수 없고 `main`은 예외를 뭉갠다.** 단계 1부터 5를
  별도 모듈에 두어 `facts.py`의 닫힌 집합과 시험을 건드리지 않게 했고, 같은 재고 이름 시험을
  새 모듈에 걸며 단계마다 예외를 잡게 했다.
- **1장의 "형 검사 실패와 key 오기" 출처가 인수 기록에 없었다.** 이 세션의 QA에서 난 것임을
  적고 인수 기록에 없다는 사실을 밝혔다.
- **`series.history_depth`의 시험 설계가 주장을 증명하지 못하고 `series.value_shapes`와
  겹쳤다.** key 집합과 봉별 값 대조로 바꾸고 관계를 문장에 적었다.
- 사소한 정정: 등록 MCP 설계의 절 번호(7장이 아니라 6장), `_NOT_CHECKED`에서 빼는 것이 아니라
  `checks_performed`에 더하는 것, `series_value`가 안 쓰인 이유, 정규식 두 표기의 차이,
  `read_inputs`가 여섯 입력을 다 다루는 것과 `number`의 `bool` 제외, 절 번호마다 문서 경로를
  붙이는 것, 사용자 지시를 무효화하는 규칙을 열린 결정으로 옮긴 것.

### 9.2 외부 검토(Codex, `gpt-5.6-terra`)

- **인공 캔들 시험은 "배포된 전략"이 아니라 새 전략 셋만 돌린다.** `_STRATEGIES`가 셋으로 고정되어
  `vessel-reference`가 빠져 있었고, 그대로 옮기면 넷에 대한 완료 기준이 성립하지 않았다. 2장의
  서술을 고치고 등록 행 fixture를 발견 결과 기반으로 바꿨다(3.4.1).
- **규범 4.1절의 예시는 `decision_contract`를 선언하지 않아 정책을 붙일 수 없다.** 기본값이
  `TradingSignal`이라 `create_runtime`이 거부한다. 발견과 사전 점검은 통과하고 단계 3에서만
  드러나는 결함이었다. 예시 수정에 그 선언을 더했다(3.3).
- **임시 패키지의 예시에는 등록 문장 생성이 성립하지 않는다.** `_validate_module_path`가 실제
  배포 패키지 경로만 허용한다. 예시 시험에서 등록 문장 생성과 사전 점검을 빼고, 사실 함수에
  시험용 우회 인자를 두지 않기로 했다(3.3, 4장).
- **`series.history_depth`의 문장이 과했다.** 확정 캔들은 전부 오므로 캔들 값끼리의 교차는
  표현된다. 등록된 series의 직전 값이 없다는 것으로 좁혔다(3.2).
- **단계 3은 기본값 없는 설정을 가진 정책에 대해 만들 수 없고, `create_runtime`은 `create`를
  다시 부른다.** mode별 대표 설정을 `--mode-settings`로 받고 없으면 `policy-settings-required`로
  실패하게 했으며, 중복 생성은 의도된 것으로 적었다(3.4).
- **새 모듈을 둔다고 MCP 도구가 생기지는 않는다.** wrapper는 명시적이다. wrapper와 그 시험,
  등록 MCP 설계의 한 줄을 3.4.2와 6장에 더했다.
- **이 검사는 지원하는 모든 정책 경로와 방향별 진입·청산 증거를 증명하지 못하므로 완료
  판정이 아니다.** 단계 6을 지원 mode 전부로 넓히고, 이름을 배포 전 검사로 바꾸고, 완료의
  정의를 배포 전 검사·검산·사람의 확인 셋으로 다시 썼다(문서 제목, 3.4, skill 문구).
- **통합 시험의 이름에 전략 id가 없어 `-k <id>`가 아무것도 고르지 못한다.** 시험을 배포된
  전략과 정책으로 매개변수화하고, 명령이 수집 건수를 확인하게 했다(3.4, 5장 4번).
- **초안이 `decision_contract`를 내지 않으면 기본값 `TradingSignal` 때문에 단계 3에서
  실패한다.** 생성기가 언제나 `DECISION_INTENT`를 내고 legacy 초안은 만들지 않게 했다(3.5).
- 외부 검토가 확인한 것: `diagnostics` 하위 패키지를 일반 모듈이 import하지 않는 한 순환도
  import 비용도 생기지 않는다.
- **확인 검토(같은 Codex)가 고친 판에서 찾은 것 하나.** 2장의 "`web_api`는 설정과 runner
  경로만 import한다"는 틀렸다. `web_api/main.py`는 `backtest_service.adapters.catalog_store`도
  import한다. 운영 모듈을 import하되 진단 모듈은 import하지 않는다는 뜻으로 고쳤다. 아홉
  항목의 반영은 모두 본문에 있음을 같은 검토가 확인했다.
