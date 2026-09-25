# 전략 작성 Agent 사용법

이 문서는 **사람이 쓴 전략 기술 문서를 이 플랫폼에서 도는 전략으로 옮기는 방법**을 적는다.

규칙 자체는 `docs/strategy-authoring-contract.md`에 기술한다.  
이 문서는 그 규칙을 어떻게 쓰는지만 다루며, 규칙에 어긋나면 오류가 발생한다.   
`Concenpt은 docs/fullspec/strategy_authoring_workflow_design.md`와`docs/fullspec/strategy_registration_mcp_design.md`에  기술되어 있다.

## 1. 전체 흐름

전략 기술 문서를 건네면 절차가 그것을 구조로 옮기고, 필요한 재료와 능력이 있는지 확인한 뒤
둘 중 하나를 돌려준다. 하나는 등록되어 백테스트가 도는 전략이고, 다른 하나는 **무엇 때문에
막혔고 무엇이 있으면 풀리는지를 적은 보고**다.

막히지 않으면 전략 코드와 등록 문장과 시험이 한 changeset으로 만들어진다. 그 뒤에 검산 절차가
계산이 문서와 맞는지 되짚는다.

**절차가 스스로 끝내지 않는 걸음이 셋이다.** 등록 문장을 데이터베이스에 적용하는 것과, 서비스를
다시 띄우는 것과, 화면에서 실행해 보는 것이다. 앞의 하나는 도구가 아예 하지 않고, 뒤의 둘은
실행 환경을 건드리는 일이라 **권한을 물어보고 없으면 미완료로 보고한다.** 그러므로 "전략이
만들어졌다"와 "화면에서 돈다"는 같은 말이 아니다.

**등록이 끝난 것과 전략 개발이 끝난 것도 다르다.** 규범의 "전략 개발 완료 체크리스트"가 완료의
기준이며, 등록은 그 목록의 한 항목일 뿐이다.

## 2. 무엇을 준비하는가

**전략 기술 문서 하나면 된다.** 형식은 자유롭다. 유튜브 강의를 정리한 글도 되고 가설과 검증
순서를 갖춘 연구 설계서도 된다. `docs/samples_for_strategy_agent/`에 두 종류가 예시로 있다.

문서가 완전할 필요는 없다. **비어 있는 값은 지어내지 않고 물어보므로**, 모르는 것은 모르는
채로 두는 편이 낫다. 값을 채워 넣으면 그 값으로 재고 만다.

## 3. 부르는 법

```
/author-strategy docs/samples_for_strategy_agent/00.TCT_MultiTF.md
```

슬래시로 부르지 않고 "이 문서로 전략 만들어 줘"라고 해도 같은 절차가 실린다. 전략 기술
문서나 매매 아이디어 정리본을 건네는 상황이면 자동으로 붙는다.

구현이 끝나고 백테스트를 돌린 뒤에는 검산을 따로 부른다. **검산은 무엇을 대조할지 알아야
하므로 다음 넷을 함께 준다.**

```
/verify-strategy
```

건네는 것은 원본 전략 기술 문서의 경로, 전략 id, 검산할 실행의 Evidence 위치, 그리고 **같은
설정으로 두 번 돌린 실행 둘**이다. 마지막 것은 결정성을 보기 위한 것이라 한 번만 돌렸으면
검산의 그 항목을 할 수 없다.

**검산은 구현 코드를 읽고 확인하는 것이 아니다.** 원본 문서와 계산 표준에서 값을 다시 끌어와
직접 계산해 대조한다. 구현할 때 한 오해를 확인할 때 되풀이하지 않으려는 것이다.

**다만 같은 세션이 만들고 같은 세션이 검산하면 한계가 있다.** 값을 문서에서 다시 끌어오는 것이
그 위험을 줄이지만 없애지는 못하며, 독립된 눈은 다른 모델의 코드 리뷰가 맡는다. 검산 통과를
그 리뷰의 대체로 읽으면 안 된다.

## 4. 돌아오는 답을 읽는 법

막혔다면 사유가 **세 갈래로 갈려서** 온다. 이 구분이 절차의 핵심이다.

