# 전략과 정책의 사실을 도구로 내주고 등록 SQL을 선언에서 만든다

이 문서는 전략 작성 절차가 쓰는 사실을 MCP 도구로 내주고, 등록 행을 클래스 선언에서 만들어
내는 서버 하나를 정한다. **운영 데이터베이스에 등록 행을 쓰는 일은 여기 넣지 않는다**(사용자
확정, 6장).

절차 자체는 `.claude/skills/author-strategy/SKILL.md`가 계속 소유한다. **skill은 무엇을 언제
판단할지를 갖고, 이 서버는 그 판단이 딛는 사실을 갖는다.**

## 1. 지금 무엇이 아쉬운가

**사실이 프롬프트를 거쳐 전달된다.** skill은 registry에 물어보라며 파이썬 조각을 적어 두고,
읽는 쪽이 그것을 돌려 결과를 말로 옮긴다. 옮기는 자리마다 틀릴 수 있고, **틀려도 아무것도
멈추지 않는다.**

**구현자가 바뀌었다.** 2026-08-11부터 구현은 Codex가 한다. 지금 구조에서는 능력 목록과 두
registry의 내용이 내 프롬프트를 통해서만 Codex에 닿는다. 도구로 두면 **둘이 같은 자리에서 같은
답을 받는다.**

**등록 행을 손으로 베낀다.** 규범 4.6은 코드 선언과 등록 행이 같아야 한다고 요구하지만, 지금
어긋남을 잡는 방식은 **실행 거부**다. 어긋나게 쓰는 것 자체를 막지는 못하고, 실행할 때가 되어야
드러난다.

## 2. 코드에서 확인한 사실

### 2.1 등록 행이 요구하는 것과 클래스가 선언하는 것

`init-scripts/signal-service/20260724/01-redefine-strategy-registry.sql`의
`strategy_registry`와 `init-scripts/signal-service/20260810/01-create-money-management-registry.sql`의
`money_management_registry`가 담는 값 가운데 **클래스 선언에서 그대로 나오는 것과 나오지 않는
것이 갈린다.**

전략에서 선언에서 나오는 것은 `strategy_id`와 `class_name`과 `module_path`와
`strategy_version`과 `supported_timeframes`와 `required_indicators_json`과 `min_history`와
`default_params_json`이다. 정책에서는 `mode`와 `class_name`과 `module_path`와
`policy_version`과 `settings_names`가 그렇다.

**나오지 않는 것이 셋이다.** `display_name`과 `description`은 사람이 정하는 표시 정보이고,
`is_active`와 `is_deprecated`는 규범 6.4가 "켜고 끄는 것은 코드가 아니라 이 두 열이 맡는다"고
정한 **스위치**다.

### 2.2 런타임은 등록 표에 쓰지 않는다

`services/signal-service/signal_service/infrastructure/strategy_registry.py`의 `register`는
`PermissionError`를 낸다. 규범 6.4는 운영자가 배포 전에 init SQL을 적용한다고 정하고, 로드맵
3-1 계획서 11장은 운영 중 임의 카탈로그 쓰기 API를 범위 밖으로 못박았다.

### 2.3 대조는 이미 순수 함수다

`core_lib/strategy/reconciliation.py`의 `reconcile_strategy_registries`와
`core_lib/money_management/reconciliation.py`의 `reconcile_money_management_availability`는
등록 행 목록과 발견 결과를 받아 상태를 낸다. **데이터베이스를 알지 못한다.** 그래서 만들어 낸
행을 그 함수에 그대로 먹여 볼 수 있다.

### 2.4 이 저장소에는 아직 자체 MCP 서버가 없다

`.mcp.json`에 등록된 다섯은 모두 외부 npx 패키지다(`codex-cli`, `perplexity`, 그리고 읽기 전용
Postgres 셋). **이 서버가 저장소가 소유하는 첫 MCP 서버가 된다.** 그 값을 치르는 대신 얻는
것은 `core_lib`을 직접 import해 사실을 내준다는 것이며, 그러려면 저장소의 `.venv`로 돌아야
한다.

## 3. 도구 표면

서버 이름은 `trading-plugins`로 한다. 도구는 일곱이다.

**읽는 것 넷.**

