# 전략의 정책 설정 기본값 선언과 기록 규칙 보강 설계

> 작성일: 2026-09-25 (같은 날 Codex 설계 검토를 반영해 고쳐 씀)
> 상태: 2차 검토를 반영해 구현함(2026-09-25). 구현은 8장의 판정대로이며, 코드 리뷰(Codex)를 거쳐 커밋한다.
> 선행 문서: `docs/fullspec/stage_3_1_acceptance_three_strategies.md` 5.7절과 7장 13·14·15·16번,
> `docs/fullspec/author_check_and_scaffold_design.md`(승인된 배포 전 검사 설계).
> ClickUp: 전략이 지원 정책의 설정 기본값을 선언할 수 있게 한다(z8nrz7e3k9).

## 1. 지금 무엇이 아쉬운가

전략 작성 Agent가 절차대로 만든 다섯 번째 전략(세 봉 평균회귀)은 코드가 원문대로 오류 없이
돌았지만, 회차의 검토가 코드 밖에서 셋을 남겼다.

첫째, **원문이 정한 보호 값이 배포에 실리지 않는다.** 원문은 "1.5×ATR 손절, 1.5R 목표"라고
정했는데, 전략은 정책을 이름(`manual`)으로만 지원하고 정책 설정의 값을 밝힐 자리가 없다.
그래서 화면 기본값과 설정 없는 실행은 manual 정책의 기본값(손절 배수 2.0, 손익비 2.0)으로
돌고, 원문과 다른 전략이 된다. Codex가 네 번째 전략(Donchian, 1.5×ATR·2R)과 다섯 번째 전략에서
두 번 Blocking으로 지적했다. 규범 7장은 이미 "처음 값은 전략이 그 mode에 대해 밝힌 기본값에서
채운다"고 적어 두었는데, 전략이 밝힐 자리가 플랫폼에 없어 그 문장이 실현되지 않는다.

둘째, **Agent의 기록에 정밀도 결함이 셋 있었고, 절차가 그 항목을 요구하지 않았다.** `StrategyProfile`의
열두 값을 Agent가 채웠지만 어디서 왔는지 기록하지 않았다. 체결 봉에서는 손절과 목표를 검사하지
않는 Engine 규칙이 거래 66건(전체 손실의 약 45%)의 결과를 바꿨는데, 능력 목록이 이 규칙을 말하지
않아 Agent가 인용할 근거가 없었다. 출처의 자료가 "spot 봉"이라는 단정은 연구 공통 문장에서 온
것인데 그 페이지의 문장인 것처럼 적혔다. 네 번째 전략의 `4h` 광고도 같은 종류의 결함이다. 출처가
말하지 않은 시간대를 선언했고, 절차에 "선언은 출처의 차트 세팅을 넘지 않는다"는 규칙이 없었다.

셋째, **규범 9.1절의 공통 시험은 전략마다 손으로 써야 한다.** 이것은 승인된 배포 전 검사 설계와
층별 공통 규범 시험(ClickUp z8nrz7e3k1)이 닫는 것이므로 이 문서의 범위 밖이다.

## 2. 코드에서 확인한 사실

- `services/core-lib/core_lib/strategy/base.py` 22~40행. `MoneyManagementSupport`는
  `@dataclass(frozen=True, slots=True)`이고 자리가 여섯(`supported`, `default`,
  `supports_external_stop`, `supports_external_take_profit`, `supports_signal_exit`,
  `supports_pyramiding`)이다. `__post_init__`은 mode 중복과 `default`가 `supported` 밖인 것을
  거부한다. 정책 설정 값을 담는 자리는 없다.
- `services/backtest-service/backtest_service/config/run_config.py`. 37~57행의 manual과 Turtle
  설정 모델은 손으로 쓴 것이고 기본값(leverage 1, reward_risk 2.0, atr_stop_multiple 2.0 등)을
  `Field`로 갖는다. 60~121행의 `_config_model_for`는 파일로 배포된 정책의 dataclass에서 모델을
  만들고 검증 시점에 정책을 한 번 구성한다. 두 종류 모두 사용자가 비운 필드를 **정책의 기본값으로
  채운다.** 367행에서 `RunConfig.money_management`의 기본은 `ManualMoneyManagementConfig()`
  (규범 5.5절의 "없으면 manual")이고, 370~389행의 `_normalize_legacy_money_management`가
  `vessel-reference`의 옛 값을 manual 설정으로 옮기는 before 검증기다. 474~476행의 `revalidate`는
  `model_dump()`로 다시 검증한다.
- **파생 실행은 전체 덤프로 만들어진다.** `services/web-api/web_api/main.py` 543~553행의
  `_prepare_sweep`은 `base.model_dump()`를, `services/backtest-service/backtest_service/harness/harness.py`
  325~346행의 `_segment_config`는 `config.model_dump()`를 새 `RunConfig`의 입력으로 쓴다. 전체 덤프는
  정책 기본값으로 채워진 값을 담으므로, "사용자가 비웠다"는 사실은 파생 실행에 전해지지 않는다.