| 갈래 | 무슨 뜻인가 | 당신이 할 일 |
|---|---|---|
| 문서가 비워 둔 값 | 문서에 숫자가 없거나 `TODO`다 | 값을 정해 준다 |
| 계산 재료의 부재 | 필요한 지표나 패턴이 등록되어 있지 않다 | 그 재료를 먼저 만들지 결정한다. 전략 작업이 아니라 플랫폼 작업이다 |
| 실행 능력의 부재 | 플랫폼이 그 요구를 표현할 수 없다 | 요구를 바꾸거나 플랫폼을 넓히는 별도 작업을 연다 |

**셋 다 걸리는 문서가 보통이다.** 그래서 가장 앞선 하나만 보고하지 않고 걸린 것을 전부 적는다.
하이킨아시를 만든 뒤에야 "하루 5회 제한도 안 됩니다"를 듣는 일이 없게 하려는 것이다.

**전부 막혀도 되는 부분이 있으면 함께 온다.** 문서가 실험 순서를 정해 두었다면 지금 능력으로
어디까지 잴 수 있는지 밝힌다. 이때 **문서와 달라지는 점을 빠짐없이 적고 당신의 승인을
받는다.** 조용히 바꿔 구현하면 문서가 물은 것과 다른 것을 잰 뒤 답을 얻었다고 믿게 된다.

## 5. 직접 물어보기

전략을 만들기 전에 "이런 게 되나"를 확인하고 싶으면 직접 물어도 된다. 저장소 뿌리에서 돈다.

```
.venv/bin/python -m trading_plugins.facts <조회> [인자]
```

결과는 언제나 JSON이고, 실패하면 종료 코드가 0이 아니면서 `error` 하나를 담은 JSON이 온다.

```
$ .venv/bin/python -m trading_plugins.facts declaration strategy nope
{"error": "unknown strategy: nope"}
```

### 5.1 `capabilities` — 플랫폼이 표현할 수 있는 것

```
.venv/bin/python -m trading_plugins.facts capabilities
.venv/bin/python -m trading_plugins.facts capabilities exit.partial
```

스물일곱 항목이 있고 이름만 보아도 무엇을 묻는지 알 수 있다. `exit.partial`은 부분 익절이
되는지, `series.multi_timeframe`은 상위 timeframe을 볼 수 있는지, `risk.between_trade_rules`는
하루 손실 한도 같은 거래 간 규칙이 있는지다.

**값만 보지 말고 문장을 읽는다.** 값은 참거짓이나 숫자일 뿐이고, 왜 그런지와 어느 경로에
해당하는지는 문장에 있다.

### 5.2 `series` — 지금 등록된 지표와 패턴

```
.venv/bin/python -m trading_plugins.facts series
.venv/bin/python -m trading_plugins.facts series EMA
```

**답은 언제나 배열이다.** 이름을 주어도 그 이름의 조합이 여럿일 수 있기 때문이다.

```json
[{"kind": "indicator", "name": "EMA", "params": {"period": 9}, "min_history": 9,
  "pinned_impl": "technical_indicators_calc_spec.md §0.3 (SMA seed, recursive)"},
 {"kind": "indicator", "name": "EMA", "params": {"period": 21}, "min_history": 21,
  "pinned_impl": "technical_indicators_calc_spec.md §0.3 (SMA seed, recursive)"}]
```

**지표는 이름과 parameter 조합 단위로 등록된다.** `EMA`는 9와 21과 55와 200 넷만 있으므로
50봉 EMA는 선언할 수 없다.

**채택 근거는 지표에만 실린다.** 패턴은 공통 판만 있고 항목마다의 근거가 없으므로,
`docs/references/candlestick_pattern_calc_spec.md`를 읽어 정의를 확인해야 한다는 문구가 함께
온다.

### 5.3 `deployed` — 지금 배포된 전략과 정책

```
.venv/bin/python -m trading_plugins.facts deployed strategy
.venv/bin/python -m trading_plugins.facts deployed money_management
```

```
{"kind": "money_management",
 "items": [{"identifier": "manual", "class_name": "ManualMoneyManagement",
            "module_path": "trading_plugins.money_management.manual"}, ...],
 "faults": []}
```

**`faults`를 반드시 본다.** 불러오지 못한 파일이 여기 사유와 함께 남는다. 파일 하나가 잘못돼도
나머지는 그대로 배포되므로, 이 자리를 보지 않으면 빠진 것을 눈치채지 못한다.