1. `capabilities(id?)` — `core_lib.capabilities`의 항목을 그대로 낸다. id를 주면 하나만 낸다.
2. `series(name?)` — 지표 조합과 패턴을 이름·parameter·warm-up·채택 근거와 함께 낸다. 지표와
   패턴을 한 목록에 내되 종류를 함께 싣는다.
3. `deployed(kind)` — 발견된 전략 또는 정책과, 불러오지 못한 파일과 그 사유를 낸다.
4. `declaration(kind, id)` — 그 클래스가 선언한 것을 낸다. 전략이면 metadata와
   `StrategyProfile`과 parameter schema, 정책이면 설정 이름과 판과 두 capability다.

**등록을 돕는 것 셋.**

5. `registration_sql(kind, id, display_name, description, is_active)` — 선언에서 멱등 등록
   SQL을 만들어 글자로 낸다. 기존 파일과 같은 모양, 즉 하나의 트랜잭션 안에서 `ON CONFLICT DO
   UPDATE`하되 **실제로 달라진 것이 없으면 갱신하지 않는** 형태다.
6. `precheck(kind, id, row?)` — 데이터베이스 없이 본다. 만들어 낸 행(또는 건네받은 행)을
   런타임과 같은 대조 함수에 먹이고, 매니저가 그 행으로 클래스를 만들 수 있는지까지 본다.
7. `precheck_database(kind, id, dsn)` — 일회용 데이터베이스에 표를 세우고 그 SQL을 적용해
   제약을 통과하는지, 다시 읽은 행이 만든 행과 같은지 본다.

**도구는 어느 것도 운영 데이터베이스에 쓰지 않는다.** 5는 글자만 내고, 6은 데이터베이스를
건드리지 않으며, 7은 일회용 대상에만 쓴다.

## 4. 선언에서 나오지 않는 셋을 어떻게 다루는가

**`display_name`과 `description`은 인자로 받는다.** `description`을 비우면 클래스 docstring의
첫 문장을 쓴다. 지어내지 않는다.

**`is_active`는 인자로 받되 기본값을 두지 않는다.** 이것이 스위치이므로 기본값을 두면 도구가
운영 결정을 대신하게 된다. `is_deprecated`는 언제나 거짓으로 만든다 — 폐기는 새 등록이 아니라
기존 행을 고치는 일이다.

**`module_path`는 클래스에서 읽되 발견된 패키지 안인지 확인한다.** 규범 6.3이 정한 두 패키지
밖을 가리키는 행은 만들지 않는다. 등록 행의 경로는 적재에 쓰이지 않지만, **대조에 쓰이므로
틀리면 실행이 거부된다.**

## 5. 사전 점검을 두 층으로 나눈다

**첫째 층은 데이터베이스가 없어도 된다.** 만들어 낸 행을 런타임이 쓰는 그 대조 함수에 먹여
`registered_only`나 `identity_mismatch` 같은 상태가 아닌지 보고, 매니저가 그 행으로 클래스를
만드는지 본다. **여기서 통과하지 못하는 행은 데이터베이스에 넣어도 실행되지 않는다.** 승인이
필요 없으므로 기본 경로로 삼는다.

**둘째 층은 일회용 데이터베이스가 필요하다.** 첫째 층이 보지 못하는 것은 SQL이 실제로 유효한지,
표의 제약을 통과하는지, 넣었다 읽은 값이 같은지다. 특히 정책 표의 `settings_names`는 정렬된
중복 없는 배열이어야 한다는 제약이 있어 **글자만 보아서는 알 수 없다.**

**둘째 층은 데이터베이스를 만들고 지우므로 쓰기다.** 하네스는 쓰기를 그때마다 승인받게 하고
있으므로, 이 도구는 대상 이름이 일회용임을 확인하고 **호출할 때마다 사용자 승인을 거친다.**
운영 데이터베이스 이름이 오면 거부한다.

## 6. 하지 않는 것

- **운영 데이터베이스에 등록 행을 쓰지 않는다.** 사용자가 정한 범위다. 규범 6.4와 로드맵 3-1
  계획서 11장을 고치지 않아도 되는 자리에 머무른다.