- `services/backtest-service/backtest_service/engine/engine.py`. 378~382행에서 Engine은
  `config.money_management.model_dump()`를 `manager.create_runtime`에 넘긴다. 457~460행에서
  `params_json`에 `_money_management`(정책 id·version·`config_schema_version`·`resolved_config`)를
  넣고, 509행에서 `normalized_config_hash(self._run_meta)`로 설정 해시를 만든다.
  `services/backtest-service/backtest_service/adapters/catalog_store.py` 21~45행의
  `_CONFIG_HASH_FIELDS`에 `params_json`이 있으므로 **해석된 정책 설정은 이미 설정 해시에
  들어간다.** 실행 `BT_20260925_001516`의 카탈로그 행 `params_json`은
  `{"_money_management": {..., "resolved_config": {"mode": "manual", "leverage": 1,
  "reward_risk": 1.5, "atr_stop_multiple": 1.5}}}`이다. 2288~2291행에서 Evidence에
  `submitted_money_management_json`은 `exclude_unset=True`로 사용자가 지정한 필드만,
  `money_management_json`은 `_money_management_evidence()`(2003~2024행)의 값을 적는다.
- `services/backtest-service/backtest_service/adapters/evidence_schema.py` 13행
  `EVIDENCE_SCHEMA_VERSION = "1.10.0"`. `services/backtest-service/tests/test_engine_and_harness.py`
  3789~3795행이 판마다 네 고정 실행의 Evidence 해시를 고정하고, 3833~3847행의 설명은 해시되는
  내용이 바뀌면 같은 변경에서 판을 올려야 한다고 정한다.
- `services/core-lib/core_lib/strategy/manager.py` 70~121행. `AdapterManager.create_runtime`은
  전략을 만들고, 지원 mode가 없으면 정책 없이 돌려주며, mode의 runnable 여부를 확인한 뒤
  `MoneyManagementFactory.create(money_management_config, policies)`로 정책을 만들고 전략이 그
  mode를 지원하는지와 `requires_signal_exit` 정합을 확인한다. 전략의 선언이 정책 설정에 관여하는
  자리는 없다.
- `services/core-lib/core_lib/money_management/registry.py` 29~47행. `MoneyManagementFactory.create`는
  최상위 `mode`를 요구하고, 정책이 받는 이름 밖의 키를 거부하며, 주어진 이름만 넘겨 dataclass
  기본값이 나머지를 채운다. 정책의 `__post_init__`이 범위를 검증한다.
- `services/signal-service/signal_service/application/service.py` 114~126행. 신호 생성 세션은
  `config.params`에서 `leverage`, `reward_risk`, `atr_stop_multiple`을 꺼내되 **없으면 1, 2.0, 2.0을
  직접 넣어** manual 설정을 만들고 `create_runtime`에 넘긴다. 이 경로에서는 전략 선언이 들어갈
  틈이 없다. `SignalGenerationConfig`(`core/config.py` 14행)에는 자금관리 필드가 없다.
- `services/web-api/web_api/repository.py` 183~241행과 661·743행. 전략 목록의
  `default_money_management`는 `_money_management_options(support.supported, support.default)`가
  돌려주는 값이고, 그 값은 모듈 적재 시 정책 기본값으로 얼려 둔 JSON을 요청마다 새로 풀어 낸
  것이다. 전략 선언은 여기 들어가지 않는다. 655~667행의 바깥 예외 처리는 선언 읽기가 실패하면
  mode 목록을 비우고 전략을 실행 불가로 표시한다. `services/web-api/tests/test_runs_api.py`
  520~535행과 561~600행이 "기본값은 정책에서 온다"와 두 인자 helper를 고정한다.
- `services/web-api/web_api/main.py` 384~389행. 제출은 `RunConfig.model_validate(value)`로
  검증된다. `RunConfig`는 `models.py` 847·872행의 `SkipValidation[RunConfig]`로 요청 봉투에 들어
  있어 OpenAPI에 노출된다. 필드를 더하면 `npm run generate:api`로 생성 파일을 갱신해야 한다.
- `apps/web/src/pages/run-management-page.tsx` 1055~1091행. 화면은 전략 응답의
  `default_money_management`에서 `mode`, `leverage`, `reward_risk`, `atr_stop_multiple`을 읽어
  처음 한 번 채운다(규범 7장). 응답 모델 `StrategyOption.default_money_management`는
  `dict[str, object]`라 값이 바뀌어도 그 스키마는 바뀌지 않는다.
- `services/trading-plugins/trading_plugins/__init__.py`는 `discover_strategies`,
  `build_strategy_registry`, `discover_money_management`, `registered_money_management`를 내보낸다.
  `facts.py` 197~216행의 `declaration`은 `money_management`의 여섯 자리를 이름을 적어 내보내므로
  새 자리는 명시적으로 더해야 보인다. 562~590행의 `_precheck_strategy`는 등록 행과 선언을
  대조하고 `AdapterManager.create`로 어댑터만 구성하며 정책은 구성하지 않는다.