**격리에는 한계가 있다.** 막아 주는 것은 보통의 예외와 `sys.exit` 둘뿐이다. 파일이 불러오는
도중 멈추거나 프로세스를 즉시 끝내면 **그 조회 자체가 함께 멈춘다.** 조회가 응답하지 않으면
새로 둔 파일부터 의심한다.

### 5.4 `declaration` — 그 클래스가 스스로 밝힌 것

```
.venv/bin/python -m trading_plugins.facts declaration strategy <전략 id>
.venv/bin/python -m trading_plugins.facts declaration money_management <mode>
```

전략이면 선언한 series와 최소 이력과 지원 timeframe과 판단 방식, `StrategyProfile` 전부,
parameter schema가 온다. 정책이면 설정마다의 기본값 유무와 판과 두 capability와 그 정책이
선언한 요구가 온다.

**조회는 서술하고 거부하지 않는다.** 요구를 하나도 선언하지 않은 정책이나 기본값 없는 설정을
가진 정책도 그대로 서술한다. 실행되지 않는 것을 조회했을 때 침묵하면 진단이 막히기 때문이다.

**빈 요구 목록을 "요구가 없다"로 읽지 않는다.** 기본값이 없는 설정이 하나라도 있으면 정책을
만들 수 없어 요구를 읽어 올 수 없고, 그때도 목록은 비어 있다. 두 경우는
`indicator_requirements_unavailable_reason`으로 갈린다. 그 자리가 비어 있으면 정말 요구가
없는 것이고, 사유가 적혀 있으면 **읽지 못한 것**이다.

### 5.5 `registration_sql` — 등록 문장 만들기

```
.venv/bin/python -m trading_plugins.facts registration_sql \
    strategy <전략 id> "<표시 이름>" "<설명>" <true|false> [기본값 JSON]

.venv/bin/python -m trading_plugins.facts registration_sql \
    money_management <mode> "<표시 이름>" "<설명>" <true|false>
```

선언에서 나오는 열은 클래스에서 읽고 **나머지는 인자로 받는다.** 자세한 것은 6절에 있다.

**정책에는 기본값 인자가 없다.** 정책 등록 표에는 그 열이 없으므로 주면 거부된다.

```
{"error": "default_params is only valid for a strategy"}
```

**정책을 처음 등록하기 전에 표가 있어야 한다.** `money_management_registry`는
`init-scripts/signal-service/20260810/01-create-money-management-registry.sql`이 만든다. 표가
아직 없는 환경이라면 그 파일을 먼저 적용한다.

### 5.6 `catalog_precheck` — 후보 행이 클래스와 맞는지

**이 도구는 데이터베이스를 읽지 않는다.** 이름 때문에 "등록되어 있는 행을 본다"로 읽기 쉬우나
그렇지 않다. 건네받은 **후보 행**과 배포된 클래스를 견줄 뿐이다.

```
.venv/bin/python -m trading_plugins.facts catalog_precheck strategy <전략 id>
```

```
{"passed": true,
 "checks_performed": ["catalog identity and declaration", "catalog lifecycle",
                      "adapter construction"],
 "not_checked": ["execution timeframe support", "series resolution", "policy input arity",
                 "live-signal capability", "return-type violation on the first decision"],
 "findings": []}
```

**행을 주지 않으면 무엇과 견주는지 알아야 한다.** 그때는 클래스에서 만든 행을 쓰는데, 표시
이름을 전략 id로, 설명을 빈 문자열로, `is_active`를 참으로 채운 **합성 행**이다. 그러므로
행 없이 부른 결과는 "이 클래스로 등록 행을 만들면 그 행이 클래스와 맞는다"는 뜻이며,
**데이터베이스에 실제로 무엇이 들어 있는지와는 아무 관계가 없다.** 등록 행이 없어도, 비활성이나
폐기 상태여도, 선언과 어긋나 있어도 이 명령은 통과한다.

**실제로 들어 있는 행을 보려면 그 행을 직접 건네야 한다.** 데이터베이스에서 행을 읽어 주는
도구는 없으므로 조회는 따로 해야 한다. 아래는 등록된 전략 행을 읽는 예다.