- **런타임의 쓰기 거부를 풀지 않는다.** `register`는 계속 `PermissionError`를 낸다.
- **능력 목록을 다시 쓰지 않는다.** 서버는 `core_lib.capabilities`를 실어 나르기만 한다.
- **재고를 서버 안에 적지 않는다.** 지표와 패턴과 정책 mode는 언제나 조회 결과다.
- **전략을 만들지 않는다.** 이 작업은 도구만 만든다.
- **skill의 판단 규칙을 서버로 옮기지 않는다.** 막힘을 세 가지로 가르는 것은 절차의 몫이다.

## 7. skill과 어떻게 이어지는가

`author-strategy`의 "먼저 읽는 것"에서 파이썬 조각을 걷어내고 도구 호출로 바꾼다. 절차의
문장은 그대로다 — **재고는 조회하고 능력은 목록에서 읽으라는 규칙이 바뀌는 것이 아니라, 그
조회가 도구가 되는 것이다.**

**서버가 없어도 절차는 돌아야 한다.** MCP가 붙지 않은 환경에서도 같은 값을 얻을 수 있도록,
서버는 얇은 껍데기로 두고 실제 계산은 import 가능한 모듈에 둔다. skill에는 도구를 쓰되 없으면
그 모듈을 직접 부르라고 적는다.

## 8. 드리프트를 어떻게 막는가

**서버가 내주는 값이 원본과 같은지 검사한다.** `capabilities`가 내는 것이
`PLATFORM_CAPABILITIES`와 항목 대 항목으로 같은지, `series`가 내는 것이 두 registry의 내용과
같은지 본다. 서버가 값을 손질하기 시작하면 이 검사가 깨진다.

**`registration_sql`이 만든 것이 실제로 도는지 검사한다.** 기존
`02-register-vessel-reference.sql`은 사람이 쓴 것이므로, **같은 클래스에서 만들어 낸 SQL이 그
파일과 의미가 같은지**를 회귀로 붙든다. 표시 정보 둘과 스위치는 인자로 주어 맞춘다.

**둘째 층 점검은 표시가 붙은 시험으로 둔다.** 저장소의 `integration` 표시와 같은 방식으로,
명시적으로 고르지 않으면 건너뛴다.

## 9. changeset 분리

1. **사실 모듈과 읽기 도구 넷.** 계산을 import 가능한 모듈에 두고 MCP 서버를 그 위에 얹는다.
   드리프트 검사를 함께 둔다.
2. **등록 SQL 생성과 데이터베이스 없는 점검.** 도구 다섯째와 여섯째, 그리고 기존 등록 파일과
   의미가 같은지 보는 회귀.
3. **일회용 데이터베이스 점검.** 도구 일곱째와 표시가 붙은 시험.
4. **skill 연결.** `author-strategy`의 조회 자리를 도구로 바꾸고, 서버가 없을 때의 길을 적는다.

순서는 1, 2, 3, 4다. 2와 3은 1의 사실 모듈에 기대고, 4는 도구가 있어야 쓸 수 있다.

## 10. 무엇을 만족하면 닫힌 것인가

- 서버가 `.mcp.json`에 등록되어 저장소 `.venv`로 뜨고, 도구 일곱이 스키마와 함께 보인다.
- `capabilities`와 `series`가 내는 값이 원본과 항목 대 항목으로 같음을 검사가 확인한다.
  서버가 값을 손질하면 그 검사가 깨진다.
- `registration_sql`이 `VesselReference`에서 만든 SQL이 기존 등록 파일과 의미가 같다.
- 선언과 어긋나는 행을 일부러 만들어 넣으면 `precheck`가 그 상태를 이름으로 낸다.
- `precheck`가 통과시킨 행이 일회용 데이터베이스에서도 제약을 통과하고, 다시 읽은 값이 만든
  값과 같다.
- **어떤 도구도 운영 데이터베이스에 쓰지 않는다.** 운영 이름을 주면 거부하는 것을 확인한다.
- 서버 없이 같은 모듈을 직접 불러도 같은 값이 나온다.
- 저장소 뿌리에서 `.venv/bin/python -m pytest services -q`가 exit 0이고, `ruff check`와
  `ruff format --check`가 exit 0이며, 바뀐 서비스 디렉터리 안에서 돌린 mypy가 exit 0이다.
- 기존 전략 판단과 Evidence와 등록 행이 달라지지 않는다. 이 작업은 도구와 검사와 문서만 더한다.