- `services/core-lib/core_lib/execution/matcher.py` `resolve_triggers`. `PositionBook.skip_first_sl_check`가
  참이면 `candle.open_time <= entry_time`인 캔들(체결 봉)을 통째로 건너뛰므로 손절·목표·강제청산
  셋 다 다음 봉부터 검사된다. 같은 봉에서 손절과 목표에 함께 닿으면 손절을 택한다.
  `services/core-lib/core_lib/execution/position_book.py` 24행에서 `skip_first_sl_check`는
  `ClassVar[bool]`이며 실행 설정이나 API로 바꾸는 자리는 없다.
  `services/core-lib/tests/test_execution.py` 363행
  `test_trigger_gap_uses_unfavorable_open_and_skips_the_fill_candle`은 **손절**이 체결 봉에서
  건너뛰어지는 것만 시험하고, 348행 `test_simultaneous_stop_and_take_profit_resolves_to_stop_loss`는
  동시 도달의 손절 우선을 시험한다.
- `services/core-lib/core_lib/capabilities.py`. 능력 항목은 27개이고 보호 검사 시점을 말하는 항목이
  없다. 항목마다 `verified_by`가 실재하는 시험 함수여야 한다
  (`services/core-lib/tests/test_core_lib_capabilities.py::test_every_capability_names_a_test_that_exists`).
- `docs/strategy-authoring-contract.md` 4.3절은 여섯 자리를 표로 적고, 5.5절은 "`money_management`가
  없는 설정은 manual로 해석하며 기본값은 leverage 1, reward_risk 2.0, atr_stop_multiple 2.0"이라
  적고 `submitted_money_management_json`이 "사용자가 실제로 지정한 필드만" 담는다고 적으며, 7장
  1786~1788행은 "처음 값은 전략이 그 mode에 대해 밝힌 기본값에서 채운다"고 적는다.
- `.claude/skills/author-strategy/SKILL.md`. 2단계 구조화 항목은 방향·진입·청산·위험·시간대·종목·series다.
  프로필 값, 플랫폼이 고정한 규칙, 출처 문장의 인용 위치, "출처가 말하지 않은 것을 선언하지
  않는다"는 규칙이 없다.
- 승인된 배포 전 검사 설계 3.4절 "mode별 대표 설정"은 정책 설정에 기본값이 모두 있으면 기본값을,
  없으면 `--mode-settings` 파일을 쓴다. 전략이 선언한 값을 대표 설정으로 쓰는 규칙은 없다.

## 3. 무엇을 만드는가

### 3.1 `MoneyManagementSupport.default_settings`: 전략이 지원 mode의 설정 값을 선언한다

`MoneyManagementSupport`에 일곱째 자리 `default_settings: Mapping[str, Mapping[str, object]]`를 둔다.
키는 mode 이름, 값은 그 정책이 받는 설정의 부분집합이다. 기본은 빈 mapping이다.

```python
money_management=MoneyManagementSupport(
    supported=("manual",),
    default="manual",
    default_settings={"manual": {"atr_stop_multiple": 1.5, "reward_risk": 1.5}},
    supports_external_stop=True,
    supports_external_take_profit=True,
    supports_signal_exit=False,
    supports_pyramiding=False,
)
```

`__post_init__`이 구조만 검증한다. 키가 `supported` 밖이면 거부하고, 값이 mapping이 아니거나
`mode`라는 이름을 담으면 거부하며, 설정 값은 JSON 스칼라(`int`, `float`, `str`, `bool`)만 허용해
그 밖의 형과 **유한하지 않은 float(NaN, 무한)**를 거부한다. Evidence 직렬화가 유한하지 않은 값을
거부하므로 선언 시점에 막아야 실행 끝에서 터지지 않는다. 바깥과 안쪽 mapping을 `object.__setattr__`로 `MappingProxyType`으로 바꿔
두므로 불변이며, 값이 스칼라뿐이라 얕은 동결로 충분하다. 설정 이름이 정책에 있는지와 값이 범위
안인지는 core_lib이 정책을 모르므로 여기서 보지 않고, 정책을 실제로 구성하는 자리(3.2와 3.4)가
본다.

### 3.2 해석 규칙은 함수 하나, 적용은 설정이 만들어지는 경계마다

해석 순서는 **사용자가 지정한 값, 전략이 선언한 값, 정책의 기본값** 순이다. 규칙은 core_lib의 순수
함수 하나가 갖고, 설정이 만들어지는 경계마다 그 함수를 부른다. 1차 설계는 `create_runtime` 한
곳에서 "비운 필드"를 읽어 덮으려 했으나, 파생 실행(스윕, walk-forward, IS/OOS)이 전체 덤프로
만들어져 "비웠다"는 사실이 런타임에 닿지 않는다는 것이 검토에서 드러났다(8장). 그래서 해석을
**설정이 처음 검증되는 자리**로 옮긴다. 그 뒤로는 전략이 선언한 값이 설정에 명시된 값으로
남으므로, 전체 덤프로 만드는 파생 실행에도 그대로 전해진다.