```
psql -h <host> -U <user> -d signal_db -At -c \
  "SELECT row_to_json(t) FROM (SELECT * FROM public.strategy_registry WHERE strategy_id='<전략 id>') t"
```

**`not_checked`를 반드시 읽는다.** 통과는 "후보 행과 선언이 맞는다"는 뜻이지 "이제 실행된다"는
뜻이 아니다. 실행 timeframe 지원과 series 해석과 정책 입력 개수와 라이브 신호 capability는
실행 설정이 정해진 뒤에야 검사되고, 반환 형 위반은 첫 판단을 받아야 드러난다.

## 6. 등록까지 가는 길

등록은 다섯 걸음이고 **마지막 둘은 사람이 한다.**

**첫째, 문장을 만든다.** `registration_sql`로 만든다.

**둘째, 후보 행이 클래스와 맞는지 본다.** `catalog_precheck`가 그것을 본다. 5.6절이 밝힌 대로
데이터베이스는 보지 않는다.

**셋째, JSON 문자열을 실행 가능한 SQL로 푼다.** 모든 조회가 JSON을 내므로 `registration_sql`의
표준 출력도 따옴표와 `\n`이 escape된 **JSON 문자열 하나**다. 그대로 `.sql` 파일에 넣으면 psql이
읽지 못한다.

```
.venv/bin/python -m trading_plugins.facts registration_sql \
    strategy <전략 id> "<표시 이름>" "<설명>" true \
  | .venv/bin/python -c "import json,sys; sys.stdout.write(json.load(sys.stdin))" \
  > /tmp/registration.sql
```

**넷째, 파일로 옮기며 껍데기를 씌운다.** `init-scripts/signal-service/<날짜>/` 아래에 두고 기존
파일처럼 `\set ON_ERROR_STOP on`과 `BEGIN`과 `COMMIT`으로 감싼다. **도구가 그것까지 내지 않는
것은 의도된 것이다** — 도구는 SQL 문장 하나만 만들고 파일의 모양은 운영 절차가 정한다. 문장
하나는 그 자체로 원자적이라 감싸지 않아도 동작은 같고, 껍데기는 파일을 사람이 적용할 때의
안전장치다.

**다섯째, 운영자가 적용한다.** 적용 전에 대상을 눈으로 확인하고, 적용한 뒤 실제로 들어갔는지
읽어 본다.

```
psql -h <host> -U <user> -d signal_db -c "SELECT current_database(), current_user, inet_server_addr()"
psql -h <host> -U <user> -d signal_db -v ON_ERROR_STOP=1 -f init-scripts/signal-service/<날짜>/<파일>.sql
```

**적용은 되돌리기 어려운 일이다.** 문장은 한 트랜잭션이므로 실패하면 통째로 취소되지만,
성공한 뒤에는 이전 값이 남지 않는다. 기존 행을 고치는 경우라면 **적용 전에 그 행을 읽어
따로 남겨 둔다.**

### 6.1 무엇이 사람 몫인가

선언에서 나오지 않는 값이 넷이고 전략은 다섯이다.

**표시 이름과 설명**은 사람이 정한다. 클래스 docstring으로 대신 채우지 않는다. 그것은 사실
조회가 아니라 등록 문구를 고르는 일이기 때문이다.

**`is_active`는 인자이며 기본값이 없다.** 이것이 켜고 끄는 스위치이므로 기본값을 두면 도구가
운영 결정을 대신하게 된다.

**전략의 `default_params_json`은 두 문서가 서로 다른 말을 하는 자리다.** 데이터베이스 설계서는
그것을 "초기값 제안이며 검증 표준이 아니다"라고 정의하고, 규범 2.1은 "전략 version과 parameter
기본값과 `StrategyProfile`을 등록과 맞춘다"고 요구한다. **규범이 규칙 문서이므로 지금은 클래스
기본값과 같게 적는다.** 다르게 적고 싶다면 그것은 규범과 어긋나는 결정이므로 따로 합의해야
한다.

**그리고 그 값은 지금 거의 쓰이지 않는다.** Web API는 클래스 선언을 읽을 수 있으면 parameter
schema에서 기본값을 새로 만들고, 등록 행의 값은 **선언을 읽지 못했을 때만** 쓴다. 그런데 선언을
읽지 못하는 전략은 어차피 실행할 수 없다. 그러므로 여기에 공들여 다른 값을 넣어도 화면에
나타나지 않는다.