- **규칙 함수.** `core_lib.money_management.apply_declared_settings(support, submitted) -> dict`.
  `submitted`는 최상위 `mode`(문자열)를 가진 mapping이다. `{"mode": mode,
  **support.default_settings.get(mode, {}), **(submitted에서 mode를 뺀 것)}`를 돌려준다. 같은 결과에
  다시 적용해도 값이 바뀌지 않는다(멱등).
- **`RunConfig`.** 검증기 하나가 자금관리 설정을 해석한다. 기존 before 검증기
  `_normalize_legacy_money_management`를 **wrap 검증기 `_resolve_money_management` 하나로 바꾸고**,
  그 안에서 차례로 `vessel-reference`의 옛 값 이동, 제출 값 보존, 전략 선언 덮기를 한 뒤 안쪽
  검증을 부른다. 같은 클래스의 before 검증기 둘은 pydantic v2(설치된 2.13.4)가 선언의 역순으로
  돌리므로, 둘로 나누면 선언 덮기가 옛 값 이동보다 먼저 돌아 옛 값이 `params`에 남는다. 하나로
  합치는 것이 그 함정을 피하는 유일한 길이며, 옛 값 이동이 뒤에 오는 선언 덮기와 함께 도는
  회귀 시험을 둔다. 입력에 `money_management`가 없으면 `{"mode": "manual"}`로 읽고(규범 5.5절의
  "없으면 manual"과 같다), 배포된 전략의 선언을 찾아 규칙 함수를 적용한 값을 `money_management`로
  넣는다. 그 뒤 기존 pydantic 모델이 나머지를 정책 기본값으로 채우고 범위를 검증하므로, **전략이
  범위 밖 값을 선언하면 제출 시점에 거부된다.**
- **선언 조회는 느리게, 바꿔 끼울 수 있게.** `backtest_service.config.declarations.declared_money_management(strategy_id)
  -> MoneyManagementSupport | None`은 처음 불릴 때 `trading_plugins.discover_strategies()`를 한 번
  읽어 캐시한다. 모듈 적재 시 읽지 않는 이유는 `RunConfig`를 스키마 노출만을 위해 import하는 과정과
  가짜 전략만 등록하는 시험이 배포된 전략 모듈 전부의 import 비용과 실패를 떠안지 않게 하기
  위해서다. fault가 난 모듈과 배포되지 않은 id는 `None`이며 그때는 덮지 않는다. 시험은 캐시를
  monkeypatch로 바꿔 가짜 전략의 선언을 넣는다.
- **제출 값의 출처 보존.** 검증기가 선언 값을 입력에 넣으면 pydantic은 그 필드를 "지정된 것"으로
  보므로 `exclude_unset=True`로는 사용자가 지정한 것을 더는 가려낼 수 없다. 그래서 wrap 검증기가
  안쪽 검증이 돌려준 인스턴스에 **private 속성 `_money_management_submitted`**로 사용자가 보낸 원래
  mapping(없었으면 빈 dict, 옛 값 이동이 일어났으면 이동된 mapping)을 붙이고, 읽기 전용 속성
  `money_management_submitted`로 내보낸다. 필드가 아니므로 클라이언트가 지정할 수 없고
  (`extra="forbid"`가 그 이름을 거부한다), OpenAPI에도 나타나지 않아 생성 파일 갱신이 없다.
  web-api의 job은 검증된 `RunConfig` 인스턴스를 그대로 Engine에 넘기므로(`jobs.py` 214행) 속성이
  살아서 닿는다. 파생 실행은 부모의 전체 덤프로 다시 검증되므로 그 자식의 제출 값은 부모의 해석된
  전체 mapping이 되는데, 이것은 지금도 그런 동작이며(전체 덤프가 곧 제출 값) 규범 5.5절에 그렇게
  적는다. `model_copy`는 private 속성을 함께 복사한다.
- **`AdapterManager.create_runtime`.** 정책을 만들기 전에 같은 규칙 함수를 한 번 더 적용한다.
  `RunConfig`를 거치지 않는 호출자(신호 생성 세션, 시험)를 위한 안전망이며, `RunConfig`를 거친
  값에는 멱등이라 아무것도 바꾸지 않는다. 규칙은 여전히 함수 하나이고, 적용 지점이 둘이다.
- **Engine.** 378~382행은 그대로 전체 덤프를 넘긴다. `submitted_money_management_json`은
  `config.money_management_submitted`를 적는다. 모든 필드를 명시한 실행에서는 지금의
  `exclude_unset` 덤프와 같은 값이다.
- **신호 생성 세션.** `service.py` 114~126행의 직접 주입을 없애고, `config.params`에 **있는** 이름만
  manual 설정에 넣는다. 없는 값은 `create_runtime`의 안전망이 전략 선언과 정책 기본값으로 채운다.
  규범 10장의 "백테스트, paper 및 live가 같은 core policy 구현을 사용한다"가 이 값에도 성립한다.
  `SignalGenerationConfig`에 자금관리 필드를 더하는 일은 하지 않는다(4장).
- **`config_schema_version`을 `1.2.0`으로 올린다.** 규범 5.5절은 "해석은 두 층이 나눠 한다.
  실행 설정의 자금관리 모델이 기본값과 범위를 먼저 적용하고 정규화된 결과가 Factory에 간다.
  어느 한 층만 바뀌어도 해석이 달라지므로 version은 두 층을 함께 가리킨다"고 정한다. 이번 변경은
  실행 설정 층이 비운 값을 읽는 방식을 바꾸므로 그 문장대로 판을 올린다. 1차 설계는 Factory
  규칙이 그대로라는 이유로 올리지 않으려 했는데 규범이 두 층을 함께 가리키므로 그 판단이 틀렸다.
  `MONEY_MANAGEMENT_SCHEMA_VERSION`의 설명에 "1.2.0은 실행 설정 층이 비운 값을 전략 선언으로 먼저
  채운다"를 적고, 이 값을 고정한 시험(`test_engine_and_harness.py` 3936행,
  `test_output_adapters.py` 644행의 판별 골든 값)을 갱신한다.
- **설정 해시의 입력 목록은 바꾸지 않지만, 값은 모두 바뀐다.** `params_json._money_management`가
  `config_schema_version`과 3.7의 `declared_by_strategy`를 담으므로 앞으로의 모든 실행이 지난
  실행과 다른 `config_hash`를 갖는다. 결정성 검사는 같은 해시의 선행 실행을 찾지 못해
  `no_prior_config_run`으로 답하며, 이것이 판을 올릴 때의 정상 동작이다(옛 실행이 거짓 불일치로
  보고되는 일은 없다). 선언 값이 적용된 실행과 정책 기본값으로 돈 실행은 `resolved_config`가 달라
  서로 다른 해시를 갖는다.

### 3.3 화면 기본값이 전략 선언을 반영한다

`repository.py`의 `_money_management_options`가 `MoneyManagementSupport` 전체를 받는다. 선택 가능한
mode 목록은 지금과 같이 만들고, `default` mode의 기본값은 얼려 둔 정책 기본값을 풀어 낸 dict 위에
`default_settings[default]`를 덮은 뒤 `validate_money_management_config`(최종 union)로 검증해 돌려준다.
검증이 거부하면(전략이 범위 밖 값을 선언) **helper 안에서** 잡아 정책 기본값으로 되돌리고
`_LOGGER.exception`으로 남긴다. 바깥 예외 처리로 새어 나가면 그 전략이 실행 불가로 표시되기
때문이다. 배포된 정책의 구성이 요청마다 돌지 않도록, (mode, 선언의 정렬 JSON) 쌍을 키로 검증 결과의
JSON 문자열을 `functools.lru_cache`에 두고 요청마다 풀어 낸다. 응답 모델은 바뀌지 않는다.

### 3.4 사실 조회와 배포 전 검사가 선언을 보인다

- `facts declaration`의 `money_management`에 `default_settings`를 더한다(JSON 객체, mode별).
- `facts catalog_precheck`(전략)에 검사 "policy default settings"를 더한다. `supported`의 mode마다 그
  정책이 배포돼 있으면 `MoneyManagementFactory.create({"mode": mode, **default_settings.get(mode, {})},
  policies)`를 실제로 불러, 거부되면 finding `{"rule": "policy-default-settings-refused", "mode": ...,
  "detail": ...}`을 더한다. 배포돼 있지 않은 mode는 기존 availability finding이 말하므로 더하지 않는다.
  `checks_performed`에 이름을 더한다.
- 승인된 배포 전 검사 설계 3.4절의 "mode별 대표 설정"에 "전략이 `default_settings`로 선언한 값이
  있으면 그것을 대표 설정으로 쓰고, 그 위에 `--mode-settings`가 덮는다"는 문장을 더한다.
- `registration_sql`과 `signal_db.strategy_registry`는 바꾸지 않는다.

### 3.5 능력 목록에 보호 검사 시점 둘을 넣는다

`capabilities.py`에 항목 둘을 더한다. 둘 다 BEHAVIOR다.

- `execution.protection_checked_from_bar_after_fill`: 손절, 목표, 강제청산은 체결 봉에서는 검사하지
  않고 다음 봉부터 검사한다. 체결 봉 안에서 수준에 닿아도 그 봉에서 청산되지 않는다. 이것을 끄는
  실행 설정이나 API는 없다. 값 `True`. 시험은 기존
  `test_execution.py::test_trigger_gap_uses_unfavorable_open_and_skips_the_fill_candle`(손절)과 새로
  쓰는 `test_execution.py::test_take_profit_and_liquidation_are_not_checked_on_the_fill_candle`(목표와
  강제청산) 둘이다. 기존 시험만으로는 문장의 셋 중 하나만 증명되므로 새 시험을 더한다.