### 6.2 폐기된 전략을 되살리지 않는다

만들어진 문장은 충돌했을 때 **선언과 표시 열만 갱신하고 `is_active`와 `is_deprecated`는 건드리지
않는다.** 그래서 폐기해 둔 전략에 같은 문장을 다시 적용해도 폐기가 유지된다. 활성화와 폐기는
등록과 다른 일이며 별도 운영 문장으로 한다.

### 6.3 생성기가 PostgreSQL에서 도는지 보는 회귀 시험

표시가 붙은 시험이 있고 기본 실행에서는 건너뛴다.

```
.venv/bin/python -m pytest services -q -m integration -k facts_integration_postgres
```

**이 시험은 당신이 방금 만든 문장을 검사하지 않는다.** 시험 안에서 배포된 전략과 정책 하나씩에
대해 문장을 새로 만들어 적용해 보는 **생성기의 회귀 시험**이다. 그래서 여기가 초록이어도 당신의
표시 이름 길이나 새 plugin 선언이나 파일 껍데기의 실수는 걸리지 않는다. 그런 것은 6절 다섯째
걸음에서 실제로 적용해 보아야 드러난다.

**이것은 데이터베이스에 쓰는 일이고, 대상은 저장소 `.env`가 가리키는 곳이다.** 이름에 임의
문자열이 붙은 임시 schema를 만들어 그 안에서만 표를 세우고 끝나면 지운다. 기존 표와 행은
건드리지 않고 데이터베이스를 만들거나 지우지 않는다. 다만 **`.env`의 쓰기 자격증명을 그대로
쓰고, 그 대상이 운영인지 아닌지를 시험이 확인하지 않는다.**

그래서 돌리기 전에 셋을 한다. **대상을 눈으로 확인하고, 운영을 가리키고 있으면 돌리지 않으며,
승인을 받는다.**

```
psql -h <host> -U <user> -d signal_db -At -c "SELECT current_database(), current_user"
```

**비정상 종료에 대비한다.** 정리는 끝맺음에서 하지만 강제 종료나 연결이 끊기면 임시 schema가
남을 수 있다. 그때는 이름으로 찾아 지운다.

```
psql ... -At -c "SELECT nspname FROM pg_namespace WHERE nspname LIKE 'facts_registry_%'"
psql ... -c "DROP SCHEMA <남은 이름> CASCADE"
```

## 7. MCP로 쓰기

같은 조회 여섯을 MCP 도구로도 쓸 수 있다. `.mcp.json`에 `trading_plugin_facts`로 등록되어
있고 저장소의 `.venv`로 뜬다.

**절차 자체는 MCP를 필요로 하지 않는다.** skill이 가리키는 것은 명령줄이므로 서버가 없어도
그대로 돈다. MCP가 유용한 것은 다른 클라이언트가 같은 사실을 도구로 부를 때다.

**서버는 뜰 때 읽은 코드로 답한다.** 전략 파일이나 사실 모듈을 고쳤으면 **서버를 다시 띄워야**
새 내용을 답한다. 명령줄은 부를 때마다 새 프로세스라 그 함정이 없다.

## 8. 자주 틀리는 자리

**이름이 같아도 정의는 다를 수 있다.** registry의 `pat_hammer`는 TA-Lib 0.7.1 정의이지
"아랫꼬리가 몸통의 두 배"가 아니다. 문서가 이름만 적고 정의를 주지 않았다면 재료가 갖춰진
것이 아니라 **무엇을 잴지 정해야 하는 상태**다.

**지표는 조합 단위로 등록된다.** 문서에 흔한 숫자가 없으면 거기서 먼저 걸린다.

**체결은 언제나 다음 봉이다.** 판단한 그 봉의 종가로 들어가는 모형은 없다. 그것은 규범이
금지한 미래 참조라 플랫폼이 일부러 막고 있다. 문서가 종가 진입을 전제했다면 재는 것이 달라진다.

**백테스트를 통과해도 paper에서 거절될 수 있다.** 실거래 쪽에는 백테스트에 없는 관문이 따로
있고 백테스트 결과에는 그 거절이 반영되어 있지 않다. `capabilities risk.paper_execution_guard`가
그것을 적어 둔 자리다.