- `execution.simultaneous_stop_and_target`: 같은 봉에서 손절과 목표에 함께 닿으면 손절로 청산한다.
  값 `"stop_loss"`. 시험 `test_execution.py::test_simultaneous_stop_and_take_profit_resolves_to_stop_loss`.

승인된 설계 3.2절의 두 항목(`series.history_depth`, `plugin.identifier_format`)은 그 설계의
changeset 1이 넣으므로 여기서 다루지 않는다.

### 3.6 절차와 규범에 기록 규칙을 더한다

`.claude/skills/author-strategy/SKILL.md`에 다음을 더한다.

- 2단계 구조화 항목에 **프로필 값**을 더한다. `StrategyProfile`의 열두 값은 Agent가 채우는 빈
  값이며, 출처가 보고한 결과(승률, payoff, 낙폭, 거래 수)에서 가져온 것과 정한 것을 구분해 차이
  기록표에 적는다.
- 2단계에 **플랫폼이 고정한 규칙**을 더한다. `capabilities`에서 측정을 바꾸는 규칙(체결 시점,
  보호 검사 시점, 동시 도달, 포지션 수, series 이력 깊이)을 읽어 기록에 항목 id와 함께 적고,
  출처가 다르게 정했으면 차이로 분류한다.
- 6단계에 **선언은 출처를 넘지 않는다**를 더한다. `supported_timeframes`, 종목·시장, parameter는
  출처의 차트 세팅과 규칙에 있는 것만 선언한다. 출처가 말하지 않은 시간대나 시장을 "지원"으로
  광고하지 않는다.
- 6단계에 **원문의 보호 값은 `default_settings`에 둔다**를 더한다. 출처가 손절 배수, 손익비,
  leverage 같은 정책 설정 값을 정했으면 지원 mode의 `default_settings`에 넣어, 설정 없는 실행과
  화면 기본값이 원문을 재현하게 한다.
- 기록 규칙에 **출처 문장의 위치**를 더한다. 원문의 값을 적을 때 어느 페이지의 어느 문장인지
  적고, 연구 공통 문장이나 다른 페이지의 문장은 그렇다고 표시한다.

`docs/strategy-authoring-contract.md`는 4.3절 표와 예시에 `default_settings`를 더하고, 5.5절에
전략 선언이 정책 기본값보다 앞서며 `submitted_money_management_json`이 `money_management_submitted`에서
온다고 적고, 7장의 "전략이 그 mode에 대해 밝힌 기본값"이 `default_settings`를 가리킨다고 적는다.

### 3.7 Evidence가 전략 선언을 남긴다

`money_management_json`에 `declared_by_strategy`(그 실행의 mode에 대해 전략이 선언한 설정, 없으면
빈 객체)를 더한다. 옛 실행을 되짚을 때 지금의 클래스가 아니라 그때의 선언을 읽기 위해서다.
해시되는 Evidence 내용이 바뀌므로(`evidence_schema.py`는 `submitted_money_management_json`만 해시에서
빼고 `money_management_json`은 해시한다) `EVIDENCE_SCHEMA_VERSION`을 `1.11.0`으로 올리고,
`test_engine_and_harness.py`의 고정 해시 표에 `1.11.0` 항목을 더하며(기존 항목은 고치지 않는다), 판
설명에 "1.11.0은 전략이 선언한 정책 설정과 해석 판 1.2.0을 기록한다"를 적고,
`test_evidence_schema.py` 226행의 직접 고정 값을 올린다. `docs/fullspec/backtest_v2_detailed_design.md`
4172행의 "현재 Evidence 스키마 판은 1.5.0"은 이미 낡은 문장이므로 함께 바로잡는다.
`submitted_money_management_json`의 값 출처는 3.2대로 바뀐다.

## 4. 하지 않는 것

- 기존 전략 다섯의 선언을 이 changeset에서 고치지 않는다. Donchian과 MACD(제가 쓴 것)에 원문 값을
  `default_settings`로 넣는 일은 별도 커밋으로 뒤에 하고, 세 봉 전략(Agent 산출물)은 손대지 않는다.
- `SignalGenerationConfig`에 자금관리 필드를 더하지 않는다. 신호 생성 세션은 옛 `params` 이름을
  읽는 지금 방식 위에서 주입만 없앤다. 신호 생성 설정의 정식 자금관리 필드는 별도 항목이다.
- 설정 해시의 입력 목록을 바꾸지 않는다(3.2). 값이 바뀌는 것은 판 올림의 결과다.
- `RunConfig`에 클라이언트가 지정할 수 있는 필드를 더하지 않는다. 제출 값 보존은 private 속성으로
  한다(3.2).
- 규범 9.1절 공통 시험, `author_check` 명령, 규범 예시의 시험화는 승인된 설계가 맡는다.
- `apps/web`의 화면 코드는 손대지 않는다. 생성 파일(`openapi.json`, `schema.d.ts`)만 갱신한다.

## 5. changeset 분리와 순서

| 순서 | changeset | 파일 |
|---|---|---|
| A | 능력 항목 둘과 새 시험 | `core_lib/capabilities.py`, `core-lib/tests/test_execution.py` |
| B | `default_settings` 선언·해석·기록 | `core_lib/strategy/base.py`, `core_lib/money_management/`(규칙 함수), `core_lib/strategy/manager.py`, `backtest_service/config/run_config.py`와 새 `declarations.py`, `backtest_service/engine/engine.py`, `evidence_schema.py`, `signal_service/application/service.py`, `trading_plugins/facts.py`, `web_api/repository.py`, 각 서비스 시험, `apps/web/src/api` 생성 파일, `docs/strategy-authoring-contract.md`, `author_check_and_scaffold_design.md` 3.4절 한 문장 |
| C | 절차 문구 | `.claude/skills/author-strategy/SKILL.md` |

A와 C는 B와 독립이다. 셋을 따로 커밋한다.

## 6. 무엇을 만족하면 닫힌 것인가

- core-lib: `default_settings={"turtle": {...}}`를 `supported=("manual",)`과 함께 주면 거부되고,
  `{"manual": {"mode": "manual"}}`와 스칼라가 아닌 값이 거부되며, 정상 선언은 불변 mapping으로
  읽힌다. `apply_declared_settings`가 사용자 값을 이기게 하지 않고, 선언 없는 mode에는 아무것도
  더하지 않으며, 두 번 적용해도 같다. `create_runtime`이 `{"mode": "manual"}`만 받았을 때 전략이
  선언한 1.5가 정책에 들어가고, 범위 밖 선언은 `ValueError`로 거부된다.
- backtest-service: 선언한 가짜 전략으로 `money_management` 없이 `RunConfig`를 검증하면
  `money_management.atr_stop_multiple`이 선언 값이고 `money_management_submitted`가 빈 dict다.
  `{"mode": "manual", "atr_stop_multiple": 3.0}`을 주면 3.0이 이기고 `money_management_submitted`가
  그 mapping이다. 범위 밖 선언은 `ValidationError`다. `_segment_config`로 만든 파생 실행의
  `money_management`가 부모와 같고 `money_management_submitted`도 같다. 인공 캔들 경로 실행의
  Evidence에서 `money_management_json.resolved_config`가 선언 값이고 `declared_by_strategy`가 선언
  mapping이며 `submitted_money_management_json`이 빈 객체다. 고정 실행 넷의 Evidence 해시가
  `1.11.0` 항목과 같다.
- signal-service: `params`에 보호 값이 없는 세션이 선언한 가짜 전략으로 시작하면 정책의
  `atr_stop_multiple`이 선언 값이고, `params`에 값이 있으면 그 값이 이긴다.
- web-api: 선언한 전략의 `default_money_management`가 선언 값을 담고, 선언하지 않은 전략은 지금과
  같다. 범위 밖 선언은 정책 기본값으로 돌아가고 로그가 남으며 전략은 실행 가능으로 남는다.
  스윕 준비(`_prepare_sweep`)로 만든 자식 설정이 부모의 선언 값을 그대로 갖는다.
- trading-plugins: `facts declaration`이 `default_settings`를 내고, `catalog_precheck`가 범위 밖
  선언에 `policy-default-settings-refused`를 낸다.
- 능력 항목 둘이 실재하는 시험을 가리키고 `facts capabilities`에 나타난다.
- 변이 시험. `RunConfig`의 덮어쓰기를 지우면 backtest-service와 web-api의 시험이 실패한다.
  `create_runtime`의 안전망을 지우면 signal-service 시험이 실패한다. `declared_by_strategy`를 빼면
  Evidence 시험이 실패한다. `matcher.py`의 체결 봉 건너뛰기를 지우면 core-lib 시험 둘이 실패한다.
  각 변이가 잡히지 않으면 시험이 없는 것이므로 시험을 더한다.
- 저장소 루트 pytest, ruff, 형식, 바뀐 서비스마다 mypy가 exit 0. `apps/web`의 `npm test`와
  `npm run typecheck`가 exit 0. Codex 코드 리뷰 Blocking 0.
- 그 뒤 새 전략으로 Agent 회차를 다시 돌려, Agent가 원문 보호 값을 `default_settings`에 넣고
  프로필 값·플랫폼 규칙·문장 위치를 기록하는지 본다.

## 7. 열려 있는 결정

- 설정이 없는 실행의 mode는 지금처럼 `manual`로 둔다. 전략의 `default` mode가 manual이 아닐 때
  그 mode로 읽을지는 규범 5.5절을 바꾸는 일이라 이 설계에 넣지 않는다.
- 화면은 기본 mode의 선언 값만 받는다. 전략이 기본이 아닌 mode에도 값을 선언하면 화면이 그
  mode로 바꿀 때 정책 기본값을 명시해 제출하므로 선언이 묻힌다(코드 리뷰 P2). 응답에 mode별
  선언 값을 더하는 일은 별도 항목(ClickUp z8nrz7e3kb)이다. 지금 배포된 전략은 모두 기본 mode에만
  선언한다.