**거래 사이를 보는 규칙이 백테스트에 없다.** 하루 손실 한도도 연패 중단도 하루 거래 횟수
상한도 없고, 전략은 지난 거래의 결과를 입력으로 받지 않아 스스로 셀 수도 없다.

**상위 timeframe은 series로만 볼 수 있다.** 4시간봉 EMA를 15분봉 실행에서 읽는 것은 되지만,
4시간봉 원본 캔들을 봉마다 훑는 것은 되지 않는다. 전략에 들어오는 캔들은 실행 timeframe
하나다.

**거래당 위험은 1퍼센트가 상한이다.** 문서가 2퍼센트를 권해도 그 값으로는 실행되지 않는다.

## 9. 실제 판정 두 편

판정 전문은 `docs/fullspec/strategy_sample_verdicts.md`에 있다. 결론만 옮긴다.

`00.EMA_StochasticRSI.md`는 세 갈래 모두에 걸려 만들 수 없다. `00.TCT_MultiTF.md`는 문서
전체로는 만들 수 없으나 **문서가 정한 첫 실험 단계는 승인 둘과 빈 값 하나를 채우면 지금도 잴
수 있다.**

두 판정의 근거를 시험이 붙들고 있어, 플랫폼이 그 능력을 갖추면 시험이 깨지고 판정을 다시
내리게 된다.

## 10. 이 절차가 하지 않는 것

**운영 데이터베이스에 쓰지 않는다.** 등록 문장을 만들고 점검까지 하지만 적용은 사람이 한다.

**막힌 것을 우회해 구현하지 않는다.** 능력이 없으면 없다고 보고하고 멈춘다.

**등록된 지표나 패턴을 전략 안에 다시 구현하지 않는다.** 원시 캔들 비교와 전략 고유 규칙만
전략이 직접 계산한다.

**문서가 비운 값을 지어내지 않는다.** 물어보고 기다린다.

**성적이 좋다고 채택하지 않는다.** 검산을 통과하지 못하면 채택하지 않는다.

## 11. 막혔을 때 확인하는 순서

전략이 실행되지 않으면 위에서 아래로 확인한다. **가장 흔한 원인이 셋째 걸음에 있는데, 도구가
그 자리를 대신 봐 주지 않으므로 직접 읽어야 한다.**

**첫째, 파일이 실제로 배포되었는지 본다.** `deployed`로 그 id가 있는지와 `faults`가 비어
있는지 확인한다. 파일을 고친 뒤 서비스를 다시 띄우지 않으면 예전 내용이 계속 돈다. 조회가
아예 응답하지 않으면 새로 둔 파일이 불러오는 도중 멈추고 있는지 의심한다.

**둘째, 클래스가 무엇을 선언했는지 본다.** `declaration`으로 확인한다.

**셋째, 데이터베이스의 등록 행을 직접 읽는다.** 행이 아예 없는지, `is_active`가 거짓이거나
`is_deprecated`가 참인지, 클래스 이름과 모듈 경로와 최소 이력과 지원 timeframe과 series 선언이
둘째 걸음에서 본 것과 다른지를 본다. 5.6절의 조회가 그 읽는 법이며, **`catalog_precheck`를 행
없이 부르면 이 자리를 건너뛴다.**

**넷째, 읽은 행을 `catalog_precheck`에 건네 대조한다.** 어긋난 곳이 이름으로 나온다. 여기서
걸리면 등록 문장을 다시 만들어 적용한다.

**다섯째, 여기까지 맞는데 실행이 거부되면 `not_checked`의 다섯을 의심한다.** 실행 timeframe이
지원 목록에 있는지, 선언한 series 조합이 등록되어 있는지, 정책이 변동성 입력을 정확히 하나
선언했는지, 라이브 신호라면 정책이 계좌 상태와 무관하다고 선언했는지, 그리고 선언한 반환
방식과 실제로 돌려주는 값이 같은지다.

**여섯째, 그래도 남으면 실행 설정과 데이터를 본다.** 정책이 요구한 timeframe의 값이 실제로
준비되는지, 짝 series를 쓰는데 두 번째 종목을 주었는지, 그리고 선언한 warm-up을 채울 만큼 과거
데이터가 있는지다.