## 8. 검토에서 바로잡힌 사실 (Codex, `gpt-5.6-terra`, 2026-09-25)

1차 설계에 대한 검토가 Blocking 넷, Should-fix 넷, Nit 둘을 냈다. 저장소와 대조한 결과는 다음과
같다.

| 지적 | 판정 | 반영 |
|---|---|---|
| 설정 해시에 자금관리 설정이 들어가지 않아 결정성 검사가 거짓 불일치를 낸다 | **저장소가 반박한다.** `engine.py` 457~460행이 `params_json`에 `_money_management.resolved_config`를 넣고 `params_json`은 `_CONFIG_HASH_FIELDS`에 있다. 실행 001516의 카탈로그 행이 그 값을 담고 있다 | 2장에 사실을 적고 3.2에 "해시는 바꾸지 않는다"를 근거와 함께 적었다 |
| 스윕·walk-forward·IS/OOS가 전체 덤프로 파생 실행을 만들어 "비운 필드"가 사라진다 | **맞다.** `main.py` 543~553행, `harness.py` 335~346행 | 해석을 `create_runtime`에서 `RunConfig` 검증으로 옮겼다(3.2). 그 뒤로는 선언 값이 명시된 값이라 덤프에 남는다 |
| 신호 생성 세션이 manual 기본값을 직접 넣어 선언이 닿지 않는다 | **맞다.** `service.py` 114~126행 | 주입을 없애고 있는 값만 넘기며 `create_runtime`의 안전망이 채운다(3.2) |
| precheck의 Factory 호출에 `mode`가 빠졌고 precheck는 `create_runtime`을 부르지 않는다 | **맞다** | `{"mode": mode, **settings}`로 부르는 검사를 새로 더한다(3.4) |
| Evidence가 전략 선언을 남기지 않아 옛 실행을 되짚을 수 없고, Factory 판을 올려야 한다 | 앞 절반은 **맞다**, 뒤 절반은 **받아들이지 않는다** | `declared_by_strategy`를 더하고 Evidence 판을 올린다(3.7). Factory 판은 Factory의 규칙이 바뀔 때만 올린다(3.2) |
| precheck 서술이 두 검사를 뭉뚱그리고 시험이 없다 | 맞다 | 3.4에 검사 이름과 finding 규칙 이름을 정하고 6장에 시험을 적었다 |
| helper 서명과 기존 시험이 바뀌어야 하고, 되돌림은 helper 안에서 잡아야 한다 | 맞다 | 3.3에 반영 |
| 첫 능력 항목의 기존 시험은 손절만 증명하고, `skip_first_sl_check`는 `ClassVar`라 상수가 아니다 | 맞다 | 목표와 강제청산 시험을 새로 쓰고 문장에 "끄는 설정이 없다"를 적었다(3.5) |
| manual·Turtle 모델은 손으로 쓴 것이라 `_config_model_for`가 만든 것이 아니다 | 맞다 | 2장 서술을 고쳤다 |
| 동결은 얕고 "mode만 있는 실행" 시험으로는 부족하다 | 맞다 | 값을 JSON 스칼라로 제한했고(3.1), 파생 실행·신호 세션·Evidence 시험을 6장에 더했다 |

고쳐 쓴 설계에 대한 2차 검토는 Blocking 셋, Should-fix 넷, Nit 둘을 냈다.

| 지적 | 판정 | 반영 |
|---|---|---|
| 같은 클래스의 before 검증기 둘은 선언의 역순으로 돌아 옛 값 이동이 뒤로 밀린다 | **맞다**(pydantic 2.13.4) | 검증기를 wrap 하나로 합쳤다(3.2). 옛 값 이동과 선언 덮기가 함께 도는 회귀 시험을 둔다 |
| `money_management_submitted` 필드는 클라이언트가 위조할 수 있는 감사 값이다 | **맞다** | 필드 대신 private 속성으로 바꿨다(3.2). OpenAPI 갱신도 사라졌다 |
| Factory 판을 두는 것은 규범 5.5절("version은 두 층을 함께 가리킨다")과 어긋난다 | **맞다.** 1차 판단이 틀렸다 | `1.2.0`으로 올린다(3.2) |
| `declared_by_strategy`가 `params_json`에도 들어가 모든 설정 해시가 바뀐다 | 맞다 | 판 올림의 결과로 적고 결정성 검사의 동작을 설명했다(3.2) |
| 모듈 적재 시 전략 발견은 import 비용과 실패 범위를 넓힌다 | 맞다 | 처음 쓰일 때 읽는 캐시로 바꿨다(3.2) |
| 유한하지 않은 float를 선언 시점에 거부해야 한다 | 맞다 | 3.1에 반영 |
| `test_evidence_schema.py`의 직접 고정 값과 낡은 설계서 문장도 고쳐야 한다 | 맞다 | 3.7에 반영 |
| 1차 검토의 설정 해시 지적은 바르게 반박됐다 | 확인 | |
| 3.3과 신호 세션 결론은 타당하다 | 확인 | |
